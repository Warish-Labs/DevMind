"""Audit domain package for sensitive action logs and governance (docs/03 §3.5 & docs/07 §16)."""

from app.domain.audit.service import AuditService

__all__ = ["AuditService"]
