from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_user
from app.core.database import get_db
from app.models.repository import Repository
from app.models.user import User
from app.services.report_generator import ArchitectureReportGenerator

router = APIRouter()


@router.get("/repo/{repo_id}/report")
def get_architecture_report(
    repo_id: str,
    format: str = Query("json", pattern="^(json|markdown)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate comprehensive architecture report in JSON or raw Markdown format.
    Synthesizes metadata, technology stack, entry points, dependency topology, and static security audit.
    """
    repo = db.query(Repository).filter(
        Repository.id == repo_id,
        Repository.user_id == current_user.id
    ).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    generator = ArchitectureReportGenerator(db)
    try:
        report = generator.generate_report(repo_id)
        if format == "markdown":
            return PlainTextResponse(content=report["markdown"], media_type="text/markdown")
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate architecture report: {str(e)}")
