"""Environment Variable Name Checker for Deployment Diagnosis (docs/01 CAP-07, docs/07 §6).

Analyzes referenced environment variable names extracted from deployment crash logs
against declared configuration in .env.example, Pydantic settings, and environment dashboard
keys.

SECURITY GUARANTEE (docs/01 CAP-07, docs/07 §6, ADR-047):
Only handles variable *names* (keys). Never accepts, checks, parses, stores, or logs values.
"""

from __future__ import annotations

import difflib
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

# Regex to extract key names from .env or .env.example files
ENV_LINE_KEY_RX = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=", re.MULTILINE)
ENV_VAR_SIMPLE_KEY_RX = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*$", re.MULTILINE)


@dataclass
class EnvVarTypoCandidate:
    """A suspected typo or naming mismatch for an environment variable."""

    expected_name: str
    found_name: str
    similarity: float
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "expected_name": self.expected_name,
            "found_name": self.found_name,
            "similarity": round(self.similarity, 2),
            "description": self.description,
        }


@dataclass
class EnvVarCheckResult:
    """Result of validating environment variable names against declared schemas."""

    referenced_names: list[str] = field(default_factory=list)
    missing_required: list[str] = field(default_factory=list)
    referenced_missing: list[str] = field(default_factory=list)
    suspected_typos: list[EnvVarTypoCandidate] = field(default_factory=list)
    valid_configured: list[str] = field(default_factory=list)
    has_issues: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "referenced_names": self.referenced_names,
            "missing_required": self.missing_required,
            "referenced_missing": self.referenced_missing,
            "suspected_typos": [t.to_dict() for t in self.suspected_typos],
            "valid_configured": self.valid_configured,
            "has_issues": self.has_issues,
        }


