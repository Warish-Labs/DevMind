"""Deterministic ReviewBuddy checklist engine and structural rule analyzer (docs/01 CAP-05, docs/05 §6.4).

Per docs/05 §6.4:
- Evaluates project checklist rules across diffs and code files.
- Checks standard checklist categories:
  1. Input validation (require_validation)
  2. Error handling (require_error_handling)
  3. Authorization (require_auth)
  4. Testing (require_test)
  5. Documentation (require_docs)
  6. Custom pattern matching (pattern_forbidden, pattern_required, custom_regex)
- Strictly deterministic; emits located findings with exact line numbers, snippets, and evidence levels.
"""

from __future__ import annotations

import fnmatch
import hashlib
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DiffHunk(BaseModel):
    """Represents a parsed diff hunk with line mappings."""

    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: list[str] = Field(default_factory=list)


class ChangedFile(BaseModel):
    """Represents a changed file extracted from a diff or file list."""

    path: str
    old_path: str | None = None
    is_new: bool = False
    is_deleted: bool = False
    content: str | None = None
    hunks: list[DiffHunk] = Field(default_factory=list)
    added_line_numbers: list[int] = Field(default_factory=list)


class ReviewChecklistFinding(BaseModel):
    """Located finding emitted by ReviewBuddy checklist analyzer."""

    rule_id: str
    title: str
    category: str
    severity: str
    file_path: str
    start_line: int
    end_line: int
    message: str
    suggested_fix: str | None = None
    evidence_level: str = "E1"
    snippet: str = ""
    snippet_hash: str = ""

    model_config = ConfigDict(extra="ignore")


