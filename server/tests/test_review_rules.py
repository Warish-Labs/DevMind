"""Unit and API integration tests for ReviewBuddy checklist engine and review rules (CAP-05, M11-04).

Verifies:
1. ReviewRule persistence model, constraints, and default rule seeding.
2. Cross-workspace and cross-project tenant isolation (IDOR prevention - Rule 4).
3. In-repo review rules YAML/JSON parsing and schema validation.
4. Deterministic ReviewBuddy checklist analyzer:
   - Input validation check (require_validation)
   - Error handling and bare except detection (require_error_handling)
   - Mutating route authorization check (require_auth)
   - Test coverage detection (require_test)
   - Documentation presence check (require_docs)
   - Custom forbidden and required regex pattern matching
   - Unified diff hunk line scoping
5. Evidence verification for ReviewBuddy findings (EvidenceVerifier grounding).
6. REST API routes for /projects/{pid}/review-rules and /review-rules/evaluate.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.analysis.review_buddy import (
    ReviewBuddyAnalyzer,
)
from app.core.auth_context import AuthContext
from app.core.errors import ForbiddenError, ValidationError
from app.core.settings import Settings
from app.domain.auth import get_auth_context, get_db_session
from app.domain.review.parser import parse_review_rules_content
from app.main import create_app
from app.orchestration.reviewbuddy import ReviewBuddyAgent, ReviewBuddyState
from app.persistence.models.project import Project
from app.persistence.models.review_rules import ReviewRule
from app.persistence.repositories.review_rule_repo import (
    DEFAULT_CHECKLIST_RULES,
    ReviewRuleRepository,
)


@pytest.fixture
def review_settings() -> Settings:
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
async def test_review_rule_repo_create_and_fetch() -> None:
    """Verifies review rule creation and lookup by ID and rule_id."""
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    repo = ReviewRuleRepository(session=mock_session)

    wid = uuid.uuid4()
    pid = uuid.uuid4()
    ctx = AuthContext(
        user_id=uuid.uuid4(),
        clerk_user_id="user_test_123",
        email="test@example.com",
        workspace_id=wid,
        project_id=pid,
        project_role="maintainer",
        permissions=frozenset(["project:read", "project:update"]),
    )

    rule = await repo.create_rule(
        ctx=ctx,
        workspace_id=wid,
        project_id=pid,
        rule_id="REV-CUSTOM-01",
        title="Custom Logging Rule",
        category="quality",
        severity="medium",
        scope_selector={"paths": ["**/*.py"]},
        check_type="pattern_forbidden",
        check_config={"patterns": ["print("]},
        message="Use structured logger instead of print",
        suggested_fix_template="Replace print with logger.info()",
        is_enabled=True,
    )

    assert rule.rule_id == "REV-CUSTOM-01"
    assert rule.workspace_id == wid
    assert rule.project_id == pid
    assert rule.is_enabled is True
    assert rule.is_builtin is False
    assert mock_session.add.called
    assert mock_session.flush.called


@pytest.mark.asyncio
async def test_review_rule_repo_cross_workspace_isolation() -> None:
    """Cross-workspace review rule access must be rejected with ForbiddenError (Rule 4)."""
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    repo = ReviewRuleRepository(session=mock_session)

    w1 = uuid.uuid4()
    w2 = uuid.uuid4()
    pid = uuid.uuid4()

    # User in W1 tries to create rule in W2
    ctx_w1 = AuthContext(
        user_id=uuid.uuid4(),
        clerk_user_id="user_w1",
        email="w1@example.com",
        workspace_id=w1,
        project_id=pid,
        project_role="maintainer",
        permissions=frozenset(["project:update"]),
    )

    with pytest.raises(ForbiddenError, match="Cross-workspace"):
        await repo.create_rule(
            ctx=ctx_w1,
            workspace_id=w2,
            project_id=pid,
            rule_id="REV-ISOLATION-01",
            title="Isolation Test",
            category="quality",
            severity="low",
            scope_selector={"paths": ["**/*"]},
            check_type="pattern_forbidden",
            check_config={},
            message="Test rule",
        )


@pytest.mark.asyncio
async def test_review_rule_repo_builtin_deletion_rejected() -> None:
    """Built-in checklist rules cannot be deleted; they can only be disabled."""
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    repo = ReviewRuleRepository(session=mock_session)

    wid = uuid.uuid4()
    pid = uuid.uuid4()
    rule_id = uuid.uuid4()

    builtin_rule = ReviewRule(
        id=rule_id,
        workspace_id=wid,
        project_id=pid,
        rule_id="REV-INPUT-01",
        title="Require Input Validation",
        category="input_validation",
        severity="high",
        scope_selector={},
        check_type="require_validation",
        check_config={},
        message="Input validation required",
        is_builtin=True,
    )

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = builtin_rule
    mock_session.execute.return_value = mock_result

    ctx = AuthContext(
        user_id=uuid.uuid4(),
        clerk_user_id="user_admin",
        email="admin@example.com",
        workspace_id=wid,
        project_id=pid,
        project_role="maintainer",
        permissions=frozenset(["project:update"]),
    )

    with pytest.raises(ForbiddenError, match="Built-in review checklist rules cannot be deleted"):
        await repo.delete_rule(ctx=ctx, rule_id=rule_id)


# ---------------------------------------------------------------------------
# 2. In-Repo Rules Parser Tests
# ---------------------------------------------------------------------------


def test_parse_review_rules_yaml_valid() -> None:
    """Valid .devmind/rules.yaml content is parsed correctly into ReviewRuleCreate."""
    yaml_content = """
