"""Server-side Secret Detection and Redaction Pipeline (docs/07 §6, docs/03 §12.4).

Scans and deterministically masks sensitive credentials, tokens, private keys,
and connection strings into the format: [REDACTED:<type>:<hash8>].
Defense in depth: The server never trusts client-side redaction alone, and re-checks
all incoming snippets and chunks before storage, embedding, or prompt assembly.
Fail-closed: If redaction encounters an unexpected error, raises RedactionFailedClosedError.
"""

from __future__ import annotations

import hashlib
import re

from pydantic import BaseModel, Field

from app.core.errors import DevMindError

# Credential and key file path exclusion patterns (docs/06 §4, docs/07 §6).
# Credential files are path-only and content must NEVER be transmitted or stored.
CREDENTIAL_PATH_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(?:^|/)\.env(?:$|\..*)", re.IGNORECASE),
    re.compile(r"(?:^|/).*\.pem$", re.IGNORECASE),
    re.compile(r"(?:^|/).*\.key$", re.IGNORECASE),
    re.compile(r"(?:^|/)id_rsa.*", re.IGNORECASE),
    re.compile(r"(?:^|/)credentials.*\.json$", re.IGNORECASE),
    re.compile(r"(?:^|/).*\.kdbx$", re.IGNORECASE),
    re.compile(r"(?:^|/).*\.pfx$", re.IGNORECASE),
    re.compile(r"(?:^|/).*\.p12$", re.IGNORECASE),
]


def is_excluded_credential_path(path: str) -> bool:
    """Return True if path matches any excluded credential or secret file format."""
    normalized = path.replace("\\", "/").strip().lstrip("/")
    return any(pattern.search(normalized) for pattern in CREDENTIAL_PATH_PATTERNS)


