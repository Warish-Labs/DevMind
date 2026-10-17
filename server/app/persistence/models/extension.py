"""Extension registration and token models (docs/03 §3.1, ADR-012).

Tracks extension installations and issued scoped access/refresh tokens.
Never stores raw token strings; only SHA-256 hashes are persisted at rest.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Literal

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.persistence.models.base import Base, TimestampMixin, UUID7PrimaryKeyMixin

if TYPE_CHECKING:
    from app.persistence.models.user import User

TokenKind = Literal["access", "refresh"]


class ExtensionRegistration(Base, UUID7PrimaryKeyMixin, TimestampMixin):
    """Extension installation registered to a user account."""

    __tablename__ = "extension_registrations"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    platform: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    extension_version: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    user: Mapped[User] = relationship(
        "User",
        backref="extension_registrations",
    )
    tokens: Mapped[list[ExtensionToken]] = relationship(
        "ExtensionToken",
        back_populates="registration",
        cascade="all, delete-orphan",
    )


class ExtensionToken(Base, UUID7PrimaryKeyMixin, TimestampMixin):
    """Scoped opaque access or refresh token issued to an extension registration."""

    __tablename__ = "extension_tokens"

    registration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("extension_registrations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    scope: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="project:sync",
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    rotated_from: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("extension_tokens.id", ondelete="SET NULL"),
        nullable=True,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    registration: Mapped[ExtensionRegistration] = relationship(
        "ExtensionRegistration",
        back_populates="tokens",
    )
