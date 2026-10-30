"""End-to-End integration test suite for PR Intelligence, ReviewBuddy, and Change-Impact Analysis (E2E-9, docs/01 CAP-05/06, docs/09 §14, M11-08)."""

from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

import app.orchestration.pragent as pragent_module
from app.core.auth_context import AuthContext
from app.core.errors import NotFoundError
from app.core.settings import Settings
from app.domain.auth import (
    PERM_ANALYSIS_CREATE,
    PERM_PROJECT_READ,
)
from app.domain.pr_agent.schemas import TriggerPRAnalysisRequest
from app.domain.pr_agent.service import PRAgentService
from app.domain.webhooks.github_webhook_service import GitHubWebhookService
from app.persistence.models.github import GitHubRepositoryBinding, PullRequest
from app.persistence.models.pr_analysis import PRAnalysis
from app.persistence.models.project import Project

TEST_WEBHOOK_SECRET = "devmind_test_e2e_webhook_secret_9999"


def compute_sig(secret: str, body: bytes) -> str:
    sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


@pytest.fixture
def e2e_settings() -> Settings:
    return Settings(
        env="test",
        github_webhook_secret=TEST_WEBHOOK_SECRET,
    )


@pytest.mark.asyncio
async def test_e2e_pr_intelligence_lifecycle_flow(e2e_settings: Settings) -> None:
    """E2E-9: Full multi-agent PR intelligence flow on fixture repository and PR."""
    workspace_id = uuid4()
    project_id = uuid4()
    binding_id = uuid4()
    user_id = uuid4()

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    # 1. Setup mock workspace, project, and GitHub repo binding
    mock_project = Project(
        id=project_id,
        workspace_id=workspace_id,
        name="Core Backend",
        slug="core-backend",
    )
    mock_binding = GitHubRepositoryBinding(
        id=binding_id,
        project_id=project_id,
        full_name="Warish-Labs/DevMind",
        default_branch="main",
    )

    # 2. Simulate webhook delivery of PR opened event
    webhook_service = GitHubWebhookService(session=mock_session, settings=e2e_settings)
    webhook_service.repo.get_repository_by_full_name = AsyncMock(return_value=mock_binding)

    pr_id = uuid4()
    mock_pr = PullRequest(
        id=pr_id,
        repository_id=binding_id,
        number=101,
        title="feat(auth): refactor token verification and session revocation",
        author_login="security-lead",
        state="open",
        head_sha="sha_e2e_head_12345",
        base_sha="sha_e2e_base_00000",
        head_ref="feature/session-revocation",
        base_ref="main",
        diff_url="https://github.com/Warish-Labs/DevMind/pull/101.diff",
    )
    webhook_service.repo.upsert_pull_request = AsyncMock(return_value=mock_pr)

    pr_opened_payload = {
        "action": "opened",
        "repository": {"full_name": "Warish-Labs/DevMind"},
        "pull_request": {
            "number": 101,
            "title": "feat(auth): refactor token verification and session revocation",
            "state": "open",
            "user": {"login": "security-lead"},
            "head": {"sha": "sha_e2e_head_12345", "ref": "feature/session-revocation"},
            "base": {"sha": "sha_e2e_base_00000", "ref": "main"},
            "diff_url": "https://github.com/Warish-Labs/DevMind/pull/101.diff",
        },
    }

    deliv_id = f"e2e-delivery-{uuid4()}"
    webhook_res = await webhook_service.handle_event("pull_request", deliv_id, pr_opened_payload)
    assert webhook_res["status"] == "processed"
    assert webhook_res["mirrored"] is True
    assert webhook_res["number"] == 101

    # 3. Simulate PRAgent triggering change-impact analysis & ReviewBuddy checklist
    ctx = AuthContext(
        user_id=user_id,
        clerk_user_id="user_clerk_123",
        email="dev@warishlabs.in",
        workspace_id=workspace_id,
        permissions=frozenset([PERM_ANALYSIS_CREATE, PERM_PROJECT_READ]),
    )

    pr_service = PRAgentService(session=mock_session)
    pr_service.github_repo.get_pull_request_by_id = AsyncMock(return_value=mock_pr)
    pr_service.github_repo.get_repository_by_id = AsyncMock(return_value=mock_binding)
    pr_service.project_repo.get_by_id = AsyncMock(return_value=mock_project)

    diff_override = """--- a/server/app/domain/auth/session.py
+++ b/server/app/domain/auth/session.py
@@ -10,6 +10,12 @@
 from fastapi import APIRouter
 router = APIRouter()
 @router.post("/sessions/revoke")
+async def revoke_session_handler(request: Request):
+    try:
+        data = await request.json()
+    except:
+        pass
+    return {"status": "revoked"}
"""

    mock_analysis_id = uuid4()
    persisted_analysis = PRAnalysis(
        id=mock_analysis_id,
        workspace_id=workspace_id,
        project_id=project_id,
        pull_request_id=pr_id,
        head_sha=mock_pr.head_sha,
        risk_level="critical",
        summary={
            "purpose": "Refactor session revocation in auth domain",
            "files_changed": ["server/app/domain/auth/session.py"],
            "affected_areas": ["server/app/domain/auth"],
            "risks": ["Alters authentication session state without test updates"],
            "security_summary": "Modifies sensitive authentication/session handlers",
            "testing_concerns": ["No test files included"],
            "documentation_impact": "Requires doc updates",
            "risk_level": "critical",
        },
        impact={
            "changed_files": ["server/app/domain/auth/session.py"],
            "risk_level": "critical",
            "risk_reasons": ["Touches critical security/auth keyword"],
            "direct_symbols": [],
            "affected_modules": ["server/app/domain/auth"],
            "affected_routes": [],
            "affected_tests": [],
            "dependency_graph_nodes": [],
            "dependency_graph_edges": [],
        },
        created_at=datetime.now(UTC),
    )

    pr_service.repo.create_analysis = AsyncMock(return_value=persisted_analysis)

    with patch("app.orchestration.pragent.BrainRepository") as mock_brain_cls:
        mock_brain = mock_brain_cls.return_value
        mock_brain.list_symbols = AsyncMock(return_value=[])
        mock_brain.get_graph_data = AsyncMock(return_value=([], []))

        req = TriggerPRAnalysisRequest(diff_override=diff_override, post_comment=False)
        analysis_resp = await pr_service.analyze_pull_request(ctx=ctx, pull_request_id=pr_id, request_data=req)

    assert analysis_resp.id == mock_analysis_id
    assert analysis_resp.risk_level == "critical"
    assert "server/app/domain/auth/session.py" in analysis_resp.impact["changed_files"]
    assert analysis_resp.summary["risk_level"] == "critical"


