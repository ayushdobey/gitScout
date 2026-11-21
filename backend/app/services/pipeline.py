import time
from typing import Dict

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.analysis import AnalysisRun
from app.models.base import utc_now
from app.models.chunk import CodeChunk
from app.models.dependency import FileDependency
from app.models.file import FileRecord
from app.models.finding import AnalysisFinding
from app.models.repository import Repository
from app.models.symbol import CodeSymbol
from app.services.ast_parser import ASTParseResult, parse_python_source
from app.services.chunker import SyntaxAwareChunker
from app.services.embedder import get_embedder
from app.services.graph_engine import DependencyGraphEngine
from app.services.ingestion import GitHubIngestionService, IngestionResult, parse_github_url
from app.services.js_resolver import JavaScriptResolver
from app.services.resolver import ModuleResolver
from app.services.static_analysis import StaticAnalysisService


def run_repository_analysis_pipeline(
    analysis_run_id: str,
    custom_ingestion_result: IngestionResult | None = None,
    db_session: Session | None = None
) -> AnalysisRun:
    """
    Executes the end-to-end repository ingestion and AST parsing pipeline.
    Accepts an optional custom_ingestion_result for offline testing and synthetic repository benchmarks.
    """
    db: Session = db_session if db_session is not None else SessionLocal()
    should_close_db = db_session is None
    start_time = time.time()

    run = db.query(AnalysisRun).filter(AnalysisRun.id == analysis_run_id).first()
    if not run:
        db.close()
        raise ValueError(f"AnalysisRun with id {analysis_run_id} does not exist.")

    repo = db.query(Repository).filter(Repository.id == run.repository_id).first()
    if not repo:
        db.close()
        raise ValueError(f"Repository with id {run.repository_id} does not exist.")

    try:
        # Step 1: Ingestion
        run.status = "INGESTING"
        repo.status = "INGESTING"
        db.commit()

        if custom_ingestion_result:
            ingestion = custom_ingestion_result
        else:
            owner, repo_name = parse_github_url(repo.github_url)
            ingestion_service = GitHubIngestionService()
            ingestion = ingestion_service.download_and_extract(owner, repo_name, branch=repo.default_branch)

        # Update repository metadata
        repo.stars = ingestion.stars
        repo.forks = ingestion.forks
        if ingestion.primary_language:
            repo.primary_language = ingestion.primary_language
        repo.default_branch = ingestion.default_branch

        # Step 2: Parsing & Symbol Extraction
        run.status = "PARSING"
        repo.status = "ANALYZING"
        db.commit()

        created_files: Dict[str, FileRecord] = {}
        parsed_ast_results: Dict[str, ASTParseResult] = {}
        total_symbols = 0
        all_file_paths = [f.path for f in ingestion.files]
        js_resolver = JavaScriptResolver(all_file_paths)

        # Persist File Records & extract symbols
        for src_file in ingestion.files:
            line_count = len(src_file.content.splitlines())
            file_rec = FileRecord(
                analysis_id=run.id,
                path=src_file.path,
                filename=src_file.filename,
                extension=src_file.extension,
                language=src_file.language,
                file_size=src_file.file_size,
                line_count=line_count,
                content_hash=src_file.content_hash,
                is_entry_point=False
            )
            db.add(file_rec)
            db.flush()  # Obtain file_rec.id

            created_files[src_file.path] = file_rec

            # Run Python AST Visitor if .py
            if src_file.extension == ".py":
                ast_res = parse_python_source(src_file.content)
                parsed_ast_results[src_file.path] = ast_res

                if ast_res.is_entry_point:
                    file_rec.is_entry_point = True

                for sym in ast_res.symbols:
                    code_sym = CodeSymbol(
                        file_id=file_rec.id,
                        name=sym.name,
                        symbol_type=sym.symbol_type,
                        signature=sym.signature,
                        start_line=sym.start_line,
                        end_line=sym.end_line,
                        docstring=sym.docstring,
                        cyclomatic_complexity=sym.cyclomatic_complexity,
                        metadata_json={
                            "decorators": sym.decorators,
                            **sym.metadata
                        }
                    )
                    db.add(code_sym)
                    total_symbols += 1

            # Run JavaScript / TypeScript symbol extraction
            elif src_file.extension in (".ts", ".tsx", ".js", ".jsx", ".mjs"):
                if src_file.filename in ("index.ts", "index.js", "page.tsx", "main.ts", "main.js", "App.tsx", "App.js", "layout.tsx"):
                    file_rec.is_entry_point = True

                js_symbols = js_resolver.extract_symbols(src_file.content)
                for sym in js_symbols:
                    code_sym = CodeSymbol(
                        file_id=file_rec.id,
                        name=sym.name,
                        symbol_type=sym.symbol_type,
                        signature=f"export {sym.symbol_type.lower()} {sym.name}",
                        start_line=sym.line_number,
                        end_line=sym.line_number,
                        docstring=None,
                        cyclomatic_complexity=1,
                        metadata_json={"language": src_file.language}
                    )
                    db.add(code_sym)
                    total_symbols += 1

        db.commit()

        # Step 3: Module Resolution & Dependency Graph Construction
        run.status = "GRAPHING"
        db.commit()

        py_paths = [p for p in created_files.keys() if p.endswith(".py")]
        resolver = ModuleResolver(py_paths)
        total_dependencies = 0

        # Resolve Python dependencies
        for path, ast_res in parsed_ast_results.items():
            source_file = created_files.get(path)
            if not source_file:
                continue

            for imp in ast_res.imports:
                resolved_deps = resolver.resolve_import(path, imp)
                for dep in resolved_deps:
                    if dep.is_internal and dep.target_path in created_files:
                        target_file = created_files[dep.target_path]
                        
                        # Prevent self-dependency loops if imported from own module
                        if source_file.id == target_file.id:
                            continue

                        file_dep = FileDependency(
                            source_file_id=source_file.id,
                            target_file_id=target_file.id,
                            dependency_type=dep.dependency_type,
                            imported_symbol=dep.imported_symbol,
                            line_number=dep.line_number,
                            is_circular=False
                        )
                        db.add(file_dep)
                        total_dependencies += 1

        # Resolve JavaScript & TypeScript dependencies
        for src_file in ingestion.files:
            if src_file.extension in (".ts", ".tsx", ".js", ".jsx", ".mjs"):
                source_file = created_files.get(src_file.path)
                if not source_file:
                    continue

                js_deps = js_resolver.resolve_file_imports(src_file.path, src_file.content)
                for dep in js_deps:
                    if dep.target_path and dep.target_path in created_files:
                        target_file = created_files[dep.target_path]
                        if source_file.id == target_file.id:
                            continue

                        file_dep = FileDependency(
                            source_file_id=source_file.id,
                            target_file_id=target_file.id,
                            dependency_type=dep.import_type,
                            imported_symbol=dep.target_raw,
                            line_number=dep.line_number,
                            is_circular=False
                        )
                        db.add(file_dep)
                        total_dependencies += 1

        db.commit()

        # Step 4: Graph Analysis (Cycles & Centrality via NetworkX)
        graph_engine = DependencyGraphEngine()
        for f in created_files.values():
            graph_engine.add_node(
                file_id=f.id,
                path=f.path,
                filename=f.filename,
                language=f.language,
                is_entry_point=f.is_entry_point,
                line_count=f.line_count
            )

        persisted_deps = db.query(FileDependency).filter(
            FileDependency.source_file_id.in_([f.id for f in created_files.values()])
        ).all()

        for d in persisted_deps:
            graph_engine.add_dependency(
                source_id=d.source_file_id,
                target_id=d.target_file_id,
                dependency_type=d.dependency_type,
                imported_symbol=d.imported_symbol,
                line_number=d.line_number
            )

        graph_result = graph_engine.analyze()

        # Flag circular edges in database
        if graph_result.circular_edge_tuples:
            for d in persisted_deps:
                if (d.source_file_id, d.target_file_id) in graph_result.circular_edge_tuples:
                    d.is_circular = True
            db.commit()

        # Step 5: Syntax-Aware Chunking & Vector Embeddings
        run.status = "EMBEDDING"
        db.commit()

        chunker = SyntaxAwareChunker()
        embedder = get_embedder()

        for src_file in ingestion.files:
            file_rec = created_files.get(src_file.path)
            if not file_rec:
                continue

            if src_file.extension == ".py":
                raw_chunks = chunker.chunk_python_source(src_file.content, src_file.path)
            else:
                raw_chunks = chunker.chunk_text_source(src_file.content, src_file.path)

            if raw_chunks:
                texts = [c.content for c in raw_chunks]
                embeddings = embedder.embed_batch(texts)

                for chunk_data, emb in zip(raw_chunks, embeddings):
                    chunk_obj = CodeChunk(
                        file_id=file_rec.id,
                        content=chunk_data.content,
                        start_line=chunk_data.start_line,
                        end_line=chunk_data.end_line,
                        token_count=chunk_data.token_count,
                        embedding=emb
                    )
                    db.add(chunk_obj)

        db.commit()

        # Step 6: Static Code Quality & Security Audit (Ruff & Bandit)
        static_service = StaticAnalysisService()
        py_files_content = {f.path: f.content for f in ingestion.files if f.extension == ".py"}
        total_findings = 0

        if py_files_content:
            static_findings = static_service.analyze_source_files(py_files_content)
            for sf in static_findings:
                file_rec = created_files.get(sf.file_path)
                if not file_rec:
                    continue

                finding_obj = AnalysisFinding(
                    analysis_id=run.id,
                    file_id=file_rec.id,
                    tool=sf.tool,
                    rule_id=sf.rule_id,
                    severity=sf.severity,
                    category=sf.category,
                    description=sf.description,
                    line_number=sf.line_number,
                    snippet=sf.snippet,
                    remediation_hint=sf.remediation_hint
                )
                db.add(finding_obj)
                total_findings += 1

            db.commit()

        # Pipeline Completion Telemetry
        duration_ms = int((time.time() - start_time) * 1000)
        run.file_count = len(created_files)
        run.symbol_count = total_symbols
        run.dependency_count = total_dependencies
        run.finding_count = total_findings
        run.duration_ms = duration_ms
        run.status = "COMPLETED"
        run.completed_at = utc_now()

        repo.status = "READY"
        db.commit()
        db.refresh(run)
        return run

    except Exception as e:
        db.rollback()
        duration_ms = int((time.time() - start_time) * 1000)
        run.status = "FAILED"
        run.error_message = str(e)
        run.duration_ms = duration_ms
        run.completed_at = utc_now()
        repo.status = "FAILED"
        db.commit()
        raise e

    finally:
        if should_close_db:
            db.close()
