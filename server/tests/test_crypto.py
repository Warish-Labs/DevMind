"""Tests for EncryptionService (AES-256-GCM envelope encryption)."""

from __future__ import annotations

import base64
import os

import pytest

from app.core.crypto import CryptographyError, EncryptionService
from app.core.settings import Settings


def test_encryption_roundtrip() -> None:
    """Verifies that encrypting and decrypting returns the original plaintext."""
    service = EncryptionService()
    plaintext = "ghp_super_secret_github_personal_access_token_12345"
    envelope = service.encrypt(plaintext)

    assert envelope.startswith("v1:0:")
    assert plaintext not in envelope  # Ensure no plaintext leakage

    decrypted = service.decrypt(envelope)
    assert decrypted == plaintext


def test_encryption_empty_string() -> None:
    service = EncryptionService()
    assert service.encrypt("") == ""
    assert service.decrypt("") == ""


def test_tampered_ciphertext_fails_auth() -> None:
    """Verifies that tampering with ciphertext triggers AES-GCM authentication failure."""
    service = EncryptionService()
    envelope = service.encrypt("secret_message")
    parts = envelope.split(":")

    # Corrupt last byte of ciphertext
    ct_bytes = bytearray(base64.b64decode(parts[3]))
    ct_bytes[-1] ^= 0xFF
    corrupted_envelope = (
        f"{parts[0]}:{parts[1]}:{parts[2]}:{base64.b64encode(ct_bytes).decode('ascii')}"
    )

    with pytest.raises(CryptographyError) as exc_info:
        service.decrypt(corrupted_envelope)
    assert exc_info.value.code == "crypto.auth_failed"


def test_malformed_envelope_format() -> None:
    service = EncryptionService()
    with pytest.raises(CryptographyError):
        service.decrypt("invalid:envelope")


def test_key_rotation_support() -> None:
    """Verifies that ciphertext encrypted under an older key decrypts cleanly when rotated."""
    old_key = base64.b64encode(os.urandom(32)).decode("ascii")
    new_key = base64.b64encode(os.urandom(32)).decode("ascii")

    # Service with only old key
    old_settings = Settings(env="test", encryption_keys=[old_key])
    old_service = EncryptionService(settings=old_settings)
    envelope = old_service.encrypt("data_encrypted_before_rotation")

    # Rotated service with new primary key and old key retained
    rotated_settings = Settings(env="test", encryption_keys=[new_key, old_key])
    rotated_service = EncryptionService(settings=rotated_settings)

    decrypted = rotated_service.decrypt(envelope)
    assert decrypted == "data_encrypted_before_rotation"
