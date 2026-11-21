from sqlalchemy import Boolean, Column, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import generate_uuid


class FileDependency(Base):
    """
    FileDependency represents a directed dependency edge (source_file -> target_file)
    extracted from import statements via Python AST.
    """
    __tablename__ = "dependencies"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    source_file_id = Column(String(36), ForeignKey("files.id", ondelete="CASCADE"), nullable=False, index=True)
    target_file_id = Column(String(36), ForeignKey("files.id", ondelete="CASCADE"), nullable=False, index=True)
    dependency_type = Column(String(50), default="DIRECT_IMPORT", nullable=False)  # DIRECT_IMPORT, FROM_IMPORT, DYNAMIC_IMPORT
    imported_symbol = Column(String(255), nullable=True)
    line_number = Column(Integer, default=1, nullable=False)
    is_circular = Column(Boolean, default=False, nullable=False)

    __table_args__ = (
        UniqueConstraint("source_file_id", "target_file_id", "line_number", "imported_symbol", name="uq_file_dependency_edge"),
        Index("idx_dependencies_source_target", "source_file_id", "target_file_id"),
    )

    # Relationships
    source_file = relationship("FileRecord", foreign_keys=[source_file_id], back_populates="dependencies_out")
    target_file = relationship("FileRecord", foreign_keys=[target_file_id], back_populates="dependencies_in")

    def __repr__(self):
        return f"<FileDependency {self.source_file_id} -> {self.target_file_id} symbol={self.imported_symbol}>"

