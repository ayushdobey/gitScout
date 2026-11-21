import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime


def generate_uuid() -> str:
    """Generate a RFC 4122 compliant UUID4 string."""
    return str(uuid.uuid4())


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(UTC)


class TimestampMixin:
    """
    Mixin providing standard timestamp audit columns for all database entities.
    """
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

