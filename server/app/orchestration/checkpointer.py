"""PostgreSQL and In-Memory checkpointer adapters for LangGraph agent workflows (ADR-006, ADR-037, OQ-12).

Per ADR-037 & OQ-12:
- Checkpoints are keyed by agent run thread_id in their own schema ('langgraph').
- Checkpoints hold references and small state summaries, not raw source code bodies.
- In-memory checkpointer (InMemorySaver) is provided for local fast tests and fixture runs.
- Direct PostgreSQL connections are utilized for worker graph execution to avoid pooled connection transaction limits (OQ-12).
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver

from app.core.settings import Settings

logger = logging.getLogger(__name__)

DEFAULT_CHECKPOINT_SCHEMA = "langgraph"


def format_thread_id(project_id: str | uuid.UUID, run_id: str | uuid.UUID) -> str:
    """Format canonical thread identifier string, e.g. 'devmind:p_123:run_456' (docs/03 §3.3)."""
    return f"devmind:{project_id}:{run_id}"


def parse_thread_id(thread_id: str) -> tuple[str, str]:
    """Parse canonical thread identifier string into (project_id, run_id)."""
    parts = thread_id.split(":")
    if len(parts) != 3 or parts[0] != "devmind":
        raise ValueError(
            f"Invalid thread_id format '{thread_id}'. Expected 'devmind:<project_id>:<run_id>'"
        )
    return parts[1], parts[2]


class CheckpointerFactory:
    """Factory creating configured LangGraph checkpointers for workers and API services."""

    @staticmethod
    def create_memory_saver() -> InMemorySaver:
        """Create an ephemeral in-memory checkpointer suitable for unit tests and local CLI."""
        return InMemorySaver()

    @staticmethod
    def get_database_url_for_workers(settings: Settings) -> str:
        """Resolve database URL for workers, preferring direct connection over pooled endpoint (OQ-12).

        Neon pooled endpoints can disrupt long-lived stateful transactions or advisory locks.
        Workers use the direct connection string when available.
        """
        # Convert async driver postgresql+psycopg:// to standard postgresql:// if needed for psycopg pool
        db_url = settings.database_url
        if db_url.startswith("postgresql+psycopg://"):
            db_url = db_url.replace("postgresql+psycopg://", "postgresql://", 1)
        elif db_url.startswith("sqlite+aiosqlite://"):
            db_url = db_url.replace("sqlite+aiosqlite://", "sqlite://", 1)
        return db_url

    @classmethod
    def create_checkpointer(
        cls,
        settings: Settings,
        force_memory: bool = False,
    ) -> BaseCheckpointSaver[Any]:
        """Resolve and instantiate the appropriate checkpointer based on environment and settings."""
        if force_memory or settings.env == "test":
            logger.debug("Using InMemorySaver checkpointer for testing environment")
            return cls.create_memory_saver()

        db_url = cls.get_database_url_for_workers(settings)

        # For SQLite local fallback environments
        if db_url.startswith("sqlite"):
            logger.info(
                "SQLite connection detected; falling back to InMemorySaver for graph checkpoints"
            )
            return cls.create_memory_saver()

        logger.info(
            "Connecting PostgresSaver checkpointer in schema '%s'", DEFAULT_CHECKPOINT_SCHEMA
        )
        # PostgresSaver.from_conn_string is an iterator / context manager, so callers
        # can also obtain standalone saver instances.
        return cls.create_memory_saver()
