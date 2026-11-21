from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin, generate_uuid, utc_now


class ChatSession(Base, TimestampMixin):
    """
    ChatSession maintains conversational context for a user interrogating a specific repository.
    """
    __tablename__ = "chat_sessions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    repository_id = Column(String(36), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), default="Codebase Discussion", nullable=False)

    __table_args__ = (
        Index("idx_chat_user_repo", "user_id", "repository_id"),
    )

    # Relationships
    user = relationship("User", back_populates="chat_sessions")
    repository = relationship("Repository", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan", order_by="ChatMessage.created_at")

    def __repr__(self):
        return f"<ChatSession id={self.id} repo={self.repository_id}>"


class ChatMessage(Base):
    """
    ChatMessage stores an individual dialogue turn (User question or Assistant grounded answer).
    """
    __tablename__ = "chat_messages"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(50), nullable=False)  # USER, ASSISTANT, SYSTEM
    content = Column(Text, nullable=False)
    latency_ms = Column(Integer, nullable=True)
    token_usage = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    session = relationship("ChatSession", back_populates="messages")
    citations = relationship("MessageCitation", back_populates="message", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ChatMessage id={self.id} role={self.role}>"


class MessageCitation(Base):
    """
    MessageCitation enforces evidence-backed AI answers by storing exact file and line references.
    """
    __tablename__ = "message_citations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    message_id = Column(String(36), ForeignKey("chat_messages.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_id = Column(String(36), ForeignKey("code_chunks.id", ondelete="SET NULL"), nullable=True, index=True)
    file_path = Column(String(1024), nullable=False)
    start_line = Column(Integer, nullable=False)
    end_line = Column(Integer, nullable=False)
    relevance_score = Column(Float, nullable=True)

    # Relationships
    message = relationship("ChatMessage", back_populates="citations")
    chunk = relationship("CodeChunk", back_populates="citations")

    def __repr__(self):
        return f"<MessageCitation file={self.file_path} lines={self.start_line}-{self.end_line}>"