def parse_unified_diff(diff_text: str) -> list[ChangedFile]:
    """Parse unified diff text into structured ChangedFile instances."""
    if not diff_text or not diff_text.strip():
        return []

    files: list[ChangedFile] = []
    current_file: ChangedFile | None = None
    current_hunk: DiffHunk | None = None
    current_new_line = 0

    lines = diff_text.splitlines()
    for line in lines:
        if line.startswith("diff --git "):
            if current_file:
                if current_hunk:
                    current_file.hunks.append(current_hunk)
                    current_hunk = None
                files.append(current_file)

            parts = line.split()
            path_b = parts[3].lstrip("b/") if len(parts) >= 4 else "unknown"
            path_a = parts[2].lstrip("a/") if len(parts) >= 3 else path_b
            current_file = ChangedFile(path=path_b, old_path=path_a)
            current_hunk = None

        elif line.startswith("new file mode"):
            if current_file:
                current_file.is_new = True

        elif line.startswith("deleted file mode"):
            if current_file:
                current_file.is_deleted = True

        elif line.startswith("@@ ") and current_file:
            if current_hunk:
                current_file.hunks.append(current_hunk)

            # @@ -old_start,old_count +new_start,new_count @@
            match = re.match(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", line)
            if match:
                old_start = int(match.group(1))
                old_count = int(match.group(2) or 1)
                new_start = int(match.group(3))
                new_count = int(match.group(4) or 1)
                current_hunk = DiffHunk(
                    old_start=old_start,
                    old_count=old_count,
                    new_start=new_start,
                    new_count=new_count,
                )
                current_new_line = new_start

        elif current_hunk and current_file:
            current_hunk.lines.append(line)
            if line.startswith("+") and not line.startswith("+++"):
                current_file.added_line_numbers.append(current_new_line)
                current_new_line += 1
            elif line.startswith(" "):
                current_new_line += 1
            # lines starting with '-' do not advance current_new_line

    if current_file:
        if current_hunk:
            current_file.hunks.append(current_hunk)
        files.append(current_file)

    return files


class ReviewBuddyAnalyzer:
    """Deterministic checklist analyzer executing project review rules."""

    # Fast AST/regex detectors for route handlers and antipatterns
    _PY_ROUTE_RE = re.compile(
        r"@(?:router|app)\.(get|post|put|delete|patch|api_route)\s*\((.*?)\)",
        re.DOTALL,
    )
    _TS_ROUTE_RE = re.compile(
        r"(?:export\s+(?:async\s+)?function\s+(GET|POST|PUT|DELETE|PATCH)|router\.(get|post|put|delete|patch)\s*\()",
    )
    _MUTATING_METHODS = frozenset({"post", "put", "delete", "patch"})
    _AUTH_GUARDS = (
        "declare_permission",
        "require_permission",
        "require_role",
        "require_auth",
        "get_current_user",
        "AuthContext",
        "require_kill_switch_inactive",
    )

    def __init__(self, rules: list[dict[str, Any]] | None = None) -> None:
        self.rules = rules or []

    def evaluate_files(
        self,
        files: list[dict[str, Any]],
        known_test_files: set[str] | None = None,
    ) -> list[ReviewChecklistFinding]:
        """Evaluate given files against configured review rules.

        Each file dict must contain:
        - 'path': relative file path (e.g. 'server/app/api/users.py')
        - 'content': full string content of the file
        """
        findings: list[ReviewChecklistFinding] = []
        all_paths = {f["path"] for f in files} | (known_test_files or set())

        for file_info in files:
            file_path = file_info.get("path", "")
            content = file_info.get("content", "")
            if not file_path or not content:
                continue

            lines = content.splitlines()

            for rule in self.rules:
                if not rule.get("is_enabled", True):
                    continue

                if not self._matches_scope(file_path, rule.get("scope_selector", {})):
                    continue

                rule_findings = self._execute_check(
                    rule=rule,
                    file_path=file_path,
                    content=content,
                    lines=lines,
                    all_paths=all_paths,
                )
                findings.extend(rule_findings)

        return findings

    def evaluate_diff(
        self,
        diff_text: str,
        file_contents: dict[str, str] | None = None,
        known_test_files: set[str] | None = None,
    ) -> list[ReviewChecklistFinding]:
        """Evaluate unified diff against review rules, scoping checks to changed hunks."""
        changed_files = parse_unified_diff(diff_text)
        if not changed_files:
            return []

        files_to_eval: list[dict[str, Any]] = []
        for cf in changed_files:
            if cf.is_deleted:
                continue

            content = (file_contents or {}).get(cf.path)
            if not content:
                # Reconstruct added lines positioned at their original line numbers
                reconstructed_lines: dict[int, str] = {}
                for hunk in cf.hunks:
                    line_no = hunk.new_start
                    for hunk_line in hunk.lines:
                        if hunk_line.startswith("+") and not hunk_line.startswith("+++"):
                            reconstructed_lines[line_no] = hunk_line[1:]
                            line_no += 1
                        elif hunk_line.startswith(" "):
                            reconstructed_lines[line_no] = hunk_line[1:]
                            line_no += 1
                if reconstructed_lines:
                    max_line = max(reconstructed_lines.keys())
                    content = "\n".join(
                        reconstructed_lines.get(i, "") for i in range(1, max_line + 1)
                    )
                else:
                    content = ""

            files_to_eval.append({"path": cf.path, "content": content})

        all_findings = self.evaluate_files(files_to_eval, known_test_files=known_test_files)

        # Filter findings to changed lines when hunks are present
        filtered_findings: list[ReviewChecklistFinding] = []
        changed_lines_map = {cf.path: set(cf.added_line_numbers) for cf in changed_files}

        for f in all_findings:
            file_added_lines = changed_lines_map.get(f.file_path)
            if not file_added_lines:
                filtered_findings.append(f)
                continue

            # If rule touches line 1 (file-level checks like test coverage) or overlaps added lines
            if f.start_line == 1 or any(
                f.start_line <= line_no <= f.end_line for line_no in file_added_lines
            ):
                filtered_findings.append(f)

        return filtered_findings

    def _matches_scope(self, file_path: str, scope: dict[str, Any]) -> bool:
        """Evaluate glob path selectors and language filters."""
        paths = scope.get("paths", ["**/*"])
        ignore = scope.get("ignore", [])
        languages = scope.get("languages")

        # 1. Ignore patterns check
        for ign in ignore or []:
            if fnmatch.fnmatch(file_path, ign):
                return False

        # 2. Path glob matching
        matched_path = False
        for pattern in paths or ["**/*"]:
            if pattern == "**/*" or pattern == "*":
                matched_path = True
                break
            if fnmatch.fnmatch(file_path, pattern):
                matched_path = True
                break

        if not matched_path:
            return False

        # 3. Language check
        if languages:
            ext = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""
            lang_map = {
                "py": "python",
                "ts": "typescript",
                "tsx": "typescript",
                "js": "javascript",
                "jsx": "javascript",
            }
            file_lang = lang_map.get(ext)
            if file_lang and file_lang not in languages:
                return False

        return True

    def _execute_check(
        self,
        rule: dict[str, Any],
        file_path: str,
        content: str,
        lines: list[str],
        all_paths: set[str],
    ) -> list[ReviewChecklistFinding]:
        """Dispatch to check handler based on rule check_type."""
        check_type = rule.get("check_type")

        if check_type == "require_validation":
            return self._check_input_validation(rule, file_path, content, lines)
        elif check_type == "require_error_handling":
            return self._check_error_handling(rule, file_path, lines)
        elif check_type == "require_auth":
            return self._check_authorization(rule, file_path, content, lines)
        elif check_type == "require_test":
            return self._check_test_coverage(rule, file_path, all_paths)
        elif check_type == "require_docs":
            return self._check_documentation(rule, file_path, lines)
        elif check_type == "pattern_forbidden":
            return self._check_pattern_forbidden(rule, file_path, lines)
        elif check_type == "pattern_required":
            return self._check_pattern_required(rule, file_path, content, lines)
        elif check_type == "custom_regex":
            return self._check_custom_regex(rule, file_path, lines)

        return []

    def _check_input_validation(
        self,
        rule: dict[str, Any],
        file_path: str,
        content: str,
        lines: list[str],
    ) -> list[ReviewChecklistFinding]:
        """Detect route handlers accepting unvalidated parameters or request bodies."""
        findings: list[ReviewChecklistFinding] = []

        # Python route handlers
        if file_path.endswith(".py"):
            for idx, line in enumerate(lines):
                if any(
                    k in line
                    for k in (
                        "@router.post",
                        "@router.put",
                        "@router.patch",
                        "@app.post",
                        "@app.put",
                        "@app.patch",
                    )
                ):
                    # Check for unvalidated body read pattern: accepts Request but no Pydantic model
                    body_read_unvalidated = False
                    for k in range(idx + 1, min(len(lines), idx + 25)):
                        if (
                            "await request.json()" in lines[k]
                            and "validate" not in lines[k]
                            and "parse" not in lines[k]
                        ):
                            body_read_unvalidated = True
                            break

                    if body_read_unvalidated:
                        snippet = lines[idx].strip()
                        findings.append(
                            self._create_finding(
                                rule=rule,
                                file_path=file_path,
                                start_line=idx + 1,
                                end_line=idx + 1,
                                snippet=snippet,
                                message="Route reads raw request body with await request.json() without schema validation.",
                                suggested_fix="Declare a Pydantic BaseModel parameter in the route function signature.",
                            )
                        )

        # TypeScript/JavaScript handlers
        elif file_path.endswith((".ts", ".js")):
            for idx, line in enumerate(lines):
                if any(
                    k in line for k in ("router.post(", "router.put(", "router.patch(")
                ) or re.search(r"export\s+async\s+function\s+(POST|PUT|PATCH)", line):
                    # Check body reads in the next 20 lines
                    body_unvalidated = False
                    for k in range(idx, min(len(lines), idx + 20)):
                        if "await req.json()" in lines[k] or "req.body" in lines[k]:
                            # If no schema parser (e.g. zod .parse, .safeParse) is nearby
                            context_chunk = " ".join(lines[idx : min(len(lines), idx + 25)])
                            if not any(
                                v in context_chunk
                                for v in (".parse(", ".safeParse(", "validate(", "Schema")
                            ):
                                body_unvalidated = True
                                break

                    if body_unvalidated:
                        snippet = lines[idx].strip()
                        findings.append(
                            self._create_finding(
                                rule=rule,
                                file_path=file_path,
                                start_line=idx + 1,
                                end_line=idx + 1,
                                snippet=snippet,
                                message="Route accepts request payload without schema validation (e.g. Zod schema.parse).",
                                suggested_fix="Pass request payload through schema.parse() before accessing properties.",
                            )
                        )

        return findings

    def _check_error_handling(
        self,
        rule: dict[str, Any],
        file_path: str,
        lines: list[str],
    ) -> list[ReviewChecklistFinding]:
        """Detect bare excepts, empty catch blocks, or error silencing antipatterns."""
        findings: list[ReviewChecklistFinding] = []

        if file_path.endswith(".py"):
            for idx, line in enumerate(lines):
                stripped = line.strip()
                # Bare except:
                if (
                    stripped == "except:"
                    or stripped.startswith("except Exception: pass")
                    or stripped.startswith("except: pass")
                ):
                    snippet = lines[idx].strip()
                    findings.append(
                        self._create_finding(
                            rule=rule,
                            file_path=file_path,
                            start_line=idx + 1,
                            end_line=idx + 1,
                            snippet=snippet,
                            message="Bare except or silent exception swallowing detected.",
                            suggested_fix="Catch specific exception types and log or raise RFC 9457 structured errors.",
                        )
                    )
                # except Exception followed immediately by pass
                elif (
                    stripped == "except Exception:"
                    and idx + 1 < len(lines)
                    and lines[idx + 1].strip() == "pass"
                ):
                    snippet = f"{lines[idx].strip()} {lines[idx + 1].strip()}"
                    findings.append(
                        self._create_finding(
                            rule=rule,
                            file_path=file_path,
                            start_line=idx + 1,
                            end_line=idx + 2,
                            snippet=snippet,
                            message="Silent exception pass block detected without error recording.",
                            suggested_fix="Log the exception or re-raise an appropriate domain HTTP exception.",
                        )
                    )

        elif file_path.endswith((".ts", ".js")):
            for idx, line in enumerate(lines):
                stripped = line.strip()
                # Empty catch block: catch (e) {} or catch {}
                if re.search(r"catch\s*(?:\([^)]*\))?\s*\{\s*\}", stripped):
                    snippet = lines[idx].strip()
                    findings.append(
                        self._create_finding(
                            rule=rule,
                            file_path=file_path,
                            start_line=idx + 1,
                            end_line=idx + 1,
                            snippet=snippet,
                            message="Empty catch block detected; error is silenced without handling or logging.",
                            suggested_fix="Log error details or return an RFC 9457 problem response.",
                        )
                    )

        return findings

    def _check_authorization(
        self,
        rule: dict[str, Any],
        file_path: str,
        content: str,
        lines: list[str],
    ) -> list[ReviewChecklistFinding]:
        """Detect state-mutating endpoints lacking authorization guards or permission declarations."""
        findings: list[ReviewChecklistFinding] = []

        if not any(k in file_path for k in ("/api/", "/routes/", "/endpoints/")):
            return []

        if file_path.endswith(".py"):
            for idx, line in enumerate(lines):
                if any(
                    m in line
                    for m in ("@router.post", "@router.put", "@router.patch", "@router.delete")
                ):
                    # Inspect surrounding lines (up to 6 lines above and 6 lines below)
                    context_range = lines[max(0, idx - 5) : min(len(lines), idx + 8)]
                    context_text = "\n".join(context_range)

                    has_guard = any(guard in context_text for guard in self._AUTH_GUARDS)
                    if not has_guard:
                        snippet = lines[idx].strip()
                        findings.append(
                            self._create_finding(
                                rule=rule,
                                file_path=file_path,
                                start_line=idx + 1,
                                end_line=idx + 1,
                                snippet=snippet,
                                message="Mutating route definition lacks declared permission check (@declare_permission) or auth dependency.",
                                suggested_fix="Decorate endpoint with @declare_permission(PERM_...) or require AuthContext.",
                                evidence_level="E2",
                            )
                        )

        return findings

    def _check_test_coverage(
        self,
        rule: dict[str, Any],
        file_path: str,
        all_paths: set[str],
    ) -> list[ReviewChecklistFinding]:
        """Check whether newly declared API or domain services have associated test files."""
        # Only check core API or domain service files, exclude migrations, models, tests
        if any(
            ign in file_path for ign in ("tests/", "test_", "/alembic/", "/models/", "__init__")
        ):
            return []

        if not any(k in file_path for k in ("/api/", "/domain/", "/services/")):
            return []

        base_name = file_path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        test_patterns = [
            f"test_{base_name}",
            f"{base_name}_test",
            f"{base_name}.test",
            f"{base_name}.spec",
        ]

        has_test = any(any(pat in p for pat in test_patterns) for p in all_paths)
        if not has_test:
            return [
                self._create_finding(
                    rule=rule,
                    file_path=file_path,
                    start_line=1,
                    end_line=1,
                    snippet=f"# {file_path}",
                    message=f"No associated automated test module found for {base_name}.",
                    suggested_fix=f"Create a test suite in tests/test_{base_name}.py or {base_name}.test.ts.",
                )
            ]

        return []

    def _check_documentation(
        self,
        rule: dict[str, Any],
        file_path: str,
        lines: list[str],
    ) -> list[ReviewChecklistFinding]:
        """Check for docstrings or summaries on public API route functions."""
        findings: list[ReviewChecklistFinding] = []

        if not any(k in file_path for k in ("/api/", "/routes/")):
            return []

        if file_path.endswith(".py"):
            for idx, line in enumerate(lines):
                if line.strip().startswith("async def ") or line.strip().startswith("def "):
                    fn_name = (
                        line.strip()
                        .split("(")[0]
                        .replace("async def ", "")
                        .replace("def ", "")
                        .strip()
                    )
                    if fn_name.startswith("_"):
                        continue

                    # Look at next lines for docstring
                    has_doc = False
                    for k in range(idx + 1, min(len(lines), idx + 5)):
                        if '"""' in lines[k] or "'''" in lines[k]:
                            has_doc = True
                            break

                    if not has_doc:
                        # Check if route decorator has summary= or description=
                        above_lines = "\n".join(lines[max(0, idx - 6) : idx])
                        if "summary=" not in above_lines and "description=" not in above_lines:
                            snippet = line.strip()
                            findings.append(
                                self._create_finding(
                                    rule=rule,
                                    file_path=file_path,
                                    start_line=idx + 1,
                                    end_line=idx + 1,
                                    snippet=snippet,
                                    message=f"Public route handler '{fn_name}' has no docstring or OpenAPI summary.",
                                    suggested_fix="Add a summary string to the route decorator or docstring to the function.",
                                )
                            )

        return findings

    def _check_pattern_forbidden(
        self,
        rule: dict[str, Any],
        file_path: str,
        lines: list[str],
    ) -> list[ReviewChecklistFinding]:
        """Detect forbidden regex patterns."""
        findings: list[ReviewChecklistFinding] = []
        cfg = rule.get("check_config", {})
        patterns = cfg.get("patterns") or cfg.get("forbidden_patterns") or []

        for pat in patterns:
            try:
                regex = re.compile(pat)
            except Exception:
                continue

            for idx, line in enumerate(lines):
                if regex.search(line):
                    snippet = line.strip()
                    findings.append(
                        self._create_finding(
                            rule=rule,
                            file_path=file_path,
                            start_line=idx + 1,
                            end_line=idx + 1,
                            snippet=snippet,
                            message=rule.get("message") or f"Forbidden pattern '{pat}' detected.",
                            suggested_fix=rule.get("suggested_fix_template"),
                        )
                    )

        return findings

    def _check_pattern_required(
        self,
        rule: dict[str, Any],
        file_path: str,
        content: str,
        lines: list[str],
    ) -> list[ReviewChecklistFinding]:
        """Ensure required regex pattern is present in target file."""
        cfg = rule.get("check_config", {})
        pat = cfg.get("pattern") or cfg.get("required_pattern")
        if not pat:
            return []

        try:
            regex = re.compile(pat)
        except Exception:
            return []

        if not regex.search(content):
            snippet = lines[0].strip() if lines else ""
            return [
                self._create_finding(
                    rule=rule,
                    file_path=file_path,
                    start_line=1,
                    end_line=1,
                    snippet=snippet,
                    message=rule.get("message")
                    or f"Required pattern '{pat}' was not found in file.",
                    suggested_fix=rule.get("suggested_fix_template"),
                )
            ]

        return []

    def _check_custom_regex(
        self,
        rule: dict[str, Any],
        file_path: str,
        lines: list[str],
    ) -> list[ReviewChecklistFinding]:
        """Evaluate custom regex in must_match or must_not_match mode."""
        findings: list[ReviewChecklistFinding] = []
        cfg = rule.get("check_config", {})
        regex_str = cfg.get("regex")
        mode = cfg.get("mode", "must_not_match")

        if not regex_str:
            return []

        try:
            regex = re.compile(regex_str)
        except Exception:
            return []

        if mode == "must_not_match":
            for idx, line in enumerate(lines):
                if regex.search(line):
                    findings.append(
                        self._create_finding(
                            rule=rule,
                            file_path=file_path,
                            start_line=idx + 1,
                            end_line=idx + 1,
                            snippet=line.strip(),
                            message=rule.get("message")
                            or f"Line matched forbidden regex '{regex_str}'.",
                            suggested_fix=rule.get("suggested_fix_template"),
                        )
                    )
        elif mode == "must_match":
            full_content = "\n".join(lines)
            if not regex.search(full_content):
                findings.append(
                    self._create_finding(
                        rule=rule,
                        file_path=file_path,
                        start_line=1,
                        end_line=1,
                        snippet=lines[0].strip() if lines else "",
                        message=rule.get("message")
                        or f"File did not match required regex '{regex_str}'.",
                        suggested_fix=rule.get("suggested_fix_template"),
                    )
                )

        return findings

    def _create_finding(
        self,
        rule: dict[str, Any],
        file_path: str,
        start_line: int,
        end_line: int,
        snippet: str,
        message: str,
        suggested_fix: str | None = None,
        evidence_level: str | None = None,
    ) -> ReviewChecklistFinding:
        """Helper to instantiate finding with deterministic hash."""
        rule_id = rule.get("rule_id", "REV-001")
        title = rule.get("title", "Review Checklist Item")
        category = rule.get("category", "quality")
        severity = rule.get("severity", "medium")
        level = evidence_level or rule.get("evidence_level", "E1")

        snippet_hash = hashlib.sha256(snippet.encode("utf-8")).hexdigest()

        return ReviewChecklistFinding(
            rule_id=rule_id,
            title=title,
            category=category,
            severity=severity,
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            message=message,
            suggested_fix=suggested_fix or rule.get("suggested_fix_template"),
            evidence_level=level,
            snippet=snippet,
            snippet_hash=snippet_hash,
        )
