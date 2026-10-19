"""LLM Gateway Router with capability matching, fallback rules, and data policy privacy guards (docs/05 §11.6, §12, docs/11 M6-06).

Routes LLM requests to primary models and eligible fallbacks based on tasks.yaml,
models.yaml, and providers.yaml. Enforces:
1. Model capability verification (tool calling, native structured output, streaming)
2. Source-code-allowed privacy guard (ADR-047)
3. Fallback compatibility and execution policy (ADR-027)
4. Strict non-bypass on safety refusals or schema invalid outputs
"""

from __future__ import annotations

import logging
import os
import time
from collections.abc import AsyncIterator
from typing import Any

from app.llm.adapter import LLMAdapter
from app.llm.config import GatewayConfig, ModelEntry, load_gateway_config
from app.llm.exceptions import (
    LLMContextLengthExceededError,
    LLMError,
    LLMInvalidOutputError,
    LLMPermissionError,
    LLMProviderError,
    LLMQuotaExceededError,
    LLMRateLimitError,
    LLMRefusalError,
    LLMTimeoutError,
    LLMUnavailableError,
)
from app.llm.models import (
    LLMGenerationRequest,
    LLMGenerationResponse,
    LLMStreamChunk,
    ModelCapabilities,
    ProviderDataPolicy,
    StructuredOutputMode,
    StructuredOutputSpec,
)
from app.llm.quotas import LLMConcurrencyManager, LLMQuotaEnforcer, LLMRateLimiter
from app.llm.registry import create_adapter
from app.llm.repair import StructuredOutputRepairer
from app.llm.schemas import SchemaRegistry, default_schema_registry
from app.llm.usage import LLMUsageRecorder

logger = logging.getLogger(__name__)


