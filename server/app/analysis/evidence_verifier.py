"""Deterministic Evidence Verifier for Grounding, Proof Verification, and Citations (docs/05 §7, docs/03 §3.4, §12.1).

Enforces strict mathematical and code-fact grounding for all draft findings and model citations:
1. File and snapshot presence: cited path must exist in snapshot; version must match.
2. Line range integrity: 1 <= start <= end <= total_lines.
3. Snippet hash confirmation: SHA-256 of cited line slice must equal cited snippet_hash.
4. Rule ID registry: Rule ID must belong to DevMind rule registry or known scanner prefixes.
5. Structural claim verification: Re-checks guard chain resolution on route authorization findings.
6. Evidence level verification: Claims E2 with unresolved callees/dependencies -> downgraded to E1.
   Never claims E3 in v1 (ADR-041). Enforces no exploitability claims for E0/E1 (AGENTS.md §5.7).
7. Secret redaction in evidence: Checks snippets for credentials/keys and redacts with [REDACTED:<type>:<hash8>].
8. Citation verification: Verifies inline and structured citations against snapshot files, symbols, and context chunks.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.analysis.guard_resolution import (
    RouteGuardAnalyzer,
    RouteSecurityEvaluation,
)

logger = logging.getLogger("devmind.analysis.evidence_verifier")


# ---------------------------------------------------------------------------
# Constants and Secret Detection Patterns (docs/07 §6, docs/03 §12.4)
# ---------------------------------------------------------------------------

KNOWN_RULES: dict[str, str] = {
    "devmind.authn.unprotected_route": "Sensitive or non-exempt route without authentication guard",
    "devmind.authz.missing_role_check": "Authenticated route missing required role or permission guard",
    "devmind.secret.detected_credential": "Hard-coded credential, secret, or private key in code",
    "devmind.injection.sql": "Untrusted input formatted directly into SQL query",
    "devmind.injection.command": "Untrusted input passed to OS shell or subprocess execution",
    "devmind.path_traversal": "Unsanitized path parameter used in file system operations",
    "devmind.crypto.weak_algorithm": "Insecure cryptographic algorithm (e.g. MD5, SHA1 for signatures)",
}

ALLOWED_RULE_PREFIXES: tuple[str, ...] = (
    "bandit.",
    "semgrep.",
    "trivy.",
    "gitleaks.",
    "eslint.",
    "ruff.",
    "devmind.",
)

_SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "private_key",
        re.compile(
            r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"
        ),
    ),
    ("anthropic_key", re.compile(r"\b(sk-ant-[A-Za-z0-9\-_]{32,})\b")),
    ("openai_key", re.compile(r"\b(sk-[A-Za-z0-9]{32,})\b")),
    ("stripe_live", re.compile(r"\b(sk_live_[0-9a-zA-Z]{24,})\b")),
    ("stripe_test", re.compile(r"\b(sk_test_[0-9a-zA-Z]{24,})\b")),
    (
        "github_token",
        re.compile(r"\b(ghp_[0-9a-zA-Z]{36}|gho_[0-9a-zA-Z]{36}|github_pat_[0-9a-zA-Z_]{82})\b"),
    ),
    ("gitlab_token", re.compile(r"\b(glpat-[0-9a-zA-Z\-_]{20,})\b")),
    ("slack_token", re.compile(r"\b(xox[baprs]-[0-9a-zA-Z\-]{24,})\b")),
    ("aws_access_key", re.compile(r"\b(AKIA[0-9A-Z]{16})\b")),
    ("db_connection", re.compile(r"postgres(?:ql)?:\/\/[^:]+:([^@]+)@")),
]

# Regex to detect inline citations in markdown text
_CITATION_INLINE_RE = re.compile(
    r"\[source:\s*([a-zA-Z0-9_\-./]+(?::\d+(?:-\d+)?)?)\]|"
    r"\[([a-zA-Z0-9_\-./]+(?::\d+(?:-\d+)?)?)\]|"
    r"\(([a-zA-Z0-9_\-./]+:\d+(?:-\d+)?)\)"
)

# Prohibited exploitability wording for E0/E1 (AGENTS.md §5.7)
_EXPLOITABILITY_RE = re.compile(
    r"\b(vulnerable|vulnerability|exploitable|exploit)\b", re.IGNORECASE
)


def is_known_rule(rule_id: str) -> bool:
    """Return True if rule_id is recognized in DevMind registry or matches allowed scanner prefix."""
    if not rule_id:
        return False
    if rule_id in KNOWN_RULES:
        return True
    return any(rule_id.startswith(pfx) for pfx in ALLOWED_RULE_PREFIXES)


def register_known_rule(rule_id: str, description: str) -> None:
    """Register an additional known rule ID dynamically."""
    KNOWN_RULES[rule_id] = description


def compute_snippet_hash(snippet: str) -> str:
    """Compute deterministic SHA-256 digest of snippet with normalized newlines."""
    normalized = snippet.replace("\r\n", "\n").rstrip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def redact_evidence_secrets(text: str) -> tuple[str, int]:
    """Scan and redact known secrets in evidence text, returning (redacted_text, count)."""
    if not text:
        return text, 0
    count = 0
    res = text
    for secret_type, pattern in _SECRET_PATTERNS:
        matches = list(pattern.finditer(res))
        if matches:
            for m in reversed(matches):
                val = m.group(1) if m.groups() else m.group(0)
                digest8 = hashlib.sha256(val.encode("utf-8")).hexdigest()[:8]
                placeholder = f"[REDACTED:{secret_type}:{digest8}]"
                start, end = m.span(1 if m.groups() else 0)
                res = res[:start] + placeholder + res[end:]
                count += 1
    return res, count


def sanitize_exploitability_language(text: str | None) -> str | None:
    """Replace forbidden exploitability claims with compliant phrasing for E0/E1 (AGENTS.md §5.7)."""
    if not text:
        return text

    def _replace(m: re.Match[str]) -> str:
        word = m.group(1).lower()
        if word in ("vulnerable", "exploitable"):
            return "potentially unprotected"
        if word == "vulnerability":
            return "potential security gap"
        if word == "exploit":
            return "bypass"
        return "unverified gap"

    return _EXPLOITABILITY_RE.sub(_replace, text)


# ---------------------------------------------------------------------------
# Data Models (docs/05 §7, docs/03 §3.4)
# ---------------------------------------------------------------------------


class EvidenceItem(BaseModel):
    """Machine-checkable evidence item supporting a finding."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    path: str
    start_line: int
    end_line: int
    snippet_hash: str
    snippet_text: str | None = None
    file_version_id: str | None = None
    role: str = "primary"  # primary | supporting | missing_check
    detail: dict[str, Any] = Field(default_factory=dict)
    is_current: bool = True


