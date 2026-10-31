"""Unit and integration tests for BugMemoryAgent specialist (docs/01 CAP-03, docs/05 §6.6)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.analysis.error_normalizer import ErrorNormalizer
from app.core.auth_context import AuthContext
from app.core.ids import generate_uuid7
from app.domain.bug_memory.schemas import BugMatchResponse, ResolutionProposal
from app.llm.models import LLMGenerationResponse, TokenUsage
from app.llm.router import LLMGatewayRouter
from app.llm.schemas import BugSimilarityExplanation
from app.orchestration.bug_memory import BugMemoryAgent
from app.persistence.models.bug_memory import BugRecord, BugResolution


@pytest.fixture
def auth_ctx() -> AuthContext:
    return AuthContext(
        user_id=generate_uuid7(),
        clerk_user_id="user_test_agent",
        email="test_agent@devmind.test",
        workspace_id=generate_uuid7(),
        workspace_role="admin",
        permissions=frozenset({"project:read", "analysis:create"}),
    )


@pytest.mark.asyncio
async def test_bug_memory_agent_exact_match(auth_ctx: AuthContext) -> None:
    """Verify that an exact fingerprint match produces a high-confidence explanation and previous fix."""
    session = AsyncMock()
    project_id = generate_uuid7()
    raw_trace = (
        "Traceback (most recent call last):\n"
        '  File "/app/auth/verifier.py", line 42, in verify\n'
        "    token_id = header['kid']\n"
        "KeyError: 'kid'"
    )
    norm = ErrorNormalizer.normalize(raw_trace)

    bug_id = generate_uuid7()
    res_id = generate_uuid7()
    mock_resolution = BugResolution(
        id=res_id,
        bug_record_id=bug_id,
        cause="Missing kid header in symmetric dev tokens",
        fix_summary="Added fallback check for header.get('kid')",
        files=[{"path": "auth/verifier.py"}],
    )
    mock_record = BugRecord(
        id=bug_id,
        workspace_id=auth_ctx.workspace_id,
        project_id=project_id,
        fingerprint=norm.fingerprint,
        error_signature=norm.normalized_signature,
        title="KeyError: 'kid'",
        summary="Token header validation failure",
        module_hint="auth/verifier.py",
        occurrence_count=5,
        resolutions=[mock_resolution],
    )

    agent = BugMemoryAgent(session=session)
    agent.repo.search_similar_bugs = AsyncMock(
        return_value=[(mock_record, 1.0, "exact_fingerprint")]
    )

    resp: BugMatchResponse = await agent.match_and_explain(
        ctx=auth_ctx,
        project_id=project_id,
        raw_error=raw_trace,
    )

    assert resp.matched is True
    assert resp.confidence_label == "high"
    assert len(resp.candidates) == 1
    assert resp.candidates[0].score == 1.0
    assert resp.candidates[0].match_type == "exact_fingerprint"
    assert "Exact match found" in resp.explanation
    assert "Previous fix" in resp.explanation
    assert resp.recommended_fix == "Added fallback check for header.get('kid')"


@pytest.mark.asyncio
async def test_bug_memory_agent_fuzzy_match_fallback(auth_ctx: AuthContext) -> None:
    """Verify deterministic fallback explanation when candidate is fuzzy and no LLM router is present."""
    session = AsyncMock()
    project_id = generate_uuid7()

    bug_id = generate_uuid7()
    mock_record = BugRecord(
        id=bug_id,
        workspace_id=auth_ctx.workspace_id,
        project_id=project_id,
        fingerprint="different_hash_123",
        error_signature="KeyError in auth/verifier.py at verify",
        title="KeyError: 'alg'",
        summary="Missing algorithm specification",
        module_hint="auth/verifier.py",
        occurrence_count=2,
        resolutions=[],
    )

    agent = BugMemoryAgent(session=session)
    agent.repo.search_similar_bugs = AsyncMock(
        return_value=[(mock_record, 0.65, "fuzzy_signature")]
    )

    resp: BugMatchResponse = await agent.match_and_explain(
        ctx=auth_ctx,
        project_id=project_id,
        raw_error="KeyError: 'alg' missing in token header",
        module_hint="auth/verifier.py",
    )

    assert resp.matched is True
    assert resp.confidence_label == "medium"
    assert len(resp.candidates) == 1
    assert resp.candidates[0].score == 0.65
    assert "Similar past issue found" in resp.explanation
    assert resp.candidates[0].match_type == "fuzzy_signature"


@pytest.mark.asyncio
async def test_bug_memory_agent_zero_matches(auth_ctx: AuthContext) -> None:
    """Verify that zero matches return matched=False and confidence none."""
    session = AsyncMock()
    project_id = generate_uuid7()

    agent = BugMemoryAgent(session=session)
    agent.repo.search_similar_bugs = AsyncMock(return_value=[])

    resp = await agent.match_and_explain(
        ctx=auth_ctx,
        project_id=project_id,
        raw_error="Some completely unknown error",
    )

    assert resp.matched is False
    assert resp.confidence_label == "none"
    assert resp.candidates == []
    assert "No similar bugs found" in resp.explanation
    assert resp.recommended_fix is None


@pytest.mark.asyncio
async def test_bug_memory_agent_llm_comparison_synthesis(auth_ctx: AuthContext) -> None:
    """Verify that LLMGatewayRouter is invoked to synthesize similarity explanation when present."""
    session = AsyncMock()
    project_id = generate_uuid7()

    bug_id = generate_uuid7()
    mock_record = BugRecord(
        id=bug_id,
        workspace_id=auth_ctx.workspace_id,
        project_id=project_id,
        fingerprint="candidate_hash_xyz",
        error_signature="DatabaseConnectionTimeout in db/pool.py",
        title="DatabaseConnectionTimeout in connection pool",
        summary="Pool exhausted under heavy concurrent load",
        module_hint="db/pool.py",
        occurrence_count=3,
        resolutions=[],
    )

    # Mock LLM router
    mock_router = MagicMock(spec=LLMGatewayRouter)
    llm_explanation_payload = BugSimilarityExplanation(
        summary="Both incidents stem from pool exhaustion during parallel query spikes.",
        is_similar=True,
        confidence=0.92,
        confidence_label="high",
        shared_characteristics=["connection pool timeout", "db/pool.py"],
        differences=["Observed error has higher thread count"],
        recommended_action="Increase max_pool_size to 20 and configure idle recycle timeout.",
    )
    mock_router.generate = AsyncMock(
        return_value=LLMGenerationResponse(
            task="bug_similarity_explanation",
            model_id="primary_reasoning",
            provider_id="fake",
            content=json.dumps(llm_explanation_payload.model_dump()),
            usage=TokenUsage(input_tokens=100, output_tokens=50),
        )
    )

    agent = BugMemoryAgent(session=session, router=mock_router)
    agent.repo.search_similar_bugs = AsyncMock(
        return_value=[(mock_record, 0.75, "fuzzy_signature")]
    )

    resp = await agent.match_and_explain(
        ctx=auth_ctx,
        project_id=project_id,
        raw_error="DatabaseConnectionTimeout: QueuePool limit of size 5 overflow 10 reached",
        module_hint="db/pool.py",
    )

    assert resp.matched is True
    assert resp.confidence_label == "high"
    assert "Both incidents stem from pool exhaustion" in resp.explanation
    assert (
        resp.recommended_fix == "Increase max_pool_size to 20 and configure idle recycle timeout."
    )


def test_bug_memory_agent_propose_resolution() -> None:
    """Verify formulation and validation of resolution proposals."""
    proposal: ResolutionProposal = BugMemoryAgent.propose_resolution(
        cause="Improper handling of empty array",
        fix_summary="Added default [] when array is None",
        files=[{"path": "data/parser.py", "details": "line 15-22"}],
    )
    assert proposal.cause == "Improper handling of empty array"
    assert proposal.fix_summary == "Added default [] when array is None"
    assert len(proposal.files) == 1

    with pytest.raises(ValueError, match="cause cannot be empty"):
        BugMemoryAgent.propose_resolution(cause="  ", fix_summary="fix")

    with pytest.raises(ValueError, match="fix_summary cannot be empty"):
        BugMemoryAgent.propose_resolution(cause="cause", fix_summary="  ")
