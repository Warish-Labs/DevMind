"""Living Documentation domain package (docs/01 CAP-04, docs/03 §3.4)."""

from app.domain.living_docs.schemas import (
    DocDriftDetectRequest,
    DocDriftDetectResponse,
    DocDriftItemResponse,
    DocRecordCreate,
    DocRecordDetailResponse,
    DocRecordResponse,
    DriftActionResponse,
    DriftApprovalRequest,
    PatchProposalResponse,
)
from app.domain.living_docs.service import LivingDocService

__all__ = [
    "DocDriftDetectRequest",
    "DocDriftDetectResponse",
    "DocDriftItemResponse",
    "DocRecordCreate",
    "DocRecordDetailResponse",
    "DocRecordResponse",
    "DriftActionResponse",
    "DriftApprovalRequest",
    "LivingDocService",
    "PatchProposalResponse",
]
