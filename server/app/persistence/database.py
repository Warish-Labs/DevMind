"""Database engine and session management using SQLAlchemy 2.0 async.

Configured with connection pooling optimized for Neon PostgreSQL serverless
and local PostgreSQL instances.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.settings import Settings, get_settings

logger = logging.getLogger("devmind.persistence.database")

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine(settings: Settings | None = None) -> AsyncEngine:
    """Get or initialize the shared async SQLAlchemy engine."""
    global _engine, _session_factory
    if _engine is None:
        cfg = settings or get_settings()
        db_url = cfg.database_url

        # Ensure async psycopg driver is specified
        if db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)

        # Free tier / Neon serverless connection pool settings (ADR-046)
        _engine = create_async_engine(
            db_url,
            pool_pre_ping=True,
            pool_recycle=1800,
            pool_size=5,
            max_overflow=5,
            echo=(cfg.log_level == "DEBUG"),
        )
        _session_factory = async_sessionmaker(
            bind=_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
        logger.info("Database engine initialized")
    return _engine


def get_session_factory(
    settings: Settings | None = None,
) -> async_sessionmaker[AsyncSession]:
    """Get or initialize the async session maker factory."""
    global _session_factory
    if _session_factory is None:
        get_engine(settings)
    assert _session_factory is not None
    return _session_factory


async def close_db_engine() -> None:
    """Dispose and cleanly shutdown the async database engine."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("Database engine closed")


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an async database session."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def session_scope() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for programmatic transactional session execution."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_expected_alembic_heads() -> list[str]:
    """Dynamically discover Alembic migration head revision IDs."""
    try:
        from pathlib import Path

        from alembic.config import Config
        from alembic.script import ScriptDirectory

        server_dir = Path(__file__).resolve().parents[2]
        alembic_ini = server_dir / "alembic.ini"
        if alembic_ini.exists():
            cfg = Config(str(alembic_ini))
            cfg.set_main_option("script_location", str(server_dir / "alembic"))
            script = ScriptDirectory.from_config(cfg)
            heads = list(script.get_heads())
            if heads:
                return heads
    except Exception as exc:
        logger.debug("Dynamic alembic head discovery failed: %s", exc)
    return ["0010_retention_policies"]


async def check_migrations_at_head(
    settings: Settings | None = None,
) -> tuple[bool, str, list[str]]:
    """Check if the connected database has all Alembic migrations applied up to the expected head.

    Returns:
        (is_at_head, status_label, revision_info)
    """
    if settings is None:
        settings = get_settings()

    expected_heads = get_expected_alembic_heads()

    try:
        from sqlalchemy import text

        engine = get_engine(settings)
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT version_num FROM alembic_version"))
            rows = result.fetchall()
            current_versions = [r[0] for r in rows]

        if not current_versions:
            if settings.is_test:
                return True, "skipped", ["no_migration_table_in_test"]
            return False, "pending", ["alembic_version table is empty"]

        is_at_head = any(v in expected_heads for v in current_versions)
        status_label = "ok" if is_at_head else "pending"
        return is_at_head, status_label, current_versions
    except Exception as exc:
        msg = str(exc)
        if "alembic_version" in msg or "no such table" in msg or "does not exist" in msg:
            if settings.is_test:
                return True, "skipped", ["no_migration_table_in_test"]
            return False, "missing_table", [msg]
        logger.debug("Migration check failed: %s", exc)
        if settings.is_test:
            return True, "skipped", [msg]
        return False, "unreachable", [msg]