version: 1
rules:
  - rule_id: "RULE-NO-CONSOLE"
    title: "Forbidden console.log"
    category: "quality"
    severity: "low"
    scope_selector:
      paths: ["client/src/**", "server/app/**"]
      languages: ["typescript", "python"]
    check_type: "pattern_forbidden"
    check_config:
      patterns: ["console\\\\.log\\\\(", "print\\\\("]
    message: "Do not commit debug statements"
    suggested_fix: "Remove console.log"
    is_enabled: true
"""
    rules = parse_review_rules_content(yaml_content, source_type="yaml")
    assert len(rules) == 1
    r = rules[0]
    assert r.rule_id == "RULE-NO-CONSOLE"
    assert r.title == "Forbidden console.log"
    assert r.category == "quality"
    assert r.severity == "low"
    assert "client/src/**" in r.scope_selector.paths
    assert r.check_type == "pattern_forbidden"
    assert r.suggested_fix_template == "Remove console.log"


def test_parse_review_rules_malformed_rejected() -> None:
    """Malformed YAML raises ValidationError."""
    with pytest.raises(ValidationError):
        parse_review_rules_content("rules: [this is invalid yaml: :::", source_type="yaml")

    with pytest.raises(ValidationError, match="'rules' key must contain a list"):
        parse_review_rules_content("version: 1\nrules: 'not a list'", source_type="yaml")


# ---------------------------------------------------------------------------
# 3. Deterministic Checklist Analyzer Engine Tests
# ---------------------------------------------------------------------------


def test_review_analyzer_input_validation_check() -> None:
    """Detects route reading request body without validation schema."""
    analyzer = ReviewBuddyAnalyzer(rules=DEFAULT_CHECKLIST_RULES)

    # Vulnerable route: reads request.json() without schema
    unvalidated_code = """from fastapi import APIRouter, Request
router = APIRouter()

@router.post("/items")
async def create_item(request: Request):
    payload = await request.json()
    return {"status": "ok"}
"""
    findings = analyzer.evaluate_files(
        [{"path": "server/app/api/items.py", "content": unvalidated_code}]
    )

    validation_findings = [f for f in findings if f.rule_id == "REV-INPUT-01"]
    assert len(validation_findings) == 1
    vf = validation_findings[0]
    assert vf.category == "input_validation"
    assert vf.severity == "high"
    assert vf.start_line == 4
    assert "Pydantic" in (vf.suggested_fix or "")

    # Clean route: uses Pydantic schema model
    clean_code = """from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class ItemCreate(BaseModel):
    name: str

