from sqlalchemy import Boolean, Column, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin, generate_uuid


class FileRecord(Base, TimestampMixin):
    """
    FileRecord stores metadata for a single tracked source file within an analysis run.
    Contains content hash for incremental differential scanning.
    """
    __tablename__ = "files"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    analysis_id = Column(String(36), ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    path = Column(String(1024), nullable=False)
    filename = Column(String(255), nullable=False)
    extension = Column(String(50), nullable=False)
    language = Column(String(100), nullable=False)
    file_size = Column(Integer, default=0, nullable=False)
    line_count = Column(Integer, default=0, nullable=False)
    content_hash = Column(String(64), nullable=False)  # SHA-256
    is_entry_point = Column(Boolean, default=False, nullable=False)

    __table_args__ = (
        UniqueConstraint("analysis_id", "path", name="uq_analysis_file_path"),
        Index("idx_files_analysis_lang", "analysis_id", "language"),
    )

    # Relationships
    analysis = relationship("AnalysisRun", back_populates="files")
    symbols = relationship("CodeSymbol", back_populates="file", cascade="all, delete-orphan")
    chunks = relationship("CodeChunk", back_populates="file", cascade="all, delete-orphan")
    dependencies_out = relationship(
        "FileDependency",
        foreign_keys="FileDependency.source_file_id",
        back_populates="source_file",
        cascade="all, delete-orphan"
    )
    dependencies_in = relationship(
        "FileDependency",
        foreign_keys="FileDependency.target_file_id",
        back_populates="target_file",
        cascade="all, delete-orphan"
    )
    findings = relationship("AnalysisFinding", back_populates="file", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<FileRecord id={self.id} path={self.path}>"

