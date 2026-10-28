"""Comprehensive test suite for PRAgent, change-impact analysis, and PR intelligence (docs/01 CAP-06, docs/05 §6.5)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.analysis.change_impact import ChangeImpactAnalyzer
from app.core.auth_context import AuthContext
from app.core.errors import ForbiddenError
from app.core.settings import Settings
from app.domain.auth import get_auth_context, get_db_session
from app.main import create_app
from app.orchestration.manager import (
    classify_intent_deterministically,
)
from app.orchestration.pragent import PRAgent, PRAgentState
from app.orchestration.state import RequestState
from app.persistence.models.github import GitHubRepositoryBinding, PullRequest
from app.persistence.models.pr_analysis import PRAnalysis
from app.persistence.models.project import Project
from app.persistence.repositories.pr_analysis_repo import PRAnalysisRepository


@pytest.fixture
def pr_settings() -> Settings:
    return Settings(
        env="test",
        github_client_id="test_github_client_id",
        github_client_secret="test_github_client_secret",
        encryption_keys=["c3VwZXJfc2VjcmV0X2tleV9mb3JfdGVzdF8zMmJ5dGVzIQ=="],
    )


# ---------------------------------------------------------------------------
# 1. Repository & Tenancy Isolation Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pr_analysis_repo_create_and_fetch() -> None:
    """Verifies PRAnalysis creation, lookup by id, and latest retrieval."""
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    repo = PRAnalysisRepository(session=mock_session)

    wid = uuid.uuid4()
    pid = uuid.uuid4()
    pr_id = uuid.uuid4()

    ctx = AuthContext(
        user_id=uuid.uuid4(),
        clerk_user_id="user_test_pr",
        email="pr@example.com",
        workspace_id=wid,
        project_id=pid,
        project_role="maintainer",
        permissions=frozenset(["project:read", "analysis:create"]),
    )

    analysis = await repo.create_analysis(
        ctx=ctx,
        workspace_id=wid,
        project_id=pid,
        pull_request_id=pr_id,
        head_sha="a1b2c3d4e5",
        job_id=None,
        risk_level="medium",
        summary={"purpose": "Add review rules"},
        impact={"affected_modules": ["api"]},
    )

    assert analysis.workspace_id == wid
    assert analysis.project_id == pid
    assert analysis.pull_request_id == pr_id
    assert analysis.risk_level == "medium"
    assert mock_session.add.called
    assert mock_session.flush.called


@pytest.mark.asyncio
async def test_pr_analysis_repo_cross_workspace_isolation() -> None:
    """Cross-workspace PR analysis creation must be blocked with ForbiddenError."""
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    repo = PRAnalysisRepository(session=mock_session)

    w1 = uuid.uuid4()
    w2 = uuid.uuid4()
    pid = uuid.uuid4()

    ctx_w1 = AuthContext(
        user_id=uuid.uuid4(),
        clerk_user_id="user_w1",
        email="w1@example.com",
        workspace_id=w1,
        project_id=pid,
        project_role="maintainer",
        permissions=frozenset(["analysis:create"]),
    )

    with pytest.raises(ForbiddenError, match="Cross-workspace"):
        await repo.create_analysis(
            ctx=ctx_w1,
            workspace_id=w2,
            project_id=pid,
            pull_request_id=uuid.uuid4(),
            head_sha="deadbeef",
            job_id=None,
            risk_level="low",
            summary={},
            impact={},
        )


# ---------------------------------------------------------------------------
# 2. Change-Impact Analysis Engine Tests
# ---------------------------------------------------------------------------


def test_change_impact_empty_diff() -> None:
    """Empty change set returns low risk with empty collections."""
    analyzer = ChangeImpactAnalyzer()
    report = analyzer.analyze(changed_files=[], diff_text="")
    assert report.risk_level == "low"
    assert len(report.changed_files) == 0
    assert len(report.affected_routes) == 0


def test_change_impact_subgraph_traversal() -> None:
    """Traverses callers and importers through symbol relationships."""
    symbols = [
        {
            "name": "validate_token",
            "kind": "function",
            "file_path": "server/app/domain/auth/tokens.py",
        },
        {"name": "login_handler", "kind": "function", "file_path": "server/app/api/auth.py"},
    ]
    relationships = [
        {
            "from_symbol_name": "login_handler",
            "to_symbol_name": "validate_token",
            "kind": "calls",
            "from_file_path": "server/app/api/auth.py",
            "to_file_path": "server/app/domain/auth/tokens.py",
        }
    ]

    analyzer = ChangeImpactAnalyzer(symbols=symbols, relationships=relationships)
    report = analyzer.analyze(
        changed_files=["server/app/domain/auth/tokens.py"],
        diff_text="",
    )

    assert "server/app/domain/auth/tokens.py" in report.changed_files
    # Direct symbol
    direct_names = [s.name for s in report.direct_symbols]
    assert "validate_token" in direct_names
    # Traversed dependent module
    assert "server/app/api" in report.affected_modules
    # Subgraph nodes include caller login_handler
    node_labels = [n.label for n in report.dependency_graph_nodes]
    assert "login_handler" in node_labels
    assert "validate_token" in node_labels


def test_change_impact_detects_affected_routes() -> None:
    """Detects REST API route decorators in diff text."""
    sample_diff = """