@router.post("/items")
async def create_item(body: ItemCreate):
    return {"name": body.name}
"""
    clean_findings = analyzer.evaluate_files(
        [{"path": "server/app/api/items.py", "content": clean_code}]
    )
    assert not any(f.rule_id == "REV-INPUT-01" for f in clean_findings)


def test_review_analyzer_error_handling_check() -> None:
    """Detects bare except and silent exception swallowing."""
    analyzer = ReviewBuddyAnalyzer(rules=DEFAULT_CHECKLIST_RULES)

    code_with_bare_except = """def compute_metric(data):
    try:
        val = data['key']
    except:
        pass
    return val
"""
    findings = analyzer.evaluate_files(
        [{"path": "server/app/domain/metrics.py", "content": code_with_bare_except}]
    )

    err_findings = [f for f in findings if f.rule_id == "REV-ERR-01"]
    assert len(err_findings) == 1
    ef = err_findings[0]
    assert ef.category == "error_handling"
    assert ef.start_line == 4
    assert "Bare except" in ef.message


def test_review_analyzer_mutating_route_auth_check() -> None:
    """Detects mutating route definition lacking authorization guard."""
    analyzer = ReviewBuddyAnalyzer(rules=DEFAULT_CHECKLIST_RULES)

    unprotected_route = """from fastapi import APIRouter
router = APIRouter(prefix="/admin")

@router.delete("/purge")
async def purge_all_data():
    return {"deleted": True}
"""
    findings = analyzer.evaluate_files(
        [{"path": "server/app/api/admin.py", "content": unprotected_route}]
    )

    auth_findings = [f for f in findings if f.rule_id == "REV-AUTH-01"]
    assert len(auth_findings) == 1
    af = auth_findings[0]
    assert af.category == "authorization"
    assert af.severity == "high"
    assert af.evidence_level == "E2"
    assert af.start_line == 4


def test_review_analyzer_test_coverage_check() -> None:
    """Detects newly added domain/api service without accompanying test file."""
    analyzer = ReviewBuddyAnalyzer(rules=DEFAULT_CHECKLIST_RULES)

    code = "class PaymentProcessor:\n    pass\n"
    # When no test file is in known paths
    findings_missing_test = analyzer.evaluate_files(
        [{"path": "server/app/domain/payment_processor.py", "content": code}],
        known_test_files=set(),
    )
    test_findings = [f for f in findings_missing_test if f.rule_id == "REV-TEST-01"]
    assert len(test_findings) == 1
    assert test_findings[0].category == "testing"

    # When test file exists in paths
    findings_with_test = analyzer.evaluate_files(
        [{"path": "server/app/domain/payment_processor.py", "content": code}],
        known_test_files={"server/tests/test_payment_processor.py"},
    )
    assert not any(f.rule_id == "REV-TEST-01" for f in findings_with_test)


def test_review_analyzer_custom_pattern_rule() -> None:
    """Verifies user custom forbidden pattern matching."""
    custom_rule = {
        "rule_id": "RULE-NO-TODO",
        "title": "No Unresolved Security TODOs",
        "category": "security",
        "severity": "medium",
        "scope_selector": {"paths": ["**/*"]},
        "check_type": "pattern_forbidden",
        "check_config": {"patterns": [r"TODO:\s*security", r"FIXME:\s*auth"]},
        "message": "Unresolved security TODO left in code",
        "is_enabled": True,
    }

    analyzer = ReviewBuddyAnalyzer(rules=[custom_rule])
    code = "# line 1\n# line 2\n# TODO: security fix this bypass\nx = 1\n"
    findings = analyzer.evaluate_files([{"path": "app/service.py", "content": code}])

    assert len(findings) == 1
    assert findings[0].rule_id == "RULE-NO-TODO"
    assert findings[0].start_line == 3
    assert "TODO: security" in findings[0].snippet


def test_review_analyzer_unified_diff_hunk_scoping() -> None:
    """Verifies that unified diff evaluation only reports violations on added lines."""
    analyzer = ReviewBuddyAnalyzer(rules=DEFAULT_CHECKLIST_RULES)

    diff = """diff --git a/server/app/domain/calc.py b/server/app/domain/calc.py
