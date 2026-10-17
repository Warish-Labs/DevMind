"""LLM Gateway inference accounting, cost computation, and usage persistence (docs/05 §13, docs/03 §3.5, M6-08).

Tracks and audits every LLM gateway call:
- workspace_id, project_id, job_id
- llm_task, provider_id, model_id
- input_tokens, output_tokens, total_tokens
- cost_units calculated from models.yaml price_units
- latency_ms
- outcome ('success', 'failure', 'cached', 'timeout')

Maintains in-memory audit logs and delegates persistence to an optional asynchronous
sink (such as `create_database_usage_sink` from `app.persistence`).
Architectural constraint (docs/02 §4.1): app.llm never imports app.persistence directly.
"""

from __future__ import annotations

import inspect
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.ids import generate_uuid7
from app.llm.config import ModelPriceUnitsConfig
from app.llm.models import TokenUsage

logger = logging.getLogger(__name__)

UsageOutcome = Literal["success", "failure", "cached", "timeout"]
UsageSink = Callable[["RecordedUsage"], Any]


def calculate_cost_units(
    input_tokens: int,
    output_tokens: int,
    price_units: ModelPriceUnitsConfig | None = None,
) -> int:
    """Calculate integer cost accounting units from token counts and pricing units (docs/05 §13)."""
    if not price_units:
        return 0
    in_rate = float(price_units.input_per_1k) if price_units.input_per_1k is not None else 0.0
    out_rate = float(price_units.output_per_1k) if price_units.output_per_1k is not None else 0.0
    cost = (input_tokens * in_rate + output_tokens * out_rate) / 1000.0
    return int(round(cost))


class RecordedUsage(BaseModel):
    """In-memory audit representation of an inference usage entry."""

    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=generate_uuid7)
    workspace_id: UUID | None = None
    project_id: UUID | None = None
    job_id: UUID | None = None
    llm_task: str
    provider_id: str
    model_id: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_units: int = 0
    latency_ms: int = 0
    outcome: UsageOutcome = "success"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class LLMUsageRecorder:
    """Records and meters inference calls in memory and forwards to optional persistence sink (docs/05 §13, docs/03 §3.5)."""

    def __init__(
        self,
        sink: UsageSink | None = None,
    ) -> None:
        self.sink = sink
        self.history: list[RecordedUsage] = []

    def _parse_uuid(self, val: Any) -> UUID | None:
        """Safely parse UUID from UUID object or string."""
        if val is None:
            return None
        if isinstance(val, UUID):
            return val
        if isinstance(val, str) and val.strip():
            try:
                return UUID(val.strip())
            except ValueError:
                return None
        return None

    async def record_call(
        self,
        *,
        task: str,
        provider_id: str,
        model_id: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        latency_ms: int = 0,
        outcome: UsageOutcome = "success",
        workspace_id: UUID | str | None = None,
        project_id: UUID | str | None = None,
        job_id: UUID | str | None = None,
        price_units: ModelPriceUnitsConfig | None = None,
    ) -> RecordedUsage:
        """Record an inference call, compute cost units, and optionally dispatch to persistence sink."""
        ws_uuid = self._parse_uuid(workspace_id)
        proj_uuid = self._parse_uuid(project_id)
        job_uuid = self._parse_uuid(job_id)

        cost_units = calculate_cost_units(input_tokens, output_tokens, price_units)
        total_tokens = input_tokens + output_tokens

        entry = RecordedUsage(
            workspace_id=ws_uuid,
            project_id=proj_uuid,
            job_id=job_uuid,
            llm_task=task,
            provider_id=provider_id,
            model_id=model_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost_units=cost_units,
            latency_ms=latency_ms,
            outcome=outcome,
        )

        self.history.append(entry)

        # Forward to persistence sink if configured
        if self.sink is not None:
            try:
                res = self.sink(entry)
                if inspect.isawaitable(res):
                    await res
            except Exception as exc:
                logger.error(
                    "Failed to persist usage entry for task '%s' (workspace %s): %s",
                    task,
                    ws_uuid,
                    exc,
                )

        return entry

    def get_records_for_workspace(self, workspace_id: UUID | str) -> list[RecordedUsage]:
        """Return history entries for a specific workspace."""
        ws_uuid = self._parse_uuid(workspace_id)
        if ws_uuid is None:
            return []
        return [r for r in self.history if r.workspace_id == ws_uuid]

    def get_token_totals(self, workspace_id: UUID | str | None = None) -> TokenUsage:
        """Aggregate total input and output tokens across recorded calls."""
        ws_uuid = self._parse_uuid(workspace_id) if workspace_id else None
        records = [r for r in self.history if ws_uuid is None or r.workspace_id == ws_uuid]
        input_sum = sum(r.input_tokens for r in records)
        output_sum = sum(r.output_tokens for r in records)
        return TokenUsage(
            input_tokens=input_sum,
            output_tokens=output_sum,
            total_tokens=input_sum + output_sum,
        )

    def clear_history(self) -> None:
        """Clear in-memory history (for unit testing)."""
        self.history.clear()
