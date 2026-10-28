"""Domain service for review rules management and ReviewBuddy checklist evaluation."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.review_buddy import ReviewBuddyAnalyzer, ReviewChecklistFinding
from app.core.auth_context import AuthContext, SystemContext
from app.core.errors import NotFoundError, ValidationError
from app.domain.review.parser import parse_review_rules_content
from app.domain.review.schemas import (
    ChecklistEvaluationRequest,
    ChecklistEvaluationResponse,
    ChecklistEvaluationSummary,
    ChecklistFinding,
    ReviewRuleCreate,
    ReviewRuleResponse,
    ReviewRuleUpdate,
)
from app.persistence.repositories.project_repo import ProjectRepository
from app.persistence.repositories.review_rule_repo import ReviewRuleRepository

logger = logging.getLogger(__name__)


class ReviewRuleService:
    """Coordinates review rules retrieval, project seeding, and ReviewBuddy checklist execution."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ReviewRuleRepository(session)
        self.project_repo = ProjectRepository(session)

    async def list_rules(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        enabled_only: bool = False,
        category: str | None = None,
    ) -> list[ReviewRuleResponse]:
        """List rules for a project, auto-seeding standard defaults if none exist."""
        # Check project existence
        project = await self.project_repo.get_by_id(ctx, project_id)
        if not project:
            raise NotFoundError(detail=f"Project {project_id} not found")

        rules = await self.repo.list_rules_by_project(
            ctx=ctx,
            project_id=project_id,
            enabled_only=enabled_only,
            category=category,
        )

        if not rules and not enabled_only and not category:
            # First time accessing rules for project -> auto-seed built-ins
            rules = await self.repo.seed_default_rules(
                ctx=ctx,
                workspace_id=project.workspace_id,
                project_id=project_id,
            )

        return [ReviewRuleResponse.model_validate(r) for r in rules]

    async def get_rule(
        self,
        ctx: AuthContext | SystemContext,
        rule_id: UUID,
    ) -> ReviewRuleResponse:
        """Fetch a specific review rule by id."""
        rule = await self.repo.get_rule_by_id(ctx, rule_id)
        if not rule:
            raise NotFoundError(detail=f"Review rule {rule_id} not found")
        return ReviewRuleResponse.model_validate(rule)

    async def create_rule(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        data: ReviewRuleCreate,
    ) -> ReviewRuleResponse:
        """Create a custom review rule for a project."""
        project = await self.project_repo.get_by_id(ctx, project_id)
        if not project:
            raise NotFoundError(detail=f"Project {project_id} not found")

        # Check for duplicate rule_id in project
        existing = await self.repo.get_rule_by_code(ctx, project_id, data.rule_id)
        if existing:
            raise ValidationError(detail=f"Rule ID '{data.rule_id}' already exists in this project")

        rule = await self.repo.create_rule(
            ctx=ctx,
            workspace_id=project.workspace_id,
            project_id=project_id,
            rule_id=data.rule_id,
            title=data.title,
            category=data.category,
            severity=data.severity,
            scope_selector=data.scope_selector.model_dump(),
            check_type=data.check_type,
            check_config=data.check_config,
            message=data.message,
            suggested_fix_template=data.suggested_fix_template,
            is_enabled=data.is_enabled,
            is_builtin=False,
        )
        return ReviewRuleResponse.model_validate(rule)

    async def update_rule(
        self,
        ctx: AuthContext | SystemContext,
        rule_id: UUID,
        data: ReviewRuleUpdate,
    ) -> ReviewRuleResponse:
        """Update an existing review rule."""
        update_data = data.model_dump(exclude_unset=True)
        if "scope_selector" in update_data and update_data["scope_selector"] is not None:
            update_data["scope_selector"] = data.scope_selector.model_dump()  # type: ignore

        updated = await self.repo.update_rule(ctx, rule_id, **update_data)
        if not updated:
            raise NotFoundError(detail=f"Review rule {rule_id} not found")
        return ReviewRuleResponse.model_validate(updated)

    async def delete_rule(
        self,
        ctx: AuthContext | SystemContext,
        rule_id: UUID,
    ) -> bool:
        """Delete a custom review rule."""
        deleted = await self.repo.delete_rule(ctx, rule_id)
        if not deleted:
            raise NotFoundError(detail=f"Review rule {rule_id} not found")
        return True

    async def load_effective_rules(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        repo_rules_content: str | None = None,
    ) -> list[dict[str, Any]]:
        """Load effective review rules combining database rules and optional in-repo file rules."""
        db_rules = await self.list_rules(ctx, project_id, enabled_only=True)
        rule_map: dict[str, dict[str, Any]] = {r.rule_id: r.model_dump() for r in db_rules}

        # If repo has custom .devmind/rules.yaml content, merge it in
        if repo_rules_content:
            try:
                repo_rules = parse_review_rules_content(repo_rules_content)
                for rr in repo_rules:
                    if rr.is_enabled:
                        rule_map[rr.rule_id] = {
                            "rule_id": rr.rule_id,
                            "title": rr.title,
                            "category": rr.category,
                            "severity": rr.severity,
                            "scope_selector": rr.scope_selector.model_dump(),
                            "check_type": rr.check_type,
                            "check_config": rr.check_config,
                            "message": rr.message,
                            "suggested_fix_template": rr.suggested_fix_template,
                            "is_enabled": True,
                            "is_builtin": False,
                        }
            except Exception as exc:
                logger.warning("Could not parse repo rules content: %s", exc)

        return list(rule_map.values())

    async def evaluate_checklist(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        request: ChecklistEvaluationRequest,
        repo_rules_content: str | None = None,
    ) -> ChecklistEvaluationResponse:
        """Evaluate ReviewBuddy checklist on requested diff or files."""
        effective_rules = await self.load_effective_rules(
            ctx=ctx,
            project_id=project_id,
            repo_rules_content=repo_rules_content,
        )

        analyzer = ReviewBuddyAnalyzer(rules=effective_rules)

        raw_findings: list[ReviewChecklistFinding] = []
        if request.diff:
            raw_findings = analyzer.evaluate_diff(request.diff)
        elif request.files:
            raw_findings = analyzer.evaluate_files(request.files)

        findings: list[ChecklistFinding] = []
        counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}

        for rf in raw_findings:
            sev = rf.severity.lower()
            if sev in counts:
                counts[sev] += 1
            else:
                counts["info"] += 1

            findings.append(
                ChecklistFinding(
                    rule_id=rf.rule_id,
                    title=rf.title,
                    category=rf.category,
                    severity=rf.severity,
                    file_path=rf.file_path,
                    start_line=rf.start_line,
                    end_line=rf.end_line,
                    message=rf.message,
                    suggested_fix=rf.suggested_fix,
                    evidence_level=rf.evidence_level,
                    snippet=rf.snippet,
                )
            )

        # Checklist passes if zero critical or high findings
        passed = counts["critical"] == 0 and counts["high"] == 0

        summary = ChecklistEvaluationSummary(
            total_rules_evaluated=len(effective_rules),
            total_findings=len(findings),
            critical_count=counts["critical"],
            high_count=counts["high"],
            medium_count=counts["medium"],
            low_count=counts["low"],
            info_count=counts["info"],
            passed_checklist=passed,
        )

        return ChecklistEvaluationResponse(
            project_id=project_id,
            summary=summary,
            findings=findings,
        )
