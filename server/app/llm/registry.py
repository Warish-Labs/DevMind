"""Adapter registry and factory for LLM providers (docs/05 §11-§12, docs/11 M6-01)."""

from __future__ import annotations

import logging
from typing import Any

from app.llm.adapter import LLMAdapter
from app.llm.exceptions import LLMError

logger = logging.getLogger(__name__)

_ADAPTER_REGISTRY: dict[str, type[LLMAdapter]] = {}


def register_adapter(adapter_type: str, adapter_cls: type[LLMAdapter]) -> None:
    """Register an adapter class for a provider type."""
    key = adapter_type.strip().lower()
    if key in _ADAPTER_REGISTRY:
        logger.debug("Overwriting existing adapter for '%s' with %s", key, adapter_cls.__name__)
    _ADAPTER_REGISTRY[key] = adapter_cls


def get_adapter_class(adapter_type: str) -> type[LLMAdapter]:
    """Retrieve the registered adapter class for a provider type."""
    key = adapter_type.strip().lower()
    if key not in _ADAPTER_REGISTRY:
        raise LLMError(
            f"Unsupported or unregistered LLM adapter type: '{adapter_type}'. Available: {list_supported_adapters()}",
            code="llm.unregistered_adapter",
        )
    return _ADAPTER_REGISTRY[key]


def list_supported_adapters() -> list[str]:
    """List all registered adapter type identifiers."""
    return sorted(_ADAPTER_REGISTRY.keys())


def create_adapter(adapter_type: str, **kwargs: Any) -> LLMAdapter:
    """Instantiate a registered LLM adapter with keyword arguments."""
    cls = get_adapter_class(adapter_type)
    return cls(**kwargs)
