from sqlalchemy import JSON, Column, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import generate_uuid


class CodeSymbol(Base):
    """
    CodeSymbol stores program entities extracted deterministically via AST (Classes, Functions, Methods).
    Includes line numbers, docstrings, and parameter signatures.
    """
    __tablename__ = "code_symbols"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    file_id = Column(String(36), ForeignKey("files.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    symbol_type = Column(String(50), nullable=False)  # FUNCTION, ASYNC_FUNCTION, CLASS, METHOD
    signature = Column(Text, nullable=True)
    start_line = Column(Integer, nullable=False)
    end_line = Column(Integer, nullable=False)
    docstring = Column(Text, nullable=True)
    cyclomatic_complexity = Column(Integer, default=1, nullable=False)
    metadata_json = Column(JSON, nullable=True)

    __table_args__ = (
        Index("idx_symbols_file_type", "file_id", "symbol_type"),
        Index("idx_symbols_name", "name"),
    )

    # Relationships
    file = relationship("FileRecord", back_populates="symbols")
    chunks = relationship("CodeChunk", back_populates="symbol")

    def __repr__(self):
        return f"<CodeSymbol id={self.id} name={self.name} type={self.symbol_type} lines={self.start_line}-{self.end_line}>"