class LLMGatewayRouter:
    """Central gateway router managing task dispatch, model resolution, and fallback chains (docs/05 §12)."""

    def __init__(
        self,
        config: GatewayConfig | None = None,
        environment: str | None = None,
        adapter_overrides: dict[str, LLMAdapter] | None = None,
        concurrency_manager: LLMConcurrencyManager | None = None,
        rate_limiter: LLMRateLimiter | None = None,
        quota_enforcer: LLMQuotaEnforcer | None = None,
        usage_recorder: LLMUsageRecorder | None = None,
        repairer: StructuredOutputRepairer | None = None,
        schema_registry: SchemaRegistry | None = None,
    ) -> None:
        self.config = config or load_gateway_config()
        self.environment = (
            (
                environment
                or os.getenv("DEVMIND_ENVIRONMENT")
                or os.getenv("ENVIRONMENT")
                or "development"
            )
            .lower()
            .strip()
        )
        self._adapter_cache: dict[str, LLMAdapter] = {}
        self._adapter_overrides: dict[str, LLMAdapter] = adapter_overrides or {}
        self.concurrency_manager = concurrency_manager or LLMConcurrencyManager(self.config)
        self.rate_limiter = rate_limiter or LLMRateLimiter(self.config)
        self.quota_enforcer = quota_enforcer or LLMQuotaEnforcer(self.config)
        self.usage_recorder = usage_recorder or LLMUsageRecorder()
        self.repairer = repairer or StructuredOutputRepairer(schema_registry)
        self.schema_registry = schema_registry or default_schema_registry

    def register_adapter_override(self, model_key: str, adapter: LLMAdapter) -> None:
        """Register a mock or pre-instantiated adapter for a specific logical model key."""
        self._adapter_overrides[model_key] = adapter

    def get_adapter(self, model_key: str) -> LLMAdapter:
        """Resolve or instantiate the LLM adapter for a given logical model key."""
        if model_key in self._adapter_overrides:
            return self._adapter_overrides[model_key]

        if model_key in self._adapter_cache:
            return self._adapter_cache[model_key]

        if model_key not in self.config.models.models:
            raise LLMError(
                f"Model '{model_key}' is not registered in models.yaml",
                code="llm.unknown_model",
            )

        model_entry = self.config.models.models[model_key]
        provider_key = model_entry.provider

        if provider_key not in self.config.providers.providers:
            raise LLMError(
                f"Provider '{provider_key}' for model '{model_key}' is not in providers.yaml",
                code="llm.unknown_provider",
            )

        provider_entry = self.config.providers.providers[provider_key]

        # Resolve API key from environment if configured
        api_key = ""
        if provider_entry.api_key_env:
            api_key = os.getenv(provider_entry.api_key_env, "")

        # Prepare data policy
        data_policy = ProviderDataPolicy(
            source_code_allowed=provider_entry.data_policy.source_code_allowed,
            terms_reviewed=provider_entry.terms_reviewed,
            note=provider_entry.data_policy.note,
        )

        timeout_s = float(provider_entry.timeouts.read_s)

        # Build adapter via registry
        adapter_kwargs: dict[str, Any] = {
            "model_id": model_entry.model_id,
            "data_policy": data_policy,
        }

        # Provider-specific parameter mapping
        adapter_type = provider_entry.adapter.lower().strip()
        if adapter_type in ("google", "gemini"):
            adapter_kwargs["api_key"] = api_key
            if provider_entry.base_url:
                adapter_kwargs["base_url"] = provider_entry.base_url
            adapter_kwargs["timeout_seconds"] = timeout_s
        elif adapter_type in ("openai_compatible", "openai", "groq"):
            adapter_kwargs["api_key"] = api_key
            if provider_entry.base_url:
                adapter_kwargs["base_url"] = provider_entry.base_url
            adapter_kwargs["provider_id"] = provider_key
            adapter_kwargs["timeout_seconds"] = timeout_s

        adapter = create_adapter(adapter_type, **adapter_kwargs)
        self._adapter_cache[model_key] = adapter
        return adapter

    def resolve_candidates(
        self,
        task_name: str,
        may_contain_source: bool = False,
        streaming: bool = False,
        model_override: str | None = None,
    ) -> list[str]:
        """Resolve ordered list of eligible models (primary + fallbacks) for a task (docs/05 §11.6).

        Filters candidate models by:
        1. Required capabilities matching
        2. Customer source code privacy policy (ADR-047)
        3. Deprecation and environment enablement status
        """
        if task_name not in self.config.tasks.tasks:
            raise LLMError(
                f"Task '{task_name}' is not configured in tasks.yaml",
                code="llm.unknown_task",
            )

        task_entry = self.config.tasks.tasks[task_name]
        candidate_keys = [task_entry.model] + task_entry.fallbacks
        if model_override:
            if model_override in self.config.models.models:
                candidate_keys = [model_override] + [
                    k for k in candidate_keys if k != model_override
                ]
            else:
                logger.warning(
                    "Requested model_override '%s' not found in models.yaml", model_override
                )

        contains_source = task_entry.data.may_contain_source or may_contain_source
        is_prod_staging = self.environment in ("staging", "production")

        eligible_models: list[str] = []

        for m_key in candidate_keys:
            if m_key not in self.config.models.models:
                logger.warning(
                    "Configured model '%s' not in models.yaml; skipping candidate", m_key
                )
                continue

            m_entry = self.config.models.models[m_key]
            p_key = m_entry.provider

            if p_key not in self.config.providers.providers:
                logger.warning(
                    "Provider '%s' not in providers.yaml; skipping model '%s'", p_key, m_key
                )
                continue

            p_entry = self.config.providers.providers[p_key]

            # 1. Environment & enablement check
            if not p_entry.enabled:
                logger.debug("Provider '%s' is disabled; skipping model '%s'", p_key, m_key)
                continue

            if self.environment not in p_entry.environments:
                logger.debug(
                    "Provider '%s' not enabled for environment '%s'; skipping model '%s'",
                    p_key,
                    self.environment,
                    m_key,
                )
                continue

            # 2. Status check: deprecated models are ineligible (docs/05 §11.6 rule 4)
            if m_entry.status == "deprecated":
                logger.debug("Model '%s' is deprecated; skipping", m_key)
                continue

            # 3. Capability verification (docs/05 §11.6 rule 1)
            caps = m_entry.capabilities or ModelCapabilities()
            cap_mismatch = False
            for req_cap in task_entry.required_capabilities:
                if req_cap == "tool_calling" and not caps.tool_calling:
                    cap_mismatch = True
                    break
                if req_cap == "structured_output" and caps.structured_output == "none":
                    cap_mismatch = True
                    break
                if req_cap == "streaming" and not caps.streaming:
                    cap_mismatch = True
                    break

            if streaming and not caps.streaming:
                cap_mismatch = True

            if cap_mismatch:
                logger.debug(
                    "Model '%s' lacks required capabilities for task '%s'; skipping",
                    m_key,
                    task_name,
                )
                continue

            # 4. Source code privacy check (docs/05 §11.6 rule 2 & ADR-047)
            if contains_source:
                if not p_entry.data_policy.source_code_allowed:
                    logger.debug(
                        "Provider '%s' data policy disallows source code transmission; skipping model '%s'",
                        p_key,
                        m_key,
                    )
                    continue

                if is_prod_staging and not p_entry.terms_reviewed:
                    logger.debug(
                        "Provider '%s' terms not reviewed for source code in %s; skipping model '%s'",
                        p_key,
                        self.environment,
                        m_key,
                    )
                    continue

            eligible_models.append(m_key)

        if not eligible_models:
            raise LLMUnavailableError(
                f"No eligible provider or fallback model available for task '{task_name}' under environment '{self.environment}' and data policy constraints"
            )

        return eligible_models

    async def _record_call_outcome(
        self,
        *,
        task: str,
        provider_key: str,
        model_entry: ModelEntry,
        workspace_id: Any,
        request: LLMGenerationRequest,
        response: LLMGenerationResponse | None = None,
        latency_ms: int = 1,
        outcome: str = "success",
    ) -> None:
        """Record usage and update quota limits upon call completion."""
        if response and response.usage:
            in_tokens = response.usage.input_tokens
            out_tokens = response.usage.output_tokens
            if workspace_id:
                self.quota_enforcer.record_usage(workspace_id, response.usage.total_tokens)
        else:
            in_tokens = self.quota_enforcer.estimate_input_tokens(request)
            out_tokens = (
                max(1, len(response.content or "") // 4) if (response and response.content) else 0
            )

        await self.usage_recorder.record_call(
            task=task,
            provider_id=provider_key,
            model_id=model_entry.model_id,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            latency_ms=latency_ms,
            outcome=outcome,  # type: ignore[arg-type]
            workspace_id=workspace_id,
            project_id=request.metadata.get("project_id"),
            job_id=request.metadata.get("job_id"),
            price_units=model_entry.price_units,
        )

        try:
            from app.core.telemetry import record_llm_call

            record_llm_call(
                provider=provider_key,
                model=model_entry.model_id,
                task_name=task,
                status=outcome,
                input_tokens=in_tokens,
                output_tokens=out_tokens,
                duration_seconds=latency_ms / 1000.0,
            )
        except Exception:
            pass

    async def generate(self, request: LLMGenerationRequest) -> LLMGenerationResponse:
        """Route non-streaming request to the primary eligible model with fallback execution (docs/05 §12)."""
        may_contain_source = bool(request.metadata.get("may_contain_source", False))
        candidates = self.resolve_candidates(
            task_name=request.task,
            may_contain_source=may_contain_source,
            streaming=False,
            model_override=request.model_alias,
        )

        task_entry = self.config.tasks.tasks[request.task]
        workspace_id = request.metadata.get("workspace_id")
        last_exception: Exception | None = None

        # Resolve structured output specification from request options or task declaration (docs/05 §10)
        task_spec: StructuredOutputSpec | None = None
        if request.options.structured_output:
            task_spec = request.options.structured_output.model_copy()
        elif task_entry.output_schema and self.schema_registry.contains(task_entry.output_schema):
            task_spec = self.schema_registry.build_spec(task_entry.output_schema)

        for idx, model_key in enumerate(candidates):
            model_entry = self.config.models.models[model_key]
            provider_key = model_entry.provider

            # 1. Pre-call quota & context length checks (docs/05 §11.6 rule 5 & §13)
            try:
                self.quota_enforcer.check_pre_call(request, task_entry, model_entry)
            except LLMContextLengthExceededError as exc:
                logger.warning(
                    "Model '%s' context length exceeded for task '%s': %s; trying fallback",
                    model_key,
                    request.task,
                    exc,
                )
                last_exception = exc
                continue
            except LLMQuotaExceededError:
                # Quota or budget exhausted stops immediately (docs/05 §12)
                raise

            # 2. Sliding-window rate limit check per provider (docs/05 §13)
            allowed, remaining, retry_after = await self.rate_limiter.check_and_acquire(
                provider_key
            )
            if not allowed:
                logger.warning(
                    "Provider '%s' rate limited (retry_after=%.1fs); trying fallback candidate",
                    provider_key,
                    retry_after,
                )
                last_exception = LLMRateLimitError(
                    f"Provider '{provider_key}' rate limit exceeded",
                    retry_after_s=retry_after,
                )
                continue

            adapter = self.get_adapter(model_key)
            is_fallback = idx > 0

            if is_fallback:
                logger.warning(
                    "Executing fallback model '%s' for task '%s' (fallback %d/%d)",
                    model_key,
                    request.task,
                    idx,
                    len(candidates) - 1,
                )

            # Adapt structured output mode according to model capabilities
            call_request = request
            call_spec: StructuredOutputSpec | None = None
            if task_spec is not None:
                model_caps = model_entry.capabilities
                adapted_mode: StructuredOutputMode = "native"
                if model_caps and model_caps.structured_output in (
                    "native",
                    "json_mode",
                    "prompt_only",
                ):
                    adapted_mode = model_caps.structured_output

                call_spec = task_spec.model_copy()
                call_spec.mode = adapted_mode
                call_options = request.options.model_copy(deep=True)
                call_options.structured_output = call_spec
                call_request = request.model_copy(update={"options": call_options})

            call_start = time.time()
            try:
                # 3. Concurrency semaphore acquisition per provider and workspace (docs/05 §13)
                async with self.concurrency_manager.acquire(provider_key, workspace_id):
                    try:
                        from app.core.telemetry import trace_span

                        with trace_span(
                            "devmind.llm.generate",
                            attributes={
                                "llm.provider": provider_key,
                                "llm.model": model_entry.model_id,
                                "llm.task": request.task,
                                "llm.fallback": is_fallback,
                            },
                        ):
                            response = await adapter.generate(call_request)
                    except LLMInvalidOutputError as initial_err:
                        # Adapter rejected syntax or failed JSON decoding -> attempt 1 repair (docs/05 §10)
                        if call_spec is None:
                            raise
                        repair_response, repair_val = await self.repairer.attempt_repair(
                            adapter=adapter,
                            request=call_request,
                            raw_output=initial_err.raw_output or "",
                            errors=initial_err.validation_errors or [str(initial_err)],
                            spec=call_spec,
                        )
                        repair_latency_ms = repair_response.latency_ms or 1
                        await self._record_call_outcome(
                            task=request.task,
                            provider_key=provider_key,
                            model_entry=model_entry,
                            workspace_id=workspace_id,
                            request=call_request,
                            response=repair_response,
                            latency_ms=repair_latency_ms,
                            outcome="success" if repair_val.is_valid else "failure",
                        )
                        if repair_val.is_valid:
                            repair_response.content = repair_val.cleaned_json
                            return repair_response
                        raise LLMInvalidOutputError(
                            message=f"Output failed schema validation after repair attempt for schema '{call_spec.schema_name}'",
                            raw_output=repair_response.content,
                            validation_errors=repair_val.errors,
                        ) from initial_err

                    # Validate structured output against specification
                    if call_spec is not None:
                        val_res = self.repairer.validate(response.content, call_spec)
                        if val_res.is_valid:
                            response.content = val_res.cleaned_json
                        else:
                            # Attempt one repair attempt (docs/05 §10)
                            repair_response, repair_val = await self.repairer.attempt_repair(
                                adapter=adapter,
                                request=call_request,
                                raw_output=response.content or "",
                                errors=val_res.errors,
                                spec=call_spec,
                            )
                            repair_latency_ms = repair_response.latency_ms or 1
                            await self._record_call_outcome(
                                task=request.task,
                                provider_key=provider_key,
                                model_entry=model_entry,
                                workspace_id=workspace_id,
                                request=call_request,
                                response=repair_response,
                                latency_ms=repair_latency_ms,
                                outcome="success" if repair_val.is_valid else "failure",
                            )
                            if repair_val.is_valid:
                                repair_response.content = repair_val.cleaned_json
                                return repair_response
                            raise LLMInvalidOutputError(
                                message=f"Output failed schema validation after repair attempt for schema '{call_spec.schema_name}'",
                                raw_output=repair_response.content,
                                validation_errors=repair_val.errors,
                            )

                    latency_ms = max(1, int((time.time() - call_start) * 1000))
                    await self._record_call_outcome(
                        task=request.task,
                        provider_key=provider_key,
                        model_entry=model_entry,
                        workspace_id=workspace_id,
                        request=call_request,
                        response=response,
                        latency_ms=latency_ms,
                        outcome="success",
                    )
                    return response
            except LLMRefusalError:
                # ADR-027 / docs/05 §12 Table: Content refusal must NEVER be retried on fallbacks to bypass
                latency_ms = max(1, int((time.time() - call_start) * 1000))
                await self.usage_recorder.record_call(
                    task=request.task,
                    provider_id=provider_key,
                    model_id=model_entry.model_id,
                    input_tokens=self.quota_enforcer.estimate_input_tokens(request),
                    output_tokens=0,
                    latency_ms=latency_ms,
                    outcome="failure",
                    workspace_id=workspace_id,
                    project_id=request.metadata.get("project_id"),
                    job_id=request.metadata.get("job_id"),
                    price_units=model_entry.price_units,
                )
                logger.info(
                    "LLM provider returned content refusal for task '%s'; not attempting fallbacks",
                    request.task,
                )
                raise
            except LLMInvalidOutputError:
                # ADR-027 / docs/05 §12 Table: Schema invalid output fails without falling back
                latency_ms = max(1, int((time.time() - call_start) * 1000))
                await self.usage_recorder.record_call(
                    task=request.task,
                    provider_id=provider_key,
                    model_id=model_entry.model_id,
                    input_tokens=self.quota_enforcer.estimate_input_tokens(request),
                    output_tokens=0,
                    latency_ms=latency_ms,
                    outcome="failure",
                    workspace_id=workspace_id,
                    project_id=request.metadata.get("project_id"),
                    job_id=request.metadata.get("job_id"),
                    price_units=model_entry.price_units,
                )
                logger.info(
                    "LLM output failed schema validation for task '%s'; not attempting fallbacks",
                    request.task,
                )
                raise
            except LLMPermissionError:
                # Policy/privacy violations must fail immediately
                raise
            except LLMRateLimitError as exc:
                latency_ms = max(1, int((time.time() - call_start) * 1000))
                await self.usage_recorder.record_call(
                    task=request.task,
                    provider_id=provider_key,
                    model_id=model_entry.model_id,
                    input_tokens=self.quota_enforcer.estimate_input_tokens(request),
                    output_tokens=0,
                    latency_ms=latency_ms,
                    outcome="failure",
                    workspace_id=workspace_id,
                    project_id=request.metadata.get("project_id"),
                    job_id=request.metadata.get("job_id"),
                    price_units=model_entry.price_units,
                )
                self.rate_limiter.record_backoff(provider_key, exc.retry_after_s)
                logger.warning(
                    "Provider '%s' returned HTTP 429 rate limit; recorded backoff", provider_key
                )
                last_exception = exc
                continue
            except LLMTimeoutError as exc:
                latency_ms = max(1, int((time.time() - call_start) * 1000))
                await self.usage_recorder.record_call(
                    task=request.task,
                    provider_id=provider_key,
                    model_id=model_entry.model_id,
                    input_tokens=self.quota_enforcer.estimate_input_tokens(request),
                    output_tokens=0,
                    latency_ms=latency_ms,
                    outcome="timeout",
                    workspace_id=workspace_id,
                    project_id=request.metadata.get("project_id"),
                    job_id=request.metadata.get("job_id"),
                    price_units=model_entry.price_units,
                )
                logger.warning(
                    "Provider timeout on model '%s' for task '%s': %s",
                    model_key,
                    request.task,
                    exc,
                )
                last_exception = exc
                continue
            except (
                LLMProviderError,
                LLMUnavailableError,
                LLMContextLengthExceededError,
            ) as exc:
                latency_ms = max(1, int((time.time() - call_start) * 1000))
                await self.usage_recorder.record_call(
                    task=request.task,
                    provider_id=provider_key,
                    model_id=model_entry.model_id,
                    input_tokens=self.quota_enforcer.estimate_input_tokens(request),
                    output_tokens=0,
                    latency_ms=latency_ms,
                    outcome="failure",
                    workspace_id=workspace_id,
                    project_id=request.metadata.get("project_id"),
                    job_id=request.metadata.get("job_id"),
                    price_units=model_entry.price_units,
                )
                logger.warning(
                    "Provider error on model '%s' for task '%s': %s",
                    model_key,
                    request.task,
                    exc,
                )
                last_exception = exc
                continue
            except Exception as exc:
                latency_ms = max(1, int((time.time() - call_start) * 1000))
                await self.usage_recorder.record_call(
                    task=request.task,
                    provider_id=provider_key,
                    model_id=model_entry.model_id,
                    input_tokens=self.quota_enforcer.estimate_input_tokens(request),
                    output_tokens=0,
                    latency_ms=latency_ms,
                    outcome="failure",
                    workspace_id=workspace_id,
                    project_id=request.metadata.get("project_id"),
                    job_id=request.metadata.get("job_id"),
                    price_units=model_entry.price_units,
                )
                logger.error(
                    "Unexpected error on model '%s' for task '%s': %s",
                    model_key,
                    request.task,
                    exc,
                )
                last_exception = exc
                continue

        # If all candidates exhausted
        raise LLMUnavailableError(
            f"All eligible models exhausted for task '{request.task}'. Last error: {last_exception}"
        )

    async def stream_generate(self, request: LLMGenerationRequest) -> AsyncIterator[LLMStreamChunk]:
        """Route streaming request to primary eligible model with fallback on initial connection failure (docs/05 §12)."""
        may_contain_source = bool(request.metadata.get("may_contain_source", False))
        candidates = self.resolve_candidates(
            task_name=request.task,
            may_contain_source=may_contain_source,
            streaming=True,
            model_override=request.model_alias,
        )

        task_entry = self.config.tasks.tasks[request.task]
        workspace_id = request.metadata.get("workspace_id")
        last_exception: Exception | None = None

        for idx, model_key in enumerate(candidates):
            model_entry = self.config.models.models[model_key]
            provider_key = model_entry.provider

            # 1. Pre-call quota & context length checks
            try:
                self.quota_enforcer.check_pre_call(request, task_entry, model_entry)
            except LLMContextLengthExceededError as exc:
                logger.warning(
                    "Streaming model '%s' context length exceeded for task '%s': %s",
                    model_key,
                    request.task,
                    exc,
                )
                last_exception = exc
                continue
            except LLMQuotaExceededError:
                raise

            # 2. Sliding-window rate limit check per provider
            allowed, remaining, retry_after = await self.rate_limiter.check_and_acquire(
                provider_key
            )
            if not allowed:
                logger.warning(
                    "Streaming provider '%s' rate limited (retry_after=%.1fs); trying fallback",
                    provider_key,
                    retry_after,
                )
                last_exception = LLMRateLimitError(
                    f"Provider '{provider_key}' rate limit exceeded",
                    retry_after_s=retry_after,
                )
                continue

            adapter = self.get_adapter(model_key)
            is_fallback = idx > 0

            if is_fallback:
                logger.warning(
                    "Executing fallback streaming model '%s' for task '%s'",
                    model_key,
                    request.task,
                )

            call_start = time.time()
            stream_started = False
            total_out_tokens = 0
            try:
                async with self.concurrency_manager.acquire(provider_key, workspace_id):
                    async for chunk in adapter.stream_generate(request):
                        stream_started = True
                        if chunk.delta_content:
                            total_out_tokens += max(1, len(chunk.delta_content) // 4)
                        if workspace_id and chunk.usage:
                            self.quota_enforcer.record_usage(workspace_id, chunk.usage.total_tokens)
                        yield chunk
                # Stream finished successfully
                latency_ms = max(1, int((time.time() - call_start) * 1000))
                in_tokens = self.quota_enforcer.estimate_input_tokens(request)
                await self.usage_recorder.record_call(
                    task=request.task,
                    provider_id=provider_key,
                    model_id=model_entry.model_id,
                    input_tokens=in_tokens,
                    output_tokens=total_out_tokens,
                    latency_ms=latency_ms,
                    outcome="success",
                    workspace_id=workspace_id,
                    project_id=request.metadata.get("project_id"),
                    job_id=request.metadata.get("job_id"),
                    price_units=model_entry.price_units,
                )
                return
            except LLMRefusalError:
                latency_ms = max(1, int((time.time() - call_start) * 1000))
                await self.usage_recorder.record_call(
                    task=request.task,
                    provider_id=provider_key,
                    model_id=model_entry.model_id,
                    input_tokens=self.quota_enforcer.estimate_input_tokens(request),
                    output_tokens=total_out_tokens,
                    latency_ms=latency_ms,
                    outcome="failure",
                    workspace_id=workspace_id,
                    project_id=request.metadata.get("project_id"),
                    job_id=request.metadata.get("job_id"),
                    price_units=model_entry.price_units,
                )
                raise
            except LLMInvalidOutputError:
                latency_ms = max(1, int((time.time() - call_start) * 1000))
                await self.usage_recorder.record_call(
                    task=request.task,
                    provider_id=provider_key,
                    model_id=model_entry.model_id,
                    input_tokens=self.quota_enforcer.estimate_input_tokens(request),
                    output_tokens=total_out_tokens,
                    latency_ms=latency_ms,
                    outcome="failure",
                    workspace_id=workspace_id,
                    project_id=request.metadata.get("project_id"),
                    job_id=request.metadata.get("job_id"),
                    price_units=model_entry.price_units,
                )
                raise
            except LLMPermissionError:
                raise
            except LLMRateLimitError as exc:
                if stream_started:
                    raise
                self.rate_limiter.record_backoff(provider_key, exc.retry_after_s)
                last_exception = exc
                continue
            except Exception as exc:
                latency_ms = max(1, int((time.time() - call_start) * 1000))
                await self.usage_recorder.record_call(
                    task=request.task,
                    provider_id=provider_key,
                    model_id=model_entry.model_id,
                    input_tokens=self.quota_enforcer.estimate_input_tokens(request),
                    output_tokens=total_out_tokens,
                    latency_ms=latency_ms,
                    outcome="failure",
                    workspace_id=workspace_id,
                    project_id=request.metadata.get("project_id"),
                    job_id=request.metadata.get("job_id"),
                    price_units=model_entry.price_units,
                )
                if stream_started:
                    # If stream already began emitting tokens to the client, we cannot silently switch providers mid-stream
                    logger.error(
                        "Stream aborted mid-generation on model '%s' for task '%s': %s",
                        model_key,
                        request.task,
                        exc,
                    )
                    raise
                logger.warning(
                    "Initial stream connection failed on model '%s' for task '%s': %s",
                    model_key,
                    request.task,
                    exc,
                )
                last_exception = exc
                continue

        raise LLMUnavailableError(
            f"All eligible streaming models exhausted for task '{request.task}'. Last error: {last_exception}"
        )