diff --git a/server/app/api/users.py b/server/app/api/users.py
--- a/server/app/api/users.py
+++ b/server/app/api/users.py
@@ -10,3 +10,6 @@
+@router.post("/users", status_code=201)
+async def create_user(body: CreateUserRequest):
+    return {"status": "ok"}
"""
    analyzer = ChangeImpactAnalyzer()
    report = analyzer.analyze(
        changed_files=["server/app/api/users.py"],
        diff_text=sample_diff,
    )

    assert len(report.affected_routes) == 1
    route = report.affected_routes[0]
    assert route.method == "POST"
    assert route.path == "/users"


def test_change_impact_risk_assessment_critical_security() -> None:
    """Changes to auth/tokens/permissions elevate risk level to critical."""
    analyzer = ChangeImpactAnalyzer()
    report = analyzer.analyze(
        changed_files=["server/app/domain/auth/policy.py"],
        diff_text="",
    )
    assert report.risk_level == "critical"
    assert any("security or authentication" in r.lower() for r in report.risk_reasons)


def test_change_impact_risk_assessment_migration_high() -> None:
    """Changes adding or modifying database migrations elevate risk level to high."""
    analyzer = ChangeImpactAnalyzer()
    report = analyzer.analyze(
        changed_files=["server/alembic/versions/0014_new_table.py"],
        diff_text="",
    )
    assert report.risk_level == "high"
    assert any("infrastructure/migration" in r.lower() for r in report.risk_reasons)


def test_change_impact_risk_assessment_docs_low() -> None:
    """Documentation-only modifications evaluate to low risk."""
    analyzer = ChangeImpactAnalyzer()
    report = analyzer.analyze(
        changed_files=["docs/01-product-requirements.md", "README.md"],
        diff_text="",
    )
    assert report.risk_level == "low"


# ---------------------------------------------------------------------------
# 3. PRAgent Specialist & Intent Routing Tests
# ---------------------------------------------------------------------------


def test_classify_intent_deterministically_pr_analysis() -> None:
    """Explicit job_type='pr_analysis' deterministically routes to PRAgent."""
    req = RequestState(job_type="pr_analysis", user_message="Analyze PR #86")
    intent = classify_intent_deterministically(req)
    assert intent is not None
    assert intent.category == "pr_analysis"
    assert intent.requires_specialists == ["pragent"]
    assert intent.confidence == 1.0


@pytest.mark.asyncio
async def test_pragent_specialist_execution() -> None:
    """PRAgent executes change impact, review checklist, evidence verification, and proposals."""
    sample_diff = """
