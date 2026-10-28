"""Review rules and ReviewBuddy checklist API endpoints (docs/01 CAP-05, docs/03 §11.1)."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_context import AuthContext
from app.core.errors import ForbiddenError
from app.core.kill_switches import require_kill_switch_inactive
from app.domain.auth import (
    PERM_ANALYSIS_CREATE,
    PERM_PROJECT_READ,
    PERM_PROJECT_UPDATE,
    declare_permission,
    get_auth_context,
    get_db_session,
)
from app.domain.review.schemas import (
    ChecklistEvaluationRequest,
    ChecklistEvaluationResponse,
    ReviewRuleCreate,
    ReviewRuleResponse,
    ReviewRuleUpdate,
)
from app.domain.review.service import ReviewRuleService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/projects/{project_id}/review-rules",
    tags=["Review Rules"],
    dependencies=[Depends(require_kill_switch_inactive("analysis"))],
)


@router.get(
    "",
    response_model=list[ReviewRuleResponse],
    status_code=status.HTTP_200_OK,
    summary="List project review rules",
    description="List all active or configured ReviewBuddy checklist and custom review rules for a project.",
)
@declare_permission(PERM_PROJECT_READ)
async def list_project_review_rules(
    project_id: UUID,
    enabled_only: bool = Query(default=False, description="Filter for enabled rules only"),
    category: str | None = Query(default=None, description="Optional filter by rule category"),
    ctx: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> list[ReviewRuleResponse]:
    """Retrieve list of review rules configured for a project."""
    service = ReviewRuleService(session)
    return await service.list_rules(
        ctx=ctx,
        project_id=project_id,
        enabled_only=enabled_only,
        category=category,
    )


@router.post(
    "",
    response_model=ReviewRuleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create custom review rule",
    description="Create a new custom checklist rule for the project.",
)
@declare_permission(PERM_PROJECT_UPDATE)
async def create_project_review_rule(
    project_id: UUID,
    body: ReviewRuleCreate,
    ctx: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> ReviewRuleResponse:
    """Register a new review rule for the project."""
    service = ReviewRuleService(session)
    rule = await service.create_rule(
        ctx=ctx,
        project_id=project_id,
        data=body,
    )
    await session.commit()
    return rule


@router.get(
    "/{rule_id}",
    response_model=ReviewRuleResponse,
    status_code=status.HTTP_200_OK,
    summary="Get review rule by ID",
    description="Retrieve details of a single review rule by primary key.",
)
@declare_permission(PERM_PROJECT_READ)
async def get_project_review_rule(
    project_id: UUID,
    rule_id: UUID,
    ctx: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> ReviewRuleResponse:
    """Retrieve single review rule by id."""
    service = ReviewRuleService(session)
    rule = await service.get_rule(ctx=ctx, rule_id=rule_id)
    if rule.project_id != project_id:
        raise ForbiddenError(detail="Review rule does not belong to specified project")
    return rule


@router.patch(
    "/{rule_id}",
    response_model=ReviewRuleResponse,
    status_code=status.HTTP_200_OK,
    summary="Update review rule",
    description="Modify parameters or toggle enabled state of an existing review rule.",
)
@declare_permission(PERM_PROJECT_UPDATE)
async def update_project_review_rule(
    project_id: UUID,
    rule_id: UUID,
    body: ReviewRuleUpdate,
    ctx: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> ReviewRuleResponse:
    """Update review rule properties."""
    service = ReviewRuleService(session)
    existing = await service.get_rule(ctx=ctx, rule_id=rule_id)
    if existing.project_id != project_id:
        raise ForbiddenError(detail="Review rule does not belong to specified project")

    updated = await service.update_rule(ctx=ctx, rule_id=rule_id, data=body)
    await session.commit()
    return updated


@router.delete(
    "/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete custom review rule",
    description="Permanently delete a custom review rule from the project.",
)
@declare_permission(PERM_PROJECT_UPDATE)
async def delete_project_review_rule(
    project_id: UUID,
    rule_id: UUID,
    ctx: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete custom review rule."""
    service = ReviewRuleService(session)
    existing = await service.get_rule(ctx=ctx, rule_id=rule_id)
    if existing.project_id != project_id:
        raise ForbiddenError(detail="Review rule does not belong to specified project")

    await service.delete_rule(ctx=ctx, rule_id=rule_id)
    await session.commit()


@router.post(
    "/evaluate",
    response_model=ChecklistEvaluationResponse,
    status_code=status.HTTP_200_OK,
    summary="Evaluate ReviewBuddy checklist",
    description="Evaluate project review rules against submitted code diff or files.",
)
@declare_permission(PERM_ANALYSIS_CREATE)
async def evaluate_review_checklist(
    project_id: UUID,
    body: ChecklistEvaluationRequest,
    ctx: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> ChecklistEvaluationResponse:
    """Execute ReviewBuddy checklist evaluation on diff or files."""
    service = ReviewRuleService(session)
    return await service.evaluate_checklist(
        ctx=ctx,
        project_id=project_id,
        request=body,
    )


review_rules_router = router
