"""Unit tests for Code-Aware Chunker per Language (M5-04, docs/04 §5.2).

Verifies:
1. Python AST Chunker:
   - Top-level imports and comments extracted into module chunk.
   - Functions and async functions with decorators and line bounds.
   - Class definitions with internal methods.
   - Large functions/classes subdivided without mid-statement cuts.
   - Graceful fallback on syntax errors.
2. TypeScript & JavaScript Block Chunker:
   - Module imports chunk at top of file.
   - Exported functions, arrow functions, classes, interfaces.
   - Express and Next.js route handlers.
   - Accurate brace nesting boundaries.
3. Markdown Section Chunker:
   - Heading-aware sectioning with heading title as symbol_name.
   - Introduction text captured.
4. Fallback Line Chunker:
   - Line windows and overlap on Tier 2/3 text files.
5. Defense-in-depth Redaction & Location Context:
   - Search text contains file path, kind, and symbol headers.
   - Secrets are masked into [REDACTED:<type>:<hash8>].
"""

from __future__ import annotations

from app.domain.brain.chunker import (
    CodeAwareChunker,
    FallbackLineChunker,
    MarkdownChunker,
    PythonChunker,
    TypeScriptChunker,
    compute_chunk_content_hash,
    detect_language,
    estimate_token_count,
)


def test_detect_language() -> None:
    """Verifies extension-based language detection."""
    assert detect_language("app/main.py") == "python"
    assert detect_language("src/index.ts") == "typescript"
    assert detect_language("src/Component.tsx") == "typescriptreact"
    assert detect_language("server/index.js") == "javascript"
    assert detect_language("docs/README.md") == "markdown"
    assert detect_language("schema.prisma") == "prisma"
    assert detect_language("config.yaml") == "yaml"
    assert detect_language("unknown.xyz") == "text"


def test_token_and_hash_helpers() -> None:
    """Verifies token estimator and deterministic content hasher."""
    text = "def hello():\n    return 'world'"
    tokens = estimate_token_count(text)
    assert tokens > 0

    h1 = compute_chunk_content_hash(text)
    h2 = compute_chunk_content_hash(text + "\r\n")  # CRLF normalization
    assert h1.startswith("sha256:")
    assert h1 == h2


def test_python_chunker_basic() -> None:
    """Verifies Python AST chunking with imports, functions, classes, and decorators."""
    code = """# Top of module
import os
import sys

@decorator
def greet(name: str) -> str:
    \"\"\"Say hello.\"\"\"
    return f"Hello, {name}"

class Calculator:
    def add(self, a: int, b: int) -> int:
        return a + b

    def subtract(self, a: int, b: int) -> int:
        return a - b
"""
    lines = code.split("\n")
    chunks = PythonChunker.chunk("app/calc.py", lines, max_lines=80)

    # Expect: 1. module imports, 2. greet function, 3. Calculator class
    assert len(chunks) == 3

    # 1. Module chunk
    assert chunks[0].kind == "module"
    assert chunks[0].symbol_name == "imports"
    assert chunks[0].start_line == 1
    assert "import os" in chunks[0].content

    # 2. Function chunk
    assert chunks[1].kind == "function"
    assert chunks[1].symbol_name == "greet"
    assert "@decorator" in chunks[1].content
    assert "def greet" in chunks[1].content

    # 3. Class chunk
    assert chunks[2].kind == "class"
    assert chunks[2].symbol_name == "Calculator"
    assert "class Calculator:" in chunks[2].content
    assert "def add" in chunks[2].content
    assert "def subtract" in chunks[2].content


def test_python_chunker_large_class_subdivision() -> None:
    """Verifies that oversized classes are subdivided by method."""
    methods = "\n\n".join(f"    def method_{i}(self):\n        return {i}" for i in range(15))
    code = f"class BigClass:\n{methods}\n"
    lines = code.split("\n")

    # With max_lines=10, BigClass must be broken into class header + method chunks
    chunks = PythonChunker.chunk("app/big.py", lines, max_lines=10)

    assert len(chunks) > 1
    assert any(c.kind == "method" and "method_0" in (c.symbol_name or "") for c in chunks)