diff --git a/server/app/api/demo.py b/server/app/api/demo.py
--- a/server/app/api/demo.py
+++ b/server/app/api/demo.py
@@ -1,4 +1,8 @@
+@router.post("/items")
+async def create_item(request: Request):
+    data = await request.json()
+    return data
"""
    agent = PRAgent()
    state: PRAgentState = {
        "project_id": str(uuid.uuid4()),
        "workspace_id": str(uuid.uuid4()),
        "diff": sample_diff,
        "changed_files": ["server/app/api/demo.py"],
    }

    result = await agent.execute(state)

    assert "impact_report" in result
    assert "pr_summary" in result
    assert "summary_report" in result

    impact = result["impact_report"]
    summary = result["pr_summary"]

    assert "server/app/api/demo.py" in impact["changed_files"]
    assert summary["risk_level"] in ("high", "critical", "medium")

    # ReviewBuddy checklist finding (REV-INPUT-01 for unvalidated request.json())
    verified_findings = result["verified_findings"]
    assert len(verified_findings) >= 1
    assert any(f.rule_id == "REV-INPUT-01" for f in verified_findings)

    # Proposals contain human-approval gated PR comment
    proposals = result["proposals"]
    assert len(proposals) == 1
    assert proposals[0].proposal_type == "pr_comment"
    assert proposals[0].gated is True


# ---------------------------------------------------------------------------
# 4. API Endpoints Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_api_analyze_and_get_pr_analysis(pr_settings: Settings) -> None:
    """Tests POST /pull-requests/{id}/analyze and GET /pull-requests/{id}/analyses/latest."""
    app = create_app(settings=pr_settings)

    wid = uuid.uuid4()
    pid = uuid.uuid4()
    repo_id = uuid.uuid4()
    pr_id = uuid.uuid4()
    analysis_id = uuid.uuid4()

    mock_project = Project(
        id=pid,
        workspace_id=wid,
        name="PR Test Project",
        slug="pr-test-proj",
    )
    mock_binding = GitHubRepositoryBinding(
        id=repo_id,
        project_id=pid,
        connection_id=uuid.uuid4(),
        full_name="Warish-Labs/DevMind",
        default_branch="main",
        is_active=True,
    )
    mock_pr = PullRequest(
        id=pr_id,
        repository_id=repo_id,
        number=86,
        title="feat: implement review rules",
        author_login="agent",
        state="open",
        head_sha="feedface1234",
        base_sha="c0ffee5678",
    )
    mock_analysis = PRAnalysis(
        id=analysis_id,
        workspace_id=wid,
        project_id=pid,
        pull_request_id=pr_id,
        head_sha="feedface1234",
        job_id=None,
        risk_level="high",
        summary={
            "purpose": "Database schema migration",
            "files_changed": ["server/alembic/versions/0013_pr_analyses.py"],
            "affected_areas": ["server/alembic"],
            "risks": ["Modifies migration infrastructure"],
            "security_summary": "No critical security risks",
            "testing_concerns": [],
            "documentation_impact": "None",
            "risk_level": "high",
        },
        impact={
            "changed_files": ["server/alembic/versions/0013_pr_analyses.py"],
            "direct_symbols": [],
            "affected_modules": ["server/alembic"],
            "affected_routes": [],
            "affected_tests": [],
            "dependency_graph_nodes": [],
            "dependency_graph_edges": [],
            "risk_level": "high",
            "risk_reasons": ["Modifies high-impact infrastructure/migration"],
        },
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    mock_session = AsyncMock()
    mock_session.add = MagicMock()

    async def _mock_exec(query, *args, **kwargs):
        res = MagicMock()
        q_str = str(query)
        if "pull_requests" in q_str:
            res.scalar_one_or_none.return_value = mock_pr
            res.scalars.return_value.first.return_value = mock_pr
            res.scalars.return_value.all.return_value = [mock_pr]
        elif "github_repositories" in q_str:
            res.scalar_one_or_none.return_value = mock_binding
            res.scalars.return_value.first.return_value = mock_binding
        elif "projects" in q_str:
            res.scalar_one_or_none.return_value = mock_project
            res.scalars.return_value.first.return_value = mock_project
        elif "review_rules" in q_str:
            res.scalars.return_value.all.return_value = []
        elif "code_symbols" in q_str or "code_relationships" in q_str:
            res.scalars.return_value.all.return_value = []
        elif "pr_analyses" in q_str:
            res.scalar_one_or_none.return_value = mock_analysis
            res.scalars.return_value.all.return_value = [mock_analysis]
        return res

    mock_session.execute.side_effect = _mock_exec

    async def _override_db():
        yield mock_session

    async def _override_auth():
        return AuthContext(
            user_id=uuid.uuid4(),
            clerk_user_id="user_test_client",
            email="client@example.com",
            workspace_id=wid,
            project_id=pid,
            project_role="maintainer",
            permissions=frozenset(["project:read", "analysis:create"]),
        )

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_auth_context] = _override_auth

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Trigger PR analysis with diff override
        payload = {
            "diff_override": "diff --git a/test.py b/test.py\n+print('hello')",
            "post_comment": False,
        }
        res_post = await client.post(f"/api/v1/pull-requests/{pr_id}/analyze", json=payload)
        assert res_post.status_code == 200
        data = res_post.json()
        assert data["head_sha"] == "feedface1234"
        assert data["risk_level"] in ("low", "medium", "high", "critical")

        # 2. Get latest analysis
        res_get = await client.get(f"/api/v1/pull-requests/{pr_id}/analyses/latest")
        assert res_get.status_code == 200
        data_latest = res_get.json()
        assert data_latest["id"] == str(analysis_id)

        # 3. List analyses
        res_list = await client.get(f"/api/v1/pull-requests/{pr_id}/analyses")
        assert res_list.status_code == 200
        data_list = res_list.json()
        assert len(data_list) == 1
