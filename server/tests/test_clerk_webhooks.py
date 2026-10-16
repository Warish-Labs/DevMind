"""Unit and integration tests for Clerk webhook receiver and Svix signature verification."""

import base64
import hashlib
import hmac
import json
import time
import uuid
from unittest.mock import AsyncMock

from starlette.testclient import TestClient

from app.core.settings import Settings
from app.domain.auth import get_db_session
from app.integrations.clerk_webhook import verify_svix_signature
from app.main import create_app


def generate_svix_headers(
    secret: str,
    body: bytes,
    msg_id: str | None = None,
    timestamp: float | None = None,
) -> dict[str, str]:
    """Helper to generate valid Svix signature headers for testing."""
    msg_id = msg_id or f"msg_{uuid.uuid4().hex[:12]}"
    ts = str(int(timestamp if timestamp is not None else time.time()))

    if secret.startswith("whsec_"):
        key = base64.b64decode(secret[6:])
    else:
        key = secret.encode("utf-8")

    to_sign = f"{msg_id}.{ts}.".encode() + body
    computed = base64.b64encode(hmac.new(key, to_sign, hashlib.sha256).digest()).decode()
    return {
        "svix-id": msg_id,
        "svix-timestamp": ts,
        "svix-signature": f"v1,{computed}",
    }


def test_svix_signature_verification_algorithm() -> None:
    """Verify Svix signature verification logic directly."""
    raw_secret_bytes = b"0123456789abcdef0123456789abcdef"
    whsec_secret = f"whsec_{base64.b64encode(raw_secret_bytes).decode()}"
    body = b'{"type":"user.created","data":{"id":"user_test_1"}}'
    msg_id = "msg_12345"
    now = time.time()

    headers = generate_svix_headers(whsec_secret, body, msg_id=msg_id, timestamp=now)

    # 1. Valid signature
    assert verify_svix_signature(
        secret=whsec_secret,
        svix_id=headers["svix-id"],
        svix_timestamp=headers["svix-timestamp"],
        svix_signature=headers["svix-signature"],
        body=body,
    )

    # 2. Tampered body
    assert not verify_svix_signature(
        secret=whsec_secret,
        svix_id=headers["svix-id"],
        svix_timestamp=headers["svix-timestamp"],
        svix_signature=headers["svix-signature"],
        body=b'{"type":"user.created","data":{"id":"user_tampered"}}',
    )

    # 3. Wrong secret
    other_secret = f"whsec_{base64.b64encode(b'wrong_secret_bytes_123456789012').decode()}"
    assert not verify_svix_signature(
        secret=other_secret,
        svix_id=headers["svix-id"],
        svix_timestamp=headers["svix-timestamp"],
        svix_signature=headers["svix-signature"],
        body=body,
    )

    # 4. Expired timestamp (> 300s old)
    old_ts = now - 305
    old_headers = generate_svix_headers(whsec_secret, body, msg_id=msg_id, timestamp=old_ts)
    assert not verify_svix_signature(
        secret=whsec_secret,
        svix_id=old_headers["svix-id"],
        svix_timestamp=old_headers["svix-timestamp"],
        svix_signature=old_headers["svix-signature"],
        body=body,
    )


def test_clerk_webhook_missing_headers_returns_401() -> None:
    """Verify missing Svix headers return RFC 9457 Problem Details (401)."""
    raw_secret_bytes = b"0123456789abcdef0123456789abcdef"
    secret = f"whsec_{base64.b64encode(raw_secret_bytes).decode()}"
    settings = Settings(
        clerk_webhook_secret=secret,
        redis_key_prefix=f"test_{uuid.uuid4().hex[:6]}:",
    )
    app = create_app(settings=settings)

    with TestClient(app) as client:
        # No headers
        res = client.post("/api/v1/webhooks/clerk", json={"type": "user.created"})
        assert res.status_code == 401
        data = res.json()
        assert data["code"] == "auth.unauthenticated"
        assert "Missing required Svix webhook headers" in data["detail"]


