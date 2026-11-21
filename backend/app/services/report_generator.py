from typing import Any, Dict

from sqlalchemy.orm import Session

from app.models.analysis import AnalysisRun
from app.models.dependency import FileDependency
from app.models.file import FileRecord
from app.models.finding import AnalysisFinding
from app.models.repository import Repository
from app.models.symbol import CodeSymbol
from app.services.graph_engine import DependencyGraphEngine


class ArchitectureReportGenerator:
    """
    Synthesizes comprehensive architectural documentation from database snapshots,
    AST symbols, NetworkX graph metrics, and static analysis findings.
    Supports clean Markdown and structured JSON export.
    """
    def __init__(self, db: Session):
        self.db = db

    def generate_report(self, repository_id: str) -> Dict[str, Any]:
        """
        Compile full architecture report for the latest completed analysis run of a repository.
        """
        repo = self.db.query(Repository).filter(Repository.id == repository_id).first()
        if not repo:
            raise ValueError(f"Repository {repository_id} does not exist.")

        latest_run = (
            self.db.query(AnalysisRun)
            .filter(AnalysisRun.repository_id == repository_id, AnalysisRun.status == "COMPLETED")
            .order_by(AnalysisRun.completed_at.desc())
            .first()
        )

        if not latest_run:
            raise ValueError("No completed analysis run found. Please run repository analysis first.")

        # 1. Fetch Relational Entities
        files = self.db.query(FileRecord).filter(FileRecord.analysis_id == latest_run.id).all()
        file_map = {f.id: f for f in files}

        symbols = self.db.query(CodeSymbol).join(FileRecord).filter(FileRecord.analysis_id == latest_run.id).all()
        dependencies = (
            self.db.query(FileDependency)
            .filter(FileDependency.source_file_id.in_(list(file_map.keys())))
            .all()
        )
        findings = (
            self.db.query(AnalysisFinding)
            .filter(AnalysisFinding.analysis_id == latest_run.id)
            .all()
        )

        # 2. Graph Metrics via NetworkX
        graph_engine = DependencyGraphEngine()
        for f in files:
            graph_engine.add_node(f.id, f.path, f.filename, f.language, f.is_entry_point, f.line_count)
        for d in dependencies:
            graph_engine.add_dependency(d.source_file_id, d.target_file_id, d.dependency_type, d.imported_symbol, d.line_number)
        
        graph_metrics = graph_engine.analyze()

        # 3. Categorize Elements
        entry_points = [f.path for f in files if f.is_entry_point]
        classes = [s for s in symbols if s.symbol_type == "CLASS"]
        functions = [s for s in symbols if s.symbol_type in ("FUNCTION", "ASYNC_FUNCTION")]

        # Language distribution
        languages: Dict[str, int] = {}
        for f in files:
            languages[f.language] = languages.get(f.language, 0) + 1

        # Findings summary
        findings_by_sev = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for fd in findings:
            findings_by_sev[fd.severity] = findings_by_sev.get(fd.severity, 0) + 1

        # 4. Generate Markdown
        markdown_sections = []

        markdown_sections.append(f"""# GitScout Architecture Report: `{repo.owner}/{repo.name}`

> Generated automatically by the **GitScout Repository Intelligence Platform**.  
> Snapshot Analysis ID: `{latest_run.id}` | Duration: `{latest_run.duration_ms or 0}ms`

---

## 1. Repository Overview & Statistics

| Metric | Value |
| :--- | :--- |
| **Repository URL** | [{repo.github_url}]({repo.github_url}) |
| **Default Branch** | `{repo.default_branch}` |
| **GitHub Stars** | {repo.stars:,} |
| **GitHub Forks** | {repo.forks:,} |
| **Total Source Files** | {len(files)} |
| **Classes Extracted** | {len(classes)} |
| **Functions Extracted** | {len(functions)} |
| **Total Code Symbols** | {len(symbols)} |
| **Dependency Edges** | {len(dependencies)} |
| **Static Audit Findings** | {len(findings)} |

---

## 2. Technology Stack & Language Distribution

""")
        for lang, count in sorted(languages.items(), key=lambda x: x[1], reverse=True):
            pct = round((count / len(files)) * 100, 1) if files else 0
            markdown_sections.append(f"- **{lang}**: {count} files ({pct}%)")

        markdown_sections.append("""
---

## 3. Structural Entry Points & Orchestrators

Entry points detected through AST heuristics (`if __name__ == '__main__':`, web framework instantiation, CLI groups):
""")
        if entry_points:
            for ep in entry_points:
                markdown_sections.append(f"- `[ENTRY POINT]` `{ep}`")
        else:
            markdown_sections.append("- *No standalone executable entry points detected.*")

        markdown_sections.append("""
---

## 4. Key Architectural Modules & Centrality (PageRank)

Top hub modules ranked by architectural connectivity (in-degree fan-in and PageRank centrality):

| File Path | In-Degree (Fan-In) | Out-Degree (Fan-Out) | PageRank Score |
| :--- | :--- | :--- | :--- |
""")
        for hub in graph_metrics.hub_modules[:8]:
            markdown_sections.append(
                f"| `{hub['path']}` | {hub['in_degree']} | {hub['out_degree']} | {hub['pagerank']:.4f} |"
            )

        markdown_sections.append(f"""
---

## 5. Dependency Graph Topology & Cycle Analysis

- **Graph Density**: `{graph_metrics.density}`
- **Directed Acyclic Graph (DAG)**: `{'Yes (Pure DAG)' if graph_metrics.is_dag else 'No (Contains Cycles)'}`
- **Isolated Modules**: {len(graph_metrics.isolated_modules)} files with no internal imports.
""")

        if graph_metrics.circular_dependencies:
            markdown_sections.append("\n### ⚠️ Detected Circular Dependency Loops:\n")
            for idx, cycle in enumerate(graph_metrics.circular_dependencies, start=1):
                markdown_sections.append(f"{idx}. " + " $\\rightarrow$ ".join([f"`{p}`" for p in cycle]) + f" $\\rightarrow$ `{cycle[0]}`")
        else:
            markdown_sections.append("\n> **Clean Topology**: No circular dependency loops detected.")

        markdown_sections.append(f"""
---

## 6. Static Code Quality & Security Audit (Ruff & Bandit)

- **Critical Vulnerabilities**: `{findings_by_sev['CRITICAL']}`
- **High Severity Findings**: `{findings_by_sev['HIGH']}`
- **Medium Severity Findings**: `{findings_by_sev['MEDIUM']}`
- **Low Severity / Style Issues**: `{findings_by_sev['LOW']}`

### Top Audit Findings:
""")
        if findings:
            for finding in sorted(findings, key=lambda x: x.severity, reverse=True)[:10]:
                markdown_sections.append(
                    f"- **[{finding.tool}] {finding.rule_id} ({finding.severity})** in `{file_map.get(finding.file_id, None).path if file_map.get(finding.file_id) else 'file'}:{finding.line_number}`: {finding.description}"
                )
        else:
            markdown_sections.append("- *No static code smells or vulnerabilities detected.*")

        markdown_sections.append("""
---

## 7. Architectural Observations & Recommendations

""")
        if not graph_metrics.is_dag:
            markdown_sections.append("- **Refactor Circular Loops**: Circular module dependencies increase tight coupling and can cause subtle runtime import errors during module initialization.")
        if graph_metrics.density > 0.3:
            markdown_sections.append("- **High Coupling Warning**: The repository has a high graph density, indicating that modules are heavily interconnected.")
        else:
            markdown_sections.append("- **Modular Decoupling**: The repository exhibits clean modular separation with low overall graph density.")

        markdown_report = "\n".join(markdown_sections)

        return {
            "repository": f"{repo.owner}/{repo.name}",
            "url": repo.github_url,
            "markdown": markdown_report,
            "summary": {
                "total_files": len(files),
                "total_symbols": len(symbols),
                "total_dependencies": len(dependencies),
                "total_findings": len(findings),
                "is_dag": graph_metrics.is_dag,
                "density": graph_metrics.density,
                "circular_cycle_count": len(graph_metrics.circular_dependencies),
                "findings_by_severity": findings_by_sev
            }
        }
