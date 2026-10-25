"""Centralized subsystem kill switches and feature flag controls (docs/07 §12, docs/10 §11, §17).

Enforces operational kill switches:
- indexing: disables indexed mode chunking and code snippet upload
- llm: disables LLM generation gateway calls
- embed: disables vector embedding generation
- webhooks: disables external webhook ingestion (Clerk, GitHub)
- pause_queues: disables background job queueing and worker claiming
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from fastapi import Depends

from app.core.errors import FeatureDisabledError
from app.core.settings import Settings, get_settings

logger = logging.getLogger("devmind.kill_switches")

# In-memory overrides for drills, tests, and runtime toggles
_dynamic_overrides: dict[str, bool] = {}

VALID_KILL_SWITCHES = frozenset({"indexing", "llm", "embed", "webhooks", "pause_queues"})


def set_dynamic_kill_switch(switch_name: str, active: bool) -> None:
    """Dynamically override a kill switch at runtime (for drills/tests)."""
    norm = switch_name.lower().replace("-", "_").replace("kill_", "").replace("pause_", "")
    _dynamic_overrides[norm] = active
    logger.warning("Dynamic kill switch override set: %s=%s", norm, active)


def reset_dynamic_kill_switches() -> None:
    """Clear all dynamic kill switch overrides."""
    _dynamic_overrides.clear()


def is_kill_switch_active(switch_name: str, settings: Settings | None = None) -> bool:
    """Return True if the specified kill switch is active in configuration or dynamic override."""
    norm = switch_name.lower().replace("-", "_").replace("kill_", "").replace("pause_", "")

    # Dynamic in-memory override takes precedence if explicitly set
    if norm in _dynamic_overrides:
        return _dynamic_overrides[norm]

    if settings is None:
        settings = get_settings()

    if norm == "indexing":
        return bool(settings.kill_indexing)
    elif norm == "llm":
        return bool(settings.kill_llm)
    elif norm == "embed":
        return bool(settings.kill_embed)
    elif norm == "webhooks":
        return bool(settings.kill_webhooks)
    elif norm in ("pause_queues", "queues"):
        return bool(settings.pause_queues)

    return False


def check_kill_switch(switch_name: str, settings: Settings | None = None) -> None:
    """Check if kill switch is active; raises FeatureDisabledError if so."""
    if is_kill_switch_active(switch_name, settings):
        norm = switch_name.lower().replace("-", "_").replace("kill_", "").replace("pause_", "")
        logger.warning("Blocked operation due to active kill switch: %s", norm)
        raise FeatureDisabledError(feature=norm)


def get_active_kill_switches(settings: Settings | None = None) -> dict[str, bool]:
    """Return dictionary of all defined kill switches and their current active status."""
    if settings is None:
        settings = get_settings()

    return {
        "indexing": is_kill_switch_active("indexing", settings),
        "llm": is_kill_switch_active("llm", settings),
        "embed": is_kill_switch_active("embed", settings),
        "webhooks": is_kill_switch_active("webhooks", settings),
        "pause_queues": is_kill_switch_active("pause_queues", settings),
    }


def require_kill_switch_inactive(switch_name: str) -> Callable[..., Any]:
    """FastAPI route dependency ensuring a kill switch is not active."""

    async def _dependency(settings: Settings = Depends(get_settings)) -> None:
        check_kill_switch(switch_name, settings)

    return _dependency
