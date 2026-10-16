/**
 * DevMind Sections Data Specification
 * Sources: docs/08-ui-ux-design-specification.md §9, docs/04 §2, and common/data/*.json
 */

import capabilitiesData from "../../common/data/capabilities.json";
import releaseStatusData from "../../common/data/release-status.json";
import walkthroughData from "../../common/data/walkthrough.json";
import privacyLedgerData from "../../common/data/privacy-ledger.json";

export { capabilitiesData, releaseStatusData, walkthroughData, privacyLedgerData };

export interface ConsequenceItem {
  id: "security" | "review" | "docs" | "pr" | "health";
  title: string;
  tag: string;
  category: string;
  description: string;
  highlightedLines: number[];
}

export const SECTION_02_CONSEQUENCES: ConsequenceItem[] = [
  {
    id: "security",
    title: "Security & Authorization Gap",
    tag: "authz.missing_role_check",
    category: "Security",
    description:
      "Authentication is verified with requireAuth, but no role authorization guard is applied to /admin/users.",
    highlightedLines: [7],
  },
  {
    id: "review",
    title: "Code Review Invariant Breach",
    tag: "review.missing_test",
    category: "Code Review",
    description:
      "Missing authorization check on sensitive administrative endpoint; no automated tests verify 403 Forbidden.",
    highlightedLines: [7],
  },
  {
    id: "docs",
    title: "Living Documentation Drift",
    tag: "docs.unregistered_route",
    category: "Documentation",
    description:
      "Endpoint /admin/users has no corresponding entry in OpenAPI schema or documentation records.",
    highlightedLines: [7],
  },
  {
    id: "pr",
    title: "Pull Request Risk & Blast Radius",
    tag: "pr.high_risk_exposure",
    category: "PR Intelligence",
    description:
      "PR flags high risk: administrative endpoint exposes sensitive user list without role restriction.",
    highlightedLines: [7, 8],
  },
  {
    id: "health",
    title: "Project Health & Release Gate",
    tag: "health.unresolved_e1",
    category: "Release Readiness",
    description:
      "Security health score drops; authorization invariant broken across administrative routes.",
    highlightedLines: [7],
  },
];

export interface BrainStratum {
  number: number;
  name: string;
  definition: string;
  notDefinition: string;
  whereItLives: string;
  isHeroPath: boolean;
  exampleRecord: string;
}

export const BRAIN_STRATA: BrainStratum[] = [
  {
    number: 1,
    name: "Local manifest and scan state",
    definition:
      "Per-file hashes, sizes, languages, last-scan info, local findings, and sync queue.",
    notDefinition: "The cloud's view of the project.",
    whereItLives: "Extension storage outside repo",
    isHeroPath: true,
    exampleRecord:
      '{\n  "file": "src/routes/admin.ts",\n  "hash": "a1b2c3d4...",\n  "tier": 1,\n  "localFindings": 1\n}',
  },
  {
    number: 2,
    name: "Structured cloud project model",
    definition: "Projects, files, file versions, snapshots, and scan execution runs.",
    notDefinition: "Raw source code content.",
    whereItLives: "PostgreSQL (projects, files, snapshots)",
    isHeroPath: false,
    exampleRecord:
      '{\n  "projectId": "proj_01J...",\n  "snapshotId": "snap_01J...",\n  "branch": "main"\n}',
  },
  {
    number: 3,
    name: "Searchable code index",
    definition: "Chunks (when consented), symbol records, and keyword search text.",
    notDefinition: "Embeddings vectors.",
    whereItLives: "PostgreSQL (code_chunks, code_symbols)",
    isHeroPath: true,
    exampleRecord:
      '{\n  "symbol": "router.get",\n  "kind": "route",\n  "path": "/admin/users",\n  "lines": "7-7"\n}',
  },
  {
    number: 4,
    name: "Vector embeddings",
    definition: "Numeric vectors per chunk per embedding space for semantic similarity.",
    notDefinition: "Structural code index; vectors are source-derived data.",
    whereItLives: "PostgreSQL pgvector (chunk_embeddings)",
    isHeroPath: false,
    exampleRecord:
      '{\n  "chunkId": "chk_01...",\n  "dimensions": 1536,\n  "space": "text-embedding-3-small"\n}',
  },
  {
    number: 5,
    name: "Relationship model",
    definition:
      "Typed edges between symbols and files (imports, calls, defines_route, guarded_by).",
    notDefinition: "Cosine similarity or text proximity.",
    whereItLives: "PostgreSQL (code_relationships)",
    isHeroPath: true,
    exampleRecord:
      '{\n  "source": "/admin/users",\n  "target": "requireAuth",\n  "type": "guarded_by"\n}',
  },
  {
    number: 6,
    name: "Bug history",
    definition: "Historical error signatures, causes, fixes, and affected files.",
    notDefinition: "Active finding list.",
    whereItLives: "PostgreSQL (bug_records, bug_resolutions)",
    isHeroPath: false,
    exampleRecord:
      '{\n  "bugId": "bug_403_leak",\n  "cause": "missing role check",\n  "fixCommit": "71a2..."\n}',
  },
  {
    number: 7,
    name: "Agent execution state",
    definition: "Workflow state and checkpoints per reasoning run.",
    notDefinition: "Permanent project knowledge; temporary scratch state.",
    whereItLives: "Redis & PostgreSQL (agent_runs, langgraph)",
    isHeroPath: false,
    exampleRecord:
      '{\n  "runId": "run_98...",\n  "agent": "AuthCheck",\n  "step": "verify_role_guard"\n}',
  },
  {
    number: 8,
    name: "Findings and evidence",
    definition: "Issues, evidence citations (E0-E3), confidence, and remediation status.",
    notDefinition: "Unverified LLM prose.",
    whereItLives: "PostgreSQL (findings, finding_evidence)",
    isHeroPath: true,
    exampleRecord:
      '{\n  "rule": "devmind.authz.missing_role_check",\n  "evidence": "E1",\n  "confidence": 0.95\n}',
  },
  {
    number: 9,
    name: "Documentation and history",
    definition: "Known docs, drift items, snapshot history, and status transitions.",
    notDefinition: "Current active code.",
    whereItLives: "PostgreSQL (doc_records, doc_drift_items)",
    isHeroPath: false,
    exampleRecord:
      '{\n  "doc": "api/admin.md",\n  "drift": "missing endpoint /admin/users",\n  "severity": "medium"\n}',
  },
  {
    number: 10,
    name: "Current vs historical snapshots",
    definition: "current_version_id for live state vs immutable snapshots for audits.",
    notDefinition: "Ephemeral git stash.",
    whereItLives: "PostgreSQL (files, snapshot_files)",
    isHeroPath: false,
    exampleRecord:
      '{\n  "fileId": "file_12...",\n  "currentVersion": "v14",\n  "snapshotCount": 8\n}',
  },
];
