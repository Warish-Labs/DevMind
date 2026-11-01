"""Deployment Log Parser and Secret Redaction Pre-filter (docs/01 CAP-07, docs/07 §6).

Parses raw deployment logs from Render, Vercel, Docker, Python/FastAPI, and Node.js.
Applies deterministic server-side redaction pre-filtering to guarantee that no
passwords, API keys, bearer tokens, or connection strings are ever stored or logged.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

from app.domain.brain.redaction_service import (
    RedactionResult,
    RedactionService,
    compute_redacted_token_hash,
)

# Regex to strip ANSI terminal color codes
ANSI_ESCAPE_RX = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")

# Regex to detect additional key=value secrets in deployment logs
ENV_ASSIGNMENT_SECRET_RX = re.compile(
    r"\b((?:[A-Z0-9_]*(?:SECRET|PASSWORD|TOKEN|KEY|PASSWD|CREDENTIAL|AUTH|DATABASE_URL|REDIS_URL)[A-Z0-9_]*)\s*=\s*[\"']?)([^\s\"'\r\n]{6,})([\"']?)",
    re.IGNORECASE,
)

# Additional PAT fallback regex for GitHub tokens with variable length
GITHUB_PAT_FALLBACK_RX = re.compile(r"\b(ghp_[0-9a-zA-Z]{20,})\b")

# Failure category heuristics patterns
MISSING_ENV_PATTERNS = [
    re.compile(r"KeyError:\s*['\"]([A-Z0-9_]+)['\"]"),
    re.compile(
        r"Environment variable\s+['\"]?([A-Z0-9_]+)['\"]?\s+(?:is not set|missing|required|not found)",
        re.IGNORECASE,
    ),
    re.compile(
        r"Missing required environment variable\s+['\"]?([A-Z0-9_]+)['\"]?",
        re.IGNORECASE,
    ),
    re.compile(r"([A-Z0-9_]+)\s+Field required"),
    re.compile(r"process\.env\.([A-Z0-9_]+)\s+is (?:undefined|not defined)"),
    re.compile(
        r"validation error for [A-Za-z0-9_]+[\s\S]*?\b([A-Z][A-Z0-9_]{2,})\b[^\n]*\n[^\n]*Field required",
        re.IGNORECASE,
    ),
    re.compile(
        r"validation error for Settings[\s\S]*?\n\s*([A-Z0-9_]+)\s*\n\s*Field required",
        re.MULTILINE,
    ),
]

DB_MIGRATION_PATTERNS = [
    re.compile(r"alembic\.util\.exc\.CommandError:\s*(.*)", re.IGNORECASE),
    re.compile(
        r"Can't locate revision identified by ['\"]?([a-zA-Z0-9_]+)['\"]?",
        re.IGNORECASE,
    ),
    re.compile(r"Target database is not up to date", re.IGNORECASE),
    re.compile(r"relation ['\"]?([a-zA-Z0-9_]+)['\"]? does not exist", re.IGNORECASE),
    re.compile(r"column ['\"]?([a-zA-Z0-9_]+)['\"]? does not exist", re.IGNORECASE),
    re.compile(
        r"duplicate key value violates unique constraint ['\"]?([a-zA-Z0-9_]+)['\"]?",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:psycopg|asyncpg|sqlalchemy)\.(?:errors|exceptions)\.(\w+)",
        re.IGNORECASE,
    ),
    re.compile(r"OperationalError: connection to server at .* failed", re.IGNORECASE),
]

DEPENDENCY_MISMATCH_PATTERNS = [
    re.compile(r"ModuleNotFoundError:\s*No module named ['\"]?([a-zA-Z0-9_\.\-]+)['\"]?"),
    re.compile(r"ImportError:\s*cannot import name ['\"]?([a-zA-Z0-9_\.\-]+)['\"]?"),
    re.compile(r"npm ERR! code (?:ERESOLVE|ENOENT|MODULE_NOT_FOUND)"),
    re.compile(r"Cannot find module ['\"]?([^'\"\r\n]+)['\"]?"),
    re.compile(r"pnpm: No matching version found for ([a-zA-Z0-9_\.\-]+)"),
    re.compile(r"uv: Failed to resolve dependencies"),
]

PORT_BINDING_PATTERNS = [
    re.compile(r"Errno 98.*Address already in use", re.IGNORECASE),
    re.compile(r"EADDRINUSE.*?(\d+)?", re.IGNORECASE),
    re.compile(r"bind:\s*address already in use", re.IGNORECASE),
    re.compile(r"port (\d+) is already in use", re.IGNORECASE),
]

BUILD_COMPILATION_PATTERNS = [
    re.compile(r"Failed to compile", re.IGNORECASE),
    re.compile(r"Type error:\s*(.*)", re.IGNORECASE),
    re.compile(r"SyntaxError:\s*(.*)", re.IGNORECASE),
    re.compile(r"webpack.*compilation failed", re.IGNORECASE),
    re.compile(r"npm run build exited with code [1-9]"),
    re.compile(r"Next\.js build failed", re.IGNORECASE),
]

TIMEOUT_PATTERNS = [
    re.compile(r"asyncio\.exceptions\.TimeoutError"),
    re.compile(r"TimeoutError:\s*(.*)", re.IGNORECASE),
    re.compile(r"Operation timed out", re.IGNORECASE),
    re.compile(r"Worker timeout", re.IGNORECASE),
    re.compile(r"Connection timed out", re.IGNORECASE),
    re.compile(
        r"(?:health check|startup|service|connection|request)\s+(?:has\s+)?timed\s*out",
        re.IGNORECASE,
    ),
    re.compile(r"timed\s*out after \d+", re.IGNORECASE),
]

# Stack frame location patterns
PYTHON_FRAME_RX = re.compile(r'File "([^"]+)", line (\d+)(?:, in (\w+))?')
NODE_FRAME_RX = re.compile(r"at (?:async )?(?:[A-Za-z0-9_$.]+ )?\(?([^():\r\n]+):(\d+):(\d+)\)?")
ENV_VAR_TOKEN_RX = re.compile(r"\b([A-Z][A-Z0-9_]{3,})\b")

# Well-known harmless words in uppercase to ignore from env var extraction
ENV_VAR_IGNORE_WORDS = {
    "TRUE",
    "FALSE",
    "NONE",
    "NULL",
    "INFO",
    "WARN",
    "WARNING",
    "ERROR",
    "FATAL",
    "DEBUG",
    "HTTP",
    "HTTPS",
    "GET",
    "POST",
    "PATCH",
    "DELETE",
    "PUT",
    "HEAD",
    "JSON",
    "HTML",
    "TEXT",
    "UTF8",
    "FAIL",
    "PASS",
    "STEP",
    "PORT",
    "HOST",
    "NODE",
    "RENDER",
    "VERCEL",
    "DOCKER",
    "LINUX",
    "PYTHON",
}


@dataclass
class LogFrame:
    """A single parsed and redacted log line."""

    line_number: int
    raw_message: str
    timestamp: str | None = None
    level: str | None = None


@dataclass
class ParsedDeploymentLog:
    """Structured, sanitized analysis of a deployment log output."""

    raw_length: int
    redacted_text: str
    redaction_count: int
    counts_by_type: dict[str, int]
    failure_category: str
    confidence: float
    error_signature: str
    fingerprint: str
    summary: str
    probable_cause: str
    recommended_action: str
    referenced_env_vars: list[str] = field(default_factory=list)
    referenced_files: list[dict[str, Any]] = field(default_factory=list)
    primary_log_line: int | None = None
    environment: str = "production"
    service_name: str | None = None


class LogParser:
    """Deterministic deployment log parser with security pre-redaction (CAP-07)."""

    @classmethod
    def redact_log(cls, raw_log: str) -> tuple[str, int, dict[str, int]]:
        """Mask all credentials and sensitive tokens in deployment logs.

        Guarantees that no raw secrets, API keys, passwords, or connection strings
        are ever stored or processed in downstream analytics.
        """
        if not raw_log:
            return "", 0, {}

        # 1. Base server-side redaction (API keys, private keys, JWTs, connection strings)
        redact_res: RedactionResult = RedactionService.redact(raw_log)
        redacted = redact_res.redacted_text
        counts = dict(redact_res.counts_by_type)
        total_count = redact_res.redaction_count

        # 2. Additional environment assignment key=value secret masking
        def sub_env_secret(m: re.Match[str]) -> str:
            nonlocal total_count
            prefix = m.group(1)
            val = m.group(2)
            suffix = m.group(3) or ""
            if val.startswith("[REDACTED:"):
                return m.group(0)
            h8 = compute_redacted_token_hash(val)
            total_count += 1
            counts["env_secret"] = counts.get("env_secret", 0) + 1
            return f"{prefix}[REDACTED:env_secret:{h8}]{suffix}"

        redacted = ENV_ASSIGNMENT_SECRET_RX.sub(sub_env_secret, redacted)

        # 3. GitHub PAT fallback masking
        def sub_pat_secret(m: re.Match[str]) -> str:
            nonlocal total_count
            val = m.group(1)
            h8 = compute_redacted_token_hash(val)
            total_count += 1
            counts["api_key"] = counts.get("api_key", 0) + 1
            return f"[REDACTED:api_key:{h8}]"

        redacted = GITHUB_PAT_FALLBACK_RX.sub(sub_pat_secret, redacted)

        return redacted, total_count, counts

    @classmethod
    def redact_and_parse(
        cls,
        raw_log: str,
        environment: str = "production",
        service_name: str | None = None,
    ) -> ParsedDeploymentLog:
        """Sanitize raw log output and extract failure characteristics."""
        redacted_text, redaction_count, counts_by_type = cls.redact_log(raw_log)

        # Strip ANSI escape codes
        clean_text = ANSI_ESCAPE_RX.sub("", redacted_text)

        lines = clean_text.splitlines()
        raw_length = len(raw_log)

        if not clean_text.strip():
            return ParsedDeploymentLog(
                raw_length=raw_length,
                redacted_text="",
                redaction_count=redaction_count,
                counts_by_type=counts_by_type,
                failure_category="unknown",
                confidence=0.0,
                error_signature="empty_log",
                fingerprint=hashlib.sha256(b"unknown:empty_log").hexdigest(),
                summary="Empty or insufficient log payload",
                probable_cause="No log content was provided for analysis.",
                recommended_action="Paste complete service logs covering container initialization, build, and runtime startup.",
                environment=environment,
                service_name=service_name,
            )

        # Detect failure category and extract relevant signals
        category, primary_line, matched_detail = cls._classify_failure(lines)
        referenced_env_vars = cls._extract_env_vars(clean_text, category, matched_detail)
        referenced_files = cls._extract_code_references(clean_text)

        error_signature = cls._compute_error_signature(
            category=category,
            matched_detail=matched_detail,
            lines=lines,
            primary_line=primary_line,
        )

        fp_input = f"{category}:{error_signature}"
        fingerprint = hashlib.sha256(fp_input.encode("utf-8")).hexdigest()

        summary, probable_cause, recommended_action, confidence = cls._synthesize_diagnosis(
            category=category,
            matched_detail=matched_detail,
            env_vars=referenced_env_vars,
            referenced_files=referenced_files,
            environment=environment,
            service_name=service_name,
        )

        return ParsedDeploymentLog(
            raw_length=raw_length,
            redacted_text=clean_text,
            redaction_count=redaction_count,
            counts_by_type=counts_by_type,
            failure_category=category,
            confidence=confidence,
            error_signature=error_signature,
            fingerprint=fingerprint,
            summary=summary,
            probable_cause=probable_cause,
            recommended_action=recommended_action,
            referenced_env_vars=referenced_env_vars,
            referenced_files=referenced_files,
            primary_log_line=primary_line,
            environment=environment,
            service_name=service_name,
        )

    @classmethod
    def _classify_failure(cls, lines: list[str]) -> tuple[str, int | None, str]:
        """Classify failure category from lines and locate primary line number."""
        full_text = "\n".join(lines)

        # 1. Missing environment variables (highest priority startup failure)
        for rx in MISSING_ENV_PATTERNS:
            m = rx.search(full_text)
            if m:
                matched_val = m.group(1) if m.groups() else m.group(0)
                line_idx = cls._find_line_index(lines, m.group(0))
                return "missing_env_var", line_idx, matched_val.strip()

        # 2. Database migration failures
        for rx in DB_MIGRATION_PATTERNS:
            m = rx.search(full_text)
            if m:
                matched_val = m.group(1) if m.groups() else m.group(0)
                line_idx = cls._find_line_index(lines, m.group(0))
                return "database_migration_failed", line_idx, matched_val.strip()

        # 3. Dependency mismatches
        for rx in DEPENDENCY_MISMATCH_PATTERNS:
            m = rx.search(full_text)
            if m:
                matched_val = m.group(1) if m.groups() else m.group(0)
                line_idx = cls._find_line_index(lines, m.group(0))
                return "dependency_mismatch", line_idx, matched_val.strip()

        # 4. Port binding failures
        for rx in PORT_BINDING_PATTERNS:
            m = rx.search(full_text)
            if m:
                matched_val = m.group(1) if m.groups() and m.group(1) else m.group(0)
                line_idx = cls._find_line_index(lines, m.group(0))
                return "port_binding_failed", line_idx, matched_val.strip()

        # 5. Build & compilation failures
        for rx in BUILD_COMPILATION_PATTERNS:
            m = rx.search(full_text)
            if m:
                matched_val = m.group(1) if m.groups() else m.group(0)
                line_idx = cls._find_line_index(lines, m.group(0))
                return "build_compilation_failed", line_idx, matched_val.strip()

        # 6. Timeouts
        for rx in TIMEOUT_PATTERNS:
            m = rx.search(full_text)
            if m:
                matched_val = m.group(1) if m.groups() else m.group(0)
                line_idx = cls._find_line_index(lines, m.group(0))
                return "timeout", line_idx, matched_val.strip()

        # 7. Unhandled exceptions (generic traceback inspection)
        if "Traceback (most recent call last):" in full_text:
            # Pick last line of traceback
            tb_lines = [line_str for line_str in lines if line_str.strip()]
            for idx in range(len(tb_lines) - 1, -1, -1):
                line = tb_lines[idx].strip()
                if (
                    ":" in line
                    and not line.startswith("File ")
                    and not line.startswith("Traceback")
                ):
                    line_idx = cls._find_line_index(lines, line)
                    return "unhandled_exception", line_idx, line

        # 8. Unhandled Node/JS error
        node_err_match = re.search(r"(?:Uncaught |Unhandled )?([A-Za-z]+Error:[^\r\n]+)", full_text)
        if node_err_match:
            err_line = node_err_match.group(1).strip()
            line_idx = cls._find_line_index(lines, err_line)
            return "unhandled_exception", line_idx, err_line

        return "unknown", None, ""

    @classmethod
    def _find_line_index(cls, lines: list[str], needle: str) -> int | None:
        """Find 1-based line number containing needle."""
        needle_first_line = needle.splitlines()[0].strip() if needle else ""
        if not needle_first_line:
            return None
        for idx, line in enumerate(lines, 1):
            if needle_first_line in line:
                return idx
        return None

    @classmethod
    def _extract_env_vars(cls, full_text: str, category: str, matched_detail: str) -> list[str]:
        """Extract referenced environment variable names."""
        found: set[str] = set()

        if category == "missing_env_var" and matched_detail and matched_detail.isupper():
            found.add(matched_detail)

        for match in ENV_VAR_TOKEN_RX.finditer(full_text):
            token = match.group(1)
            if (
                token not in ENV_VAR_IGNORE_WORDS
                and len(token) >= 4
                and not token.isdigit()
                and (
                    token.startswith("DEVMIND_")
                    or token.startswith("CLERK_")
                    or token.startswith("DATABASE_")
                    or token.startswith("REDIS_")
                    or token.startswith("PORT")
                    or token.endswith("_KEY")
                    or token.endswith("_SECRET")
                    or token.endswith("_URL")
                    or token.endswith("_ID")
                    or token.endswith("_MODE")
                    or token.endswith("_DIR")
                    or token.endswith("_TOKEN")
                )
            ):
                found.add(token)

        return sorted(found)

    @classmethod
    def _extract_code_references(cls, full_text: str) -> list[dict[str, Any]]:
        """Extract referenced file paths and line numbers from stack traces."""
        refs: list[dict[str, Any]] = []
        seen: set[tuple[str, int]] = set()

        # Python frames
        for m in PYTHON_FRAME_RX.finditer(full_text):
            path = m.group(1).replace("\\", "/")
            line = int(m.group(2))
            fn = m.group(3) if m.group(3) else None
            # Filter standard library / site-packages noise unless project-relevant
            if (path, line) not in seen:
                seen.add((path, line))
                refs.append(
                    {
                        "path": path,
                        "line": line,
                        "function": fn,
                        "is_project_code": "/site-packages/" not in path
                        and "/lib/python" not in path,
                    }
                )

        # Node / TypeScript frames
        for m in NODE_FRAME_RX.finditer(full_text):
            path = m.group(1).replace("\\", "/")
            line = int(m.group(2))
            if (path, line) not in seen:
                seen.add((path, line))
                refs.append(
                    {
                        "path": path,
                        "line": line,
                        "function": None,
                        "is_project_code": "/node_modules/" not in path,
                    }
                )

        # Sort so project code is listed first
        refs.sort(key=lambda r: (not r["is_project_code"], r["path"]))
        return refs

    @classmethod
    def _compute_error_signature(
        cls,
        category: str,
        matched_detail: str,
        lines: list[str],
        primary_line: int | None,
    ) -> str:
        """Compute normalized, canonical signature for fingerprinting."""
        if category == "missing_env_var":
            return f"MissingEnvVar:{matched_detail or 'unspecified'}"

        if category == "port_binding_failed":
            port = (
                matched_detail if matched_detail and matched_detail.isdigit() else "assigned_port"
            )
            return f"PortBindingFailed:port_{port}"

        if matched_detail:
            # Strip dynamic memory addresses and timestamps
            norm_detail = re.sub(r"0x[0-9a-fA-F]+", "0xADDR", matched_detail)
            norm_detail = re.sub(
                r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?", "TIMESTAMP", norm_detail
            )
            return f"{category}:{norm_detail[:120].strip()}"

        if primary_line and 1 <= primary_line <= len(lines):
            line_content = lines[primary_line - 1].strip()
            line_content = re.sub(r"0x[0-9a-fA-F]+", "0xADDR", line_content)
            line_content = re.sub(
                r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?", "TIMESTAMP", line_content
            )
            return f"{category}:{line_content[:120].strip()}"

        return f"{category}:generic_failure"

    @classmethod
    def _synthesize_diagnosis(
        cls,
        category: str,
        matched_detail: str,
        env_vars: list[str],
        referenced_files: list[dict[str, Any]],
        environment: str,
        service_name: str | None,
    ) -> tuple[str, str, str, float]:
        """Formulate deterministic diagnosis: (summary, probable_cause, recommended_action, confidence)."""
        env_context = f" in {environment}" if environment else ""
        service_context = f" for '{service_name}'" if service_name else ""

        if category == "missing_env_var":
            var_name = matched_detail or (env_vars[0] if env_vars else "REQUIRED_VAR")
            summary = f"Missing required environment variable: {var_name}"
            probable_cause = (
                f"The application failed during startup{env_context}{service_context} because environment "
                f"variable '{var_name}' is required by application settings but was not defined in the deployment environment."
            )
            recommended_action = (
                f"Add '{var_name}' to your environment variables dashboard (e.g. Render / Vercel configuration) "
                f"and trigger a fresh deployment."
            )
            confidence = 0.98
            return summary, probable_cause, recommended_action, confidence

        if category == "database_migration_failed":
            detail = matched_detail or "pending migrations or schema mismatch"
            summary = f"Database migration or schema mismatch: {detail}"
            probable_cause = (
                f"Database migration or query execution failed{env_context}: {detail}. "
                f"A database schema mismatch was detected: the live database schema does not match the active application code expectations."
            )
            recommended_action = (
                "Ensure database connectivity is reachable from the deployment host, then execute "
                "'alembic upgrade head' or verify that prior migrations succeeded without locking conflicts."
            )
            confidence = 0.95
            return summary, probable_cause, recommended_action, confidence

        if category == "dependency_mismatch":
            dep = matched_detail or "missing package"
            summary = f"Missing or unresolvable runtime dependency: {dep}"
            probable_cause = (
                f"Module or package '{dep}' was imported or required at runtime but is not present in "
                f"the installed container environment."
            )
            recommended_action = (
                f"Add '{dep}' to package dependencies in pyproject.toml or package.json, regenerate "
                f"the lockfile, and rebuild the deployment container."
            )
            confidence = 0.95
            return summary, probable_cause, recommended_action, confidence

        if category == "port_binding_failed":
            summary = "Port binding conflict: address already in use"
            probable_cause = (
                f"The web process failed to bind its listening socket{env_context} because the requested port is "
                f"already in use by another worker or process."
            )
            recommended_action = (
                "Verify that the web entrypoint binds to the platform-assigned PORT environment variable "
                "($PORT) and ensure worker services are not configured to bind to HTTP ports."
            )
            confidence = 0.96
            return summary, probable_cause, recommended_action, confidence

        if category == "build_compilation_failed":
            summary = f"Build compilation error: {matched_detail or 'compilation failed'}"
            probable_cause = f"Static build step failed during asset bundling or TypeScript compilation: {matched_detail}."
            recommended_action = "Run 'pnpm build' or typechecks locally to reproduce and fix compiler errors before pushing."
            confidence = 0.92
            return summary, probable_cause, recommended_action, confidence

        if category == "timeout":
            summary = "Service startup or health check timeout"
            probable_cause = f"The application container exceeded the maximum platform initialization or health check timeout{env_context}."
            recommended_action = (
                "Inspect initialization routines for blocking synchronous network calls, slow database connection pools, "
                "or consider increasing the health check timeout."
            )
            confidence = 0.88
            return summary, probable_cause, recommended_action, confidence

        if category == "unhandled_exception":
            ex_type = matched_detail or "Exception"
            summary = f"Unhandled application exception: {ex_type}"
            probable_cause = (
                f"An unhandled exception occurred during application execution: {ex_type}."
            )
            recommended_action = (
                "Examine referenced code frames in the stack trace and implement appropriate exception handling "
                "or input validation guards."
            )
            confidence = 0.85
            return summary, probable_cause, recommended_action, confidence

        summary = "Unclassified deployment failure"
        probable_cause = "The log indicates a runtime failure, but no known category pattern could be identified with high confidence."
        recommended_action = "Review raw log frames for errors or enable verbose debugging output in application configuration."
        confidence = 0.30
        return summary, probable_cause, recommended_action, confidence
