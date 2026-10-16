"""SQLAlchemy DeclarativeBase and common column mixins.

Conventions (docs/03 §1):
- Primary keys: UUID (UUIDv7 for index locality and temporal ordering)
- Timestamps: timestamptz, UTC (created_at, updated_at)
- Deletion: soft delete via deleted_at where applicable
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.ids import generate_uuid7


class Base(DeclarativeBase):
    """Base declarative class for all DevMind persistence entities."""

    pass


class UUID7PrimaryKeyMixin:
    """Provides an RFC 9562 UUIDv7 primary key column."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=generate_uuid7,
        sort_order=-100,
    )


class TimestampMixin:
    """Provides created_at and updated_at UTC timestamp columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        sort_order=100,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        sort_order=101,
    )


class SoftDeleteMixin:
    """Provides soft-delete deleted_at UTC timestamp column."""

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        sort_order=102,
    )
