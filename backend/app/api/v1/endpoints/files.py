from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_user
from app.core.database import get_db
from app.models.analysis import AnalysisRun
from app.models.file import FileRecord
from app.models.repository import Repository
from app.models.symbol import CodeSymbol
from app.models.user import User
from app.schemas.file import FileRecordDetail, FileRecordRead

router = APIRouter()


@router.get("/repo/{repo_id}/files", response_model=List[FileRecordRead])
def list_repository_files(
    repo_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all tracked files for the latest analysis run of a repository."""
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
        return []

    return db.query(FileRecord).filter(
        FileRecord.analysis_id == latest_run.id
    ).order_by(FileRecord.path.asc()).all()


@router.get("/repo/{repo_id}/files/{file_id}", response_model=FileRecordDetail)
def get_file_detail(
    repo_id: str,
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve detailed metadata and AST-extracted symbols for a file."""
    repo = db.query(Repository).filter(
        Repository.id == repo_id,
        Repository.user_id == current_user.id
    ).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    file_rec = db.query(FileRecord).filter(FileRecord.id == file_id).first()
    if not file_rec:
        raise HTTPException(status_code=404, detail="File not found")

    symbols = db.query(CodeSymbol).filter(CodeSymbol.file_id == file_id).all()
    
    return {
        "id": file_rec.id,
        "analysis_id": file_rec.analysis_id,
        "path": file_rec.path,
        "filename": file_rec.filename,
        "extension": file_rec.extension,
        "language": file_rec.language,
        "file_size": file_rec.file_size,
        "line_count": file_rec.line_count,
        "is_entry_point": file_rec.is_entry_point,
        "symbols": symbols
    }

