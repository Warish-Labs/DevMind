"""Bug Memory domain module (docs/01 CAP-03, docs/03 §3.4)."""

from app.domain.bug_memory.schemas import (
    BugMatchCandidateResponse,
    BugMatchRequest,
    BugMatchResponse,
    BugRecordCreate,
    BugRecordDetailResponse,
    BugRecordResponse,
    BugResolutionCreate,
    BugResolutionResponse,
    NormalizedErrorSummary,
    ResolutionProposal,
)
from app.domain.bug_memory.service import BugMemoryService

__all__ = [
    "BugMatchCandidateResponse",
    "BugMatchRequest",
    "BugMatchResponse",
    "BugMemoryService",
    "BugRecordCreate",
    "BugRecordDetailResponse",
    "BugRecordResponse",
    "BugResolutionCreate",
    "BugResolutionResponse",
    "NormalizedErrorSummary",
    "ResolutionProposal",
]
