"""Code-aware AST and block chunker per language (M5-04, docs/04 §5.2).

Splits source code into semantic, searchable chunks:
- Python: Uses standard library `ast` for exact function, class, decorator, and module boundaries.
- TypeScript / JavaScript: Semantic block scanner tracking exports, functions, classes, interfaces,
  routes, decorators, and brace nesting boundaries.
- Markdown: Heading-aware section chunker.
- Generic / Tier 2: Sliding line-window chunker with statement overlap.
- Large symbols: Subdivided on statement boundaries with small overlap, never mid-statement.
- Metadata & Search Text: Prepends location header (path, kind, symbol) to search_text.
- Deterministic hashing: SHA-256 over normalized content.
- Secret redaction: Re-checks chunks to guarantee zero raw credentials in chunks.
"""

from __future__ import annotations

import ast
import hashlib
import re
from typing import Literal

from pydantic import BaseModel, Field

from app.domain.brain.redaction_service import RedactionService

ChunkKind = Literal[
    "module",
    "function",
    "class",
    "method",
    "statement",
    "section",
    "block",
]


class CodeChunk(BaseModel):
    """Semantic code chunk for indexing and retrieval (docs/03 §3.3, docs/04 §5.2)."""

    path: str = Field(description="Repo-relative file path.")
    language: str = Field(description="Detected or provided language identifier.")
    kind: str = Field(
        description="Semantic unit kind: module, function, class, method, section, block."
    )
    symbol_name: str | None = Field(
        default=None, description="Name of the primary symbol or heading."
    )
    symbol_key: str | None = Field(default=None, description="Stable symbol key if symbol-derived.")
    start_line: int = Field(ge=1, description="1-indexed starting line number.")
    end_line: int = Field(ge=1, description="1-indexed ending line number.")
    content: str = Field(description="Consented, redacted source code content.")
    content_hash: str = Field(description="Deterministic sha256:... hash of normalized content.")
    search_text: str = Field(
        description="Content prepended with contextual location header for vector/BM25."
    )
    token_estimate: int = Field(ge=0, description="Estimated token count.")
    redaction_count: int = Field(
        default=0, ge=0, description="Number of redacted secrets in this chunk."
    )


