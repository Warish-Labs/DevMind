"""Deterministic error signature normalizer for Bug Memory (docs/01 CAP-03, docs/05 §6.6).

Strips ephemeral runtime artifacts (system file paths, timestamps, UUIDs, memory addresses,
dynamic ports) and extracts canonical exception types, module hints, and deterministic
SHA-256 fingerprints to recognize recurring errors across environments.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

# Regex patterns for ephemeral runtime noise
_RE_UUID = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
_RE_HEX_ADDR = re.compile(r"\b0x[0-9a-fA-F]{4,16}\b")
_RE_ISO_TIMESTAMP = re.compile(
    r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?\b"
)
_RE_EPOCH_MS = re.compile(r"\b1[5-9]\d{11,12}\b")
_RE_IPV4_PORT = re.compile(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?::\d{1,5})?\b")
_RE_ABSOLUTE_POSIX_PATH = re.compile(r"(?:/[a-zA-Z0-9_\.-]+)+/([a-zA-Z0-9_\.-]+\.[a-zA-Z0-9]+)")
_RE_ABSOLUTE_WIN_PATH = re.compile(
    r"[a-zA-Z]:\\(?:[a-zA-Z0-9_\.-]+\\)+([a-zA-Z0-9_\.-]+\.[a-zA-Z0-9]+)"
)
_RE_PYTHON_FRAME = re.compile(
    r'File\s+["\'](?P<path>[^"\']+)["\'],\s+line\s+(?P<line>\d+),\s+in\s+(?P<func>[a-zA-Z0-9_<>]+)'
)
_RE_JS_FRAME = re.compile(
    r"at\s+(?:(?P<func>[a-zA-Z0-9_$.<>]+)\s+\()?(?P<path>[^:)]+):(?P<line>\d+)(?::\d+)?\)?$"
)
_RE_EXCEPTION_LINE = re.compile(
    r"^(?:(?:[a-zA-Z0-9_.]+\.)?(?P<type>[a-zA-Z0-9_]+Error|[a-zA-Z0-9_]+Exception|Panic|Error))(?::\s*(?P<msg>.*))?$",
    re.IGNORECASE,
)

# Standard library and vendor path indicators to de-prioritize for module_hint
_VENDOR_PATH_INDICATORS = (
    "site-packages",
    "dist-packages",
    "node_modules",
    "python3.",
    "/usr/lib",
    "/usr/local/lib",
    "venv",
    ".venv",
)


@dataclass(frozen=True)
class NormalizedError:
    """Structured, deterministic representation of a normalized error trace."""

    exception_type: str
    clean_message: str
    module_hint: str | None
    top_frames: list[str] = field(default_factory=list)
    normalized_signature: str = ""
    fingerprint: str = ""
    raw_preview: str = ""


class ErrorNormalizer:
    """Normalizes error messages and stack traces into deterministic signatures and fingerprints."""

    @classmethod
    def sanitize_text(cls, text: str) -> str:
        """Strip ephemeral runtime tokens such as UUIDs, memory addresses, timestamps, and absolute paths."""
        if not text:
            return ""

        s = text
        # Replace UUIDs
        s = _RE_UUID.sub("<uuid>", s)
        # Replace memory pointers
        s = _RE_HEX_ADDR.sub("<hex>", s)
        # Replace ISO timestamps
        s = _RE_ISO_TIMESTAMP.sub("<timestamp>", s)
        # Replace epoch timestamps
        s = _RE_EPOCH_MS.sub("<epoch>", s)
        # Replace IP/Port
        s = _RE_IPV4_PORT.sub("<ip:port>", s)
        # Normalize POSIX and Windows absolute paths to basename
        s = _RE_ABSOLUTE_POSIX_PATH.sub(r"<path>/\1", s)
        s = _RE_ABSOLUTE_WIN_PATH.sub(r"<path>/\1", s)
        return s.strip()

    @classmethod
    def normalize(cls, raw_error: str) -> NormalizedError:
        """Parse raw error trace or exception message into a canonical NormalizedError."""
        if not raw_error or not raw_error.strip():
            raw_clean = ""
            return NormalizedError(
                exception_type="UnknownError",
                clean_message="Empty error provided",
                module_hint=None,
                top_frames=[],
                normalized_signature="UnknownError: Empty error provided",
                fingerprint=hashlib.sha256(b"UnknownError: Empty error provided").hexdigest(),
                raw_preview=raw_clean,
            )

        sanitized_full = cls.sanitize_text(raw_error)
        lines = [line.strip() for line in raw_error.splitlines() if line.strip()]

        exception_type = "Error"
        clean_message = ""
        app_module: str | None = None
        frames: list[str] = []

        # 1. Scan lines for stack frames and exception details
        for line in lines:
            # Python frame check
            m_py = _RE_PYTHON_FRAME.search(line)
            if m_py:
                path = m_py.group("path")
                func_name = m_py.group("func")
                norm_path = cls._canonical_path(path)
                frame_desc = f"{norm_path}:{func_name}"
                frames.append(frame_desc)

                if app_module is None and not cls._is_vendor_path(path):
                    app_module = norm_path
                continue

            # JS/TS frame check
            m_js = _RE_JS_FRAME.search(line)
            if m_js:
                path = m_js.group("path")
                func_name = m_js.group("func") or "<anonymous>"
                norm_path = cls._canonical_path(path)
                frame_desc = f"{norm_path}:{func_name}"
                frames.append(frame_desc)

                if app_module is None and not cls._is_vendor_path(path):
                    app_module = norm_path
                continue

            # Exception header/trailer check
            m_exc = _RE_EXCEPTION_LINE.match(line)
            if m_exc:
                exc_cand = m_exc.group("type")
                msg_cand = m_exc.group("msg") or ""
                # Avoid generic 'Error' if a more specific exception type was already found
                if exc_cand and (exception_type in ("Error", "UnknownError") or len(exc_cand) > 5):
                    exception_type = exc_cand
                    clean_message = cls.sanitize_text(msg_cand)

        # 2. Fallback exception detection if regex didn't catch trailing line
        if exception_type == "Error" and lines:
            last_line = lines[-1]
            if ":" in last_line:
                parts = last_line.split(":", 1)
                candidate = parts[0].strip().split(".")[-1]
                if "Error" in candidate or "Exception" in candidate:
                    exception_type = candidate
                    clean_message = cls.sanitize_text(parts[1].strip())
            if not clean_message:
                clean_message = cls.sanitize_text(lines[-1])

        if not clean_message and lines:
            clean_message = cls.sanitize_text(lines[0])

        # 3. Canonicalize top frames (up to 5 most specific frames)
        # In Python traces, the bottom-most app frame is often the immediate point of failure
        top_app_frames = [f for f in frames if not cls._is_vendor_path(f)]
        if not top_app_frames:
            top_app_frames = frames

        canonical_frames = top_app_frames[-5:] if top_app_frames else []

        # 4. Formulate deterministic signature
        signature_parts = [f"Exception: {exception_type}"]
        if clean_message:
            # Mask single-quoted/double-quoted variable values in messages
            masked_msg = re.sub(r"['\"][^'\"]*['\"]", "'<value>'", clean_message)
            signature_parts.append(f"Message: {masked_msg}")
        if canonical_frames:
            signature_parts.append("Trace: " + " -> ".join(canonical_frames))

        normalized_signature = "\n".join(signature_parts)
        fingerprint = hashlib.sha256(normalized_signature.encode("utf-8")).hexdigest()

        # Generate a clean raw preview (first 1000 characters, secrets/UUIDs sanitized)
        raw_preview = sanitized_full[:1000]

        return NormalizedError(
            exception_type=exception_type,
            clean_message=clean_message,
            module_hint=app_module,
            top_frames=canonical_frames,
            normalized_signature=normalized_signature,
            fingerprint=fingerprint,
            raw_preview=raw_preview,
        )

    @classmethod
    def _is_vendor_path(cls, path: str) -> bool:
        """Check whether a path points to standard libraries or third-party packages."""
        p_lower = path.lower()
        return any(indicator in p_lower for indicator in _VENDOR_PATH_INDICATORS)

    @classmethod
    def _canonical_path(cls, path: str) -> str:
        """Convert an arbitrary path into a canonical relative or base identifier."""
        clean = path.replace("\\", "/")
        # Strip query strings or line references if attached
        clean = clean.split("?")[0]

        # If inside a repository structure, isolate from project root if detectable
        for root_marker in ("server/", "client/", "app/", "src/", "packages/"):
            idx = clean.find(root_marker)
            if idx != -1:
                return clean[idx:]

        # Fallback to last two path segments
        parts = clean.strip("/").split("/")
        if len(parts) >= 2:
            return f"{parts[-2]}/{parts[-1]}"
        return parts[-1] if parts else clean
