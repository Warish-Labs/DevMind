import type { FindingItem } from "@devmind/common/api";

export type ProjectBrainMode = "indexed" | "metadata_only";

export interface BrainSnapshotSummary {
  id: string;
  name: string;
  createdAt: string;
  isCurrent: boolean;
  fileCount: number;
  symbolCount: number;
  isStale?: boolean;
}

export interface BrainSymbolDetail {
  id: string;
  name: string;
  kind: "function" | "class" | "method" | "interface" | "route" | "variable";
  path: string;
  startLine: number;
  endLine: number;
  signature?: string;
  docstring?: string;
}

export interface BrainRelationshipItem {
  id: string;
  sourceSymbol: string;
  targetSymbol: string;
  kind: "calls" | "imports" | "extends" | "guards" | "defines";
  direction: "outgoing" | "incoming";
  targetPath?: string;
}

export interface BrainFileNode {
  id: string;
  path: string;
  name: string;
  isDirectory: boolean;
  children?: BrainFileNode[];
  sizeBytes?: number;
  lineCount?: number;
  languageTier?: "tier1" | "tier2" | "tier3";
  isStale?: boolean;
  hasFindings?: boolean;
  findingsCount?: number;
  contentHash?: string;
}

export interface BrainFileContent {
  id: string;
  path: string;
  content: string;
  lineCount: number;
  contentHash: string;
  languageTier: "tier1" | "tier2" | "tier3";
  symbols: BrainSymbolDetail[];
  relationships: BrainRelationshipItem[];
  findings: FindingItem[];
  isUnindexed?: boolean;
  unindexedReason?: string;
}

export const SAMPLE_SNAPSHOTS: BrainSnapshotSummary[] = [
  {
    id: "snap-001",
    name: "snapshot-20261018-090000",
    createdAt: "2026-10-18T09:00:00Z",
    isCurrent: true,
    fileCount: 248,
    symbolCount: 1420,
    isStale: false,
  },
  {
    id: "snap-002",
    name: "snapshot-20261017-183000",
    createdAt: "2026-10-17T18:30:00Z",
    isCurrent: false,
    fileCount: 242,
    symbolCount: 1390,
    isStale: true,
  },
  {
    id: "snap-003",
    name: "snapshot-20261016-120000",
    createdAt: "2026-10-16T12:00:00Z",
    isCurrent: false,
    fileCount: 235,
    symbolCount: 1340,
    isStale: true,
  },
];

export const SAMPLE_FILE_TREE: BrainFileNode[] = [
  {
    id: "dir-server",
    path: "server",
    name: "server",
    isDirectory: true,
    children: [
      {
        id: "dir-server-app",
        path: "server/app",
        name: "app",
        isDirectory: true,
        children: [
          {
            id: "dir-server-app-api",
            path: "server/app/api",
            name: "api",
            isDirectory: true,
            children: [
              {
                id: "file-api-findings",
                path: "server/app/api/findings.py",
                name: "findings.py",
                isDirectory: false,
                languageTier: "tier1",
                lineCount: 128,
                hasFindings: true,
                findingsCount: 1,
                contentHash: "a1b2c3d4e5f60718",
              },
              {
                id: "file-api-brain",
                path: "server/app/api/brain.py",
                name: "brain.py",
                isDirectory: false,
                languageTier: "tier1",
                lineCount: 227,
                contentHash: "f6e5d4c3b2a19827",
              },
            ],
          },
          {
            id: "dir-server-app-domain",
            path: "server/app/domain",
            name: "domain",
            isDirectory: true,
            children: [
              {
                id: "dir-server-app-domain-auth",
                path: "server/app/domain/auth",
                name: "auth",
                isDirectory: true,
                children: [
                  {
                    id: "file-auth-permissions",
                    path: "server/app/domain/auth/permissions.py",
                    name: "permissions.py",
                    isDirectory: false,
                    languageTier: "tier1",
                    lineCount: 85,
                    hasFindings: false,
                    contentHash: "8b7c6d5e4f3a2b1c",
                  },
                ],
              },
              {
                id: "dir-server-app-domain-brain",
                path: "server/app/domain/brain",
                name: "brain",
                isDirectory: true,
                children: [
                  {
                    id: "file-brain-repo",
                    path: "server/app/domain/brain/repository.py",
                    name: "repository.py",
                    isDirectory: false,
                    languageTier: "tier1",
                    lineCount: 310,
                    contentHash: "3d4e5f6a7b8c9d0e",
                  },
                ],
              },
            ],
          },
        ],
      },
    ],
  },
  {
    id: "dir-client",
    path: "client",
    name: "client",
    isDirectory: true,
    children: [
      {
        id: "dir-client-components",
        path: "client/components",
        name: "components",
        isDirectory: true,
        children: [
          {
            id: "dir-client-components-chat",
            path: "client/components/chat",
            name: "chat",
            isDirectory: true,
            children: [
              {
                id: "file-chat-conversation",
                path: "client/components/chat/ConversationView.tsx",
                name: "ConversationView.tsx",
                isDirectory: false,
                languageTier: "tier1",
                lineCount: 421,
                contentHash: "4f5a6b7c8d9e0f1a",
              },
            ],
          },
        ],
      },
    ],
  },
];