def test_clerk_webhook_invalid_signature_returns_401() -> None:
    """Verify invalid signature returns RFC 9457 Problem Details (401)."""
    raw_secret_bytes = b"0123456789abcdef0123456789abcdef"
    secret = f"whsec_{base64.b64encode(raw_secret_bytes).decode()}"
    settings = Settings(
        clerk_webhook_secret=secret,
        redis_key_prefix=f"test_{uuid.uuid4().hex[:6]}:",
    )
    app = create_app(settings=settings)

    with TestClient(app) as client:
        headers = {
            "svix-id": "msg_bad",
            "svix-timestamp": str(int(time.time())),
            "svix-signature": "v1,invalid_base64_sig==",
        }
        res = client.post("/api/v1/webhooks/clerk", json={"type": "user.created"}, headers=headers)
        assert res.status_code == 401
        data = res.json()
        assert data["code"] == "auth.unauthenticated"


def test_clerk_webhook_deduplication() -> None:
    """Verify that repeated webhook deliveries with the same svix-id are ignored."""
    raw_secret_bytes = b"0123456789abcdef0123456789abcdef"
    secret = f"whsec_{base64.b64encode(raw_secret_bytes).decode()}"
    settings = Settings(
        clerk_webhook_secret=secret,
        redis_key_prefix=f"test_{uuid.uuid4().hex[:6]}:",
    )
    app = create_app(settings=settings)

    # Mock DB session commit
    mock_session = AsyncMock()
    app.dependency_overrides[get_db_session] = lambda: mock_session

    body = json.dumps({"type": "ping", "data": {}}).encode()
    msg_id = f"msg_{uuid.uuid4().hex}"
    headers = generate_svix_headers(secret, body, msg_id=msg_id)

    with TestClient(app) as client:
        # First delivery: processed
        res1 = client.post("/api/v1/webhooks/clerk", content=body, headers=headers)
        assert res1.status_code == 200
        assert res1.json()["status"] == "processed"

        # Second delivery with SAME svix-id: ignored duplicate
        res2 = client.post("/api/v1/webhooks/clerk", content=body, headers=headers)
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["status"] == "ignored"
        assert data2["reason"] == "duplicate_delivery"


def test_clerk_webhook_user_created_sync() -> None:
    """Verify user.created event syncs user and provisions personal workspace."""
    raw_secret_bytes = b"0123456789abcdef0123456789abcdef"
    secret = f"whsec_{base64.b64encode(raw_secret_bytes).decode()}"
    settings = Settings(
        clerk_webhook_secret=secret,
        redis_key_prefix=f"test_{uuid.uuid4().hex[:6]}:",
    )
    app = create_app(settings=settings)

    # Mock DB session & repositories in service
    mock_session = AsyncMock()
    app.dependency_overrides[get_db_session] = lambda: mock_session

    payload = {
        "type": "user.created",
        "data": {
            "id": "user_2test123",
            "email_addresses": [{"id": "idn_1", "email_address": "alice@example.com"}],
            "primary_email_address_id": "idn_1",
            "first_name": "Alice",
            "last_name": "Liddell",
        },
    }
    body = json.dumps(payload).encode()
    headers = generate_svix_headers(secret, body)

    with TestClient(app) as client:
        # Mocking user_repo and workspace_repo inside ClerkWebhookService
        from unittest.mock import patch

        from app.persistence.models.user import User

        created_user = User(
            id=uuid.uuid4(),
            clerk_user_id="user_2test123",
            email="alice@example.com",
            display_name="Alice Liddell",
        )

        with (
            patch(
                "app.domain.webhooks.service.UserRepository.get_by_clerk_user_id",
                new_callable=AsyncMock,
            ) as mock_get_user,
            patch(
                "app.domain.webhooks.service.UserRepository.create", new_callable=AsyncMock
            ) as mock_create_user,
            patch(
                "app.domain.webhooks.service.WorkspaceRepository.list_for_user",
                new_callable=AsyncMock,
            ) as mock_list_ws,
            patch(
                "app.domain.webhooks.service.WorkspaceRepository.create", new_callable=AsyncMock
            ) as mock_create_ws,
            patch(
                "app.domain.webhooks.service.WorkspaceRepository.add_member", new_callable=AsyncMock
            ) as mock_add_member,
        ):
            mock_get_user.return_value = None
            mock_create_user.return_value = created_user
            mock_list_ws.return_value = []  # No workspaces yet

            mock_ws = AsyncMock()
            mock_ws.id = uuid.uuid4()
            mock_create_ws.return_value = mock_ws

            res = client.post("/api/v1/webhooks/clerk", content=body, headers=headers)
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "processed"
            assert data["event"] == "user.created"
            assert data["result"]["action"] == "user.created"

            mock_create_user.assert_awaited_once()
            mock_create_ws.assert_awaited_once()
            mock_add_member.assert_awaited_once()