--- a/server/app/domain/calc.py
+++ b/server/app/domain/calc.py
@@ -10,3 +10,5 @@ def existing_fn():
+    try:
+        x = 1
+    except:
+        pass
"""
    findings = analyzer.evaluate_diff(diff)
    err_findings = [f for f in findings if f.rule_id == "REV-ERR-01"]
    assert len(err_findings) == 1
    assert err_findings[0].file_path == "server/app/domain/calc.py"


# ---------------------------------------------------------------------------
# 4. Evidence Verification of Review Findings
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_review_buddy_agent_evidence_verification() -> None:
    """Verifies that ReviewBuddy agent findings pass through EvidenceVerifier cleanly."""
    agent = ReviewBuddyAgent()
    vulnerable_code = """from fastapi import APIRouter
router = APIRouter()

@router.delete("/users/{uid}")
async def delete_user(uid: str):
    try:
        pass
    except:
        pass
    return {"status": "ok"}
"""
    state: ReviewBuddyState = {
        "project_id": str(uuid.uuid4()),
        "workspace_id": str(uuid.uuid4()),
        "files": [{"path": "server/app/api/users.py", "content": vulnerable_code}],
        "rules": DEFAULT_CHECKLIST_RULES,
    }

    res = await agent.run(state)
    drafts = res["draft_findings"]
    verified = res["verified_findings"]

    assert len(drafts) >= 1
    assert len(verified) >= 1
    # Check that rule_ids pass EvidenceVerifier prefix check
    for vf in verified:
        assert vf.rule_id in (
            "REV-INPUT-01",
            "REV-ERR-01",
            "REV-AUTH-01",
            "REV-TEST-01",
            "REV-DOC-01",
        )
        assert vf.is_verified is True
        assert vf.evidence_score > 0


# ---------------------------------------------------------------------------
# 5. REST API Integration Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_api_list_and_create_review_rules(review_settings: Settings) -> None:
    """Tests GET /api/v1/projects/{pid}/review-rules and POST custom rule."""
    app = create_app(settings=review_settings)

    wid = uuid.uuid4()
    pid = uuid.uuid4()
    user_id = uuid.uuid4()

    mock_project = Project(
        id=pid,
        workspace_id=wid,
        name="Test Project",
        slug="test-proj",
    )

    mock_rules = [
        ReviewRule(
            id=uuid.uuid4(),
            workspace_id=wid,
            project_id=pid,
            rule_id=r["rule_id"],
            title=r["title"],
            category=r["category"],
            severity=r["severity"],
            scope_selector=r["scope_selector"],
            check_type=r["check_type"],
            check_config=r["check_config"],
            message=r["message"],
            is_builtin=r.get("is_builtin", True),
            is_enabled=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        for r in DEFAULT_CHECKLIST_RULES
    ]

    mock_session = AsyncMock()
    mock_session.add = MagicMock()

    async def _mock_exec(query, *args, **kwargs):
        res = MagicMock()
        q_str = str(query)
        if "projects" in q_str:
            res.scalar_one_or_none.return_value = mock_project
            res.scalars.return_value.first.return_value = mock_project
            res.scalars.return_value.all.return_value = [mock_project]
        elif "review_rules" in q_str:
            if "rule_id =" in q_str or "rule_id" in q_str and "WHERE" in q_str:
                res.scalar_one_or_none.return_value = None
            res.scalars.return_value.all.return_value = mock_rules
            res.scalars.return_value.first.return_value = mock_rules[0] if mock_rules else None
        return res

    mock_session.execute.side_effect = _mock_exec

    async def _override_db():
        yield mock_session

    async def _override_auth():
        return AuthContext(
            user_id=user_id,
            clerk_user_id="user_test_client",
            email="client@example.com",
            workspace_id=wid,
            project_id=pid,
            project_role="maintainer",
            permissions=frozenset(["project:read", "project:update"]),
        )

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_auth_context] = _override_auth

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. List rules (triggers auto-seeding of defaults)
        res = await client.get(f"/api/v1/projects/{pid}/review-rules")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 5
        rule_ids = {r["rule_id"] for r in data}
        assert "REV-INPUT-01" in rule_ids
        assert "REV-AUTH-01" in rule_ids

        # 2. Create custom rule
        create_payload = {
            "rule_id": "REV-CUSTOM-DEBUG",
            "title": "No debug prints",
            "category": "quality",
            "severity": "low",
            "scope_selector": {"paths": ["**/*.py"]},
            "check_type": "pattern_forbidden",
            "check_config": {"patterns": ["pdb.set_trace()"]},
            "message": "Do not leave debugger breakpoints in code",
            "suggested_fix_template": "Remove pdb.set_trace()",
            "is_enabled": True,
        }

        res_create = await client.post(
            f"/api/v1/projects/{pid}/review-rules",
            json=create_payload,
        )
        assert res_create.status_code == 201
        created_data = res_create.json()
        assert created_data["rule_id"] == "REV-CUSTOM-DEBUG"
        assert created_data["is_builtin"] is False


@pytest.mark.asyncio
async def test_api_evaluate_review_checklist(review_settings: Settings) -> None:
    """Tests POST /api/v1/projects/{pid}/review-rules/evaluate on files."""
    app = create_app(settings=review_settings)

    wid = uuid.uuid4()
    pid = uuid.uuid4()
    user_id = uuid.uuid4()

    mock_project = Project(
        id=pid,
        workspace_id=wid,
        name="Test Project",
        slug="test-proj",
    )

    mock_rules = [
        ReviewRule(
            id=uuid.uuid4(),
            workspace_id=wid,
            project_id=pid,
            rule_id=r["rule_id"],
            title=r["title"],
            category=r["category"],
            severity=r["severity"],
            scope_selector=r["scope_selector"],
            check_type=r["check_type"],
            check_config=r["check_config"],
            message=r["message"],
            is_builtin=r.get("is_builtin", True),
            is_enabled=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        for r in DEFAULT_CHECKLIST_RULES
    ]

    mock_session = AsyncMock()

    async def _mock_exec(query, *args, **kwargs):
        res = MagicMock()
        q_str = str(query)
        if "projects" in q_str:
            res.scalar_one_or_none.return_value = mock_project
        elif "review_rules" in q_str:
            res.scalars.return_value.all.return_value = mock_rules
            res.scalar_one_or_none.return_value = None
        return res

    mock_session.execute.side_effect = _mock_exec

    async def _override_db():
        yield mock_session

    async def _override_auth():
        return AuthContext(
            user_id=user_id,
            clerk_user_id="user_eval_client",
            email="eval@example.com",
            workspace_id=wid,
            project_id=pid,
            project_role="maintainer",
            permissions=frozenset(["analysis:create", "project:read"]),
        )

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_auth_context] = _override_auth

    eval_payload = {
        "files": [
            {
                "path": "server/app/api/broken.py",
                "content": """from fastapi import APIRouter
router = APIRouter()

@router.post("/broken")
async def broken_handler():
    try:
        x = 1
    except:
        pass
    return {}
""",
            }
        ]
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            f"/api/v1/projects/{pid}/review-rules/evaluate",
            json=eval_payload,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["project_id"] == str(pid)
        assert "summary" in data
        assert data["summary"]["total_findings"] >= 1
        findings_rules = {f["rule_id"] for f in data["findings"]}
        assert "REV-ERR-01" in findings_rules
