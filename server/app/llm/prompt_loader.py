"""Versioned prompt template loader with untrusted context escaping and injection defense (docs/05 §8, docs/07 §8, ADR-028, M6-10).

Manages versioned prompt files under `server/app/llm/prompts/<task>/vN.md`:
1. YAML front matter: task, version, input_variables, untrusted_variables, output_schema, required_capabilities.
2. Template rendering: deterministic variable substitution with {var} or {{var}}.
3. Prompt injection defenses (docs/07 §8):
   - Untrusted repository and user inputs are strictly encapsulated in <untrusted_data name="..."> envelopes.
   - Closing tag injection attempts (e.g. </untrusted_data>) are neutralized.
   - Heuristic scanning flags suspicious injection patterns (e.g. "ignore previous instructions") in audit metadata.
   - System prompts mandate that data block contents must never be interpreted as instructions.
4. Generates ChatMessage sequence and metadata for agent runs audit trail (`agent_runs.prompt_versions`).
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from app.llm.exceptions import LLMError
from app.llm.models import ChatMessage, LLMGenerationOptions, LLMGenerationRequest

logger = logging.getLogger(__name__)

DEFAULT_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

# Injection signal patterns per docs/07 §8 and docs/09 §12
_INJECTION_PATTERNS = [
    (
        re.compile(
            r"(?i)(?:ignore|disregard|forget|override|bypass)[-_\s]+(?:(?:all|previous|prior|above|developer|system|authorization|auth|retrieved)[-_\s]+)*(?:instructions|prompts|rules|commands|constraints|checks|guards|context|auth|tokens)"
        ),
        "Instruction override attempt: ignore previous instructions or bypass rules",
    ),
    (
        re.compile(
            r"(?i)\b(?:system|security)\s+override\b|\bprompt\s+injection\b|\bdisregard\s+developer\s+instructions\b"
        ),
        "Privileged system override instruction attempt",
    ),
    (
        re.compile(
            r"(?i)\b(?:you are now|act as|jailbreak|developer mode|do anything now|\bdan\b|\bdan\s*\()"
        ),
        "Persona or system role hijack attempt",
    ),
    (
        re.compile(
            r"(?i)(?:^|\n)\s*(?:system|assistant|human|user)\s*:\s*(?:you are|i confirm|great|understood|ignore)"
        ),
        "Role-prefix impersonation attempt",
    ),
    (
        re.compile(r"(?i)</?untrusted_data(?:\s+[^>]*)?>"),
        "Untrusted data boundary escape attempt",
    ),
    (
        re.compile(
            r"(?i)(?:reveal|print|exfiltrate|leak|show|output)[-_\s]+(?:the[-_\s]+|all[-_\s]+)?(?:system[-_\s]+prompt|developer[-_\s]+secrets|process\.env|secrets?|tokens?|api[-_]?keys?|passwords?|credentials?|database[-_\s]+credentials)\b"
        ),
        "Secret exfiltration instruction attempt",
    ),
    (
        re.compile(
            r"(?i)\b(?:call|execute|invoke)\s+(?:the\s+)?(?:deploy|admin|delete)\s+(?:tool|function|api)\b|\bmark\s+(?:this\s+route\s+)?safe\b|\breport\s+0\s+findings\b"
        ),
        "Adversarial tool invocation or finding suppression attempt",
    ),
    (
        re.compile(r"(?i)\b(?:reveal\s+project_id|reveal\s+other\s+projects?|cross[-_]tenant)\b"),
        "Cross-tenant data extraction attempt",
    ),
]


def detect_injection_signals(text: str) -> list[str]:
    """Inspect text for heuristic prompt injection signals (docs/07 §8)."""
    signals: list[str] = []
    if not text:
        return signals
    for pattern, description in _INJECTION_PATTERNS:
        if pattern.search(text):
            signals.append(description)
    return signals


def escape_untrusted_content(var_name: str, raw_content: Any) -> tuple[str, list[str]]:
    """Encapsulate untrusted input in a secure XML boundary, escaping escape attempts (docs/07 §8)."""
    text = str(raw_content) if raw_content is not None else ""
    signals = detect_injection_signals(text)

    # Neutralize any attempts to close or open the untrusted_data XML tag
    sanitized = re.sub(
        r"(?i)</?untrusted_data(?:\s+[^>]*)?>",
        "[sanitized_delimiter]",
        text,
    )

    wrapped = f'<untrusted_data name="{var_name}">\n{sanitized}\n</untrusted_data>'
    return wrapped, signals


class PromptFrontMatter(BaseModel):
    """Schema for YAML front matter in versioned prompt files (docs/05 §8)."""

    model_config = ConfigDict(extra="forbid")

    task: str = Field(description="Target task key matching tasks.yaml")
    version: int = Field(ge=1, description="Sequential prompt version number")
    description: str | None = Field(default=None, description="Human readable description")
    input_variables: list[str] = Field(
        default_factory=list,
        description="Declared template variables required for rendering",
    )
    untrusted_variables: list[str] = Field(
        default_factory=list,
        description="Variables representing untrusted repository or user content",
    )
    output_schema: str | None = Field(
        default=None,
        description="Expected structured output schema name (e.g. 'AgentPlan')",
    )
    required_capabilities: list[str] = Field(
        default_factory=list,
        description="Capabilities required by this prompt (e.g. ['structured_output'])",
    )


class RenderedPrompt(BaseModel):
    """Rendered prompt ready for LLM invocation with security audit metadata."""

    model_config = ConfigDict(extra="forbid")

    task: str
    version: int
    prompt_id: str
    system_prompt: str
    user_prompt: str
    messages: list[ChatMessage]
    output_schema: str | None = None
    required_capabilities: list[str] = Field(default_factory=list)
    injection_detected: bool = False
    injection_signals: list[str] = Field(default_factory=list)
    variables_used: list[str] = Field(default_factory=list)

    def to_request(
        self,
        options: LLMGenerationOptions | None = None,
        metadata: dict[str, Any] | None = None,
        model_alias: str | None = None,
    ) -> LLMGenerationRequest:
        """Construct an LLMGenerationRequest carrying prompt audit metadata."""
        merged_metadata = dict(metadata or {})
        merged_metadata["prompt_version"] = self.prompt_id
        if self.injection_detected:
            merged_metadata["injection_signals"] = self.injection_signals

        return LLMGenerationRequest(
            task=self.task,
            messages=self.messages,
            options=options or LLMGenerationOptions(),
            model_alias=model_alias,
            metadata=merged_metadata,
        )


class PromptTemplate:
    """Versioned prompt template with front matter metadata and rendering logic."""

    def __init__(
        self,
        front_matter: PromptFrontMatter,
        system_template: str,
        user_template: str,
        file_path: Path | None = None,
    ) -> None:
        self.meta = front_matter
        self.system_template = system_template.strip()
        self.user_template = user_template.strip()
        self.file_path = file_path

    @property
    def prompt_id(self) -> str:
        """Format prompt identifier string, e.g. 'agent_manager_routing:v1'."""
        return f"{self.meta.task}:v{self.meta.version}"

    @property
    def front_matter(self) -> PromptFrontMatter:
        """Alias for meta."""
        return self.meta

    def render(self, variables: dict[str, Any]) -> RenderedPrompt:
        """Render prompt template with variable substitution and untrusted context escaping."""
        # 1. Validate required input variables
        missing = [v for v in self.meta.input_variables if v not in variables]
        if missing:
            raise ValueError(
                f"Missing required input variables for prompt '{self.prompt_id}': {missing}"
            )

        injection_signals: list[str] = []
        processed_vars: dict[str, str] = {}

        # 2. Process and escape variables
        for var_name in self.meta.input_variables:
            val = variables.get(var_name, "")
            if var_name in self.meta.untrusted_variables:
                escaped_text, signals = escape_untrusted_content(var_name, val)
                processed_vars[var_name] = escaped_text
                injection_signals.extend(signals)
            else:
                str_val = str(val) if val is not None else ""
                processed_vars[var_name] = str_val
                # Check for injection signals even in non-declared variables
                signals = detect_injection_signals(str_val)
                injection_signals.extend(signals)

        # 3. Deterministic template replacement (supports {var} and {{var}})
        def _substitute(template: str) -> str:
            rendered = template
            for k, v in processed_vars.items():
                # Replace {{ k }} or {{k}}
                rendered = re.sub(rf"\{{\{{\s*{k}\s*\}}\}}", lambda _, val=v: val, rendered)
                # Replace {k}
                rendered = re.sub(rf"\{{{k}\}}", lambda _, val=v: val, rendered)
            return rendered

        rendered_system = _substitute(self.system_template)
        rendered_user = _substitute(self.user_template)

        # Build message history
        messages: list[ChatMessage] = []
        if rendered_system:
            messages.append(ChatMessage.system(rendered_system))
        messages.append(ChatMessage.user(rendered_user))

        return RenderedPrompt(
            task=self.meta.task,
            version=self.meta.version,
            prompt_id=self.prompt_id,
            system_prompt=rendered_system,
            user_prompt=rendered_user,
            messages=messages,
            output_schema=self.meta.output_schema,
            required_capabilities=self.meta.required_capabilities,
            injection_detected=len(injection_signals) > 0,
            injection_signals=sorted(list(set(injection_signals))),
            variables_used=list(self.meta.input_variables),
        )


class PromptLoader:
    """Loads and caches versioned prompt templates from the filesystem (docs/05 §8, ADR-028)."""

    def __init__(self, prompts_dir: Path | str | None = None) -> None:
        self.prompts_dir = Path(prompts_dir) if prompts_dir else DEFAULT_PROMPTS_DIR
        self._cache: dict[str, PromptTemplate] = {}

    def _parse_prompt_file(self, file_path: Path) -> PromptTemplate:
        """Parse a markdown prompt file with YAML front matter into PromptTemplate."""
        content = file_path.read_text(encoding="utf-8")
        if not content.startswith("---"):
            raise LLMError(
                f"Prompt file '{file_path.name}' is missing YAML front matter",
                code="llm.invalid_prompt",
            )

        parts = content.split("---", 2)
        if len(parts) < 3:
            raise LLMError(
                f"Prompt file '{file_path.name}' has malformed front matter delimiters",
                code="llm.invalid_prompt",
            )

        yaml_text = parts[1]
        body = parts[2].strip()

        try:
            front_matter_data = yaml.safe_load(yaml_text) or {}
            front_matter = PromptFrontMatter.model_validate(front_matter_data)
        except Exception as exc:
            raise LLMError(
                f"Invalid YAML front matter in '{file_path.name}': {exc}",
                code="llm.invalid_prompt",
            ) from exc

        # Split system and user prompt sections if marked by headers
        system_template = ""
        user_template = body

        # Look for ## System and ## User headers
        system_match = re.search(r"##\s*System\b", body, re.IGNORECASE)
        user_match = re.search(r"##\s*User\b", body, re.IGNORECASE)

        if system_match and user_match and user_match.start() > system_match.end():
            system_template = body[system_match.end() : user_match.start()].strip()
            user_template = body[user_match.end() :].strip()
        elif user_match:
            user_template = body[user_match.end() :].strip()

        return PromptTemplate(
            front_matter=front_matter,
            system_template=system_template,
            user_template=user_template,
            file_path=file_path,
        )

    def load(self, task: str, version: int | None = None) -> PromptTemplate:
        """Load prompt template for a specific task and version (defaults to highest version)."""
        task_dir = self.prompts_dir / task
        if not task_dir.is_dir():
            raise LLMError(
                f"No prompt directory found for task '{task}' at {task_dir}",
                code="llm.prompt_not_found",
            )

        if version is not None:
            file_path = task_dir / f"v{version}.md"
            cache_key = f"{task}:v{version}"
            if cache_key in self._cache:
                return self._cache[cache_key]

            if not file_path.is_file():
                raise LLMError(
                    f"Prompt file not found for task '{task}' version {version}: {file_path}",
                    code="llm.prompt_not_found",
                )
            template = self._parse_prompt_file(file_path)
            self._cache[cache_key] = template
            return template

        # Find latest version
        latest_version = self.get_latest_version(task)
        return self.load(task, latest_version)

    def get_template(self, task: str, version: int | None = None) -> PromptTemplate:
        """Alias for load()."""
        return self.load(task, version=version)

    def render(
        self,
        task: str,
        variables: dict[str, Any],
        version: int | None = None,
    ) -> RenderedPrompt:
        """Load and render prompt template for a specific task and version."""
        template = self.load(task, version=version)
        return template.render(variables)

    def get_latest_version(self, task: str) -> int:
        """Find the highest version number available for a task."""
        task_dir = self.prompts_dir / task
        if not task_dir.is_dir():
            raise LLMError(
                f"No prompt directory found for task '{task}'",
                code="llm.prompt_not_found",
            )

        version_files = list(task_dir.glob("v*.md"))
        if not version_files:
            raise LLMError(
                f"No versioned prompt files (v*.md) found for task '{task}'",
                code="llm.prompt_not_found",
            )

        versions: list[int] = []
        for f in version_files:
            match = re.match(r"^v(\d+)\.md$", f.name)
            if match:
                versions.append(int(match.group(1)))

        if not versions:
            raise LLMError(
                f"No valid version numbers parsed for task '{task}'",
                code="llm.prompt_not_found",
            )

        return max(versions)

    def list_tasks(self) -> list[str]:
        """List all task names that have prompt directories."""
        if not self.prompts_dir.is_dir():
            return []
        return [d.name for d in self.prompts_dir.iterdir() if d.is_dir()]


# Global default prompt loader instance
default_prompt_loader = PromptLoader()
