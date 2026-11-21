from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import generate_uuid, utc_now


class AnalysisRun(Base):
    """
    AnalysisRun tracks an execution of the code intelligence engine on a repository snapshot.
    Records duration, counts, and failure diagnostics.
    """
    __tablename__ = "analysis_runs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    repository_id = Column(String(36), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    commit_hash = Column(String(64), nullable=True)
    status = Column(String(50), default="PENDING", nullable=False)  # PENDING, INGESTING, PARSING, GRAPHING, EMBEDDING, COMPLETED, FAILED
    error_message = Column(Text, nullable=True)
    
    # Telemetry metrics
    file_count = Column(Integer, default=0, nullable=False)
    symbol_count = Column(Integer, default=0, nullable=False)
    dependency_count = Column(Integer, default=0, nullable=False)
    finding_count = Column(Integer, default=0, nullable=False)
    duration_ms = Column(Integer, nullable=True)
    
    started_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_analysis_repo_status", "repository_id", "status"),
    )

    # Relationships
    repository = relationship("Repository", back_populates="analysis_runs")
    files = relationship("FileRecord", back_populates="analysis", cascade="all, delete-orphan")
    findings = relationship("AnalysisFinding", back_populates="analysis", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<AnalysisRun id={self.id} status={self.status} repo={self.repository_id}>"