class FindingVerificationResult(BaseModel):
    """Evaluation result from deterministic evidence verification."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    draft_id: str
    status: str  # verified | downgraded | rejected
    original_level: str  # E0 | E1 | E2 | E3
    verified_level: str  # E0 | E1 | E2
    is_verified: bool
    evidence_score: float = 1.0
    confidence: float = 0.9
    rejection_reasons: list[str] = Field(default_factory=list)
    downgrade_reasons: list[str] = Field(default_factory=list)
    sanitized_evidence: list[EvidenceItem] = Field(default_factory=list)
    resolution_notes: str | None = None
    title: str | None = None
    summary: str | None = None
    explanation: str | None = None
    file_path: str | None = None
    line_range: tuple[int, int] | None = None
    rule_id: str | None = None
    citation_ref: str | None = None


@dataclass
class CitationItem:
    """A citation verified against snapshot files and symbols."""

    raw_citation: str
    path: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    symbol_key: str | None = None
    doc_id: str | None = None
    resolved: bool = False
    error_reason: str | None = None

    def to_citation_string(self) -> str:
        if self.path and self.start_line and self.end_line:
            return f"{self.path}:{self.start_line}-{self.end_line}"
        if self.path:
            return self.path
        if self.symbol_key:
            return self.symbol_key
        return self.raw_citation


class CitationBatchVerificationResult(BaseModel):
    """Batch citation verification outcome."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    total_citations: int
    resolved_citations: list[CitationItem] = Field(default_factory=list)
    unresolved_citations: list[CitationItem] = Field(default_factory=list)
    grounding_ratio: float = 1.0
    is_fully_grounded: bool = True
    feedback_message: str | None = None