export const SAMPLE_FILE_CONTENTS: Record<string, BrainFileContent> = {
  "server/app/domain/auth/permissions.py": {
    id: "file-auth-permissions",
    path: "server/app/domain/auth/permissions.py",
    languageTier: "tier1",
    lineCount: 85,
    contentHash: "8b7c6d5e4f3a2b1c9012345678abcdef01234567",
    content: `"""FastAPI role-based access control and dependency injection guards."""

from typing import Callable, Any
from fastapi import Depends, HTTPException, status
from app.domain.auth.models import AuthContext
from app.core.errors import ForbiddenError

def require_permission(permission: str) -> Callable[[AuthContext], AuthContext]:
    """Dependency factory checking that AuthContext possesses the required permission scope."""
    async def _dependency(ctx: AuthContext = Depends(get_auth_context)) -> AuthContext:
        if not ctx.has_permission(permission):
            raise ForbiddenError(f"Missing required permission '{permission}'")
        return ctx
    return _dependency

def declare_permission(permission: str):
    """Decorator registering required permission for OpenAPI schema documentation and CI checks."""
    def decorator(fn: Any) -> Any:
        fn.__devmind_permission__ = permission
        return fn
    return decorator
`,
    symbols: [
      {
        id: "sym-require-perm",
        name: "require_permission",
        kind: "function",
        path: "server/app/domain/auth/permissions.py",
        startLine: 8,
        endLine: 15,
        signature: "def require_permission(permission: str) -> Callable",
        docstring:
          "Dependency factory checking that AuthContext possesses the required permission scope.",
      },
      {
        id: "sym-declare-perm",
        name: "declare_permission",
        kind: "function",
        path: "server/app/domain/auth/permissions.py",
        startLine: 17,
        endLine: 23,
        signature: "def declare_permission(permission: str)",
        docstring: "Decorator registering required permission for OpenAPI schema documentation.",
      },
    ],
    relationships: [
      {
        id: "rel-01",
        sourceSymbol: "require_permission",
        targetSymbol: "AuthContext.has_permission",
        kind: "calls",
        direction: "outgoing",
        targetPath: "server/app/domain/auth/models.py",
      },
      {
        id: "rel-02",
        sourceSymbol: "transition_finding_status",
        targetSymbol: "require_permission",
        kind: "calls",
        direction: "incoming",
        targetPath: "server/app/api/findings.py",
      },
      {
        id: "rel-03",
        sourceSymbol: "require_permission",
        targetSymbol: "ForbiddenError",
        kind: "imports",
        direction: "outgoing",
        targetPath: "server/app/core/errors.py",
      },
    ],
    findings: [],
  },
  "server/app/api/findings.py": {
    id: "file-api-findings",
    path: "server/app/api/findings.py",
    languageTier: "tier1",
    lineCount: 128,
    contentHash: "a1b2c3d4e5f6071890abcdef1234567890abcdef",
    content: `@router.post("/{fid}/transitions")
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
    symbols: [
      {
        id: "sym-trans-finding",
        name: "transition_finding_status",
        kind: "route",
        path: "server/app/api/findings.py",
        startLine: 1,
        endLine: 11,
        signature: "async def transition_finding_status(pid, fid, payload, ctx)",
        docstring: "Advance finding status with permission and lifecycle transition verification.",
      },
    ],
    relationships: [
      {
        id: "rel-findings-perm",
        sourceSymbol: "transition_finding_status",
        targetSymbol: "require_permission",
        kind: "guards",
        direction: "outgoing",
        targetPath: "server/app/domain/auth/permissions.py",
      },
    ],
    findings: [
      {
        id: "f-01",
        project_id: "018f0a00-0000-7000-8000-000000000101",
        fingerprint: "fp_auth_triage_001",
        rule_id: "SEC-AUTH-001",
        source: "agent",
        category: "security",
        title: "Triage privilege boundary guard verification",
        summary: "Verify that unauthorized contributors cannot bypass maintainer review.",
        severity: "critical",
        confidence: "0.95",
        evidence_level: "E2",
        status: "open",
        primary_path: "server/app/api/findings.py",
        primary_start_line: 9,
        primary_end_line: 11,
        created_at: "2026-10-18T10:00:00Z",
        updated_at: "2026-10-18T10:00:00Z",
      },
    ],
  },
};
