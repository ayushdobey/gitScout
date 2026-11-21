from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_user
from app.core.database import get_db
from app.models.analysis import AnalysisRun
from app.models.repository import Repository
from app.models.user import User
from app.schemas.analysis import AnalysisRunRead, AnalysisStatusRead

router = APIRouter()


@router.get("/{run_id}/status", response_model=AnalysisStatusRead)
def get_analysis_status(
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Poll execution progress and current phase for an analysis run.
    """
    run = db.query(AnalysisRun).join(Repository).filter(
        AnalysisRun.id == run_id,
        Repository.user_id == current_user.id
    ).first()

    if not run:
        raise HTTPException(status_code=404, detail="Analysis run not found")

    step_map = {
        "PENDING": ("Queued for execution", 5),
        "INGESTING": ("Fetching repository source archive from GitHub", 25),
        "PARSING": ("Extracting AST symbols and imports", 50),
        "GRAPHING": ("Constructing directed dependency graph", 70),
        "EMBEDDING": ("Generating syntax-aware vector embeddings", 85),
        "COMPLETED": ("Analysis completed successfully", 100),
        "FAILED": ("Analysis failed", 100),
    }
    step_desc, progress = step_map.get(run.status, ("Processing", 50))

    return {
        "run_id": run.id,
        "repository_id": run.repository_id,
        "status": run.status,
        "current_step": step_desc,
        "progress_percentage": progress,
        "error_message": run.error_message
    }


@router.get("/repo/{repo_id}/runs", response_model=List[AnalysisRunRead])
def list_repository_runs(
    repo_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List historical analysis runs for a repository."""
    repo = db.query(Repository).filter(
        Repository.id == repo_id,
        Repository.user_id == current_user.id
    ).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    return db.query(AnalysisRun).filter(
        AnalysisRun.repository_id == repo_id
    ).order_by(AnalysisRun.started_at.desc()).all()