# ---------------------------------------------------------------------------
# Citation Verifier
# ---------------------------------------------------------------------------


class CitationVerifier:
    """Deterministic citation verification engine (docs/04 §8.7, docs/05 §6.1)."""

    def __init__(
        self,
        available_files: set[str] | None = None,
        file_line_counts: dict[str, int] | None = None,
        available_symbols: set[str] | None = None,
        available_chunks: set[str] | None = None,
    ) -> None:
        self.available_files = available_files or set()
        self.file_line_counts = file_line_counts or {}
        self.available_symbols = available_symbols or set()
        self.available_chunks = available_chunks or set()

    def verify_single(self, raw: str) -> CitationItem:
        """Verify a single citation against snapshot files, symbols, and chunks."""
        clean = raw.strip().strip("[]()").strip()
        if clean.lower().startswith("source:"):
            clean = clean[7:].strip()

        if not clean:
            return CitationItem(raw_citation=raw, resolved=False, error_reason="Empty citation")

        # 1. Match chunk doc_id
        if clean in self.available_chunks:
            return CitationItem(raw_citation=raw, doc_id=clean, resolved=True)

        # 2. Match symbol name
        if clean in self.available_symbols:
            return CitationItem(raw_citation=raw, symbol_key=clean, resolved=True)

        # 3. Match path with line range: path:start-end or path:line
        if ":" in clean:
            path_part, line_part = clean.split(":", 1)
            path_part = path_part.strip()
            line_part = line_part.strip()

            # Resolve path part
            resolved_path = self._resolve_file_path(path_part)
            if not resolved_path:
                return CitationItem(
                    raw_citation=raw,
                    path=path_part,
                    resolved=False,
                    error_reason=f"File path '{path_part}' not found in snapshot",
                )

            max_lines = self.file_line_counts.get(resolved_path)

            if "-" in line_part:
                parts = line_part.split("-", 1)
                try:
                    s_line, e_line = int(parts[0]), int(parts[1])
                    if s_line <= 0:
                        return CitationItem(
                            raw_citation=raw,
                            path=resolved_path,
                            resolved=False,
                            error_reason=f"Start line must be >= 1 (got {s_line})",
                        )
                    if e_line < s_line:
                        return CitationItem(
                            raw_citation=raw,
                            path=resolved_path,
                            resolved=False,
                            error_reason=f"End line ({e_line}) < start line ({s_line})",
                        )
                    if max_lines and e_line > max_lines:
                        return CitationItem(
                            raw_citation=raw,
                            path=resolved_path,
                            resolved=False,
                            error_reason=f"Line range {s_line}-{e_line} exceeds file length ({max_lines} lines)",
                        )
                    return CitationItem(
                        raw_citation=raw,
                        path=resolved_path,
                        start_line=s_line,
                        end_line=e_line,
                        resolved=True,
                    )
                except ValueError:
                    return CitationItem(
                        raw_citation=raw,
                        path=resolved_path,
                        resolved=False,
                        error_reason=f"Invalid line range syntax: '{line_part}'",
                    )
            else:
                try:
                    line_num = int(line_part)
                    if line_num <= 0:
                        return CitationItem(
                            raw_citation=raw,
                            path=resolved_path,
                            resolved=False,
                            error_reason=f"Line number must be >= 1 (got {line_num})",
                        )
                    if max_lines and line_num > max_lines:
                        return CitationItem(
                            raw_citation=raw,
                            path=resolved_path,
                            resolved=False,
                            error_reason=f"Line number {line_num} exceeds file length ({max_lines} lines)",
                        )
                    return CitationItem(
                        raw_citation=raw,
                        path=resolved_path,
                        start_line=line_num,
                        end_line=line_num,
                        resolved=True,
                    )
                except ValueError:
                    return CitationItem(
                        raw_citation=raw,
                        path=resolved_path,
                        resolved=False,
                        error_reason=f"Invalid line syntax: '{line_part}'",
                    )

        # 4. Match file path directly
        resolved_path = self._resolve_file_path(clean)
        if resolved_path:
            return CitationItem(raw_citation=raw, path=resolved_path, resolved=True)

        return CitationItem(
            raw_citation=raw,
            resolved=False,
            error_reason=f"Citation '{clean}' does not match any file, symbol, or chunk",
        )

    def _resolve_file_path(self, path: str) -> str | None:
        """Find matching snapshot file path allowing relative suffixes."""
        if path in self.available_files:
            return path
        # Normalize slashes
        norm = path.replace("\\", "/").strip().lstrip("./")
        if norm in self.available_files:
            return norm
        for f in self.available_files:
            if f.endswith(norm) or f.endswith(f"/{norm}"):
                return f
        return None

    def verify_batch(
        self,
        citations: list[str],
        text_content: str | None = None,
    ) -> CitationBatchVerificationResult:
        """Extract and verify all citations from explicit list and text body."""
        extracted: list[str] = list(citations)
        if text_content:
            for match in _CITATION_INLINE_RE.finditer(text_content):
                val = next((g for g in match.groups() if g), None)
                if val and val not in extracted:
                    extracted.append(val)

        if not extracted:
            return CitationBatchVerificationResult(
                total_citations=0,
                resolved_citations=[],
                unresolved_citations=[],
                grounding_ratio=1.0,
                is_fully_grounded=True,
            )

        resolved: list[CitationItem] = []
        unresolved: list[CitationItem] = []

        for raw in extracted:
            item = self.verify_single(raw)
            if item.resolved:
                resolved.append(item)
            else:
                unresolved.append(item)

        total = len(extracted)
        ratio = len(resolved) / total if total > 0 else 1.0
        is_grounded = len(unresolved) == 0

        feedback = None
        if not is_grounded:
            issues = [f"{u.raw_citation} ({u.error_reason})" for u in unresolved]
            feedback = f"Unresolved citations detected: {', '.join(issues)}."

        return CitationBatchVerificationResult(
            total_citations=total,
            resolved_citations=resolved,
            unresolved_citations=unresolved,
            grounding_ratio=ratio,
            is_fully_grounded=is_grounded,
            feedback_message=feedback,
        )


