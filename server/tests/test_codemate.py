"""Tests for CodeMate workflow nodes, reasoning loop, and citation validation (docs/04 §8.7, docs/05 §6.2, CAP-01, M7-04).

Verifies:
1. Citation resolution by doc_id, symbol key, file path, and overlapping line ranges.
2. Extraction of structured and inline markdown citations ([path:start-end]).
3. Insufficient context detection and explicit missing-context explanations.
4. Grounded answer generation strictly constrained to context pack.
5. Regeneration trigger on unresolvable citations.
6. SynthesizedAnswer schema generation via CodeMateAgent.
7. End-to-end integration with Agent Manager workflow.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.ids import generate_uuid7
from app.llm.models import LLMGenerationResponse
from app.llm.router import LLMGatewayRouter
from app.llm.schemas import SynthesizedAnswer
from app.orchestration.codemate import (
    CitationValidationResult,
    CodeMateAgent,
    create_initial_codemate_state,
    resolve_single_citation,
    validate_citations,
)
from app.orchestration.manager import AgentManager
from app.orchestration.state import (
    CitationRef,
    create_initial_run_state,
)


def _make_refs() -> list[CitationRef]:
    return [
        CitationRef(
            doc_id="chunk_001",
            path="server/app/main.py",
            start_line=10,
            end_line=50,
            symbol="create_app",
            score=0.95,
        ),
        CitationRef(
            doc_id="chunk_002",
            path="server/app/core/auth_context.py",
            start_line=20,
            end_line=60,
            symbol="AuthContext",
            score=0.88,
        ),
    ]


# ---------------------------------------------------------------------------
# Citation Resolution & Validation Tests (docs/04 §8.7)
# ---------------------------------------------------------------------------


def test_resolve_single_citation_variations() -> None:
    """Verify single citation resolution against diverse citation formats."""
    refs = _make_refs()

    # 1. Exact doc_id
    res1 = resolve_single_citation("chunk_001", refs)
    assert res1 is not None
    assert res1.path == "server/app/main.py"

    # 2. Symbol name
    res2 = resolve_single_citation("create_app", refs)
    assert res2 is not None
    assert res2.doc_id == "chunk_001"

    # 3. Path and overlapping line range
    res3 = resolve_single_citation("server/app/main.py:20-40", refs)
    assert res3 is not None
    assert res3.doc_id == "chunk_001"

    # 4. Path and single overlapping line
    res4 = resolve_single_citation("server/app/core/auth_context.py:35", refs)
    assert res4 is not None
    assert res4.symbol == "AuthContext"

    # 5. Non-overlapping line range (disjoint)
    res_disjoint = resolve_single_citation("server/app/main.py:100-150", refs)
    assert res_disjoint is None

    # 6. Non-existent path
    res_missing = resolve_single_citation("server/app/missing_service.py:10-20", refs)
    assert res_missing is None


def test_validate_citations_structured_and_inline() -> None:
    """Verify validate_citations extracts inline markdown citations and computes grounding ratio."""
    refs = _make_refs()
    answer_text = (
        "The application bootstrap starts in [server/app/main.py:15-30] where FastAPI is configured. "
        "User context is parsed by [AuthContext] in (server/app/core/auth_context.py:25-45). "
        "However, secret hashing occurs in [server/app/crypto.py:1-10]."
    )
    structured_citations = ["chunk_001", "non_existent_doc_id"]

    val_res: CitationValidationResult = validate_citations(
        cited_identifiers=structured_citations,
        available_refs=refs,
        answer_text=answer_text,
    )

    # chunk_001, server/app/main.py:15-30, AuthContext, server/app/core/auth_context.py:25-45 should resolve
    resolved_paths = {r.path for r in val_res.resolved_citations}
    assert "server/app/main.py" in resolved_paths
    assert "server/app/core/auth_context.py" in resolved_paths

    # non_existent_doc_id and server/app/crypto.py:1-10 are unresolved
    assert "non_existent_doc_id" in val_res.unresolved_citations
    assert "server/app/crypto.py:1-10" in val_res.unresolved_citations

    assert val_res.is_fully_grounded is False
    assert 0.0 < val_res.grounding_ratio < 1.0


# ---------------------------------------------------------------------------
# CodeMate Graph Execution Tests (docs/05 §6.2)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_codemate_graph_insufficient_context() -> None:
    """Verify CodeMate emits clear missing context explanation when pack has zero chunks."""
    agent = CodeMateAgent(router=None, prompt_loader=None, session=None)
    state = create_initial_codemate_state(
        user_query="How does Stripe billing webhook work?",
        project_id=str(generate_uuid7()),
        workspace_id=str(generate_uuid7()),
        context_refs=[],
        context_pack_text="",
    )

    res = await agent.run(state)

    assert res["status"] == "completed"
    assert res["is_insufficient"] is True
    assert "insufficient to answer the question" in res["final_response"]
    assert len(res["missing_information"]) > 0


@pytest.mark.asyncio
async def test_codemate_graph_grounded_answer() -> None:
    """Verify CodeMate generates grounded answer with verified citations."""
    refs = _make_refs()
    context_pack_text = (
        "### [1] server/app/main.py:10-50 (ID: chunk_001)\n```python\ndef create_app(): ...\n```\n"
    )

    agent = CodeMateAgent(router=None, prompt_loader=None, session=None)
    state = create_initial_codemate_state(
        user_query="How is the application initialized?",
        project_id=str(generate_uuid7()),
        workspace_id=str(generate_uuid7()),
        context_refs=refs,
        context_pack_text=context_pack_text,
    )

    res = await agent.run(state)

    assert res["status"] == "completed"
    assert res["is_insufficient"] is False
    assert len(res["verified_citations"]) > 0
    assert len(res["unresolved_citations"]) == 0
    assert "server/app/main.py:10-50" in res["final_response"]


@pytest.mark.asyncio
async def test_codemate_graph_regeneration_on_unresolved_citations() -> None:
    """Verify CodeMate triggers one regeneration when model output has hallucinated citations."""
    refs = _make_refs()
    context_pack_text = "### [1] server/app/main.py:10-50\n```\ndef create_app(): pass\n```\n"

    mock_router = AsyncMock(spec=LLMGatewayRouter)
    # First response includes hallucinated citation [hallucinated.py:1-10]
    resp1 = MagicMock(spec=LLMGenerationResponse)
    resp1.content = "Initialized in [server/app/main.py:10-50] and [hallucinated.py:1-10]"
    resp1.raw_content = resp1.content
    resp1.usage = None

    # Second response (regenerated) fixes the citation
    resp2 = MagicMock(spec=LLMGenerationResponse)
    resp2.content = "Initialized in [server/app/main.py:10-50]"
    resp2.raw_content = resp2.content
    resp2.usage = None

    mock_router.generate.side_effect = [resp1, resp2]

    mock_loader = MagicMock()
    mock_loader.render.return_value = MagicMock(messages=[])

    agent = CodeMateAgent(router=mock_router, prompt_loader=mock_loader, session=None)
    state = create_initial_codemate_state(
        user_query="How is create_app built?",
        project_id=str(generate_uuid7()),
        workspace_id=str(generate_uuid7()),
        context_refs=refs,
        context_pack_text=context_pack_text,
    )

    res = await agent.run(state)

    assert res["status"] == "completed"
    assert res["regeneration_attempted"] is True
    assert mock_router.generate.call_count == 2
    assert len(res["verified_citations"]) == 1
    assert len(res["unresolved_citations"]) == 0


@pytest.mark.asyncio
async def test_codemate_agent_answer_question() -> None:
    """Verify CodeMateAgent.answer_question returns SynthesizedAnswer schema."""
    refs = _make_refs()
    agent = CodeMateAgent(router=None, prompt_loader=None, session=None)

    synth_ans: SynthesizedAnswer = await agent.answer_question(
        user_query="Explain AuthContext",
        project_id=str(generate_uuid7()),
        workspace_id=str(generate_uuid7()),
        context_refs=refs,
        context_pack_text="### [2] server/app/core/auth_context.py:20-60\nclass AuthContext:\n",
    )

    assert isinstance(synth_ans, SynthesizedAnswer)
    assert len(synth_ans.citations) > 0
    assert synth_ans.confidence >= 0.9
    assert len(synth_ans.missing_information) == 0


# ---------------------------------------------------------------------------
# Agent Manager Integration Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_manager_executes_codemate_specialist() -> None:
    """Verify Agent Manager ask_project run invokes CodeMate specialist workflow."""
    manager = AgentManager(router=None, prompt_loader=None, interrupt_on_approval=False)

    run_id = str(generate_uuid7())
    project_id = str(generate_uuid7())
    workspace_id = str(generate_uuid7())
    state = create_initial_run_state(
        run_id=run_id,
        job_id=str(generate_uuid7()),
        project_id=project_id,
        workspace_id=workspace_id,
        actor_id="user_clerk_test",
        job_type="ask_project",
        params={"query": "How is the app started?"},
        user_message="How is the app started?",
    )
    # Pre-attach context refs
    state["context_refs"] = _make_refs()

    result = await manager.run(state)

    assert result["status"] == "completed"
    assert result["plan"][0].specialist == "codemate"
    assert result["plan"][0].status == "completed"
    assert len(result["hypotheses"]) > 0
    assert len(result["plan"][0].input_refs) > 0
