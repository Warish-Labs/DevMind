"""Clerk Svix webhook signature verification service (docs/03 §10, docs/07 §11)."""

import base64
import hashlib
import hmac
import logging
import time

logger = logging.getLogger(__name__)


def verify_svix_signature(
    secret: str,
    svix_id: str,
    svix_timestamp: str,
    svix_signature: str,
    body: bytes,
    tolerance_seconds: int = 300,
) -> bool:
    """Verify Svix webhook signature sent by Clerk.

    Verification follows the Svix / Clerk specification:
    1. Parse secret (strip 'whsec_' prefix if present and base64 decode).
    2. Construct signed content: `{svix_id}.{svix_timestamp}.{body}`.
    3. Calculate HMAC-SHA256 signature and base64 encode.
    4. Verify timestamp is within tolerance window (default 300s) to prevent replay.
    5. Compare computed signature against signatures in `svix_signature` in constant time.
    """
    if not secret or not svix_id or not svix_timestamp or not svix_signature:
        return False

    # 1. Timestamp validation (replay attack prevention)
    try:
        ts = float(svix_timestamp)
        now = time.time()
        if abs(now - ts) > tolerance_seconds:
            logger.warning(
                "Webhook timestamp outside tolerance window",
                extra={"diff_seconds": abs(now - ts), "tolerance": tolerance_seconds},
            )
            return False
    except (ValueError, TypeError):
        return False

    # 2. Decode secret key
    try:
        if secret.startswith("whsec_"):
            key = base64.b64decode(secret[6:])
        else:
            try:
                key = base64.b64decode(secret)
            except Exception:
                key = secret.encode("utf-8")
    except Exception as exc:
        logger.error("Failed to parse Clerk webhook secret key: %s", exc)
        return False

    # 3. Construct signature payload
    to_sign = f"{svix_id}.{svix_timestamp}.".encode() + body
    computed_digest = hmac.new(key, to_sign, hashlib.sha256).digest()
    expected_b64 = base64.b64encode(computed_digest).decode()

    # 4. Check against all provided signatures (format: "v1,signature v1,signature2")
    signatures = svix_signature.strip().split()
    for sig_entry in signatures:
        if sig_entry.startswith("v1,"):
            actual_b64 = sig_entry[3:]
            if hmac.compare_digest(expected_b64, actual_b64):
                return True

    return False
