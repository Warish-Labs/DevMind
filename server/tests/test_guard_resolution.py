"""Unit tests for deterministic guard resolution and structural route check (docs/05 §6.3).

Tests:
1. Framework detection for FastAPI, Express, Next.js, and unknown frameworks.
2. Route enumeration from defines_route edges, route_handler symbols, and server actions.
3. Route sensitivity classification (public, authenticated, sensitive, and custom config).
4. Guard resolution across middleware, dependencies, decorators, and multi-depth callees.
5. Incomplete call paths tracking unresolved dynamic dependencies.
6. Deterministic E2 confirmation with required analysis_scope formatting.
7. E1 fallback when call path is incomplete.
8. Proper protection and public exemption handling.
9. Unsupported frameworks recorded as 'not analyzed' (never reported as 'safe').
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.analysis.guard_resolution import (
    RULE_MISSING_AUTH,
    RULE_MISSING_ROLE_CHECK,
    ProjectSecurityConfig,
    RouteFramework,
    RouteGuardAnalyzer,
    RouteSensitivity,
    compute_fingerprint,
)
from app.core.auth_context import SystemContext


def test_framework_detection():
    analyzer = RouteGuardAnalyzer()

    # FastAPI via tag
    sym_fastapi = {
        "id": uuid4(),
        "framework_tags": ["fastapi", "route"],
        "metadata": {},
        "kind": "function",
    }
    assert analyzer.detect_framework(sym_fastapi, "app/main.py") == RouteFramework.FASTAPI

    # Express via tag
    sym_express = {
        "id": uuid4(),
        "framework_tags": ["express"],
        "metadata": {},
        "kind": "function",
    }
    assert analyzer.detect_framework(sym_express, "src/server.ts") == RouteFramework.EXPRESS

    # Next.js via route.ts path
    sym_next = {
        "id": uuid4(),
        "framework_tags": [],
        "metadata": {},
        "kind": "route_handler",
    }
    assert analyzer.detect_framework(sym_next, "app/api/users/route.ts") == RouteFramework.NEXTJS

    # Next.js server action
    sym_action = {
        "id": uuid4(),
        "framework_tags": [],
        "metadata": {},
        "kind": "server_action",
    }
    assert analyzer.detect_framework(sym_action, "app/actions.ts") == RouteFramework.NEXTJS

    # Unknown
    sym_unknown = {
        "id": uuid4(),
        "framework_tags": ["django"],
        "metadata": {"framework": "django"},
        "kind": "function",
    }
    assert analyzer.detect_framework(sym_unknown, "myproject/views.py") == RouteFramework.UNKNOWN


def test_route_sensitivity_classification():
    config = ProjectSecurityConfig(
        public_routes=[r"^/custom-public$"],
        sensitive_routes=[r"^/custom-sensitive$"],
    )
    analyzer = RouteGuardAnalyzer(config=config)

    # Public defaults
    assert analyzer.classify_sensitivity(
        analyzer.enumerate_routes(
            [{"id": uuid4(), "symbol_key": "s1", "name": "health", "metadata": {"http_path": "/healthz", "http_method": "GET"}}],
            [],
        )[0]
    ) == RouteSensitivity.PUBLIC

    assert analyzer.classify_sensitivity(
        analyzer.enumerate_routes(
            [{"id": uuid4(), "symbol_key": "s2", "name": "docs", "metadata": {"http_path": "/docs", "http_method": "GET"}}],
            [],
        )[0]
    ) == RouteSensitivity.PUBLIC

    # Custom public
    assert analyzer.classify_sensitivity(
        analyzer.enumerate_routes(
            [{"id": uuid4(), "symbol_key": "s3", "name": "custom", "metadata": {"http_path": "/custom-public", "http_method": "GET"}}],
            [],
        )[0]
    ) == RouteSensitivity.PUBLIC

    # Sensitive admin defaults
    assert analyzer.classify_sensitivity(
        analyzer.enumerate_routes(
            [{"id": uuid4(), "symbol_key": "s4", "name": "admin_users", "metadata": {"http_path": "/admin/users", "http_method": "GET"}}],
            [],
        )[0]
    ) == RouteSensitivity.SENSITIVE

    # Mutating POST on resource
    assert analyzer.classify_sensitivity(
        analyzer.enumerate_routes(
            [{"id": uuid4(), "symbol_key": "s5", "name": "delete_user", "metadata": {"http_path": "/api/v1/users/1", "http_method": "DELETE"}}],
            [],
        )[0]
    ) == RouteSensitivity.SENSITIVE

    # Custom sensitive
    assert analyzer.classify_sensitivity(
        analyzer.enumerate_routes(
            [{"id": uuid4(), "symbol_key": "s6", "name": "custom_sens", "metadata": {"http_path": "/custom-sensitive", "http_method": "GET"}}],
            [],
        )[0]
    ) == RouteSensitivity.SENSITIVE

    # Authenticated default
    assert analyzer.classify_sensitivity(
        analyzer.enumerate_routes(
            [{"id": uuid4(), "symbol_key": "s7", "name": "get_user", "metadata": {"http_path": "/api/v1/users/me", "http_method": "GET"}}],
            [],
        )[0]
    ) == RouteSensitivity.AUTHENTICATED


def test_route_enumeration_from_defines_route():
    analyzer = RouteGuardAnalyzer()
    sym_id = uuid4()
    symbols = [
        {
            "id": sym_id,
            "symbol_key": "app.routes.users:list_users",
            "name": "list_users",
            "kind": "function",
            "start_line": 20,
            "end_line": 35,
            "framework_tags": ["fastapi"],
            "metadata": {"path": "app/routes/users.py"},
        }
    ]
    relationships = [
        {
            "from_symbol_id": sym_id,
            "to_symbol_id": None,
            "to_external": "GET /api/v1/users",
            "kind": "defines_route",
            "resolution": "resolved",
        }
    ]

    routes = analyzer.enumerate_routes(symbols, relationships)
    assert len(routes) == 1
    route = routes[0]
    assert route.symbol_id == sym_id
    assert route.http_method == "GET"
    assert route.http_route == "/api/v1/users"
    assert route.framework == RouteFramework.FASTAPI
    assert route.file_path == "app/routes/users.py"
    assert route.start_line == 20
    assert route.end_line == 35


def test_guard_resolution_and_e2_missing_role_check():
    """Test deterministic E2 confirmation for administrative route with authn but missing role check."""
    analyzer = RouteGuardAnalyzer()

    route_id = uuid4()
    guard_auth_id = uuid4()
    callee_id = uuid4()

    symbols = [
        {
            "id": route_id,
            "symbol_key": "admin_route",
            "name": "list_admin_users",
            "kind": "route_handler",
            "start_line": 42,
            "end_line": 58,
            "framework_tags": ["fastapi"],
            "metadata": {
                "path": "backend/app/routes/admin.py",
                "http_method": "GET",
                "http_path": "/admin/users",
            },
        },
        {
            "id": guard_auth_id,
            "symbol_key": "get_current_user",
            "name": "get_current_user",
            "kind": "function",
            "start_line": 10,
            "end_line": 20,
            "framework_tags": ["fastapi"],
            "metadata": {},
        },
        {
            "id": callee_id,
            "symbol_key": "fetch_users_query",
            "name": "fetch_users_query",
            "kind": "function",
            "start_line": 60,
            "end_line": 70,
            "framework_tags": ["fastapi"],
            "metadata": {},
        },
    ]

    relationships = [
        {
            "from_symbol_id": route_id,
            "to_symbol_id": guard_auth_id,
            "kind": "guarded_by",
            "resolution": "resolved",
        },
        {
            "from_symbol_id": route_id,
            "to_symbol_id": callee_id,
            "kind": "calls",
            "resolution": "resolved",
        },
    ]

    result = analyzer.analyze_routes(symbols, relationships)

    assert result.total_routes_discovered == 1
    assert result.total_analyzed == 1
    assert result.missing_authz_count == 1
    assert len(result.draft_findings) == 1

    finding = result.draft_findings[0]
    assert finding.rule_id == RULE_MISSING_ROLE_CHECK
    assert finding.category == "authorization"
    assert finding.evidence_level == "E2"
    assert finding.confidence == "high"
    assert finding.severity == "high"
    assert finding.canonical_identifier == "GET /admin/users"
    assert "no role check" in finding.title.lower()

    # Verify analysis_scope per docs/03 §12.1
    scope_str = finding.evidence_details["analysis_scope"]
    assert "handler and 2 resolved callees" in scope_str
    assert "0 unresolved dependencies" in scope_str
    assert finding.evidence_details["authentication"] == "get_current_user"
    assert finding.evidence_details["authorization"] == "none found"


def test_guard_resolution_and_e2_missing_authentication():
    """Test deterministic E2 confirmation for sensitive route with no authentication at all."""
    analyzer = RouteGuardAnalyzer()
    route_id = uuid4()
    callee_id = uuid4()

    symbols = [
        {
            "id": route_id,
            "symbol_key": "reset_route",
            "name": "reset_system_data",
            "kind": "route_handler",
            "start_line": 15,
            "end_line": 30,
            "framework_tags": ["fastapi"],
            "metadata": {
                "path": "app/routes/admin.py",
                "http_method": "DELETE",
                "http_path": "/admin/system/reset",
            },
        },
        {
            "id": callee_id,
            "symbol_key": "db_reset",
            "name": "db_reset",
            "kind": "function",
            "start_line": 100,
            "end_line": 110,
            "metadata": {},
        },
    ]
    relationships = [
        {
            "from_symbol_id": route_id,
            "to_symbol_id": callee_id,
            "kind": "calls",
            "resolution": "resolved",
        }
    ]

    result = analyzer.analyze_routes(symbols, relationships)

    assert result.missing_auth_count == 1
    assert len(result.draft_findings) == 1

    finding = result.draft_findings[0]
    assert finding.rule_id == RULE_MISSING_AUTH
    assert finding.category == "authentication"
    assert finding.evidence_level == "E2"
    assert finding.severity == "critical"  # DELETE on admin is critical
    assert finding.evidence_details["authentication"] == "none found"
    assert finding.evidence_details["authorization"] == "none found"
    assert "0 unresolved dependencies" in finding.evidence_details["analysis_scope"]


def test_e1_fallback_on_incomplete_call_path():
    """Test that unresolved dependencies downgrade evidence from E2 to E1."""
    analyzer = RouteGuardAnalyzer()
    route_id = uuid4()
    guard_id = uuid4()

    symbols = [
        {
            "id": route_id,
            "symbol_key": "admin_route",
            "name": "update_settings",
            "kind": "route_handler",
            "start_line": 1,
            "end_line": 20,
            "framework_tags": ["express"],
            "metadata": {
                "path": "src/routes/admin.ts",
                "http_method": "POST",
                "http_path": "/admin/settings",
            },
        },
        {
            "id": guard_id,
            "symbol_key": "require_auth",
            "name": "requireAuth",
            "kind": "function",
            "start_line": 5,
            "end_line": 15,
            "metadata": {},
        },
    ]

    # Includes an unresolved dynamic dependency
    relationships = [
        {
            "from_symbol_id": route_id,
            "to_symbol_id": guard_id,
            "kind": "guarded_by",
            "resolution": "resolved",
        },
        {
            "from_symbol_id": route_id,
            "to_symbol_id": None,
            "to_external": "dynamic_dispatcher(req)",
            "kind": "calls",
            "resolution": "unresolved",
        },
    ]

    result = analyzer.analyze_routes(symbols, relationships)

    assert result.missing_authz_count == 1
    finding = result.draft_findings[0]
    # E1 due to unresolved dependency
    assert finding.evidence_level == "E1"
    assert finding.confidence == "medium"
    assert finding.severity == "medium"
    assert "unresolved: 1 dynamic dependency" in finding.evidence_details["analysis_scope"]


def test_protected_route_with_authn_and_authz():
    """Test that a route with both authentication and role check is marked protected."""
    analyzer = RouteGuardAnalyzer()
    route_id = uuid4()
    auth_guard_id = uuid4()
    role_guard_id = uuid4()

    symbols = [
        {
            "id": route_id,
            "symbol_key": "admin_delete_user",
            "name": "delete_admin_user",
            "kind": "route_handler",
            "start_line": 30,
            "end_line": 45,
            "framework_tags": ["fastapi"],
            "metadata": {
                "path": "app/routes/admin.py",
                "http_method": "DELETE",
                "http_path": "/admin/users/{user_id}",
            },
        },
        {
            "id": auth_guard_id,
            "symbol_key": "get_current_user",
            "name": "get_current_user",
            "kind": "function",
            "start_line": 1,
            "end_line": 10,
            "metadata": {},
        },
        {
            "id": role_guard_id,
            "symbol_key": "require_admin",
            "name": "require_admin",
            "kind": "function",
            "start_line": 12,
            "end_line": 25,
            "metadata": {},
        },
    ]

    relationships = [
        {
            "from_symbol_id": route_id,
            "to_symbol_id": auth_guard_id,
            "kind": "guarded_by",
            "resolution": "resolved",
        },
        {
            "from_symbol_id": route_id,
            "to_symbol_id": role_guard_id,
            "kind": "guarded_by",
            "resolution": "resolved",
        },
    ]

    result = analyzer.analyze_routes(symbols, relationships)

    assert result.total_analyzed == 1
    assert result.protected_count == 1
    assert result.missing_auth_count == 0
    assert result.missing_authz_count == 0
    assert len(result.draft_findings) == 0


def test_public_exempt_route():
    """Test that public endpoints are exempt and produce no findings."""
    analyzer = RouteGuardAnalyzer()
    route_id = uuid4()
    symbols = [
        {
            "id": route_id,
            "symbol_key": "healthz_endpoint",
            "name": "health_check",
            "kind": "route_handler",
            "start_line": 1,
            "end_line": 5,
            "framework_tags": ["fastapi"],
            "metadata": {
                "path": "app/main.py",
                "http_method": "GET",
                "http_path": "/healthz",
            },
        }
    ]

    result = analyzer.analyze_routes(symbols, [])
    assert result.public_exempt_count == 1
    assert len(result.draft_findings) == 0


def test_unsupported_framework_recorded_as_not_analyzed():
    """Test that unsupported frameworks yield not_analyzed results and are not reported as safe."""
    analyzer = RouteGuardAnalyzer()
    route_id = uuid4()
    symbols = [
        {
            "id": route_id,
            "symbol_key": "rails_controller_action",
            "name": "show",
            "kind": "function",
            "start_line": 10,
            "end_line": 25,
            "framework_tags": ["ruby", "rails"],
            "metadata": {
                "path": "app/controllers/users_controller.rb",
                "http_method": "GET",
                "http_path": "/users/:id",
                "framework": "rails",
            },
        }
    ]
    relationships = [
        {
            "from_symbol_id": route_id,
            "to_symbol_id": None,
            "to_external": "GET /users/:id",
            "kind": "defines_route",
            "resolution": "resolved",
        }
    ]

    result = analyzer.analyze_routes(symbols, relationships)
    assert result.unsupported_count == 1
    assert result.protected_count == 0
    assert len(result.unsupported_routes) == 1
    assert "Unsupported framework" in result.unsupported_routes[0]["reason"]


def test_fingerprint_generation():
    fp1 = compute_fingerprint("devmind.authz.missing_role_check", "app/routes/admin.py", "GET /admin/users")
    fp2 = compute_fingerprint("devmind.authz.missing_role_check", "app/routes/admin.py", "GET /admin/users")
    fp3 = compute_fingerprint("devmind.authz.missing_role_check", "app/routes/admin.py", "POST /admin/users")

    assert fp1 == fp2
    assert fp1 != fp3
    assert len(fp1) == 64


@pytest.mark.asyncio
async def test_analyze_project_database_integration():
    """Test analyze_project domain method with mock session & repository."""
    mock_session = AsyncMock()
    analyzer = RouteGuardAnalyzer()
    project_id = uuid4()
    ctx = SystemContext(reason="test")

    sym_id = uuid4()
    sym_mock = MagicMock()
    sym_mock.id = sym_id
    sym_mock.symbol_key = "fastapi_health"
    sym_mock.name = "health"
    sym_mock.kind = "route_handler"
    sym_mock.start_line = 1
    sym_mock.end_line = 5
    sym_mock.framework_tags = ["fastapi"]
    sym_mock.metadata = {"path": "app/main.py", "http_method": "GET", "http_path": "/health"}
    sym_mock.file_version_id = uuid4()
    fake_symbols = [sym_mock]

    # Patch repository list calls
    with (
        pytest.MonkeyPatch.context() as mp,
    ):
        mp.setattr(
            "app.persistence.repositories.brain_repo.BrainRepository.list_current_symbols",
            AsyncMock(return_value=fake_symbols),
        )
        mp.setattr(
            "app.persistence.repositories.brain_repo.BrainRepository.list_relationships",
            AsyncMock(return_value=[]),
        )

        res = await analyzer.analyze_project(mock_session, project_id, ctx)
        assert res.total_routes_discovered == 1
        assert res.public_exempt_count == 1
