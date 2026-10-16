"""Usage record model for inference token metering and quota accounting (docs/03 §3.5)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.persistence.models.base import Base, UUID7PrimaryKeyMixin

if TYPE_CHECKING:
    from app.persistence.models.project import Project
    from app.persistence.models.workspace import Workspace


class UsageRecord(Base, UUID7PrimaryKeyMixin):
    """Immutable inference accounting entry metering model tokens and latency."""

    __tablename__ = "usage_records"
    __table_args__ = (
        Index("ix_usage_records_workspace_created", "workspace_id", "created_at"),
        CheckConstraint(
            "outcome IN ('success', 'failure', 'cached', 'timeout')",
            name="ck_usage_records_outcome",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    llm_task: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_id: Mapped[str] = mapped_column(String(64), nullable=False)
    model_id: Mapped[str] = mapped_column(String(128), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_units: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False, default="success")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    workspace: Mapped[Workspace] = relationship("Workspace", back_populates="usage_records")
    project: Mapped[Project | None] = relationship("Project", back_populates="usage_records")
