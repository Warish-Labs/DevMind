"""Tests for RFC 9562 UUIDv7 generator and UUID validation utilities."""

import time
import uuid

from app.core.ids import generate_uuid7, is_valid_uuid


def test_uuid7_version_and_variant() -> None:
    """Verify that generated UUIDs conform strictly to RFC 9562 (version 7, RFC 4122 variant)."""
    val = generate_uuid7()
    assert isinstance(val, uuid.UUID)
    assert val.version == 7
    assert val.variant == uuid.RFC_4122


def test_uuid7_monotonicity() -> None:
    """Verify that successive UUIDv7 identifiers are temporally ordered."""
    u1 = generate_uuid7()
    time.sleep(0.002)
    u2 = generate_uuid7()
    time.sleep(0.002)
    u3 = generate_uuid7()

    assert u1 < u2 < u3


def test_is_valid_uuid() -> None:
    """Verify UUID validation helper."""
    valid_uuid = generate_uuid7()
    assert is_valid_uuid(valid_uuid) is True
    assert is_valid_uuid(str(valid_uuid)) is True
    assert is_valid_uuid("not-a-uuid") is False
    assert is_valid_uuid("") is False
    assert is_valid_uuid(None) is False  # type: ignore[arg-type]
