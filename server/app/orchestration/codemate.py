"""CodeMate workflow nodes, reasoning loop, and citation validation (docs/04 §8.7, docs/05 §6.1-§6.2, CAP-01, M7-04).

Per docs/05 §6.2 (CodeMate specification):
1. Retrieve a context pack (docs/04 §8) for the developer question.
2. Generate an answer constrained to the pack (`code_answer` task), requiring citations by pack ID / line range.
3. Deterministic post-check: every citation resolves against the pack; claims with unresolvable citations
   are flagged and trimmed or the answer regenerated once.
4. If the pack is insufficient, respond stating clearly what information is missing.
"""

from __future__ import annotations

import logging
import re
from typing import Annotated, Any, TypedDict
from uuid import UUID

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_context import AuthContext
from app.core.ids import generate_uuid7
from app.llm.models import LLMGenerationRequest
from app.llm.prompt_loader import PromptLoader
from app.llm.router import LLMGatewayRouter
from app.llm.schemas import SynthesizedAnswer
from app.orchestration.state import (
    CitationRef,
    Hypothesis,
    NodeError,
    RunState,
    SpecialistTask,
    UsageTotals,
    append_items,
    merge_usage_totals,
)
from app.orchestration.tools import search_brain

logger = logging.getLogger("devmind.orchestration.codemate")

# Regex to detect bracketed inline citations in model generated markdown
# Matches: [path/file.py:10-25], [server/app/main.py], [chunk_id], (server/app/auth.py:5-15)
_INLINE_CITATION_RE = re.compile(
    r"\[([a-zA-Z0-9_\-./]+(?::\d+(?:-\d+)?)?)\]|\(([a-zA-Z0-9_\-./]+:\d+(?:-\d+)?)\)"
)


# ---------------------------------------------------------------------------
# Citation Validation Engine (docs/04 §8.7, docs/05 §6.2)
# ---------------------------------------------------------------------------


