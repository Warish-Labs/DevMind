"""Idempotent system bootstrap and reference data seeding (docs/03 §9, ADR-046).

Seeds only system-level reference configurations (such as active embedding spaces).
Never seeds fake production users, workspaces, credentials, or private content.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from alembic.config import Config
from sqlalchemy import select

from alembic import command
from app.core.settings import Settings, get_settings
from app.persistence.models.brain import EmbeddingSpace

logger = logging.getLogger("devmind.bootstrap")


def run_alembic_migrations(settings: Settings | None = None) -> bool:
    """Run Alembic schema migrations up to head programmatically."""
    cfg_settings = settings or get_settings()
    url = cfg_settings.database_url_direct or cfg_settings.database_url
    if not url:
        logger.warning("No database URL configured; skipping migrations")
        return False

    # Find alembic.ini
    possible_paths = [
        "alembic.ini",
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "alembic.ini"),
    ]
    ini_path = next((p for p in possible_paths if os.path.exists(p)), "alembic.ini")

    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)

    try:
        logger.info("Executing Alembic migrations (head) using %s", ini_path)
        alembic_cfg = Config(ini_path)
        alembic_cfg.set_main_option("sqlalchemy.url", url)
        command.upgrade(alembic_cfg, "head")
        logger.info("Alembic schema migrations applied successfully to head")
        return True
    except Exception as exc:
        logger.error("Database migration failed: %s", exc)
        raise


async def seed_reference_data(settings: Settings | None = None) -> dict[str, Any]:
    """Seed initial system reference data idempotently (e.g. active embedding space).

    Guarantees:
    - Never overwrites existing reference data.
    - Zero fake users, workspaces, or credentials.
    - Safe to run on every startup or deploy.
    """
    from app.persistence.database import get_session_factory

    cfg_settings = settings or get_settings()
    session_factory = get_session_factory(cfg_settings)

    results: dict[str, Any] = {"embedding_spaces_created": 0}

    async with session_factory() as session:
        # Check active embedding spaces
        stmt = (
            select(EmbeddingSpace)
            .where(EmbeddingSpace.status == "active")
            .order_by(EmbeddingSpace.created_at.desc())
        )
        res = await session.execute(stmt)
        active_space = res.scalar_one_or_none()

        if active_space is None:
            logger.info("No active embedding space found; provisioning baseline space")
            # Default space matches current fake embedding adapter (64-dim)
            new_space = EmbeddingSpace(
                provider_id=cfg_settings.embed_provider or "fake",
                model_id="fake-embed-v1",
                dimension=64,
                status="active",
                config_hash="sha256:baseline-default-space",
            )
            session.add(new_space)
            await session.commit()
            results["embedding_spaces_created"] = 1
            logger.info(
                "Provisioned default active embedding space (id=%s, dimension=%d)",
                new_space.id,
                new_space.dimension,
            )
        else:
            logger.info(
                "Active embedding space verified (id=%s, provider=%s, dimension=%d)",
                active_space.id,
                active_space.provider_id,
                active_space.dimension,
            )

    return results


async def bootstrap_database(settings: Settings | None = None) -> bool:
    """Complete bootstrap sequence: runs migrations to head then seeds reference data."""
    cfg_settings = settings or get_settings()
    run_alembic_migrations(cfg_settings)
    await seed_reference_data(cfg_settings)
    return True


if __name__ == "__main__":
    import asyncio

    logging.basicConfig(level=logging.INFO)
    asyncio.run(bootstrap_database())
