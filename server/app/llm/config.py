"""LLM Gateway configuration loaders, Pydantic schemas, and startup validation (docs/05 §11, docs/11 M6-03)."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from app.llm.exceptions import LLMError


class ConfigValidationError(LLMError):
    """Raised when LLM gateway configuration violates schema, referential integrity, or policies."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message=message, code="llm.invalid_config", details=details)


# ---------------------------------------------------------------------------
# 11.1 Providers Configuration Models
# ---------------------------------------------------------------------------


class ProviderTimeoutConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    connect_s: int = Field(default=5, ge=1)
    read_s: int = Field(default=60, ge=1)


class ProviderConcurrencyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_in_flight: int = Field(default=8, ge=1)


class ProviderDataPolicyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_code_allowed: bool = Field(default=False)
    note: str | None = Field(default=None)


class ProviderEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    adapter: str = Field(
        description="Adapter identifier: anthropic | openai | google | openai_compatible | fake"
    )
    base_url: str | None = Field(default=None)
    api_key_env: str | None = Field(default=None)
    enabled: bool = Field(default=True)
    environments: list[str] = Field(default_factory=lambda: ["development", "test"])
    terms_reviewed: bool = Field(default=False)
    data_policy: ProviderDataPolicyConfig = Field(default_factory=ProviderDataPolicyConfig)
    timeouts: ProviderTimeoutConfig = Field(default_factory=ProviderTimeoutConfig)
    concurrency: ProviderConcurrencyConfig = Field(default_factory=ProviderConcurrencyConfig)


class ProvidersConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(default=1)
    providers: dict[str, ProviderEntry] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# 11.2 Models Configuration Models
# ---------------------------------------------------------------------------


class ModelLimitsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_input_tokens: int | None = Field(default=None)
    max_output_tokens: int | None = Field(default=None)


class ModelPriceUnitsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_per_1k: float | None = Field(default=None)
    output_per_1k: float | None = Field(default=None)


class ModelCapabilitiesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_calling: bool = Field(default=False)
    structured_output: Literal["native", "json_mode", "prompt_only", "none"] = Field(default="none")
    streaming: bool = Field(default=True)
    supports_system_prompt: bool = Field(default=True)


class ModelEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = Field(description="Referenced provider key in providers.yaml")
    model_id: str = Field(description="Official model name or identifier")
    kind: Literal["generation", "embedding"] = Field(default="generation")
    status: Literal["unvalidated", "evaluated", "deprecated"] = Field(default="unvalidated")
    capabilities: ModelCapabilitiesConfig | None = Field(default=None)
    dimension: int | None = Field(
        default=None, description="Embedding dimension if kind is embedding"
    )
    limits: ModelLimitsConfig = Field(default_factory=ModelLimitsConfig)
    price_units: ModelPriceUnitsConfig = Field(default_factory=ModelPriceUnitsConfig)
    normalize: bool | None = Field(default=None)


class ModelsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(default=1)
    models: dict[str, ModelEntry] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# 11.3 Tasks Configuration Models
# ---------------------------------------------------------------------------


class RetryConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_attempts: int = Field(default=3, ge=1)
    backoff: str = Field(default="exponential")
    initial_delay_s: float = Field(default=1.0, ge=0.0)
    max_delay_s: float = Field(default=30.0, ge=1.0)
    jitter: bool = Field(default=True)
    retry_on: list[str] = Field(
        default_factory=lambda: ["timeout", "rate_limit", "provider_5xx", "connection"]
    )


class DefaultsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timeout_s: int = Field(default=60, ge=1)
    retry: RetryConfig = Field(default_factory=RetryConfig)


class TaskParamsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_output_tokens: int | None = Field(default=None, gt=0)


class TaskBudgetConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_input_tokens: int | None = Field(default=None, gt=0)


class TaskDataConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    may_contain_source: bool = Field(default=False)


class TaskBatchConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_items: int | None = Field(default=None, gt=0)


class TaskEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str = Field(description="Primary model alias in models.yaml")
    kind: Literal["generation", "embedding"] = Field(default="generation")
    fallbacks: list[str] = Field(default_factory=list)
    required_capabilities: list[str] = Field(default_factory=list)
    output_schema: str | None = Field(default=None)
    params: TaskParamsConfig = Field(default_factory=TaskParamsConfig)
    budget: TaskBudgetConfig = Field(default_factory=TaskBudgetConfig)
    data: TaskDataConfig = Field(default_factory=TaskDataConfig)
    batch: TaskBatchConfig = Field(default_factory=TaskBatchConfig)


class TasksConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(default=1)
    defaults: DefaultsConfig = Field(default_factory=DefaultsConfig)
    tasks: dict[str, TaskEntry] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# GatewayConfig Combined Object & Validator
# ---------------------------------------------------------------------------


class GatewayConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    providers: ProvidersConfig
    models: ModelsConfig
    tasks: TasksConfig
    config_hash: str = Field(
        description="SHA-256 hash of configuration files for reproducible run tracking"
    )


