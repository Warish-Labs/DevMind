"""Repository for ReviewRule persistence and project-scoped operations (docs/01 CAP-05, docs/03 §3.5)."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select, update

from app.core.auth_context import AuthContext, SystemContext
from app.core.errors import ForbiddenError
from app.core.ids import generate_uuid7
from app.persistence.models.review_rules import ReviewRule
from app.persistence.repositories.base import BaseRepository

logger = logging.getLogger(__name__)

# Standard built-in ReviewBuddy checklist rules
DEFAULT_CHECKLIST_RULES: list[dict[str, Any]] = [
    {
        "rule_id": "REV-INPUT-01",
        "title": "Require Input Validation on Route Handlers",
        "category": "input_validation",
        "severity": "high",
        "check_type": "require_validation",
        "scope_selector": {
            "paths": ["**/api/**", "**/routes/**", "**/endpoints/**", "**/controllers/**"],
            "languages": ["python", "typescript", "javascript"],
        },
        "check_config": {
            "enforce_request_body_schema": True,
            "allowed_schema_types": ["BaseModel", "pydantic", "zod", "typebox"],
        },
        "message": "Route handlers accepting external parameters or request bodies must enforce schema validation before processing.",
        "suggested_fix_template": "Add a Pydantic schema model or Zod parser validating the request payload.",
        "is_builtin": True,
    },
    {
        "rule_id": "REV-ERR-01",
        "title": "Require Structured Error Handling and Avoid Bare Excepts",
        "category": "error_handling",
        "severity": "medium",
        "check_type": "require_error_handling",
        "scope_selector": {
            "paths": ["**/*.py", "**/*.ts", "**/*.js"],
            "languages": ["python", "typescript", "javascript"],
        },
        "check_config": {
            "forbid_bare_except": True,
            "forbid_empty_catch": True,
            "require_rfc9457_exceptions": True,
        },
        "message": "Handler must not catch exceptions blindly without logging or mapping to structured problem responses (RFC 9457).",
        "suggested_fix_template": "Catch specific exception types, log error context with request_id, and raise domain HTTP exceptions.",
        "is_builtin": True,
    },
    {
        "rule_id": "REV-AUTH-01",
        "title": "Require Authorization Guards on Mutating Endpoints",
        "category": "authorization",
        "severity": "high",
        "check_type": "require_auth",
        "scope_selector": {
            "paths": ["**/api/**", "**/routes/**"],
            "languages": ["python", "typescript", "javascript"],
        },
        "check_config": {
            "mutating_methods": ["POST", "PUT", "DELETE", "PATCH"],
            "required_guard_decorators": [
                "declare_permission",
                "require_permission",
                "require_role",
                "require_auth",
            ],
        },
        "message": "State-mutating endpoints (POST/PUT/PATCH/DELETE) must declare explicit permission checks or authentication guards.",
        "suggested_fix_template": "Add @declare_permission(PERM_...) or Depends(require_auth) dependency to the route definition.",
        "is_builtin": True,
    },
    {
        "rule_id": "REV-TEST-01",
        "title": "Require Automated Test Coverage for New Endpoints and Services",
        "category": "testing",
        "severity": "medium",
        "check_type": "require_test",
        "scope_selector": {
            "paths": ["**/domain/**", "**/api/**", "**/services/**"],
            "languages": ["python", "typescript", "javascript"],
        },
        "check_config": {
            "check_associated_test_file": True,
        },
        "message": "New public API routes or domain services must have accompanying unit or integration tests.",
        "suggested_fix_template": "Author a test module verifying success, validation failure, and unauthorized failure cases.",
        "is_builtin": True,
    },
    {
        "rule_id": "REV-DOC-01",
        "title": "Require OpenAPI Documentation and Docstrings on Public APIs",
        "category": "documentation",
        "severity": "low",
        "check_type": "require_docs",
        "scope_selector": {
            "paths": ["**/api/**", "**/routes/**"],
            "languages": ["python", "typescript", "javascript"],
        },
        "check_config": {
            "require_docstring": True,
            "require_summary": True,
        },
        "message": "Public endpoints must have a descriptive docstring and OpenAPI summary for client generation.",
        "suggested_fix_template": "Add summary and docstring explaining endpoint behavior, parameters, and return schemas.",
        "is_builtin": True,
    },
]


class ReviewRuleRepository(BaseRepository):
    """Encapsulates database operations for review rules and checklist configurations."""

    async def create_rule(
        self,
        ctx: AuthContext | SystemContext,
        workspace_id: UUID,
        project_id: UUID,
        rule_id: str,
        title: str,
        category: str,
        severity: str,
        scope_selector: dict[str, Any],
        check_type: str,
        check_config: dict[str, Any],
        message: str,
        suggested_fix_template: str | None = None,
        is_enabled: bool = True,
        is_builtin: bool = False,
    ) -> ReviewRule:
        """Create a new review rule for a project."""
        self._validate_context(ctx)

        if isinstance(ctx, AuthContext):
            if ctx.workspace_id and ctx.workspace_id != workspace_id:
                raise ForbiddenError(detail="Cross-workspace review rule creation is forbidden")
            if ctx.project_id and ctx.project_id != project_id:
                raise ForbiddenError(detail="Cross-project review rule creation is forbidden")

        rule = ReviewRule(
            id=generate_uuid7(),
            workspace_id=workspace_id,
            project_id=project_id,
            rule_id=rule_id.strip(),
            title=title.strip(),
            category=category.strip(),
            severity=severity.strip(),
            scope_selector=scope_selector,
            check_type=check_type.strip(),
            check_config=check_config,
            message=message.strip(),
            suggested_fix_template=suggested_fix_template.strip()
            if suggested_fix_template
            else None,
            is_enabled=is_enabled,
            is_builtin=is_builtin,
        )
        self.session.add(rule)
        await self.session.flush()
        return rule

    async def get_rule_by_id(
        self,
        ctx: AuthContext | SystemContext,
        rule_id: UUID,
    ) -> ReviewRule | None:
        """Fetch a single review rule by primary key."""
        self._validate_context(ctx)

        query = select(ReviewRule).where(ReviewRule.id == rule_id)
        if isinstance(ctx, AuthContext):
            if ctx.workspace_id:
                query = query.where(ReviewRule.workspace_id == ctx.workspace_id)
            if ctx.project_id:
                query = query.where(ReviewRule.project_id == ctx.project_id)

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_rule_by_code(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        rule_code: str,
    ) -> ReviewRule | None:
        """Fetch a review rule by project and rule_id identifier."""
        self._validate_context(ctx)

        query = select(ReviewRule).where(
            ReviewRule.project_id == project_id,
            ReviewRule.rule_id == rule_code.strip(),
        )
        if isinstance(ctx, AuthContext) and ctx.workspace_id:
            query = query.where(ReviewRule.workspace_id == ctx.workspace_id)

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_rules_by_project(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        enabled_only: bool = False,
        category: str | None = None,
    ) -> Sequence[ReviewRule]:
        """List all review rules belonging to a project."""
        self._validate_context(ctx)

        query = select(ReviewRule).where(ReviewRule.project_id == project_id)
        if isinstance(ctx, AuthContext) and ctx.workspace_id:
            query = query.where(ReviewRule.workspace_id == ctx.workspace_id)

        if enabled_only:
            query = query.where(ReviewRule.is_enabled.is_(True))
        if category:
            query = query.where(ReviewRule.category == category.strip())

        query = query.order_by(ReviewRule.is_builtin.desc(), ReviewRule.rule_id.asc())
        result = await self.session.execute(query)
        return result.scalars().all()

    async def update_rule(
        self,
        ctx: AuthContext | SystemContext,
        rule_id: UUID,
        **updates: Any,
    ) -> ReviewRule | None:
        """Update fields of an existing review rule."""
        self._validate_context(ctx)

        rule = await self.get_rule_by_id(ctx, rule_id)
        if not rule:
            return None

        # Disallow updating primary keys, tenant IDs, or immutables
        for key in ("id", "workspace_id", "project_id", "created_at"):
            updates.pop(key, None)

        updates["updated_at"] = datetime.now(UTC)

        stmt = (
            update(ReviewRule)
            .where(ReviewRule.id == rule_id)
            .values(**updates)
            .execution_options(synchronize_session="fetch")
        )
        await self.session.execute(stmt)
        await self.session.flush()
        return await self.get_rule_by_id(ctx, rule_id)

    async def delete_rule(
        self,
        ctx: AuthContext | SystemContext,
        rule_id: UUID,
    ) -> bool:
        """Delete a custom review rule. Builtin rules can be disabled but not deleted."""
        self._validate_context(ctx)

        rule = await self.get_rule_by_id(ctx, rule_id)
        if not rule:
            return False

        if rule.is_builtin:
            raise ForbiddenError(
                detail="Built-in review checklist rules cannot be deleted; disable them instead"
            )

        stmt = delete(ReviewRule).where(ReviewRule.id == rule_id)
        await self.session.execute(stmt)
        await self.session.flush()
        return True

    async def seed_default_rules(
        self,
        ctx: AuthContext | SystemContext,
        workspace_id: UUID,
        project_id: UUID,
    ) -> list[ReviewRule]:
        """Seed the 5 standard built-in checklist rules for a project if not already present."""
        self._validate_context(ctx)

        seeded: list[ReviewRule] = []
        for default_rule in DEFAULT_CHECKLIST_RULES:
            existing = await self.get_rule_by_code(ctx, project_id, default_rule["rule_id"])
            if existing is None:
                new_rule = await self.create_rule(
                    ctx=ctx,
                    workspace_id=workspace_id,
                    project_id=project_id,
                    rule_id=default_rule["rule_id"],
                    title=default_rule["title"],
                    category=default_rule["category"],
                    severity=default_rule["severity"],
                    scope_selector=default_rule["scope_selector"],
                    check_type=default_rule["check_type"],
                    check_config=default_rule["check_config"],
                    message=default_rule["message"],
                    suggested_fix_template=default_rule.get("suggested_fix_template"),
                    is_enabled=True,
                    is_builtin=True,
                )
                seeded.append(new_rule)
            else:
                seeded.append(existing)

        return seeded
