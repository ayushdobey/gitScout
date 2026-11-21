from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_user
from app.core.database import get_db
from app.models.analysis import AnalysisRun
from app.models.file import FileRecord
from app.models.finding import AnalysisFinding
from app.models.repository import Repository
from app.models.user import User
from app.schemas.finding import FindingRead, FindingsSummary

router = APIRouter()


@router.get("/repo/{repo_id}/findings", response_model=List[FindingRead])
def get_findings(
    repo_id: str,
    tool: str | None = Query(None, description="Filter by tool: RUFF or BANDIT"),
    severity: str | None = Query(None, description="Filter by severity: LOW, MEDIUM, HIGH, CRITICAL"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List static code quality and security findings with optional filters."""
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

    query = db.query(
        AnalysisFinding, FileRecord.path.label("file_path")
    ).join(
        FileRecord, AnalysisFinding.file_id == FileRecord.id
    ).filter(
        AnalysisFinding.analysis_id == latest_run.id
    )

    if tool:
        query = query.filter(AnalysisFinding.tool == tool.upper())
    if severity:
        query = query.filter(AnalysisFinding.severity == severity.upper())

    results = query.order_by(AnalysisFinding.severity.desc(), AnalysisFinding.line_number.asc()).all()
    
    findings = []
    for finding, path in results:
        f_dict = {c.name: getattr(finding, c.name) for c in finding.__table__.columns}
        f_dict["file_path"] = path
        findings.append(FindingRead(**f_dict))
    return findings


@router.get("/repo/{repo_id}/findings/summary", response_model=FindingsSummary)
def get_findings_summary(
    repo_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Aggregate findings breakdown by tool, severity, and category."""
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
            "total_findings": 0,
            "by_severity": {},
            "by_tool": {},
            "by_category": {}
        }

    findings = db.query(AnalysisFinding).filter(
        AnalysisFinding.analysis_id == latest_run.id
    ).all()

    by_sev = {}
    by_tool = {}
    by_cat = {}
    for f in findings:
        by_sev[f.severity] = by_sev.get(f.severity, 0) + 1
        by_tool[f.tool] = by_tool.get(f.tool, 0) + 1
        by_cat[f.category] = by_cat.get(f.category, 0) + 1

    return {
        "total_findings": len(findings),
        "by_severity": by_sev,
        "by_tool": by_tool,
        "by_category": by_cat
    }

