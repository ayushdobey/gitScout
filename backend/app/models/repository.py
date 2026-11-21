from sqlalchemy import Column, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin, generate_uuid


class Repository(Base, TimestampMixin):
    """
    Repository entity tracking ingested GitHub repositories.
    Enforces per-user unique repository ingestion constraints.
    """
    __tablename__ = "repositories"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    github_url = Column(String(512), nullable=False)
    owner = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    default_branch = Column(String(100), default="main", nullable=False)
    stars = Column(Integer, default=0, nullable=False)
    forks = Column(Integer, default=0, nullable=False)
    primary_language = Column(String(100), nullable=True)
    status = Column(String(50), default="PENDING", nullable=False)  # PENDING, INGESTING, ANALYZING, READY, FAILED

    # Composite constraint and indexes
    __table_args__ = (
        UniqueConstraint("user_id", "github_url", name="uq_user_repository_url"),
        Index("idx_repos_user_status", "user_id", "status"),
    )

    # Relationships
    user = relationship("User", back_populates="repositories")
    analysis_runs = relationship("AnalysisRun", back_populates="repository", cascade="all, delete-orphan", order_by="desc(AnalysisRun.started_at)")
    chat_sessions = relationship("ChatSession", back_populates="repository", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Repository id={self.id} full_name={self.owner}/{self.name}>"

