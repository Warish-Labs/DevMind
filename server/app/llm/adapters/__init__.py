"""LLM provider adapters package (docs/05 §11-§12)."""

from app.llm.adapters.fake import FakeFaultInjection, FakeLLMAdapter

__all__ = ["FakeLLMAdapter", "FakeFaultInjection"]