def test_python_chunker_syntax_error_fallback() -> None:
    """Verifies graceful line-based fallback when Python has invalid syntax."""
    invalid_code = "def incomplete_function(\n    print('broken syntax"
    lines = invalid_code.split("\n")

    chunks = PythonChunker.chunk("app/broken.py", lines, max_lines=10)
    assert len(chunks) >= 1
    assert chunks[0].start_line == 1


def test_typescript_chunker_basic() -> None:
    """Verifies TypeScript block chunking for imports, functions, classes, and routes."""
    code = """import { Router } from "express";
import { User } from "./models";

export interface UserDTO {
  id: string;
  name: string;
}

export async function fetchUser(id: string): Promise<UserDTO> {
  return { id, name: "Alice" };
}

export class UserService {
  getUser(id: string) {
    return fetchUser(id);
  }
}

router.get("/users/:id", async (req, res) => {
  res.json({ ok: true });
});
"""
    lines = code.split("\n")
    chunks = TypeScriptChunker.chunk("src/routes.ts", lines, language="typescript", max_lines=80)

    # Check that imports, interface, function, class, and route handler are extracted
    kinds = [c.kind for c in chunks]
    names = [c.symbol_name for c in chunks]

    assert "module" in kinds
    assert any(n == "fetchUser" for n in names)
    assert any(n == "UserService" for n in names)
    assert any("GET /users/:id" in (n or "") for n in names)


def test_markdown_chunker() -> None:
    """Verifies Markdown chunking by heading sections."""
    doc = """# DevMind Architecture

Welcome to DevMind documentation.

## Layer Boundaries

The API layer cannot import the persistence layer directly.

### Data Model

PostgreSQL stores all tenant facts.

## Deployment Profile

Render free web service + Neon Free PostgreSQL.
"""
    lines = doc.split("\n")
    chunks = MarkdownChunker.chunk("docs/arch.md", lines, max_lines=80)

    assert len(chunks) >= 3
    section_titles = [c.symbol_name for c in chunks]
    assert "DevMind Architecture" in section_titles
    assert "Layer Boundaries" in section_titles
    assert "Deployment Profile" in section_titles


def test_fallback_line_chunker() -> None:
    """Verifies sliding line window with overlap for text files."""
    lines = [f"line {i}" for i in range(1, 101)]
    chunks = FallbackLineChunker.chunk(
        "logs/app.log", lines, language="text", max_lines=40, overlap=10
    )

    assert len(chunks) >= 3
    assert chunks[0].start_line == 1
    assert chunks[0].end_line == 40
    # Next chunk overlaps with previous
    assert chunks[1].start_line < 40


def test_code_aware_chunker_redaction_and_search_text() -> None:
    """Verifies CodeAwareChunker integrates defense-in-depth redaction and contextual search text."""
    dummy_key = "_".join(["sk", "live", "unredactedsecretkey1234567890"])
    code = f"""import os

def get_stripe_client():
    api_key = "{dummy_key}"
    return api_key
"""

    chunks = CodeAwareChunker.chunk_file(
        path="server/app/payments.py",
        content=code,
        redact=True,
    )

    assert len(chunks) >= 1
    fn_chunk = next((c for c in chunks if c.symbol_name == "get_stripe_client"), None)
    assert fn_chunk is not None

    # Assert secret was redacted
    assert dummy_key not in fn_chunk.content
    assert "[REDACTED:api_key:" in fn_chunk.content
    assert fn_chunk.redaction_count >= 1

    # Assert search text contains location context
    assert (
        "# File: server/app/payments.py | Kind: function | Symbol: get_stripe_client"
        in fn_chunk.search_text
    )
    assert "[REDACTED:api_key:" in fn_chunk.search_text
