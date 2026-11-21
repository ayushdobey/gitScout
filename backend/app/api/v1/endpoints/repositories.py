from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_user
from app.core.database import get_db
from app.models.analysis import AnalysisRun
from app.models.repository import Repository
from app.models.user import User
from app.schemas.repository import RepositoryCreate, RepositoryRead
from app.services.pipeline import run_repository_analysis_pipeline

router = APIRouter()


@router.post("/", response_model=RepositoryRead, status_code=status.HTTP_201_CREATED)
def create_repository(
    repo_in: RepositoryCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Register a GitHub repository for analysis.
    Validates URL format, checks uniqueness, and initiates analysis pipeline in background.
    """
    # Parse owner and name from GitHub URL
    parts = repo_in.github_url.rstrip("/").split("/")
    owner, name = parts[-2], parts[-1]

    existing = db.query(Repository).filter(
        Repository.user_id == current_user.id,
        Repository.github_url == repo_in.github_url
    ).first()

    if existing:
        return existing

    repo = Repository(
        user_id=current_user.id,
        github_url=repo_in.github_url,
        owner=owner,
        name=name,
        default_branch=repo_in.branch or "main",
        status="PENDING"
    )
    db.add(repo)
    db.commit()
    db.refresh(repo)

    # Automatically create initial pending analysis run
    run = AnalysisRun(
        repository_id=repo.id,
        status="PENDING"
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    # Queue background analysis execution
    background_tasks.add_task(run_repository_analysis_pipeline, run.id)

    return repo


@router.post("/{repo_id}/analyze", response_model=RepositoryRead)
def trigger_repository_reanalysis(
    repo_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Trigger a fresh analysis run for an existing repository.
    """
    repo = db.query(Repository).filter(
        Repository.id == repo_id,
        Repository.user_id == current_user.id
    ).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    run = AnalysisRun(
        repository_id=repo.id,
        status="PENDING"
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    background_tasks.add_task(run_repository_analysis_pipeline, run.id)
    return repo


@router.get("/", response_model=List[RepositoryRead])
def list_repositories(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all repositories registered by the current user."""
    return db.query(Repository).filter(
        Repository.user_id == current_user.id
    ).order_by(Repository.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/{repo_id}", response_model=RepositoryRead)
def get_repository(
    repo_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get metadata for a specific repository."""
    repo = db.query(Repository).filter(
        Repository.id == repo_id,
        Repository.user_id == current_user.id
    ).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    return repo


@router.delete("/{repo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_repository(
    repo_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete repository and cascade delete all associated runs, files, symbols, and graphs.
    """
    repo = db.query(Repository).filter(
        Repository.id == repo_id,
        Repository.user_id == current_user.id
    ).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    db.delete(repo)
    db.commit()
    return None