def compute_redacted_token_hash(token: str) -> str:
    """Compute an 8-character deterministic token digest for safe redacted logging (ADR-047)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:8]


class RedactionFailedClosedError(DevMindError):
    """Raised when secret redaction fails, preventing potential leakage (fail-closed)."""

    def __init__(self, detail: str = "Secret redaction failed closed.") -> None:
        super().__init__(
            status_code=500,
            detail=detail,
            code="redaction.failed_closed",
        )


class RedactionResult(BaseModel):
    """Result of redaction execution."""

    redacted_text: str = Field(description="Redacted text content with secrets masked.")
    redaction_count: int = Field(description="Number of newly redacted secrets.")
    counts_by_type: dict[str, int] = Field(
        default_factory=dict, description="Redaction counts broken down by secret type."
    )


class RedactionService:
    """Server-side secret redaction and client re-check engine (docs/07 §6)."""

    # 1. Private keys
    _PK_BLOCK_RX = re.compile(
        r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"
    )
    _PK_HEADER_RX = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----[^\r\n]*")

    # 2. Known API keys and cloud credentials
    _API_KEY_RXS = [
        re.compile(r"\b(sk-ant-[A-Za-z0-9\-_]{32,})\b"),
        re.compile(r"\b(sk-[A-Za-z0-9]{32,})\b"),
        re.compile(r"\b(sk_live_[0-9a-zA-Z]{24,})\b"),
        re.compile(r"\b(sk_test_[0-9a-zA-Z]{24,})\b"),
        re.compile(r"\b(ghp_[0-9a-zA-Z]{36})\b"),
        re.compile(r"\b(github_pat_[0-9a-zA-Z_]{60,})\b"),
        re.compile(r"\b(AKIA[0-9A-Z]{16})\b"),
    ]

    # 3. Webhook secrets & JWT
    _TOKEN_RXS = [
        re.compile(r"\b(whsec_[0-9a-zA-Z+/=]{32,})\b"),
        re.compile(r"\b(ey[A-Za-z0-9_-]{10,}\.ey[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})\b"),
    ]

    # 4. Bearer tokens
    _BEARER_RX = re.compile(r"Bearer\s+([A-Za-z0-9\-_.~+/]+=*)", re.IGNORECASE)

    # 5. Connection strings with embedded credentials
    _CONN_STR_RX = re.compile(
        r"((?:postgres|postgresql|mysql|mongodb|mongodb\+srv|redis|rediss)://[^:]+:)([^@\s'\"]+)(@[^\s'\"]+)",
        re.IGNORECASE,
    )

    # 6. Generic high-entropy secret assignments
    _SECRET_ASSIGN_RX = re.compile(
        r"\b((?:password|passwd|secret|api_secret|auth_token|client_secret)\s*[:=]\s*[\"'])([^\"'\r\n]{8,})([\"'])",
        re.IGNORECASE,
    )

    @classmethod
    def redact(cls, text: str) -> RedactionResult:
        """Scan text, replace sensitive credentials with [REDACTED:<type>:<hash8>], and return result.

        Fail-closed: If any regex or replacement raises an exception, raises RedactionFailedClosedError.
        """
        if not text:
            return RedactionResult(redacted_text="", redaction_count=0, counts_by_type={})

        try:
            result = text
            total_count = 0
            counts_by_type: dict[str, int] = {}

            # Helper to record a redaction
            def record_redaction(stype: str) -> None:
                nonlocal total_count
                total_count += 1
                counts_by_type[stype] = counts_by_type.get(stype, 0) + 1

            # 1. Private keys
            def sub_pk(m: re.Match[str]) -> str:
                match_val = m.group(0)
                if match_val.startswith("[REDACTED:"):
                    return match_val
                h8 = compute_redacted_token_hash(match_val)
                record_redaction("private_key")
                return f"[REDACTED:private_key:{h8}]"

            result = cls._PK_BLOCK_RX.sub(sub_pk, result)
            result = cls._PK_HEADER_RX.sub(sub_pk, result)

            # 2. API keys
            def sub_api_key(m: re.Match[str]) -> str:
                val = m.group(1) if m.lastindex else m.group(0)
                if val.startswith("[REDACTED:"):
                    return val
                h8 = compute_redacted_token_hash(val)
                record_redaction("api_key")
                return f"[REDACTED:api_key:{h8}]"

            for rx in cls._API_KEY_RXS:
                result = rx.sub(sub_api_key, result)

            # 3. Webhook secrets & JWT
            def sub_token(m: re.Match[str]) -> str:
                val = m.group(1) if m.lastindex else m.group(0)
                if val.startswith("[REDACTED:"):
                    return val
                h8 = compute_redacted_token_hash(val)
                record_redaction("token")
                return f"[REDACTED:token:{h8}]"

            for rx in cls._TOKEN_RXS:
                result = rx.sub(sub_token, result)

            # 4. Bearer tokens
            def sub_bearer(m: re.Match[str]) -> str:
                token = m.group(1)
                if not token or token.startswith("[REDACTED:"):
                    return m.group(0)
                h8 = compute_redacted_token_hash(token)
                record_redaction("bearer_token")
                return f"Bearer [REDACTED:bearer_token:{h8}]"

            result = cls._BEARER_RX.sub(sub_bearer, result)

            # 5. Connection strings
            def sub_conn_str(m: re.Match[str]) -> str:
                prefix, password, suffix = m.group(1), m.group(2), m.group(3)
                if not password or password.startswith("[REDACTED:"):
                    return m.group(0)
                h8 = compute_redacted_token_hash(password)
                record_redaction("connection_string")
                return f"{prefix}[REDACTED:connection_string:{h8}]{suffix}"

            result = cls._CONN_STR_RX.sub(sub_conn_str, result)

            # 6. Secret assignments
            def sub_secret_assign(m: re.Match[str]) -> str:
                prefix, secret_val, suffix = m.group(1), m.group(2), m.group(3)
                if not secret_val or secret_val.startswith("[REDACTED:"):
                    return m.group(0)
                h8 = compute_redacted_token_hash(secret_val)
                record_redaction("secret")
                return f"{prefix}[REDACTED:secret:{h8}]{suffix}"

            result = cls._SECRET_ASSIGN_RX.sub(sub_secret_assign, result)

            return RedactionResult(
                redacted_text=result,
                redaction_count=total_count,
                counts_by_type=counts_by_type,
            )
        except Exception as err:
            raise RedactionFailedClosedError(
                detail=f"Secret redaction failed closed: {err}"
            ) from err

    @classmethod
    def recheck_client_redaction(
        cls,
        text: str,
        client_redaction_count: int = 0,
    ) -> tuple[str, int, dict[str, int]]:
        """Re-runs server-side redaction on text received from client.

        If any unredacted secrets are found, they are masked and added to the count.
        Returns:
            (redacted_text, total_redaction_count, counts_by_type)
        """
        result = cls.redact(text)
        total_count = client_redaction_count + result.redaction_count
        return result.redacted_text, total_count, result.counts_by_type
