"""Cryptographic service for envelope encryption of secrets at rest (docs/07 §3).

Uses AES-256-GCM authenticated encryption via the cryptography library.
Keys are loaded from Settings.encryption_keys (DEVMIND_ENCRYPTION_KEYS).
The first key in the list is used for encryption; all keys are tried for decryption
to support zero-downtime key rotation.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.errors import DevMindError
from app.core.settings import Settings, get_settings

logger = logging.getLogger(__name__)


class CryptographyError(DevMindError):
    """Exception raised when encryption or decryption fails."""

    def __init__(
        self,
        detail: str = "Cryptographic operation failed",
        code: str = "crypto.failure",
        status_code: int = 500,
        errors: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(
            detail=detail,
            code=code,
            status_code=status_code,
            title="Cryptographic Error",
            errors=errors,
        )


class EncryptionService:
    """Provides AES-256-GCM encryption and decryption of sensitive credentials."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._raw_keys: list[bytes] = self._resolve_keys()

    def _resolve_keys(self) -> list[bytes]:
        """Parse 32-byte AES keys from settings.encryption_keys."""
        keys: list[bytes] = []
        raw_keys = self.settings.encryption_keys

        for raw in raw_keys:
            raw_str = raw.strip()
            if not raw_str:
                continue
            try:
                decoded = base64.b64decode(raw_str)
                if len(decoded) == 32:
                    keys.append(decoded)
                    continue
            except Exception:
                pass

            # Fallback: derive 32-byte key via SHA-256
            derived = hashlib.sha256(raw_str.encode("utf-8")).digest()
            keys.append(derived)

        if not keys:
            # Deterministic fallback for test/local environments
            if self.settings.env in ("test", "local"):
                fallback_key = hashlib.sha256(b"devmind_local_test_encryption_key_32b!").digest()
                keys.append(fallback_key)
            else:
                logger.error("No encryption keys configured in %s environment", self.settings.env)
                raise CryptographyError(
                    detail="Server encryption keys are not configured",
                    code="crypto.unconfigured",
                )

        return keys

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a plaintext string using the current primary key (AES-256-GCM).

        Format: v1:{key_idx}:{nonce_b64}:{ciphertext_b64}
        """
        if not plaintext:
            return ""

        key = self._raw_keys[0]
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)  # 96-bit nonce for GCM

        try:
            ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        except Exception as exc:
            logger.error("Encryption failed: %s", type(exc).__name__)
            raise CryptographyError(detail="Failed to encrypt sensitive data") from exc

        nonce_b64 = base64.b64encode(nonce).decode("ascii")
        ct_b64 = base64.b64encode(ciphertext).decode("ascii")
        return f"v1:0:{nonce_b64}:{ct_b64}"

    def decrypt(self, envelope: str) -> str:
        """Decrypt an envelope string trying configured keys in order."""
        if not envelope:
            return ""

        parts = envelope.split(":")
        if len(parts) != 4 or parts[0] != "v1":
            raise CryptographyError(detail="Malformed encryption envelope format")

        try:
            key_hint = int(parts[1])
            nonce = base64.b64decode(parts[2])
            ciphertext = base64.b64decode(parts[3])
        except Exception as exc:
            raise CryptographyError(detail="Invalid base64 payload in envelope") from exc

        # Try key matching the hint first, then any remaining keys
        keys_to_try: list[bytes] = []
        if 0 <= key_hint < len(self._raw_keys):
            keys_to_try.append(self._raw_keys[key_hint])
        for k in self._raw_keys:
            if k not in keys_to_try:
                keys_to_try.append(k)

        for key in keys_to_try:
            aesgcm = AESGCM(key)
            try:
                decrypted_bytes = aesgcm.decrypt(nonce, ciphertext, None)
                return decrypted_bytes.decode("utf-8")
            except Exception:
                continue

        logger.error("Decryption failed across all %d available keys", len(self._raw_keys))
        raise CryptographyError(
            detail="Failed to decrypt ciphertext (authentication tag mismatch or wrong key)",
            code="crypto.auth_failed",
            status_code=500,
        )