class CitationValidationResult(BaseModel):
    """Result of deterministic citation verification against retrieved context pack."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    resolved_citations: list[CitationRef] = Field(
        default_factory=list,
        description="Citations successfully resolved to existing pack chunks or symbols",
    )
    unresolved_citations: list[str] = Field(
        default_factory=list,
        description="Citations referencing non-existent files, hallucinated paths, or disjoint lines",
    )
    grounding_ratio: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Fraction of citations that resolved to verified context items",
    )
    is_fully_grounded: bool = Field(
        default=True,
        description="True if zero unresolved citations exist and all claims are verifiable",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Validation feedback and provenance notes",
    )


def resolve_single_citation(
    raw_citation: str,
    available_refs: list[CitationRef],
) -> CitationRef | None:
    """Attempt to resolve a single citation string against available provenance references.

    Supports:
    - Exact doc_id / chunk ID match: e.g. "chunk_01a14..."
    - Symbol name match: e.g. "create_app"
    - Path match: e.g. "server/app/main.py"
    - Path and line range overlap match: e.g. "server/app/main.py:10-30" overlapping [5, 40]
    """
    clean = raw_citation.strip().strip("[]()").strip()
    if not clean:
        return None

    for ref in available_refs:
        # 1. Match by doc_id
        if clean == ref.doc_id:
            return ref

        # 2. Match by symbol
        if ref.symbol and clean == ref.symbol:
            return ref

        # 3. Match with line numbers: "path:start-end" or "path:line"
        if ":" in clean:
            path_part, line_part = clean.split(":", 1)
            path_part = path_part.strip()
            line_part = line_part.strip()

            if path_part == ref.path or ref.path.endswith(path_part):
                if "-" in line_part:
                    parts = line_part.split("-", 1)
                    try:
                        s_line, e_line = int(parts[0]), int(parts[1])
                        # Overlap: max(start1, start2) <= min(end1, end2)
                        if max(s_line, ref.start_line) <= min(e_line, ref.end_line):
                            return ref
                    except ValueError:
                        pass
                else:
                    try:
                        line_num = int(line_part)
                        if ref.start_line <= line_num <= ref.end_line:
                            return ref
                    except ValueError:
                        pass

        # 4. Match by file path directly
        elif clean == ref.path or ref.path.endswith(clean):
            return ref

    return None


def validate_citations(
    cited_identifiers: list[str],
    available_refs: list[CitationRef],
    answer_text: str | None = None,
) -> CitationValidationResult:
    """Deterministically verify all citations in model output against retrieved references.

    Extracts both structured citations and inline markdown citations.
    Every citation must resolve to a known chunk, symbol, or file range in the pack.
    """
    all_cited: set[str] = set()

    # Add structured citations
    for c in cited_identifiers:
        if c and c.strip():
            all_cited.add(c.strip())

    # Extract inline citations from text
    if answer_text:
        matches = _INLINE_CITATION_RE.findall(answer_text)
        for m in matches:
            cit = m[0] or m[1]
            if cit and cit.strip():
                all_cited.add(cit.strip())

    resolved: list[CitationRef] = []
    unresolved: list[str] = []
    seen_resolved_ids: set[str] = set()

    for cit in all_cited:
        res = resolve_single_citation(cit, available_refs)
        if res:
            if res.doc_id not in seen_resolved_ids:
                resolved.append(res)
                seen_resolved_ids.add(res.doc_id)
        else:
            unresolved.append(cit)

    total_citations = len(resolved) + len(unresolved)
    grounding_ratio = (len(resolved) / total_citations) if total_citations > 0 else 1.0
    is_fully_grounded = len(unresolved) == 0

    notes: list[str] = []
    if unresolved:
        notes.append(f"Unresolved citations detected: {', '.join(unresolved)}")
    if resolved:
        notes.append(f"Successfully resolved {len(resolved)} citations against retrieved pack.")

    return CitationValidationResult(
        resolved_citations=resolved,
        unresolved_citations=unresolved,
        grounding_ratio=round(grounding_ratio, 4),
        is_fully_grounded=is_fully_grounded,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# CodeMate Graph State (docs/05 §4.2, §6.2)
# ---------------------------------------------------------------------------


class CodeMateState(TypedDict):
    """Execution state for the CodeMate specialist graph."""

    user_query: str
    project_id: str
    workspace_id: str
    context_pack_text: str
    context_refs: list[CitationRef]
    answer: str | None
    citations: list[str]
    verified_citations: list[CitationRef]
    unresolved_citations: list[str]
    is_insufficient: bool
    missing_information: list[str]
    regeneration_attempted: bool
    final_response: str | None
    status: str  # 'running', 'completed', 'failed'
    errors: Annotated[list[NodeError], append_items]
    usage: Annotated[UsageTotals, merge_usage_totals]


def create_initial_codemate_state(
    user_query: str,
    project_id: str,
    workspace_id: str,
    context_refs: list[CitationRef] | None = None,
    context_pack_text: str | None = None,
) -> CodeMateState:
    """Create initial state for CodeMate execution."""
    return {
        "user_query": user_query,
        "project_id": project_id,
        "workspace_id": workspace_id,
        "context_pack_text": context_pack_text or "",
        "context_refs": list(context_refs or []),
        "answer": None,
        "citations": [],
        "verified_citations": [],
        "unresolved_citations": [],
        "is_insufficient": False,
        "missing_information": [],
        "regeneration_attempted": False,
        "final_response": None,
        "status": "running",
        "errors": [],
        "usage": UsageTotals(),
    }


# ---------------------------------------------------------------------------
# CodeMate Graph Nodes (docs/05 §6.2)
# ---------------------------------------------------------------------------


def retrieve_context_node_factory(session: AsyncSession | None = None):
    """Factory creating context retrieval node using the Project Brain."""

    async def retrieve_context_node(state: CodeMateState) -> dict[str, Any]:
        # If context was already populated from caller, reuse it
        if state.get("context_pack_text") and state.get("context_refs"):
            return {
                "is_insufficient": False,
            }

        user_query = state.get("user_query", "").strip()
        project_id_str = state.get("project_id")
        workspace_id_str = state.get("workspace_id")

        if not user_query or not project_id_str:
            return {
                "is_insufficient": True,
                "missing_information": ["No query or project specified for CodeMate"],
            }

        # If a live session is available, execute hybrid search
        if session:
            try:
                project_id = UUID(project_id_str)
                workspace_id = UUID(workspace_id_str) if workspace_id_str else generate_uuid7()
                ctx = AuthContext(
                    user_id=generate_uuid7(),
                    clerk_user_id="user_clerk_codemate",
                    email="codemate@devmind.internal",
                    workspace_id=workspace_id,
                    workspace_role="member",
                    permissions=frozenset({"project:read", "brain:read"}),
                )
                search_res = await search_brain(
                    ctx=ctx,
                    project_id=project_id,
                    session=session,
                    query=user_query,
                    limit=10,
                )

                items = search_res.get("items", [])

                if not items:
                    return {
                        "is_insufficient": True,
                        "context_pack_text": "",
                        "context_refs": [],
                        "missing_information": [
                            f"No matching code chunks or symbols found in Project Brain for '{user_query}'"
                        ],
                    }

                # Build context text formatted per docs/04 §8
                blocks: list[str] = []
                refs: list[CitationRef] = []
                for idx, it in enumerate(items, 1):
                    doc_id = it.get("id", f"doc_{idx}")
                    path = it.get("path", "unknown")
                    s_line = it.get("start_line", 1)
                    e_line = it.get("end_line", 1)
                    symbol = it.get("symbol_key")
                    content = it.get("content", "")

                    blocks.append(
                        f"### [{idx}] {path}:{s_line}-{e_line} (ID: {doc_id})\n```\n{content}\n```\n"
                    )
                    refs.append(
                        CitationRef(
                            doc_id=doc_id,
                            path=path,
                            start_line=s_line,
                            end_line=e_line,
                            symbol=symbol,
                            score=it.get("score"),
                        )
                    )

                context_pack_text = "\n".join(blocks)
                return {
                    "context_pack_text": context_pack_text,
                    "context_refs": refs,
                    "is_insufficient": False,
                }

            except Exception as exc:
                logger.warning("CodeMate retrieval failed: %s", exc)
                return {
                    "is_insufficient": True,
                    "missing_information": [f"Retrieval error: {exc}"],
                    "errors": [
                        NodeError(
                            node="retrieve_context",
                            error_code="retrieval_failed",
                            message=str(exc),
                        )
                    ],
                }

        # Default fallback when no session is attached and no pre-populated context
        if not state.get("context_refs"):
            return {
                "is_insufficient": True,
                "missing_information": [
                    f"No code context available in Project Brain for query '{user_query}'"
                ],
            }

        return {"is_insufficient": False}

    return retrieve_context_node


def check_sufficiency(state: CodeMateState) -> str:
    """Check if retrieved context pack is sufficient for generation."""
    if state.get("is_insufficient"):
        return "insufficient_context"
    return "generate_answer"


def insufficient_context_node(state: CodeMateState) -> dict[str, Any]:
    """Emit explicit response when context pack is insufficient per docs/05 §6.2 step 4."""
    user_query = state.get("user_query", "")
    missing = state.get("missing_information", [])
    missing_desc = "; ".join(missing) if missing else "No matching code found in Project Brain"

    msg = (
        f"Retrieved code context is insufficient to answer the question about '{user_query}'.\n\n"
        f"**Missing Context:** {missing_desc}.\n\n"
        f"Please ensure the repository has been indexed or verify the symbol name."
    )

    return {
        "final_response": msg,
        "answer": msg,
        "citations": [],
        "verified_citations": [],
        "unresolved_citations": [],
        "status": "completed",
    }


def generate_answer_node_factory(
    router: LLMGatewayRouter | None = None,
    prompt_loader: PromptLoader | None = None,
):
    """Factory creating LLM generation node for code_answer."""

    async def generate_answer_node(state: CodeMateState) -> dict[str, Any]:
        user_query = state.get("user_query", "")
        context_pack = state.get("context_pack_text", "")

        # Fallback if no LLM router is available (deterministic grounding)
        if router is None or prompt_loader is None:
            refs = state.get("context_refs", [])
            citations = [r.to_citation_string() for r in refs[:3]]
            summary_answer = (
                f"Based on the retrieved context for '{user_query}', the following source locations "
                f"were identified:\n\n"
            )
            for r in refs[:3]:
                summary_answer += f"- [{r.to_citation_string()}]: Symbol `{r.symbol or r.path}`\n"

            return {
                "answer": summary_answer,
                "citations": citations,
            }

        try:
            rendered = prompt_loader.render(
                task="code_answer",
                version=1,
                variables={
                    "user_query": user_query,
                    "context_pack": context_pack,
                },
            )

            gen_req = LLMGenerationRequest(
                task="code_answer",
                messages=rendered.messages,
            )

            resp = await router.generate(gen_req)
            answer_text = resp.raw_content or (
                resp.content if isinstance(resp.content, str) else str(resp.content)
            )

            # Extract any citations provided in response
            extracted_citations: list[str] = []
            matches = _INLINE_CITATION_RE.findall(answer_text)
            for m in matches:
                cit = m[0] or m[1]
                if cit:
                    extracted_citations.append(cit.strip())

            return {
                "answer": answer_text,
                "citations": extracted_citations,
                "usage": UsageTotals(
                    total_input_tokens=resp.usage.input_tokens if resp.usage else 0,
                    total_output_tokens=resp.usage.output_tokens if resp.usage else 0,
                    total_cost_units=resp.usage.total_cost if resp.usage else 0,
                    model_calls=1,
                ),
            }

        except Exception as exc:
            logger.warning(
                "LLM code_answer generation failed: %s; using deterministic fallback", exc
            )
            refs = state.get("context_refs", [])
            citations = [r.to_citation_string() for r in refs[:3]]
            return {
                "answer": f"CodeMate identified the following relevant code locations for '{user_query}': "
                + ", ".join(f"[{c}]" for c in citations),
                "citations": citations,
                "errors": [
                    NodeError(
                        node="generate_answer",
                        error_code="generation_failed",
                        message=str(exc),
                    )
                ],
            }

    return generate_answer_node


def validate_citations_node(state: CodeMateState) -> dict[str, Any]:
    """Execute deterministic citation post-check against context pack (docs/05 §6.2 step 3)."""
    citations = state.get("citations", [])
    answer = state.get("answer", "")
    available_refs = state.get("context_refs", [])

    val_res = validate_citations(
        cited_identifiers=citations,
        available_refs=available_refs,
        answer_text=answer,
    )

    return {
        "verified_citations": val_res.resolved_citations,
        "unresolved_citations": val_res.unresolved_citations,
    }


def check_citations_edge(state: CodeMateState) -> str:
    """Decide whether to regenerate if unresolvable citations exist."""
    unresolved = state.get("unresolved_citations", [])
    regeneration_attempted = state.get("regeneration_attempted", False)

    # Regenerate once if unresolved citations are detected
    if unresolved and not regeneration_attempted:
        return "regenerate_answer"
    return "finalize"


def regenerate_answer_node_factory(
    router: LLMGatewayRouter | None = None,
    prompt_loader: PromptLoader | None = None,
):
    """Regenerate answer once with strict citation constraints on unresolvable claims."""

    async def regenerate_answer_node(state: CodeMateState) -> dict[str, Any]:
        logger.info(
            "Regenerating CodeMate answer; unresolvable citations: %s",
            state.get("unresolved_citations"),
        )
        user_query = state.get("user_query", "")
        context_pack = state.get("context_pack_text", "")
        available_refs = state.get("context_refs", [])
        valid_options = ", ".join(r.to_citation_string() for r in available_refs[:5])

        if router is None or prompt_loader is None:
            # Deterministic trim of invalid citations
            answer = state.get("answer", "")
            for unres in state.get("unresolved_citations", []):
                answer = answer.replace(f"[{unres}]", "").replace(f"({unres})", "")
            return {
                "answer": answer.strip(),
                "regeneration_attempted": True,
                "unresolved_citations": [],
            }

        try:
            rendered = prompt_loader.render(
                task="code_answer",
                version=1,
                variables={
                    "user_query": (
                        f"{user_query}\n\n"
                        f"[NOTE: Ensure every claim strictly cites only valid locations: {valid_options}]"
                    ),
                    "context_pack": context_pack,
                },
            )

            resp = await router.generate(
                LLMGenerationRequest(task="code_answer", messages=rendered.messages)
            )
            answer_text = resp.raw_content or str(resp.content)

            # Re-validate
            val_res = validate_citations([], available_refs, answer_text)

            return {
                "answer": answer_text,
                "verified_citations": val_res.resolved_citations,
                "unresolved_citations": val_res.unresolved_citations,
                "regeneration_attempted": True,
            }

        except Exception as exc:
            logger.warning("CodeMate regeneration failed: %s", exc)
            return {"regeneration_attempted": True}

    return regenerate_answer_node


def finalize_node(state: CodeMateState) -> dict[str, Any]:
    """Finalize CodeMate output and attach verified citations."""
    answer = state.get("answer") or state.get("final_response") or "No answer generated."
    unresolved = state.get("unresolved_citations", [])

    # If any unresolvable citations remain after regeneration attempt, flag them
    if unresolved:
        answer += (
            f"\n\n> Note: Unverified citations flagged during post-check: {', '.join(unresolved)}"
        )

    return {
        "final_response": answer,
        "status": "completed",
    }


# ---------------------------------------------------------------------------
# CodeMate Graph Builder & Agent Class (docs/05 §6.2)
# ---------------------------------------------------------------------------


def build_codemate_graph(
    router: LLMGatewayRouter | None = None,
    prompt_loader: PromptLoader | None = None,
    session: AsyncSession | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    """Construct and compile the CodeMate reasoning and citation validation graph."""
    builder = StateGraph(CodeMateState)

    # Nodes
    builder.add_node("retrieve_context", retrieve_context_node_factory(session=session))
    builder.add_node("insufficient_context", insufficient_context_node)
    builder.add_node("generate_answer", generate_answer_node_factory(router, prompt_loader))
    builder.add_node("validate_citations", validate_citations_node)
    builder.add_node("regenerate_answer", regenerate_answer_node_factory(router, prompt_loader))
    builder.add_node("finalize", finalize_node)

    # Edges
    builder.add_edge(START, "retrieve_context")
    builder.add_conditional_edges(
        "retrieve_context",
        check_sufficiency,
        ["generate_answer", "insufficient_context"],
    )
    builder.add_edge("insufficient_context", "finalize")
    builder.add_edge("generate_answer", "validate_citations")
    builder.add_conditional_edges(
        "validate_citations",
        check_citations_edge,
        ["regenerate_answer", "finalize"],
    )
    builder.add_edge("regenerate_answer", "finalize")
    builder.add_edge("finalize", END)

    return builder.compile(checkpointer=checkpointer)


class CodeMateAgent:
    """Standalone CodeMate specialist agent for code intelligence and grounded QA (CAP-01)."""

    def __init__(
        self,
        router: LLMGatewayRouter | None = None,
        prompt_loader: PromptLoader | None = None,
        session: AsyncSession | None = None,
        checkpointer: BaseCheckpointSaver | None = None,
    ) -> None:
        self.router = router
        self.prompt_loader = prompt_loader
        self.session = session
        self.checkpointer = checkpointer
        self.graph = build_codemate_graph(
            router=self.router,
            prompt_loader=self.prompt_loader,
            session=self.session,
            checkpointer=self.checkpointer,
        )

    async def run(
        self,
        state: CodeMateState,
        thread_id: str | None = None,
    ) -> CodeMateState:
        """Execute CodeMate workflow for a given query state."""
        config = {"configurable": {"thread_id": thread_id}} if thread_id else None
        return await self.graph.ainvoke(state, config=config)

    async def answer_question(
        self,
        user_query: str,
        project_id: str,
        workspace_id: str,
        context_refs: list[CitationRef] | None = None,
        context_pack_text: str | None = None,
    ) -> SynthesizedAnswer:
        """High-level entry point answering a developer question with grounded citations."""
        init_state = create_initial_codemate_state(
            user_query=user_query,
            project_id=project_id,
            workspace_id=workspace_id,
            context_refs=context_refs,
            context_pack_text=context_pack_text,
        )
        res = await self.run(init_state)

        verified = [c.to_citation_string() for c in res.get("verified_citations", [])]
        missing = res.get("missing_information", [])

        return SynthesizedAnswer(
            answer=res.get("final_response") or res.get("answer") or "No answer produced.",
            citations=verified,
            confidence=0.95 if verified and not missing else 0.5,
            missing_information=missing,
        )


# ---------------------------------------------------------------------------
# Specialist Node Runner for Agent Manager Integration
# ---------------------------------------------------------------------------


async def run_codemate_specialist(
    state: RunState,
    router: LLMGatewayRouter | None = None,
    prompt_loader: PromptLoader | None = None,
    session: AsyncSession | None = None,
) -> dict[str, Any]:
    """Execute CodeMate as a specialist node inside Agent Manager."""
    user_query = state["request"].user_message or state["request"].params.get("query", "")
    project_id = state.get("project_id", "")
    workspace_id = state.get("workspace_id", "")

    agent = CodeMateAgent(
        router=router,
        prompt_loader=prompt_loader,
        session=session,
    )

    init_state = create_initial_codemate_state(
        user_query=user_query,
        project_id=project_id,
        workspace_id=workspace_id,
        context_refs=list(state.get("context_refs", [])),
    )

    res = await agent.run(init_state)

    plan = list(state.get("plan", []))
    task = next((t for t in plan if t.specialist == "codemate"), None)
    task_id = task.task_id if task else f"codemate_{state.get('run_id', 'run')[:8]}"

    completed_task = SpecialistTask(
        specialist="codemate",
        task_id=task_id,
        status="completed",
        input_refs=[c.to_citation_string() for c in res.get("verified_citations", [])],
        params=state["request"].params,
    )

    hypotheses = list(state.get("hypotheses", []))
    if res.get("final_response"):
        hypotheses.append(
            Hypothesis(
                statement=res["final_response"],
                basis_refs=[c.to_citation_string() for c in res.get("verified_citations", [])],
                confidence=0.9 if res.get("verified_citations") else 0.5,
            )
        )

    return {
        "plan": [completed_task],
        "context_refs": res.get("verified_citations", []),
        "hypotheses": hypotheses,
        "final_response": res.get("final_response"),
        "usage": res.get("usage", UsageTotals()),
    }
