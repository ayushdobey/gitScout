import json

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.types import TypeDecorator

from app.core.config import settings
from app.core.database import Base
from app.models.base import generate_uuid


class SafeVector(TypeDecorator):
    """
    Cross-dialect vector type decorator.
    Uses native pgvector VECTOR(384) in PostgreSQL and falls back to JSON-serialized Text in SQLite test suites.
    """
    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(Vector(settings.EMBEDDING_DIMENSION))
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value
        if isinstance(value, list):
            return json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return value


class CodeChunk(Base):
    """
    CodeChunk stores syntax-aware code segments with embedding vectors for semantic search.
    Preserves precise line ranges and symbol parent hierarchy.
    """
    __tablename__ = "code_chunks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    file_id = Column(String(36), ForeignKey("files.id", ondelete="CASCADE"), nullable=False, index=True)
    symbol_id = Column(String(36), ForeignKey("code_symbols.id", ondelete="SET NULL"), nullable=True, index=True)
    content = Column(Text, nullable=False)
    start_line = Column(Integer, nullable=False)
    end_line = Column(Integer, nullable=False)
    token_count = Column(Integer, default=0, nullable=False)
    embedding = Column(SafeVector, nullable=True)

    __table_args__ = (
        Index("idx_chunks_file_lines", "file_id", "start_line", "end_line"),
    )

    # Relationships
    file = relationship("FileRecord", back_populates="chunks")
    symbol = relationship("CodeSymbol", back_populates="chunks")
    citations = relationship("MessageCitation", back_populates="chunk")

    def __repr__(self):
        return f"<CodeChunk id={self.id} file={self.file_id} lines={self.start_line}-{self.end_line}>"

