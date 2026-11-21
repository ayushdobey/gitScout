from typing import Tuple

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_user
from app.core.database import get_db
from app.models.analysis import AnalysisRun
from app.models.dependency import FileDependency
from app.models.file import FileRecord
from app.models.repository import Repository
from app.models.user import User
from app.schemas.graph import GraphEdge, GraphNode, GraphPathResponse, GraphResponse, NodeDependenciesResponse
from app.services.graph_engine import DependencyGraphEngine

router = APIRouter()


def _build_repo_graph_engine(repo_id: str, db: Session, user_id: str) -> Tuple[DependencyGraphEngine, AnalysisRun]:
    """Helper to load latest completed run and populate DependencyGraphEngine."""
    repo = db.query(Repository).filter(
        Repository.id == repo_id,
        Repository.user_id == user_id
    ).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    latest_run = db.query(AnalysisRun).filter(
        AnalysisRun.repository_id == repo_id,
        AnalysisRun.status == "COMPLETED"
    ).order_by(AnalysisRun.completed_at.desc()).first()

    if not latest_run:
        raise HTTPException(status_code=404, detail="No completed analysis run found for this repository")

    files = db.query(FileRecord).filter(FileRecord.analysis_id == latest_run.id).all()
    file_map = {f.id: f for f in files}

    engine = DependencyGraphEngine()
    for f in files:
        engine.add_node(
            file_id=f.id,
            path=f.path,
            filename=f.filename,
            language=f.language,
            is_entry_point=f.is_entry_point,
            line_count=f.line_count
        )

    file_ids = list(file_map.keys())
    dependencies = db.query(FileDependency).filter(
        FileDependency.source_file_id.in_(file_ids),
        FileDependency.target_file_id.in_(file_ids)
    ).all()

    for dep in dependencies:
        engine.add_dependency(
            source_id=dep.source_file_id,
            target_id=dep.target_file_id,
            dependency_type=dep.dependency_type,
            imported_symbol=dep.imported_symbol,
            line_number=dep.line_number
        )

    return engine, latest_run


@router.get("/repo/{repo_id}/graph", response_model=GraphResponse)
def get_dependency_graph(
    repo_id: str,
    include_isolated: bool = Query(True, description="Include files with no dependencies"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate graph payload tailored for React Flow visualization.
    Includes in/out-degree, circular dependency status, layout coordinates, and hub metrics.
    """
    repo = db.query(Repository).filter(
        Repository.id == repo_id,
        Repository.user_id == current_user.id
    ).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    latest_run = db.query(AnalysisRun).filter(
        AnalysisRun.repository_id == repo_id,
        AnalysisRun.status == "COMPLETED"
    ).order_by(AnalysisRun.completed_at.desc()).first()

    if not latest_run:
        return {
            "nodes": [],
            "edges": [],
            "metrics": {
                "total_nodes": 0,
                "total_edges": 0,
                "density": 0.0,
                "is_dag": True,
                "circular_dependencies": [],
                "hub_modules": [],
                "isolated_modules": []
            }
        }

    engine, _ = _build_repo_graph_engine(repo_id, db, current_user.id)
    analysis = engine.analyze()

    files = db.query(FileRecord).filter(FileRecord.analysis_id == latest_run.id).all()
    file_map = {f.id: f for f in files}

    nodes = []
    for f in files:
        metrics = analysis.node_metrics.get(f.id, {})
        in_d = metrics.get("in_degree", 0)
        out_d = metrics.get("out_degree", 0)

        if in_d == 0 and out_d == 0 and not include_isolated:
            continue

        nodes.append(
            GraphNode(
                id=f.id,
                label=f.filename,
                path=f.path,
                language=f.language,
                is_entry_point=f.is_entry_point,
                in_degree=in_d,
                out_degree=out_d,
                pagerank=metrics.get("pagerank", 0.0),
                x=metrics.get("x", 0.0),
                y=metrics.get("y", 0.0)
            )
        )

    edges = []
    dependencies = db.query(FileDependency).filter(
        FileDependency.source_file_id.in_(list(file_map.keys()))
    ).all()

    for dep in dependencies:
        is_circular = (dep.source_file_id, dep.target_file_id) in analysis.circular_edge_tuples
        edges.append(
            GraphEdge(
                id=dep.id,
                source=dep.source_file_id,
                target=dep.target_file_id,
                dependency_type=dep.dependency_type,
                imported_symbol=dep.imported_symbol,
                is_circular=is_circular
            )
        )

    return {
        "nodes": nodes,
        "edges": edges,
        "metrics": {
            "total_nodes": analysis.total_nodes,
            "total_edges": analysis.total_edges,
            "density": analysis.density,
            "is_dag": analysis.is_dag,
            "circular_dependencies": analysis.circular_dependencies,
            "hub_modules": analysis.hub_modules,
            "isolated_modules": analysis.isolated_modules
        }
    }


@router.get("/repo/{repo_id}/graph/path", response_model=GraphPathResponse)
def explore_dependency_path(
    repo_id: str,
    source_id: str = Query(..., description="Source file ID"),
    target_id: str = Query(..., description="Target file ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Compute shortest directed dependency path between two source files using NetworkX.
    """
    engine, _ = _build_repo_graph_engine(repo_id, db, current_user.id)
    
    source_meta = engine.file_metadata.get(source_id)
    target_meta = engine.file_metadata.get(target_id)
    if not source_meta or not target_meta:
        raise HTTPException(status_code=404, detail="Source or target file not found in analysis snapshot")

    path = engine.find_shortest_path(source_id, target_id)

    return {
        "source_id": source_id,
        "target_id": target_id,
        "source_path": source_meta["path"],
        "target_path": target_meta["path"],
        "path": path or [],
        "is_reachable": path is not None and len(path) > 0
    }


@router.get("/repo/{repo_id}/graph/node/{file_id}/dependencies", response_model=NodeDependenciesResponse)
def get_node_dependencies(
    repo_id: str,
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieve direct imports (outbound dependencies) and reverse dependents (inbound references) for a file.
    """
    engine, _ = _build_repo_graph_engine(repo_id, db, current_user.id)
    meta = engine.file_metadata.get(file_id)
    if not meta:
        raise HTTPException(status_code=404, detail="File node not found")

    rel_deps = engine.get_direct_and_reverse_dependencies(file_id)

    return {
        "file_id": file_id,
        "path": meta["path"],
        "dependencies": rel_deps["dependencies"],
        "dependents": rel_deps["dependents"]
    }
