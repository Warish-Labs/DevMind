"""CI contract test verifying that every API route declares a permission (docs/07 §3).

A test enumerates all FastAPI routes and fails if any route lacks a declared permission.
"""

from fastapi import APIRouter
from fastapi.routing import APIRoute

from app.domain.auth import declare_permission, find_undeclared_routes
from app.main import create_app


def test_all_api_routes_declare_permission() -> None:
    """Verify that every route in the FastAPI application declares its required permission.

    docs/07 §3: Every route declares a permission; a CI test enumerates all routes
    and fails if one lacks a declared permission.
    """
    app = create_app()
    undeclared = find_undeclared_routes(app.routes)

    assert undeclared == [], (
        f"Found API routes lacking declared permissions (must declare permission or PERMISSION_PUBLIC): {undeclared}"
    )


def test_find_undeclared_routes_detects_missing_permission() -> None:
    """Verify that the scanner catches a route deliberately missing permission declaration."""
    router = APIRouter()

    @router.get("/unprotected/test/route")
    async def rogue_endpoint() -> dict[str, str]:
        return {"status": "unprotected"}

    fake_route = router.routes[0]
    assert isinstance(fake_route, APIRoute)

    undeclared = find_undeclared_routes([fake_route])
    assert len(undeclared) == 1
    assert "/unprotected/test/route" in undeclared[0]

    # Now tag it and verify it passes
    tagged_fn = declare_permission("test:permission")(rogue_endpoint)
    fake_route.endpoint = tagged_fn
    assert find_undeclared_routes([fake_route]) == []
