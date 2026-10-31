"""Deterministic documentation drift detector (docs/01 CAP-04, docs/05 §3, §6.7).

Compares parsed documentation references against ground-truth codebase elements (API routes,
code symbols, configuration keys, and file paths) to identify discrepancies without LLM hallucinations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.analysis.doc_parser import ParsedDocument


@dataclass(frozen=True)
class DriftCandidate:
    """An identified discrepancy between code and documentation."""

    kind: str
    doc_path: str
    target_route_path: str | None
    target_symbol_key: str | None
    line_number: int | None
    explanation: str
    proposed_remediation: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "doc_path": self.doc_path,
            "target_route_path": self.target_route_path,
            "target_symbol_key": self.target_symbol_key,
            "line_number": self.line_number,
            "explanation": self.explanation,
            "proposed_remediation": self.proposed_remediation,
        }


class DocDriftDetector:
    """Deterministic analyzer identifying drift items across project documentation and code."""

    @classmethod
    def detect_drift(
        cls,
        parsed_docs: list[ParsedDocument],
        known_routes: set[str],
        known_symbols: set[str] | None = None,
        known_files: set[str] | None = None,
        known_configs: set[str] | None = None,
    ) -> list[DriftCandidate]:
        """Detect all documentation drift items against active code ground-truth."""
        drift_items: list[DriftCandidate] = []
        symbols = known_symbols or set()
        files = known_files or set()
        configs = known_configs or set()

        # Build normalized lookup for routes across all documentation files
        documented_routes_by_path: dict[str, tuple[str, int]] = {}
        documented_route_paths: set[str] = set()

        for doc in parsed_docs:
            for route_ref in doc.referenced_routes:
                norm_p = cls._normalize_route_pattern(route_ref.path)
                documented_routes_by_path[norm_p] = (doc.path, route_ref.line_number)
                documented_route_paths.add(norm_p)

        # 1. Undocumented Routes (in code, missing in docs)
        # Primary documentation target is typically README or api docs
        primary_doc = parsed_docs[0].path if parsed_docs else "README.md"
        for code_route in sorted(known_routes):
            norm_code_route = cls._normalize_route_pattern(code_route)
            # Skip operational system endpoints like /api/v1 root
            if norm_code_route in ("/api/v1", "/api/v1/"):
                continue

            if norm_code_route not in documented_route_paths:
                drift_items.append(
                    DriftCandidate(
                        kind="undocumented_route",
                        doc_path=primary_doc,
                        target_route_path=code_route,
                        target_symbol_key=None,
                        line_number=None,
                        explanation=(
                            f"API route '{code_route}' is active in code but has no corresponding entry in project documentation."
                        ),
                        proposed_remediation=(
                            f"Document endpoint '{code_route}' with request/response schema and required permissions."
                        ),
                    )
                )

        # 2. Removed Routes (documented, missing in code)
        norm_known_routes = {cls._normalize_route_pattern(r) for r in known_routes}
        for doc in parsed_docs:
            for route_ref in doc.referenced_routes:
                norm_doc_route = cls._normalize_route_pattern(route_ref.path)
                if norm_doc_route not in norm_known_routes:
                    drift_items.append(
                        DriftCandidate(
                            kind="removed_route",
                            doc_path=doc.path,
                            target_route_path=route_ref.path,
                            target_symbol_key=None,
                            line_number=route_ref.line_number,
                            explanation=(
                                f"Route '{route_ref.path}' documented in '{doc.path}' (line {route_ref.line_number}) "
                                f"was removed, renamed, or no longer exists in current code."
                            ),
                            proposed_remediation=(
                                f"Remove or update obsolete reference to '{route_ref.path}' in '{doc.path}'."
                            ),
                        )
                    )

        # 3. Missing Symbols (code symbols cited in backticks that no longer exist)
        if symbols:
            for doc in parsed_docs:
                for sym_ref in doc.referenced_symbols:
                    # Focus on PascalCase classes or identifiers with underscore
                    s_name = sym_ref.symbol_name
                    if s_name.endswith(".py") or s_name.endswith(".ts") or s_name.endswith(".json"):
                        continue
                    # Check if symbol looks like a codebase type or function and is missing
                    if (s_name[0].isupper() or "_" in s_name) and s_name not in symbols:
                        drift_items.append(
                            DriftCandidate(
                                kind="missing_symbol",
                                doc_path=doc.path,
                                target_route_path=None,
                                target_symbol_key=s_name,
                                line_number=sym_ref.line_number,
                                explanation=(
                                    f"Symbol '{s_name}' cited in '{doc.path}' (line {sym_ref.line_number}) "
                                    f"was not found in project code symbols."
                                ),
                                proposed_remediation=(
                                    f"Update or remove outdated reference to symbol '{s_name}'."
                                ),
                            )
                        )

        # 4. Stale Section (sections referencing non-existent file paths)
        if files:
            file_ref_regex = re.compile(r"[`(]([a-zA-Z0-9_\-\./]+\.[a-zA-Z0-9]+)[`)]")
            for doc in parsed_docs:
                for sec in doc.sections:
                    for match in file_ref_regex.finditer(sec.content):
                        rel_path = match.group(1).lstrip("./")
                        # Only consider paths with directory separators or matching source extensions
                        if "/" in rel_path and rel_path.endswith(
                            (".py", ".ts", ".tsx", ".js", ".json", ".md")
                        ):
                            if rel_path not in files and not rel_path.startswith("http"):
                                drift_items.append(
                                    DriftCandidate(
                                        kind="stale_section",
                                        doc_path=doc.path,
                                        target_route_path=None,
                                        target_symbol_key=rel_path,
                                        line_number=sec.line_start,
                                        explanation=(
                                            f"Section '{sec.title}' in '{doc.path}' references file '{rel_path}' "
                                            f"which does not exist in the repository."
                                        ),
                                        proposed_remediation=(
                                            f"Update file path '{rel_path}' in section '{sec.title}'."
                                        ),
                                    )
                                )

        # 5. Missing Configuration Keys
        if configs:
            for doc in parsed_docs:
                for cfg_key in doc.referenced_configs:
                    if cfg_key.startswith("DEVMIND_") and cfg_key not in configs:
                        drift_items.append(
                            DriftCandidate(
                                kind="missing_config",
                                doc_path=doc.path,
                                target_route_path=None,
                                target_symbol_key=cfg_key,
                                line_number=None,
                                explanation=(
                                    f"Configuration key '{cfg_key}' cited in '{doc.path}' "
                                    f"is not defined in project settings."
                                ),
                                proposed_remediation=(
                                    f"Verify or remove '{cfg_key}' in '{doc.path}'."
                                ),
                            )
                        )

        return drift_items

    @staticmethod
    def _normalize_route_pattern(route_path: str) -> str:
        """Normalize path parameters e.g. /projects/{pid}/bugs -> /projects/{}/bugs for robust matching."""
        # Strip trailing slashes and normalize parameter names
        normalized = route_path.strip().rstrip("/")
        normalized = re.sub(r"\{[a-zA-Z0-9_]+\}", "{}", normalized)
        return normalized.lower()
