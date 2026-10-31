"""Canonical structured output Pydantic schemas and schema registry (docs/05 §10, §11, M6-09).

Defines canonical task schemas referenced in tasks.yaml:
- AgentPlan (task: agent_manager_routing)
- FindingExplanation (task: security_explanation)
- SynthesizedAnswer (task: final_synthesis)
- RewrittenQuery (task: query_rewrite)

Provides SchemaRegistry for schema resolution and StructuredOutputSpec generation.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, ConfigDict, Field

from app.llm.models import StructuredOutputMode, StructuredOutputSpec

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Canonical Task Schemas
# ---------------------------------------------------------------------------


class AgentPlan(BaseModel):
    """Execution plan produced by agent manager routing (docs/05 §6, §10)."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(description="High-level plan summary")
    steps: list[str] = Field(description="Ordered list of execution steps")
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence score between 0.0 and 1.0",
    )
    selected_agents: list[str] = Field(
        default_factory=list,
        description="Specialist agents assigned to execution steps",
    )
    is_safe: bool = Field(
        default=True,
        description="Whether plan involves only read-only or proposal-gated operations",
    )


class FindingExplanation(BaseModel):
    """Detailed explanation and remediation proposal for a security finding (docs/05 §6.3, §10)."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(description="Clear summary of the security finding")
    impact: str = Field(description="Potential impact if unmitigated")
    likely_cause: str = Field(description="Underlying root cause or missing authorization check")
    remediation_proposal: str = Field(description="Suggested remediation or diff proposal")
    false_positive_indicators: list[str] = Field(
        default_factory=list,
        description="Reasons or conditions that might make this a false positive",
    )
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Confidence score between 0.0 and 1.0",
    )


class SynthesizedAnswer(BaseModel):
    """Grounded synthesis answering code questions with citations (docs/05 §6.2, §10)."""

    model_config = ConfigDict(extra="forbid")

    answer: str = Field(description="Synthesized technical answer")
    citations: list[str] = Field(
        default_factory=list,
        description="Context pack chunk IDs or file paths cited in answer",
    )
    confidence: float = Field(
        default=0.9,
        ge=0.0,
        le=1.0,
        description="Confidence score between 0.0 and 1.0",
    )
    missing_information: list[str] = Field(
        default_factory=list,
        description="Missing context or questions requiring further exploration",
    )


class RewrittenQuery(BaseModel):
    """Enhanced query for hybrid retrieval and RAG expansion (docs/04 §8, docs/05 §10)."""

    model_config = ConfigDict(extra="forbid")

    rewritten_query: str = Field(description="Expanded search query for keyword and vector search")
    keywords: list[str] = Field(
        default_factory=list,
        description="Key technical symbols, identifiers, and tokens",
    )
    intent: str = Field(description="Classified search intent")


class BugSimilarityExplanation(BaseModel):
    """Comparison and explanation of similarity between an error and a candidate bug record (docs/05 §6.6)."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(
        description="Summary of comparison between the observed error and historical bug"
    )
    is_similar: bool = Field(
        description="Whether the candidate is assessed as the same or closely related bug"
    )
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Confidence score between 0.0 and 1.0",
    )
    confidence_label: str = Field(
        default="medium",
        description="Confidence category: high, medium, or low",
    )
    shared_characteristics: list[str] = Field(
        default_factory=list,
        description="Key similarities such as exception type, module, failing operation",
    )
    differences: list[str] = Field(
        default_factory=list,
        description="Differences in call path, parameters, or environment",
    )
    recommended_action: str = Field(
        default="",
        description="Remediation or investigation recommendation based on past resolution",
    )


class DocPatchProposal(BaseModel):
    """Proposal for reconciling code and documentation drift (docs/01 CAP-04, docs/05 §6.7)."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(description="Summary of documentation update proposed")
    drift_kind: str = Field(
        description="The drift type addressed, e.g. undocumented_route or missing_symbol"
    )
    target_section: str | None = Field(
        default=None, description="Document section heading or context"
    )
    proposed_content: str = Field(
        description="Proposed documentation Markdown excerpt or replacement text"
    )
    diff_content: str = Field(
        description="Unified diff preview showing the exact documentation patch"
    )
    confidence: float = Field(
        default=0.9,
        ge=0.0,
        le=1.0,
        description="Confidence score between 0.0 and 1.0",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Reviewer notes, caveats, or prerequisites for maintainer approval",
    )


# ---------------------------------------------------------------------------
# Schema Registry
# ---------------------------------------------------------------------------


class SchemaRegistry:
    """Registry mapping task output_schema names to Pydantic models (docs/05 §10)."""

    def __init__(self) -> None:
        self._schemas: dict[str, type[BaseModel]] = {}
        # Pre-register canonical task schemas
        self.register("AgentPlan", AgentPlan)
        self.register("FindingExplanation", FindingExplanation)
        self.register("SynthesizedAnswer", SynthesizedAnswer)
        self.register("RewrittenQuery", RewrittenQuery)
        self.register("BugSimilarityExplanation", BugSimilarityExplanation)
        self.register("DocPatchProposal", DocPatchProposal)

    def register(self, name: str, schema_cls: type[BaseModel]) -> None:
        """Register a Pydantic model under a schema name."""
        self._schemas[name] = schema_cls

    def get(self, name: str) -> type[BaseModel] | None:
        """Retrieve a registered schema by name."""
        return self._schemas.get(name)

    def contains(self, name: str) -> bool:
        """Check if schema name is registered."""
        return name in self._schemas

    def build_spec(
        self,
        schema_name_or_cls: str | type[BaseModel],
        mode: StructuredOutputMode = "native",
        strict: bool = True,
    ) -> StructuredOutputSpec:
        """Build StructuredOutputSpec from a registered schema name or Pydantic model class."""
        if isinstance(schema_name_or_cls, str):
            schema_name = schema_name_or_cls
            schema_cls = self.get(schema_name)
            if schema_cls is None:
                raise ValueError(f"Schema '{schema_name}' is not registered in SchemaRegistry")
        elif isinstance(schema_name_or_cls, type) and issubclass(schema_name_or_cls, BaseModel):
            schema_cls = schema_name_or_cls
            schema_name = schema_cls.__name__
        else:
            raise TypeError(
                f"Expected schema name (str) or BaseModel subclass, got {type(schema_name_or_cls)}"
            )

        schema_dict = schema_cls.model_json_schema()

        return StructuredOutputSpec(
            schema_name=schema_name,
            schema_def=schema_dict,
            mode=mode,
            strict=strict,
        )

    def get_spec(
        self,
        schema_name_or_cls: str | type[BaseModel],
        mode: StructuredOutputMode = "native",
        strict: bool = True,
    ) -> StructuredOutputSpec:
        """Alias for build_spec."""
        return self.build_spec(schema_name_or_cls, mode=mode, strict=strict)


# Global default registry instance
default_schema_registry = SchemaRegistry()
