export interface CitationItem {
  id: string;
  index: number;
  path: string;
  startLine: number;
  endLine: number;
  snippet: string;
  symbolName?: string;
  role?: "rule_hit" | "structural_check" | "retrieved_context" | "symbol_definition";
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  activityLines?: string[];
  citations?: CitationItem[];
  hasInsufficientEvidence?: boolean;
  insufficientEvidenceReason?: string;
  suggestedNextSteps?: string[];
  createdAt: string;
  isStreaming?: boolean;
  jobId?: string;
}

export interface ConversationFilterState {
  searchQuery: string;
}

export const STARTER_PROMPTS: string[] = [
  "How is multi-tenant isolation enforced in database queries?",
  "Where are route permissions declared and validated?",
  "What is the lifecycle state machine for security findings?",
  "Explain the fallback mechanism when LLM providers experience outages.",
];

export const SAMPLE_CITATIONS: CitationItem[] = [
  {
    id: "cit-01",
    index: 1,
    path: "server/app/domain/auth/permissions.py",
    startLine: 28,
    endLine: 45,
    symbolName: "require_permission",
    role: "structural_check",
    snippet: `def require_permission(permission: str):
    """FastAPI dependency factory enforcing AuthContext role permissions."""
    async def _dependency(ctx: AuthContext = Depends(get_auth_context)) -> AuthContext:
        if not ctx.has_permission(permission):
            raise ForbiddenError(f"Missing required permission '{permission}'")
        return ctx
    return _dependency`,
  },
  {
    id: "cit-02",
    index: 2,
    path: "server/app/api/findings.py",
    startLine: 98,
    endLine: 118,
    symbolName: "transition_finding_status",
    role: "retrieved_context",
    snippet: `@router.post("/{fid}/transitions")
@declare_permission(PERM_FINDING_PROGRESS)
async def transition_finding_status(
    pid: UUID,
    fid: UUID,
    payload: FindingStatusTransitionRequest,
    ctx: AuthContext = Depends(require_permission(PERM_FINDING_PROGRESS)),
):
    target = payload.to_status.lower()
    if target in ("dismissed", "accepted_risk") and not ctx.has_permission(PERM_FINDING_TRIAGE):
        raise ForbiddenError("Triage requires maintainer role")`,
  },
  {
    id: "cit-03",
    index: 3,
    path: "server/app/domain/brain/repository.py",
    startLine: 54,
    endLine: 72,
    symbolName: "resolve_project_context",
    role: "structural_check",
    snippet: `async def resolve_project_context(self, ctx: AuthContext, project_id: UUID) -> AuthContext:
    # Tenant boundary enforcement: verify project belongs to caller workspace
    stmt = select(ProjectModel).where(
        ProjectModel.id == project_id,
        ProjectModel.workspace_id == ctx.workspace_id,
    )
    res = await self.session.execute(stmt)
    if not res.scalar_one_or_none():
        raise NotFoundError("Project not found in current workspace")`,
  },
];

export const SAMPLE_CONVERSATION_MESSAGES: ChatMessage[] = [
  {
    id: "msg-01",
    role: "user",
    content:
      "How does DevMind prevent unauthorized users from triaging or dismissing security findings?",
    createdAt: "2026-10-18T10:30:00Z",
  },
  {
    id: "msg-02",
    role: "assistant",
    content: `DevMind enforces role-based authorization using a two-tier permission guard at the FastAPI router level:

1. **Route-level Guard**: Every mutating finding endpoint declares required scopes using the \`@declare_permission\` decorator and FastAPI dependency injection [1].
2. **Triage Privilege Separation**: While contributors with \`finding:progress\` can advance findings to *in progress* or *acknowledged*, moving a finding to *dismissed* or *accepted_risk* explicitly checks for the maintainer permission \`finding:triage\` [2]. If caller lacks this permission, a 403 Forbidden RFC 9457 response is returned.
3. **Tenant Boundary**: All repository operations scope queries by both \`workspace_id\` and \`project_id\` to prevent cross-tenant traversal [3].`,
    activityLines: [
      "Searched Project Brain for 'finding triage permission guard' (4 chunks matched)",
      "Retrieved symbol definitions: require_permission, transition_finding_status",
      "Verified 3 citations against repository AST snapshot (100% grounded)",
    ],
    citations: SAMPLE_CITATIONS,
    createdAt: "2026-10-18T10:30:05Z",
  },
  {
    id: "msg-03",
    role: "user",
    content:
      "Can you provide the cryptographic implementation details of the zero-knowledge proofs used for data hashing?",
    createdAt: "2026-10-18T10:32:00Z",
  },
  {
    id: "msg-04",
    role: "assistant",
    content:
      "I searched the repository and index for zero-knowledge proof cryptography, but I could not find verified evidence or implementation code supporting this feature.",
    activityLines: [
      "Searched Project Brain for 'zero-knowledge proof ZKP cryptography'",
      "Queried symbol index (0 symbols matched)",
      "Grounding check: insufficient evidence in indexed repository context",
    ],
    hasInsufficientEvidence: true,
    insufficientEvidenceReason:
      "The query asks for zero-knowledge proof cryptographic primitives, but DevMind uses standard SHA-256 content hashes and HMAC signatures (docs/07 §15). No ZKP implementation exists in this codebase.",
    suggestedNextSteps: [
      "Review `docs/07-auth-and-redaction.md` for DevMind's canonical SHA-256 hashing architecture.",
      "Check `docs/12-decisions/` to confirm whether zero-knowledge proofs are considered in any accepted ADR.",
      "Rephrase your question to ask about data sanitization, redaction, or token hashing.",
    ],
    createdAt: "2026-10-18T10:32:04Z",
  },
];