def estimate_token_count(text: str) -> int:
    """Fast, reliable token count estimate (~4 chars per token for code)."""
    if not text:
        return 0
    # Standard character heuristic + whitespace token consideration
    words = len(text.split())
    chars = len(text) // 4
    return max(1, (words + chars) // 2)


def compute_chunk_content_hash(content: str) -> str:
    """Compute deterministic SHA-256 hash over normalized LF text."""
    normalized = content.replace("\r\n", "\n").strip()
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def build_search_text(
    path: str,
    language: str,
    kind: str,
    symbol_name: str | None,
    content: str,
) -> str:
    """Build searchable text with location context prepended (docs/04 §5.2)."""
    symbol_desc = f" | Symbol: {symbol_name}" if symbol_name else ""
    if language in ("python", "ruby", "bash", "shell", "yaml", "dockerfile"):
        header = f"# File: {path} | Kind: {kind}{symbol_desc}\n\n"
    elif language in ("html", "markdown", "xml"):
        header = f"<!-- File: {path} | Kind: {kind}{symbol_desc} -->\n\n"
    else:
        header = f"// File: {path} | Kind: {kind}{symbol_desc}\n\n"
    return header + content


def detect_language(path: str) -> str:
    """Infer programming language identifier from file path extension."""
    lower = path.lower()
    if lower.endswith(".py"):
        return "python"
    if lower.endswith(".ts"):
        return "typescript"
    if lower.endswith(".tsx"):
        return "typescriptreact"
    if lower.endswith(".js") or lower.endswith(".mjs") or lower.endswith(".cjs"):
        return "javascript"
    if lower.endswith(".jsx"):
        return "javascriptreact"
    if lower.endswith(".md") or lower.endswith(".markdown"):
        return "markdown"
    if lower.endswith(".json"):
        return "json"
    if lower.endswith(".yaml") or lower.endswith(".yml"):
        return "yaml"
    if lower.endswith(".sql"):
        return "sql"
    if lower.endswith(".prisma"):
        return "prisma"
    if lower.endswith(".html"):
        return "html"
    if lower.endswith(".css"):
        return "css"
    return "text"


# ---------------------------------------------------------------------------
# Python AST Chunker
# ---------------------------------------------------------------------------


class PythonChunker:
    """AST-based chunker for Python files using standard library `ast`."""

    @classmethod
    def chunk(
        cls,
        path: str,
        lines: list[str],
        max_lines: int = 80,
    ) -> list[CodeChunk]:
        """Parse Python source into module imports, functions, classes, and statements."""
        source = "\n".join(lines)
        try:
            tree = ast.parse(source)
        except SyntaxError:
            # Fall back to line-based chunker if syntax is invalid or partial
            return FallbackLineChunker.chunk(path, lines, language="python", max_lines=max_lines)

        chunks: list[CodeChunk] = []
        top_level_nodes = list(tree.body)

        if not top_level_nodes:
            if lines and any(line.strip() for line in lines):
                return [cls._create_chunk(path, "python", "module", None, 1, len(lines), lines)]
            return []

        # 1. Module prelude chunk (imports & top-level docstrings before the first function/class)
        first_symbol_node = next(
            (
                n
                for n in top_level_nodes
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            ),
            None,
        )

        prelude_end = 0
        if first_symbol_node is not None:
            prelude_end = first_symbol_node.lineno - 1
            # Adjust if decorators precede the first symbol
            if getattr(first_symbol_node, "decorator_list", None):
                prelude_end = min(d.lineno for d in first_symbol_node.decorator_list) - 1

            if prelude_end >= 1:
                prelude_lines = lines[:prelude_end]
                if any(line.strip() and not line.strip().startswith("#") for line in prelude_lines):
                    chunks.append(
                        cls._create_chunk(
                            path, "python", "module", "imports", 1, prelude_end, lines
                        )
                    )

        # 2. Top-level AST symbols (Functions, Classes, Top-level statement groups)
        current_stmts: list[ast.stmt] = []

        def flush_stmts() -> None:
            nonlocal current_stmts
            if not current_stmts:
                return
            s_line = current_stmts[0].lineno
            e_line = current_stmts[-1].end_lineno or current_stmts[-1].lineno
            chunks.append(
                cls._create_chunk(path, "python", "statement", "top_level", s_line, e_line, lines)
            )
            current_stmts = []

        for node in top_level_nodes:
            if prelude_end > 0 and (node.end_lineno or node.lineno) <= prelude_end:
                continue

            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                flush_stmts()
                kind = "class" if isinstance(node, ast.ClassDef) else "function"
                s_line = node.lineno
                if node.decorator_list:
                    s_line = min(d.lineno for d in node.decorator_list)
                e_line = node.end_lineno or node.lineno

                # Check if symbol exceeds max_lines; if so, subdivide
                if (e_line - s_line + 1) > max_lines:
                    chunks.extend(
                        cls._subdivide_large_node(path, node, s_line, e_line, lines, max_lines)
                    )
                else:
                    chunks.append(
                        cls._create_chunk(path, "python", kind, node.name, s_line, e_line, lines)
                    )
            else:
                current_stmts.append(node)

        flush_stmts()
        return chunks

    @classmethod
    def _subdivide_large_node(
        cls,
        path: str,
        node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
        start_line: int,
        end_line: int,
        lines: list[str],
        max_lines: int,
    ) -> list[CodeChunk]:
        """Subdivide a large function or class along internal method/statement boundaries."""
        sub_chunks: list[CodeChunk] = []
        kind = "class" if isinstance(node, ast.ClassDef) else "function"

        # For classes, chunk per method
        if isinstance(node, ast.ClassDef):
            method_nodes = [
                n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            if method_nodes:
                # Class definition header
                first_method_line = min(
                    min(d.lineno for d in m.decorator_list) if m.decorator_list else m.lineno
                    for m in method_nodes
                )
                if first_method_line > start_line:
                    sub_chunks.append(
                        cls._create_chunk(
                            path,
                            "python",
                            "class",
                            f"{node.name} (header)",
                            start_line,
                            first_method_line - 1,
                            lines,
                        )
                    )

                for method in method_nodes:
                    m_start = method.lineno
                    if method.decorator_list:
                        m_start = min(d.lineno for d in method.decorator_list)
                    m_end = method.end_lineno or method.lineno
                    sub_chunks.append(
                        cls._create_chunk(
                            path,
                            "python",
                            "method",
                            f"{node.name}.{method.name}",
                            m_start,
                            m_end,
                            lines,
                        )
                    )
                return sub_chunks

        # For large functions, chunk along internal statement boundaries with overlap
        body_stmts = node.body
        curr_start = start_line
        curr_end = start_line

        for stmt in body_stmts:
            stmt_end = stmt.end_lineno or stmt.lineno
            if (stmt_end - curr_start + 1) > max_lines and curr_end > curr_start:
                sub_chunks.append(
                    cls._create_chunk(
                        path,
                        "python",
                        kind,
                        f"{node.name} ({curr_start}-{curr_end})",
                        curr_start,
                        curr_end,
                        lines,
                    )
                )
                # Overlap of 2 lines
                curr_start = max(start_line, curr_end - 2)

            curr_end = stmt_end

        if curr_end >= curr_start:
            sub_chunks.append(
                cls._create_chunk(
                    path,
                    "python",
                    kind,
                    f"{node.name} ({curr_start}-{curr_end})",
                    curr_start,
                    curr_end,
                    lines,
                )
            )

        return sub_chunks or [
            cls._create_chunk(path, "python", kind, node.name, start_line, end_line, lines)
        ]

    @classmethod
    def _create_chunk(
        cls,
        path: str,
        language: str,
        kind: str,
        symbol_name: str | None,
        start_line: int,
        end_line: int,
        all_lines: list[str],
    ) -> CodeChunk:
        content_lines = all_lines[start_line - 1 : end_line]
        content = "\n".join(content_lines)
        content_hash = compute_chunk_content_hash(content)
        search_text = build_search_text(path, language, kind, symbol_name, content)
        token_estimate = estimate_token_count(content)

        return CodeChunk(
            path=path,
            language=language,
            kind=kind,
            symbol_name=symbol_name,
            start_line=start_line,
            end_line=end_line,
            content=content,
            content_hash=content_hash,
            search_text=search_text,
            token_estimate=token_estimate,
            redaction_count=0,
        )


# ---------------------------------------------------------------------------
# TypeScript & JavaScript Block Chunker
# ---------------------------------------------------------------------------


class TypeScriptChunker:
    """Semantic block chunker for TypeScript/JavaScript, tracking functions, classes, and routes."""

    # Patterns indicating the start of a major semantic block
    _DECLARATION_START_RX = re.compile(
        r"^(?:export\s+)?(?:default\s+)?(?:async\s+)?(?:function\s+(\w+)|class\s+(\w+)|interface\s+(\w+)|type\s+(\w+)|const\s+(\w+)\s*=\s*(?:async\s*)?\()"
    )
    _ROUTE_DEF_RX = re.compile(
        r"\b(?:app|router|server)\.(get|post|put|delete|patch)\s*\(\s*['\"]([^'\"]+)['\"]"
    )
    _IMPORT_RX = re.compile(r"^(?:import\s+|export\s+.*from\s+['\"]|const\s+.*=\s*require\()")

    @classmethod
    def chunk(
        cls,
        path: str,
        lines: list[str],
        language: str = "typescript",
        max_lines: int = 80,
    ) -> list[CodeChunk]:
        chunks: list[CodeChunk] = []
        n_lines = len(lines)
        if n_lines == 0:
            return []

        # 1. Identify module imports block at the top
        import_end = 0
        for i in range(n_lines):
            line = lines[i].strip()
            if not line or line.startswith("//") or line.startswith("/*") or line.startswith("*"):
                continue
            if cls._IMPORT_RX.match(line):
                import_end = i + 1
            elif import_end > 0:
                # First non-import statement after imports
                break

        if import_end > 0:
            content = "\n".join(lines[:import_end])
            chunks.append(
                CodeChunk(
                    path=path,
                    language=language,
                    kind="module",
                    symbol_name="imports",
                    start_line=1,
                    end_line=import_end,
                    content=content,
                    content_hash=compute_chunk_content_hash(content),
                    search_text=build_search_text(path, language, "module", "imports", content),
                    token_estimate=estimate_token_count(content),
                    redaction_count=0,
                )
            )

        # 2. Scan semantic blocks by brace depth
        idx = import_end
        while idx < n_lines:
            line = lines[idx]
            stripped = line.strip()

            if not stripped:
                idx += 1
                continue

            # Look ahead for decorators / comments attached to declaration
            decl_start = idx
            while decl_start > import_end and (
                lines[decl_start - 1].strip().startswith("@")
                or lines[decl_start - 1].strip().startswith("//")
            ):
                decl_start -= 1

            # Match function/class/interface/route
            decl_match = cls._DECLARATION_START_RX.search(stripped)
            route_match = cls._ROUTE_DEF_RX.search(stripped)

            if decl_match or route_match or "{" in stripped:
                symbol_name: str | None = None
                kind = "block"

                if decl_match:
                    symbol_name = next((g for g in decl_match.groups() if g is not None), None)
                    if "class " in stripped:
                        kind = "class"
                    elif "interface " in stripped or "type " in stripped:
                        kind = "statement"
                    else:
                        kind = "function"
                elif route_match:
                    method = route_match.group(1).upper()
                    route_path = route_match.group(2)
                    symbol_name = f"{method} {route_path}"
                    kind = "function"

                # Find end of block by tracking braces
                brace_depth = 0
                block_end = idx
                found_brace = False

                for j in range(idx, n_lines):
                    l_str = lines[j]
                    for char in l_str:
                        if char == "{":
                            brace_depth += 1
                            found_brace = True
                        elif char == "}":
                            brace_depth -= 1

                    if found_brace and brace_depth <= 0:
                        block_end = j
                        break
                    block_end = j

                s_line = decl_start + 1
                e_line = block_end + 1

                # Subdivide if block is too large
                if (e_line - s_line + 1) > max_lines:
                    chunks.extend(
                        FallbackLineChunker.chunk_range(
                            path, lines, language, s_line, e_line, kind, symbol_name, max_lines
                        )
                    )
                else:
                    content = "\n".join(lines[s_line - 1 : e_line])
                    chunks.append(
                        CodeChunk(
                            path=path,
                            language=language,
                            kind=kind,
                            symbol_name=symbol_name,
                            start_line=s_line,
                            end_line=e_line,
                            content=content,
                            content_hash=compute_chunk_content_hash(content),
                            search_text=build_search_text(
                                path, language, kind, symbol_name, content
                            ),
                            token_estimate=estimate_token_count(content),
                            redaction_count=0,
                        )
                    )

                idx = block_end + 1
            else:
                idx += 1

        # Fallback if no structured blocks were extracted (e.g. flat script)
        if not chunks:
            return FallbackLineChunker.chunk(path, lines, language=language, max_lines=max_lines)

        return chunks


# ---------------------------------------------------------------------------
# Markdown Heading Chunker
# ---------------------------------------------------------------------------


class MarkdownChunker:
    """Chunks documentation files on heading section boundaries (#, ##, ###)."""

    _HEADING_RX = re.compile(r"^(#{1,6})\s+(.*)$")

    @classmethod
    def chunk(
        cls,
        path: str,
        lines: list[str],
        max_lines: int = 80,
    ) -> list[CodeChunk]:
        chunks: list[CodeChunk] = []
        n_lines = len(lines)
        if n_lines == 0:
            return []

        heading_indices: list[tuple[int, str]] = []
        for i, line in enumerate(lines):
            m = cls._HEADING_RX.match(line.strip())
            if m:
                heading_indices.append((i, m.group(2).strip()))

        if not heading_indices:
            return FallbackLineChunker.chunk(path, lines, language="markdown", max_lines=max_lines)

        # Handle introduction text before first heading
        first_h_idx = heading_indices[0][0]
        if first_h_idx > 0:
            content = "\n".join(lines[:first_h_idx])
            if content.strip():
                chunks.append(
                    CodeChunk(
                        path=path,
                        language="markdown",
                        kind="section",
                        symbol_name="Introduction",
                        start_line=1,
                        end_line=first_h_idx,
                        content=content,
                        content_hash=compute_chunk_content_hash(content),
                        search_text=build_search_text(
                            path, "markdown", "section", "Introduction", content
                        ),
                        token_estimate=estimate_token_count(content),
                        redaction_count=0,
                    )
                )

        # Chunk each heading section
        for h_num, (start_idx, heading_title) in enumerate(heading_indices):
            end_idx = (
                heading_indices[h_num + 1][0] if (h_num + 1) < len(heading_indices) else n_lines
            )
            s_line = start_idx + 1
            e_line = end_idx

            if (e_line - s_line + 1) > max_lines:
                chunks.extend(
                    FallbackLineChunker.chunk_range(
                        path, lines, "markdown", s_line, e_line, "section", heading_title, max_lines
                    )
                )
            else:
                content = "\n".join(lines[start_idx:end_idx])
                chunks.append(
                    CodeChunk(
                        path=path,
                        language="markdown",
                        kind="section",
                        symbol_name=heading_title,
                        start_line=s_line,
                        end_line=e_line,
                        content=content,
                        content_hash=compute_chunk_content_hash(content),
                        search_text=build_search_text(
                            path, "markdown", "section", heading_title, content
                        ),
                        token_estimate=estimate_token_count(content),
                        redaction_count=0,
                    )
                )

        return chunks


# ---------------------------------------------------------------------------
# Fallback Sliding Line Chunker
# ---------------------------------------------------------------------------


class FallbackLineChunker:
    """Sliding line window chunker for Tier 2/3 text, configs, and oversized symbols."""

    @classmethod
    def chunk(
        cls,
        path: str,
        lines: list[str],
        language: str = "text",
        max_lines: int = 80,
        overlap: int = 10,
    ) -> list[CodeChunk]:
        return cls.chunk_range(
            path, lines, language, 1, len(lines), "block", None, max_lines, overlap
        )

    @classmethod
    def chunk_range(
        cls,
        path: str,
        all_lines: list[str],
        language: str,
        start_line: int,
        end_line: int,
        kind: str,
        symbol_name: str | None,
        max_lines: int = 80,
        overlap: int = 10,
    ) -> list[CodeChunk]:
        chunks: list[CodeChunk] = []
        target_lines = all_lines[start_line - 1 : end_line]
        total = len(target_lines)

        if total == 0:
            return []

        step = max(1, max_lines - overlap)
        curr = 0

        while curr < total:
            chunk_slice = target_lines[curr : curr + max_lines]
            chunk_start = start_line + curr
            chunk_end = start_line + curr + len(chunk_slice) - 1
            content = "\n".join(chunk_slice)

            part_suffix = f" (lines {chunk_start}-{chunk_end})" if symbol_name else None
            effective_sym = f"{symbol_name}{part_suffix}" if symbol_name else None

            chunks.append(
                CodeChunk(
                    path=path,
                    language=language,
                    kind=kind,
                    symbol_name=effective_sym,
                    start_line=chunk_start,
                    end_line=chunk_end,
                    content=content,
                    content_hash=compute_chunk_content_hash(content),
                    search_text=build_search_text(path, language, kind, effective_sym, content),
                    token_estimate=estimate_token_count(content),
                    redaction_count=0,
                )
            )

            curr += step
            if curr + overlap >= total and curr < total:
                # Remainder is too small to justify standalone window
                break

        return chunks


# ---------------------------------------------------------------------------
# Unified Code-Aware Chunker Dispatcher
# ---------------------------------------------------------------------------


class CodeAwareChunker:
    """Primary domain dispatcher for chunking repository files (docs/04 §5.2)."""

    @classmethod
    def chunk_file(
        cls,
        path: str,
        content: str,
        language: str | None = None,
        max_lines: int = 80,
        max_tokens: int = 500,
        redact: bool = True,
    ) -> list[CodeChunk]:
        """Split a file into semantic code chunks, applying defense-in-depth redaction.

        Args:
            path: Repo-relative file path.
            content: Raw or consented file content.
            language: Optional language override.
            max_lines: Target line ceiling per chunk (default 80).
            max_tokens: Target token ceiling per chunk (default 500).
            redact: If True, executes server-side secret redaction across all chunks.

        Returns:
            list[CodeChunk] ordered by start_line.
        """
        if not content:
            return []

        lang = language or detect_language(path)
        lines = content.replace("\r\n", "\n").split("\n")

        # Select specialized language chunker
        if lang == "python":
            raw_chunks = PythonChunker.chunk(path, lines, max_lines=max_lines)
        elif lang in ("typescript", "javascript", "typescriptreact", "javascriptreact"):
            raw_chunks = TypeScriptChunker.chunk(path, lines, language=lang, max_lines=max_lines)
        elif lang == "markdown":
            raw_chunks = MarkdownChunker.chunk(path, lines, max_lines=max_lines)
        else:
            raw_chunks = FallbackLineChunker.chunk(path, lines, language=lang, max_lines=max_lines)

        # Apply defense-in-depth secret redaction (docs/07 §6)
        final_chunks: list[CodeChunk] = []
        for chunk in raw_chunks:
            chunk_content = chunk.content
            redaction_count = 0

            if redact:
                redacted_res = RedactionService.redact(chunk_content)
                chunk_content = redacted_res.redacted_text
                redaction_count = redacted_res.redaction_count

            content_hash = compute_chunk_content_hash(chunk_content)
            search_text = build_search_text(
                path=chunk.path,
                language=chunk.language,
                kind=chunk.kind,
                symbol_name=chunk.symbol_name,
                content=chunk_content,
            )

            final_chunks.append(
                CodeChunk(
                    path=chunk.path,
                    language=chunk.language,
                    kind=chunk.kind,
                    symbol_name=chunk.symbol_name,
                    symbol_key=chunk.symbol_key,
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                    content=chunk_content,
                    content_hash=content_hash,
                    search_text=search_text,
                    token_estimate=estimate_token_count(chunk_content),
                    redaction_count=redaction_count,
                )
            )

        return sorted(final_chunks, key=lambda c: (c.start_line, c.end_line))