def test_clerk_webhook_user_updated_sync() -> None:
    """Verify user.updated event updates existing user profile."""
    raw_secret_bytes = b"0123456789abcdef0123456789abcdef"
    secret = f"whsec_{base64.b64encode(raw_secret_bytes).decode()}"
    settings = Settings(
        clerk_webhook_secret=secret,
        redis_key_prefix=f"test_{uuid.uuid4().hex[:6]}:",
    )
    app = create_app(settings=settings)

    mock_session = AsyncMock()
    app.dependency_overrides[get_db_session] = lambda: mock_session

    payload = {
        "type": "user.updated",
        "data": {
            "id": "user_2test123",
            "email_addresses": [{"id": "idn_1", "email_address": "alice.new@example.com"}],
            "primary_email_address_id": "idn_1",
            "first_name": "Alice",
            "last_name": "Kingsleigh",
        },
    }
    body = json.dumps(payload).encode()
    headers = generate_svix_headers(secret, body)

    with TestClient(app) as client:
        from unittest.mock import patch

        from app.persistence.models.user import User

        existing_user = User(
            id=uuid.uuid4(),
            clerk_user_id="user_2test123",
            email="alice@example.com",
            display_name="Alice Liddell",
        )

        with (
            patch(
                "app.domain.webhooks.service.UserRepository.get_by_clerk_user_id",
                new_callable=AsyncMock,
            ) as mock_get_user,
            patch(
                "app.domain.webhooks.service.UserRepository.update", new_callable=AsyncMock
            ) as mock_update_user,
        ):
            mock_get_user.return_value = existing_user

            res = client.post("/api/v1/webhooks/clerk", content=body, headers=headers)
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "processed"
            assert data["event"] == "user.updated"

            mock_update_user.assert_awaited_once()


def test_clerk_webhook_user_deleted_sync() -> None:
    """Verify user.deleted event soft deletes existing user."""
    raw_secret_bytes = b"0123456789abcdef0123456789abcdef"
    secret = f"whsec_{base64.b64encode(raw_secret_bytes).decode()}"
    settings = Settings(
        clerk_webhook_secret=secret,
        redis_key_prefix=f"test_{uuid.uuid4().hex[:6]}:",
    )
    app = create_app(settings=settings)

    mock_session = AsyncMock()
    app.dependency_overrides[get_db_session] = lambda: mock_session

    payload = {
        "type": "user.deleted",
        "data": {
            "id": "user_2test123",
        },
    }
    body = json.dumps(payload).encode()
    headers = generate_svix_headers(secret, body)

    with TestClient(app) as client:
        from unittest.mock import patch

        from app.persistence.models.user import User

        existing_user = User(
            id=uuid.uuid4(),
            clerk_user_id="user_2test123",
            email="alice@example.com",
            display_name="Alice Liddell",
        )

        with (
            patch(
                "app.domain.webhooks.service.UserRepository.get_by_clerk_user_id",
                new_callable=AsyncMock,
            ) as mock_get_user,
            patch(
                "app.domain.webhooks.service.UserRepository.soft_delete", new_callable=AsyncMock
            ) as mock_delete_user,
        ):
            mock_get_user.return_value = existing_user

            res = client.post("/api/v1/webhooks/clerk", content=body, headers=headers)
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "processed"
            assert data["event"] == "user.deleted"

            mock_delete_user.assert_awaited_once()