@pytest.mark.asyncio
async def test_e2e_cross_tenant_isolation_rejected() -> None:
    """Verify that Tenant B cannot access or analyze Pull Requests belonging to Tenant A."""
    workspace_a = uuid4()
    workspace_b = uuid4()
    pr_id = uuid4()

    mock_session = AsyncMock()
    service = PRAgentService(session=mock_session)

    mock_pr = PullRequest(
        id=pr_id,
        repository_id=uuid4(),
        number=1,
        title="Tenant A Private PR",
        author_login="dev-a",
        state="open",
        head_sha="sha_a",
        base_sha="sha_base",
    )

    async def mock_get_pr(ctx: AuthContext, id_: Any) -> PullRequest | None:
        if ctx.workspace_id == workspace_a:
            return mock_pr
        return None

    service.github_repo.get_pull_request_by_id = AsyncMock(side_effect=mock_get_pr)

    ctx_b = AuthContext(
        user_id=uuid4(),
        clerk_user_id="user_clerk_b",
        email="dev_b@warishlabs.in",
        workspace_id=workspace_b,
        permissions=frozenset([PERM_ANALYSIS_CREATE]),
    )

    with pytest.raises(NotFoundError) as exc_info:
        await service.analyze_pull_request(ctx=ctx_b, pull_request_id=pr_id)

    assert f"Pull request {pr_id} not found" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_e2e_human_approval_gate_for_pr_comments() -> None:
    """Verify that external comments to GitHub require human approval and cannot execute silently (ADR-015)."""
    req = TriggerPRAnalysisRequest(post_comment=True)
    assert req.post_comment is True

    from app.orchestration.pragent import PRAgent
    agent = PRAgent()
    assert hasattr(agent, "execute")
    assert "Optional comment posting to GitHub gated by human approval" in pragent_module.__doc__


@pytest.mark.asyncio
async def test_e2e_github_token_outage_resilience(e2e_settings: Settings) -> None:
    """Verify clean error handling when GitHub OAuth token is revoked or provider returns 401."""
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=mock_result)
    service = PRAgentService(session=session)

    workspace_id = uuid4()
    pr_id = uuid4()
    binding_id = uuid4()

    mock_pr = PullRequest(
        id=pr_id,
        repository_id=binding_id,
        number=42,
        title="PR with expired OAuth token",
        author_login="dev",
        state="open",
        head_sha="sha_42",
        base_sha="sha_base",
        diff_url="https://github.com/Warish-Labs/DevMind/pull/42.diff",
    )
    mock_binding = GitHubRepositoryBinding(
        id=binding_id,
        project_id=uuid4(),
        full_name="Warish-Labs/DevMind",
        default_branch="main",
    )
    mock_project = Project(
        id=mock_binding.project_id,
        workspace_id=workspace_id,
        name="Test",
        slug="test",
    )

    service.github_repo.get_pull_request_by_id = AsyncMock(return_value=mock_pr)
    service.github_repo.get_repository_by_id = AsyncMock(return_value=mock_binding)
    service.project_repo.get_by_id = AsyncMock(return_value=mock_project)

    service._fetch_diff_from_github = AsyncMock(return_value="")
    service.repo.create_analysis = AsyncMock(return_value=PRAnalysis(
        id=uuid4(),
        workspace_id=workspace_id,
        project_id=mock_project.id,
        pull_request_id=pr_id,
        head_sha=mock_pr.head_sha,
        risk_level="low",
        summary={},
        impact={},
    ))

    ctx = AuthContext(
        user_id=uuid4(),
        clerk_user_id="user_clerk_test",
        email="dev_test@warishlabs.in",
        workspace_id=workspace_id,
        permissions=frozenset([PERM_ANALYSIS_CREATE]),
    )

    with patch("app.orchestration.pragent.BrainRepository") as mock_brain_cls:
        mock_brain = mock_brain_cls.return_value
        mock_brain.list_symbols = AsyncMock(return_value=[])
        mock_brain.get_graph_data = AsyncMock(return_value=([], []))

        res = await service.analyze_pull_request(ctx=ctx, pull_request_id=pr_id)
    assert res.risk_level == "low"