def validate_gateway_config(config: GatewayConfig, environment: str = "development") -> None:
    """Validate referential integrity, capability matching, data policy, and environment constraints (docs/05 §11.4)."""
    env = environment.lower().strip()
    is_prod_or_staging = env in ("production", "staging")

    providers = config.providers.providers
    models = config.models.models
    tasks = config.tasks.tasks

    # 1. Referential integrity: model -> provider
    for model_key, model_entry in models.items():
        if model_entry.provider not in providers:
            raise ConfigValidationError(
                f"Model '{model_key}' references non-existent provider '{model_entry.provider}' in providers.yaml"
            )

    # 2. Referential integrity: task -> model and fallbacks -> model
    for task_key, task_entry in tasks.items():
        if task_entry.model not in models:
            raise ConfigValidationError(
                f"Task '{task_key}' references non-existent primary model '{task_entry.model}' in models.yaml"
            )

        for fallback in task_entry.fallbacks:
            if fallback not in models:
                raise ConfigValidationError(
                    f"Task '{task_key}' references non-existent fallback model '{fallback}' in models.yaml"
                )

        # 3. Capability verification (Primary + Fallbacks must satisfy required_capabilities)
        all_models_for_task = [task_entry.model] + task_entry.fallbacks
        for req_cap in task_entry.required_capabilities:
            for m_key in all_models_for_task:
                m_obj = models[m_key]
                caps = m_obj.capabilities or ModelCapabilitiesConfig()
                if req_cap == "tool_calling" and not caps.tool_calling:
                    raise ConfigValidationError(
                        f"Task '{task_key}' requires capability 'tool_calling' which is missing in model '{m_key}'"
                    )
                elif req_cap == "structured_output" and caps.structured_output == "none":
                    raise ConfigValidationError(
                        f"Task '{task_key}' requires capability 'structured_output' which is missing in model '{m_key}'"
                    )
                elif req_cap == "streaming" and not caps.streaming:
                    raise ConfigValidationError(
                        f"Task '{task_key}' requires capability 'streaming' which is missing in model '{m_key}'"
                    )

        # 4. Data Policy check: source code allowed
        if task_entry.data.may_contain_source:
            for m_key in all_models_for_task:
                prov_key = models[m_key].provider
                prov_obj = providers[prov_key]
                if is_prod_or_staging and not prov_obj.data_policy.source_code_allowed:
                    raise ConfigValidationError(
                        f"Task '{task_key}' has may_contain_source=True but provider '{prov_key}' "
                        f"(used by '{m_key}') has source_code_allowed=False"
                    )
                if is_prod_or_staging and not prov_obj.terms_reviewed:
                    raise ConfigValidationError(
                        f"Environment '{env}' requires terms_reviewed=True for provider '{prov_key}' on task '{task_key}'"
                    )

    # 5. Production / Staging Placeholders and Environment Checks
    if is_prod_or_staging:
        for p_key, p_entry in providers.items():
            if not p_entry.enabled:
                continue
            if p_entry.base_url and ".invalid" in p_entry.base_url:
                raise ConfigValidationError(
                    f"Placeholder hostname '.invalid' in provider '{p_key}' base_url is rejected in {env}"
                )
            if p_entry.adapter != "fake" and p_entry.api_key_env:
                if not os.environ.get(p_entry.api_key_env):
                    raise ConfigValidationError(
                        f"Required API key env var '{p_entry.api_key_env}' for enabled provider '{p_key}' is unset in {env}"
                    )

        # Check model placeholders for models actually used by tasks
        active_model_keys = set()
        for t in tasks.values():
            active_model_keys.add(t.model)
            active_model_keys.update(t.fallbacks)

        for m_key in active_model_keys:
            m_entry = models[m_key]
            if "REPLACE_" in m_entry.model_id:
                raise ConfigValidationError(
                    f"Placeholder model_id '{m_entry.model_id}' in active model '{m_key}' is rejected in {env}"
                )
            if m_entry.kind == "generation":
                if (
                    m_entry.limits.max_input_tokens is None
                    or m_entry.limits.max_output_tokens is None
                ):
                    raise ConfigValidationError(
                        f"Model limits (max_input_tokens, max_output_tokens) must be specified for active model '{m_key}' in {env}"
                    )


def load_gateway_config(
    config_dir: Path | str | None = None,
    environment: str = "development",
    validate: bool = True,
) -> GatewayConfig:
    """Load and optionally validate providers.yaml, models.yaml, and tasks.yaml from config directory."""
    if config_dir is None:
        # Default to repo server/configs/llm
        base_dir = Path(__file__).resolve().parent.parent.parent / "configs" / "llm"
    else:
        base_dir = Path(config_dir)

    providers_file = base_dir / "providers.yaml"
    models_file = base_dir / "models.yaml"
    tasks_file = base_dir / "tasks.yaml"

    for file_path in (providers_file, models_file, tasks_file):
        if not file_path.is_file():
            raise ConfigValidationError(
                f"Required LLM gateway configuration file missing: {file_path}"
            )

    raw_providers = providers_file.read_text(encoding="utf-8")
    raw_models = models_file.read_text(encoding="utf-8")
    raw_tasks = tasks_file.read_text(encoding="utf-8")

    # Compute deterministic SHA-256 hash of configuration files
    hasher = hashlib.sha256()
    hasher.update(raw_providers.encode("utf-8"))
    hasher.update(raw_models.encode("utf-8"))
    hasher.update(raw_tasks.encode("utf-8"))
    config_hash = hasher.hexdigest()

    try:
        dict_providers = yaml.safe_load(raw_providers) or {}
        dict_models = yaml.safe_load(raw_models) or {}
        dict_tasks = yaml.safe_load(raw_tasks) or {}

        providers_cfg = ProvidersConfig.model_validate(dict_providers)
        models_cfg = ModelsConfig.model_validate(dict_models)
        tasks_cfg = TasksConfig.model_validate(dict_tasks)
    except Exception as exc:
        raise ConfigValidationError(
            f"Failed to parse LLM gateway configuration YAML: {exc}"
        ) from exc

    gateway_cfg = GatewayConfig(
        providers=providers_cfg,
        models=models_cfg,
        tasks=tasks_cfg,
        config_hash=config_hash,
    )

    if validate:
        validate_gateway_config(gateway_cfg, environment=environment)

    return gateway_cfg
