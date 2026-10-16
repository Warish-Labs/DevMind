"""Tests for RFC 9457 Problem Details error handling."""

from collections.abc import Iterator

import pytest
from fastapi import APIRouter
from pydantic import BaseModel
from starlette.testclient import TestClient

from app.core.errors import (
    PROBLEM_MEDIA_TYPE,
    AuthenticationError,
    ConsentRequiredError,
    ForbiddenError,
    NotFoundError,
)
from app.core.settings import Settings
from app.main import create_app

error_router = APIRouter(prefix="/test-errors")


class SamplePayload(BaseModel):
    name: str
    count: int


@error_router.get("/not-found")
def trigger_not_found() -> None:
    raise NotFoundError("Finding 0192b1c0 not found")


@error_router.get("/unauthorized")
def trigger_unauthorized() -> None:
    raise AuthenticationError("Missing Bearer token")


@error_router.get("/forbidden")
def trigger_forbidden() -> None:
    raise ForbiddenError("User is not a member of this workspace")


@error_router.get("/consent-required")
def trigger_consent() -> None:
    raise ConsentRequiredError("Analysis requires an active snippet consent record")


@error_router.post("/validate")
def trigger_validation(payload: SamplePayload) -> dict[str, str]:
    return {"status": "ok"}


@pytest.fixture
def error_client() -> Iterator[TestClient]:
    app = create_app(settings=Settings(env="test"))
    app.include_router(error_router)
    with TestClient(app=app, base_url="http://testserver") as test_client:
        yield test_client


def test_not_found_problem_details(error_client: TestClient) -> None:
    response = error_client.get("/test-errors/not-found")
    assert response.status_code == 404
    assert response.headers["content-type"] == PROBLEM_MEDIA_TYPE
    data = response.json()
    assert data["code"] == "resource.not_found"
    assert data["status"] == 404
    assert data["title"] == "Resource Not Found"
    assert "Finding 0192b1c0 not found" in data["detail"]
    assert "request_id" in data


def test_unauthorized_problem_details(error_client: TestClient) -> None:
    response = error_client.get("/test-errors/unauthorized")
    assert response.status_code == 401
    assert response.headers["content-type"] == PROBLEM_MEDIA_TYPE
    data = response.json()
    assert data["code"] == "auth.unauthenticated"
    assert data["status"] == 401


def test_forbidden_problem_details(error_client: TestClient) -> None:
    response = error_client.get("/test-errors/forbidden")
    assert response.status_code == 403
    assert response.headers["content-type"] == PROBLEM_MEDIA_TYPE
    data = response.json()
    assert data["code"] == "auth.forbidden"
    assert data["status"] == 403


def test_consent_required_problem_details(error_client: TestClient) -> None:
    response = error_client.get("/test-errors/consent-required")
    assert response.status_code == 403
    assert response.headers["content-type"] == PROBLEM_MEDIA_TYPE
    data = response.json()
    assert data["code"] == "consent.required"
    assert data["status"] == 403


def test_request_validation_failure(error_client: TestClient) -> None:
    # Send missing 'name' and invalid string for 'count'
    response = error_client.post("/test-errors/validate", json={"count": "invalid_integer"})
    assert response.status_code == 422
    assert response.headers["content-type"] == PROBLEM_MEDIA_TYPE
    data = response.json()
    assert data["code"] == "validation.failed"
    assert data["status"] == 422
    assert data["title"] == "Validation Failed"
    assert "errors" in data
    assert len(data["errors"]) >= 1