# ---------------------------------------------------------------------------
# Deterministic Evidence Verifier (docs/05 §7)
# ---------------------------------------------------------------------------


class EvidenceVerifier:
    """Deterministic evidence verification engine executing all 7 checks from docs/05 §7."""

    def __init__(
        self,
        file_snapshot: dict[str, str] | None = None,
        file_versions: dict[str, str] | None = None,
        route_analyzer: RouteGuardAnalyzer | None = None,
        route_evaluations: list[RouteSecurityEvaluation]
        | dict[str, RouteSecurityEvaluation]
        | None = None,
        available_symbols: set[str] | None = None,
    ) -> None:
        self.file_snapshot = file_snapshot or {}
        self.file_versions = file_versions or {}
        self.route_analyzer = route_analyzer
        self.available_symbols = available_symbols or set()

        self.route_evaluations: dict[str, RouteSecurityEvaluation] = {}
        if route_evaluations:
            if isinstance(route_evaluations, dict):
                self.route_evaluations = dict(route_evaluations)
            elif isinstance(route_evaluations, list):
                self.route_evaluations = {e.route.symbol_key: e for e in route_evaluations}

        # Compute line counts for fast bounds checking
        self.file_line_counts: dict[str, int] = {
            p: len(content.splitlines()) if content else 0
            for p, content in self.file_snapshot.items()
        }

        # Initialize citation verifier
        self.citation_verifier = CitationVerifier(
            available_files=set(self.file_snapshot.keys()),
            file_line_counts=self.file_line_counts,
            available_symbols=self.available_symbols,
        )

    def verify_draft_finding(
        self,
        draft: Any,
    ) -> FindingVerificationResult:
        """Execute deterministic verification on a single draft finding."""
        # Normalize draft attributes from AnalyzerDraftFinding, Orchestration DraftFinding, or dict
        d_id = getattr(draft, "draft_id", None) or getattr(
            draft, "canonical_identifier", "draft_unknown"
        )
        rule_id = getattr(draft, "rule_id", "")
        file_path = getattr(draft, "file_path", "")
        line_range = getattr(draft, "line_range", None)
        if line_range is None and hasattr(draft, "start_line") and hasattr(draft, "end_line"):
            line_range = (draft.start_line, draft.end_line)
        elif isinstance(draft, dict):
            d_id = draft.get("draft_id", draft.get("canonical_identifier", "draft_unknown"))
            rule_id = draft.get("rule_id", "")
            file_path = draft.get("file_path", draft.get("location", {}).get("path", ""))
            if "line_range" in draft:
                line_range = tuple(draft["line_range"])
            elif "start_line" in draft and "end_line" in draft:
                line_range = (draft["start_line"], draft["end_line"])
            elif "location" in draft:
                loc = draft["location"]
                line_range = (loc.get("start_line", 0), loc.get("end_line", 0))

        raw_level = getattr(draft, "evidence_level", None)
        if raw_level is None and isinstance(draft, dict):
            raw_level = draft.get("evidence_level", "E2")
        if raw_level is None:
            raw_level = "E2"
        if isinstance(raw_level, int):
            raw_level = f"E{raw_level}"
        original_level = str(raw_level).upper()

        title = getattr(draft, "title", None) or (
            draft.get("title") if isinstance(draft, dict) else None
        )
        summary = getattr(draft, "summary", None) or (
            draft.get("summary") if isinstance(draft, dict) else None
        )
        explanation = getattr(draft, "explanation", None) or (
            draft.get("explanation") if isinstance(draft, dict) else None
        )

        evidence_details = getattr(draft, "evidence_details", {}) or (
            draft.get("evidence_details", {}) if isinstance(draft, dict) else {}
        )

        rejections: list[str] = []
        downgrades: list[str] = []

        # -------------------------------------------------------------------
        # Check 4: Rule ID Check (docs/05 §7)
        # -------------------------------------------------------------------
        if not is_known_rule(rule_id):
            rejections.append(f"Rule ID '{rule_id}' is unknown in DevMind registry.")

        # -------------------------------------------------------------------
        # Check 1: File and Version Check (docs/05 §7)
        # -------------------------------------------------------------------
        if not file_path:
            rejections.append("Missing file path in draft finding.")
        elif self.file_snapshot and file_path not in self.file_snapshot:
            # Check relative suffix match
            resolved_p = self.citation_verifier._resolve_file_path(file_path)
            if not resolved_p:
                rejections.append(f"File '{file_path}' is not present in the repository snapshot.")
            else:
                file_path = resolved_p

        cited_version = getattr(draft, "file_version_id", None) or (
            draft.get("file_version_id") if isinstance(draft, dict) else None
        )
        if cited_version and file_path in self.file_versions:
            expected_ver = self.file_versions[file_path]
            if cited_version != expected_ver:
                rejections.append(
                    f"Cited file version '{cited_version}' does not match snapshot version '{expected_ver}'."
                )

        # -------------------------------------------------------------------
        # Check 2: Line Range Integrity (docs/05 §7)
        # -------------------------------------------------------------------
        s_line, e_line = (0, 0)
        if not line_range or len(line_range) != 2:
            rejections.append(f"Invalid or missing line range: {line_range}.")
        else:
            s_line, e_line = line_range
            if s_line <= 0:
                rejections.append(f"Line range start must be >= 1 (got {s_line}).")
            if e_line < s_line:
                rejections.append(
                    f"Line range end ({e_line}) cannot be less than start ({s_line})."
                )

            if file_path in self.file_line_counts:
                max_lines = self.file_line_counts[file_path]
                if e_line > max_lines:
                    rejections.append(
                        f"Line range {s_line}-{e_line} is outside file bounds (total file lines: {max_lines})."
                    )

        # Extract cited lines from snapshot if available
        snippet_text: str | None = None
        if not rejections and file_path in self.file_snapshot and s_line > 0 and e_line >= s_line:
            all_lines = self.file_snapshot[file_path].splitlines()
            slice_lines = all_lines[s_line - 1 : e_line]
            snippet_text = "\n".join(slice_lines)

        # -------------------------------------------------------------------
        # Check 3: Snippet Hash Confirmation (docs/05 §7)
        # -------------------------------------------------------------------
        cited_hash = (
            evidence_details.get("snippet_hash") if isinstance(evidence_details, dict) else None
        )
        if not cited_hash and hasattr(draft, "snippet_hash"):
            cited_hash = draft.snippet_hash

        if cited_hash:
            if snippet_text is not None:
                computed_hash = compute_snippet_hash(snippet_text)
                if computed_hash != cited_hash:
                    # Try stripped lines normalization
                    stripped_hash = hashlib.sha256(
                        "\n".join(
                            line_item.strip() for line_item in snippet_text.splitlines()
                        ).encode("utf-8")
                    ).hexdigest()
                    if stripped_hash != cited_hash:
                        rejections.append(
                            f"Snippet hash mismatch: computed '{computed_hash}' != cited '{cited_hash}'."
                        )
            else:
                # If file content is not provided, rely on raw snippet if present in draft
                raw_snippet = getattr(draft, "evidence_snippet", None)
                if raw_snippet:
                    if compute_snippet_hash(raw_snippet) != cited_hash:
                        rejections.append("Snippet hash mismatch against provided snippet.")

        # -------------------------------------------------------------------
        # Check 5: Structural Claim Verification (docs/05 §7)
        # -------------------------------------------------------------------
        if rule_id in ("devmind.authn.unprotected_route", "devmind.authz.missing_role_check"):
            route_sym = evidence_details.get("route_symbol_key")
            matching_eval: RouteSecurityEvaluation | None = None
            if route_sym and route_sym in self.route_evaluations:
                matching_eval = self.route_evaluations[route_sym]

            if matching_eval:
                if matching_eval.status in ("protected", "public_exempt"):
                    rejections.append(
                        f"Structural claim failed: route is actually {matching_eval.status}."
                    )

        # -------------------------------------------------------------------
        # Check 6: Evidence Level Verification and Downgrade (docs/05 §7, ADR-041)
        # -------------------------------------------------------------------
        target_level = original_level
        if target_level == "E3":
            # E3 exploitability is explicitly prohibited in v1
            target_level = "E2"
            downgrades.append(
                "E3 exploitability findings are disabled in v1 (ADR-041); downgraded to E2."
            )

        if target_level == "E2":
            # Check for unresolved dependencies in analysis_scope
            scope = str(evidence_details.get("analysis_scope", "")).lower()
            unresolved = evidence_details.get("unresolved_dependencies", [])
            is_fully_resolved = evidence_details.get("is_fully_resolved", True)

            has_unresolved = False
            if unresolved or not is_fully_resolved:
                has_unresolved = True
            elif "dynamic" in scope:
                has_unresolved = True
            elif "unresolved: " in scope or ("unresolved" in scope and "0 unresolved" not in scope):
                has_unresolved = True

            if has_unresolved:
                target_level = "E1"
                downgrades.append(
                    "Claims E2 but analysis scope contains unresolved dependencies or dynamic callees; downgraded to E1."
                )

        # -------------------------------------------------------------------
        # Check 7: Secrets in Evidence Check & Redaction (docs/05 §7, docs/07 §6)
        # -------------------------------------------------------------------
        sanitized_snippet = snippet_text
        if sanitized_snippet:
            sanitized_snippet, redacted_count = redact_evidence_secrets(sanitized_snippet)
            if redacted_count > 0:
                downgrades.append(
                    f"Redacted {redacted_count} sensitive credential(s) from evidence snippet."
                )

        # Sanitize language for E0/E1 (AGENTS.md §5.7)
        sanitized_title = title
        sanitized_summary = summary
        sanitized_explanation = explanation

        if target_level in ("E0", "E1"):
            clean_t = sanitize_exploitability_language(sanitized_title)
            clean_s = sanitize_exploitability_language(sanitized_summary)
            clean_e = sanitize_exploitability_language(sanitized_explanation)
            if (
                clean_t != sanitized_title
                or clean_s != sanitized_summary
                or clean_e != sanitized_explanation
            ):
                downgrades.append(
                    "Sanitized exploitability terminology for E0/E1 finding (AGENTS.md §5.7)."
                )
            sanitized_title = clean_t
            sanitized_summary = clean_s
            sanitized_explanation = clean_e

        # -------------------------------------------------------------------
        # Determine Outcome Status
        # -------------------------------------------------------------------
        if rejections:
            status = "rejected"
            is_verified = False
            evidence_score = 0.0
            confidence = 0.0
            verified_level = "E0"
            res_notes = f"Rejected: {'; '.join(rejections)}"
        elif downgrades:
            status = "downgraded"
            is_verified = True
            evidence_score = 0.8
            confidence = 0.85
            verified_level = target_level
            res_notes = f"Downgraded: {'; '.join(downgrades)}"
        else:
            status = "verified"
            is_verified = True
            evidence_score = 1.0
            confidence = 0.95
            verified_level = target_level
            res_notes = f"Verified with deterministic {verified_level} evidence."

        # Assemble sanitized machine-checkable evidence item
        sanitized_evidence: list[EvidenceItem] = []
        if is_verified and file_path and s_line > 0:
            item_hash = (
                compute_snippet_hash(sanitized_snippet) if sanitized_snippet else (cited_hash or "")
            )
            sanitized_evidence.append(
                EvidenceItem(
                    path=file_path,
                    start_line=s_line,
                    end_line=e_line,
                    snippet_hash=item_hash,
                    snippet_text=sanitized_snippet,
                    file_version_id=cited_version,
                    role="primary",
                    detail=evidence_details,
                    is_current=True,
                )
            )

        citation_ref = f"{file_path}:{s_line}-{e_line}" if file_path and s_line > 0 else None

        return FindingVerificationResult(
            draft_id=d_id,
            status=status,
            original_level=original_level,
            verified_level=verified_level,
            is_verified=is_verified,
            evidence_score=evidence_score,
            confidence=confidence,
            rejection_reasons=rejections,
            downgrade_reasons=downgrades,
            sanitized_evidence=sanitized_evidence,
            resolution_notes=res_notes,
            title=sanitized_title,
            summary=sanitized_summary,
            explanation=sanitized_explanation,
            file_path=file_path,
            line_range=(s_line, e_line) if s_line > 0 else None,
            rule_id=rule_id,
            citation_ref=citation_ref,
        )

    def verify_draft_findings(
        self,
        drafts: list[Any],
    ) -> tuple[list[FindingVerificationResult], list[FindingVerificationResult]]:
        """Verify a batch of draft findings.

        Returns:
            (accepted_results, rejected_results)
        """
        accepted: list[FindingVerificationResult] = []
        rejected: list[FindingVerificationResult] = []

        for draft in drafts:
            res = self.verify_draft_finding(draft)
            if res.is_verified:
                accepted.append(res)
            else:
                rejected.append(res)

        return accepted, rejected


# ---------------------------------------------------------------------------
# Convenience Functions
# ---------------------------------------------------------------------------


def verify_evidence(
    drafts: list[Any],
    file_snapshot: dict[str, str] | None = None,
    file_versions: dict[str, str] | None = None,
    route_analyzer: RouteGuardAnalyzer | None = None,
) -> tuple[list[FindingVerificationResult], list[FindingVerificationResult]]:
    """Execute evidence verification on draft findings."""
    verifier = EvidenceVerifier(
        file_snapshot=file_snapshot,
        file_versions=file_versions,
        route_analyzer=route_analyzer,
    )
    return verifier.verify_draft_findings(drafts)


def verify_citations(
    citations: list[str],
    available_files: set[str] | None = None,
    available_symbols: set[str] | None = None,
    file_line_counts: dict[str, int] | None = None,
    text_content: str | None = None,
) -> CitationBatchVerificationResult:
    """Verify citations against snapshot files and symbols."""
    verifier = CitationVerifier(
        available_files=available_files,
        available_symbols=available_symbols,
        file_line_counts=file_line_counts,
    )
    return verifier.verify_batch(citations, text_content=text_content)
