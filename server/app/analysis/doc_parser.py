"""Deterministic Markdown documentation parser (docs/01 CAP-04, docs/05 §3, §6.7).

Extracts structural sections, referenced HTTP routes, code symbols, and configuration keys
from documentation Markdown files without relying on LLM inference.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DocSection:
    """A heading-delimited section within a documentation document."""

    title: str
    level: int
    line_start: int
    line_end: int
    content: str


@dataclass(frozen=True)
class ExtractedRoute:
    """An HTTP endpoint pattern referenced within a document."""

    method: str | None
    path: str
    line_number: int


@dataclass(frozen=True)
class ExtractedSymbol:
    """A code symbol referenced within backticks or code blocks."""

    symbol_name: str
    line_number: int


@dataclass
class ParsedDocument:
    """Structured extraction of a parsed documentation file."""

    path: str
    title: str
    content_hash: str
    sections: list[DocSection] = field(default_factory=list)
    referenced_routes: list[ExtractedRoute] = field(default_factory=list)
    referenced_symbols: list[ExtractedSymbol] = field(default_factory=list)
    referenced_configs: list[str] = field(default_factory=list)

    def to_extracted_symbols_json(self) -> list[dict[str, Any]]:
        """Serialize extracted entities for persistence in JSONB."""
        records: list[dict[str, Any]] = []
        for r in self.referenced_routes:
            records.append(
                {
                    "type": "route",
                    "method": r.method,
                    "path": r.path,
                    "line": r.line_number,
                }
            )
        for s in self.referenced_symbols:
            records.append(
                {
                    "type": "symbol",
                    "name": s.symbol_name,
                    "line": s.line_number,
                }
            )
        for c in self.referenced_configs:
            records.append(
                {
                    "type": "config",
                    "key": c,
                }
            )
        return records


class DocParser:
    """Deterministic parser extracting sections, routes, and symbols from Markdown files."""

    # Matches HTTP methods + endpoint paths e.g. `GET /api/v1/projects` or `/api/v1/projects`
    _ROUTE_REGEX = re.compile(
        r"(?:(GET|POST|PUT|PATCH|DELETE)\s+)?(/api/v[0-9]+/[a-zA-Z0-9_\-\/{}:]+)",
        re.IGNORECASE,
    )

    # Matches code symbols in single backticks e.g. `UserService`, `login`, `AuthContext`
    _SYMBOL_REGEX = re.compile(r"`([A-Za-z_][A-Za-z0-9_]{2,}(?:\.[A-Za-z0-9_]+)?)`")

    # Matches environment keys like `DEVMIND_*` or all-caps config variables
    _CONFIG_REGEX = re.compile(r"\b([A-Z][A-Z0-9_]{3,})\b")

    # Common English words/keywords in backticks to filter out from symbols
    _SYMBOL_STOPWORDS = frozenset(
        {
            "true",
            "false",
            "null",
            "none",
            "string",
            "number",
            "boolean",
            "integer",
            "float",
            "object",
            "array",
            "dict",
            "list",
            "set",
            "tuple",
            "optional",
            "any",
            "void",
            "return",
            "import",
            "from",
            "export",
            "class",
            "def",
            "function",
            "const",
            "let",
            "var",
            "async",
            "await",
            "uuid",
            "json",
            "curl",
            "bash",
            "npm",
            "pnpm",
            "python",
            "git",
            "status",
            "ready",
        }
    )

    @classmethod
    def parse(cls, content: str, path: str = "README.md") -> ParsedDocument:
        """Parse raw Markdown content into a structured ParsedDocument."""
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        lines = content.splitlines()

        # 1. Extract title (first H1 `# Title` or fallback to basename)
        doc_title = cls._extract_title(lines, fallback=path.split("/")[-1])

        # 2. Extract sections
        sections = cls._extract_sections(lines)

        # 3. Extract routes, symbols, and configs
        routes: list[ExtractedRoute] = []
        symbols: list[ExtractedSymbol] = []
        configs_seen: set[str] = set()

        seen_route_signatures: set[str] = set()
        seen_symbols: set[str] = set()

        for line_idx, line in enumerate(lines, start=1):
            # Skip code fence lines themselves
            stripped = line.strip()
            if stripped.startswith("```"):
                continue

            # Route extraction
            for match in cls._ROUTE_REGEX.finditer(line):
                method = match.group(1).upper() if match.group(1) else None
                route_path = match.group(2).rstrip(").,;:\"'")
                # Canonicalize parameter braces e.g. {pid} -> {project_id} or keep normalized
                norm_sig = f"{method or '*'}:{route_path}"
                if norm_sig not in seen_route_signatures:
                    seen_route_signatures.add(norm_sig)
                    routes.append(
                        ExtractedRoute(method=method, path=route_path, line_number=line_idx)
                    )

            # Code symbol extraction
            for match in cls._SYMBOL_REGEX.finditer(line):
                sym = match.group(1).strip()
                if sym.lower() not in cls._SYMBOL_STOPWORDS and not sym.isdigit():
                    if sym not in seen_symbols:
                        seen_symbols.add(sym)
                        symbols.append(ExtractedSymbol(symbol_name=sym, line_number=line_idx))

            # Config key extraction
            for match in cls._CONFIG_REGEX.finditer(line):
                cfg = match.group(1).strip()
                if "_" in cfg and len(cfg) >= 5 and not cfg.startswith("HTTP_"):
                    configs_seen.add(cfg)

        return ParsedDocument(
            path=path,
            title=doc_title,
            content_hash=content_hash,
            sections=sections,
            referenced_routes=routes,
            referenced_symbols=symbols,
            referenced_configs=sorted(configs_seen),
        )

    @classmethod
    def _extract_title(cls, lines: list[str], fallback: str) -> str:
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("# "):
                title_text = stripped[2:].strip()
                # Clean markdown badges or trailing tokens
                title_text = re.sub(r"\[!\[.*?\]\(.*?\)\]\(.*?\)", "", title_text).strip()
                if title_text:
                    return title_text[:255]
        return fallback

    @classmethod
    def _extract_sections(cls, lines: list[str]) -> list[DocSection]:
        sections: list[DocSection] = []
        current_title: str = "Introduction"
        current_level: int = 1
        current_start: int = 1
        current_lines: list[str] = []

        header_regex = re.compile(r"^(#{1,6})\s+(.*)$")

        for line_idx, line in enumerate(lines, start=1):
            match = header_regex.match(line.strip())
            if match:
                # Flush existing section
                if current_lines:
                    sections.append(
                        DocSection(
                            title=current_title,
                            level=current_level,
                            line_start=current_start,
                            line_end=line_idx - 1,
                            content="\n".join(current_lines),
                        )
                    )
                current_level = len(match.group(1))
                current_title = match.group(2).strip()
                current_start = line_idx
                current_lines = [line]
            else:
                current_lines.append(line)

        if current_lines:
            sections.append(
                DocSection(
                    title=current_title,
                    level=current_level,
                    line_start=current_start,
                    line_end=len(lines),
                    content="\n".join(current_lines),
                )
            )

        return sections