class EnvVarChecker:
    """Validates deployment environment variable names without inspecting values."""

    @classmethod
    def parse_env_example(cls, content: str) -> set[str]:
        """Extract environment variable names from .env.example or template text.

        Strips comments and lines with only whitespace. Ignores values completely.
        """
        if not content:
            return set()

        names: set[str] = set()
        for line in content.splitlines():
            line_clean = line.strip()
            if not line_clean or line_clean.startswith("#"):
                continue

            # Strip trailing comments if any
            if "#" in line_clean:
                line_clean = line_clean.split("#", 1)[0].strip()

            m = ENV_LINE_KEY_RX.match(line_clean)
            if m:
                names.add(m.group(1).strip())
                continue

            m_simple = ENV_VAR_SIMPLE_KEY_RX.match(line_clean)
            if m_simple:
                names.add(m_simple.group(1).strip())

        return names

    @classmethod
    def find_close_matches(
        cls,
        target_name: str,
        candidates: Iterable[str],
        cutoff: float = 0.65,
    ) -> list[tuple[str, float]]:
        """Identify potential naming typos or casing differences using SequenceMatcher."""
        target_upper = target_name.upper()
        results: list[tuple[str, float]] = []

        for candidate in candidates:
            if candidate == target_name:
                continue

            cand_upper = candidate.upper()

            # Exact case mismatch (e.g. database_url vs DATABASE_URL)
            if target_upper == cand_upper and target_name != candidate:
                results.append((candidate, 0.95))
                continue

            # Normalized prefix/suffix check (e.g. DATABASE_URL vs DEVMIND_DATABASE_URL)
            if target_upper in cand_upper or cand_upper in target_upper:
                # High semantic relationship
                sim = max(
                    difflib.SequenceMatcher(None, target_upper, cand_upper).ratio(),
                    0.80,
                )
                results.append((candidate, sim))
                continue

            # Fuzzy string similarity
            ratio = difflib.SequenceMatcher(None, target_upper, cand_upper).ratio()
            if ratio >= cutoff:
                results.append((candidate, ratio))

        # Sort by similarity descending
        results.sort(key=lambda x: x[1], reverse=True)
        return results

    @classmethod
    def verify_environment_variables(
        cls,
        referenced_names: list[str],
        configured_names: list[str] | None = None,
        example_env_content: str | None = None,
        known_settings_keys: list[str] | None = None,
    ) -> EnvVarCheckResult:
        """Cross-check referenced env var names against configured platform keys and schemas.

        Args:
            referenced_names: Environment variable names identified in crash logs.
            configured_names: Optional list of variable names set in deployment dashboard (keys only).
            example_env_content: Optional text of .env.example from repository snapshot.
            known_settings_keys: Optional list of settings fields extracted from project code.

        Returns:
            EnvVarCheckResult with missing, typo, and valid classification.
        """
        declared_example_keys: set[str] = set()
        if example_env_content:
            declared_example_keys = cls.parse_env_example(example_env_content)

        declared_keys: set[str] = set(declared_example_keys)
        if known_settings_keys:
            declared_keys.update(known_settings_keys)

        configured_set = set(configured_names) if configured_names is not None else None

        missing_required: set[str] = set()
        referenced_missing: set[str] = set()
        suspected_typos: list[EnvVarTypoCandidate] = []
        valid_configured: set[str] = set()

        # 1. If configured names are known, check referenced variables against configured
        if configured_set is not None:
            for ref in referenced_names:
                if ref in configured_set:
                    valid_configured.add(ref)
                else:
                    referenced_missing.add(ref)
                    # Check for typos among configured keys
                    close_matches = cls.find_close_matches(ref, configured_set)
                    for match_name, sim in close_matches:
                        suspected_typos.append(
                            EnvVarTypoCandidate(
                                expected_name=ref,
                                found_name=match_name,
                                similarity=sim,
                                description=(
                                    f"Crash log referenced '{ref}', which is not configured, but similar "
                                    f"variable '{match_name}' was found in configuration."
                                ),
                            )
                        )
                    # Check for typos among declared template keys
                    if declared_keys and ref not in declared_keys:
                        for tmpl_name, sim in cls.find_close_matches(ref, declared_keys):
                            if not any(
                                (t.expected_name == tmpl_name and t.found_name == ref)
                                or (t.expected_name == ref and t.found_name == tmpl_name)
                                for t in suspected_typos
                            ):
                                suspected_typos.append(
                                    EnvVarTypoCandidate(
                                        expected_name=tmpl_name,
                                        found_name=ref,
                                        similarity=sim,
                                        description=(
                                            f"Crash log referenced '{ref}', which appears to be a typo of "
                                            f"template variable '{tmpl_name}'."
                                        ),
                                    )
                                )

            # Check declared example keys missing from configuration
            for declared in declared_keys:
                if declared not in configured_set:
                    missing_required.add(declared)
                    # Check if a similar key was configured under an alternate name
                    close_matches = cls.find_close_matches(declared, configured_set)
                    for match_name, sim in close_matches:
                        if not any(
                            t.expected_name == declared and t.found_name == match_name
                            for t in suspected_typos
                        ):
                            suspected_typos.append(
                                EnvVarTypoCandidate(
                                    expected_name=declared,
                                    found_name=match_name,
                                    similarity=sim,
                                    description=(
                                        f"Required setting '{declared}' is not configured, but "
                                        f"similar variable '{match_name}' is set."
                                    ),
                                )
                            )
        else:
            # When configured keys are not explicitly provided, cross-check referenced vs declared keys
            for ref in referenced_names:
                if declared_keys and ref not in declared_keys:
                    close_matches = cls.find_close_matches(ref, declared_keys)
                    for match_name, sim in close_matches:
                        suspected_typos.append(
                            EnvVarTypoCandidate(
                                expected_name=match_name,
                                found_name=ref,
                                similarity=sim,
                                description=(
                                    f"Log referenced '{ref}', but project schema defines '{match_name}'."
                                ),
                            )
                        )

        has_issues = bool(missing_required or referenced_missing or suspected_typos)

        return EnvVarCheckResult(
            referenced_names=sorted(referenced_names),
            missing_required=sorted(missing_required),
            referenced_missing=sorted(referenced_missing),
            suspected_typos=suspected_typos,
            valid_configured=sorted(valid_configured),
            has_issues=has_issues,
        )
