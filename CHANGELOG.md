# Changelog

All notable changes to DevMind will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-10-27

### MVP Release — Initial Public Release Candidate

This is the initial MVP release candidate of **DevMind**, an agentic AI software engineering platform built around a central, version-aware mental model of codebases—the **Project Brain**.

### Added

#### Core Platform & Project Brain (CAP-01)

- **Snapshot Ingestion & Graph Indexer**: Tree-sitter powered AST symbol extraction and call-graph relationship builder for TypeScript, JavaScript, and Python.
- **RAG Hybrid Retrieval**: Reciprocal Rank Fusion combining dense semantic embeddings (pgvector) with sparse BM25 text search and deterministic AST graph hops.
- **Privacy Sync Modes**: Configurable sync tier per project (`metadata_only`, `structure_only`, and `indexed`) with explicit developer consent recording.
- **Project Brain Explorer**: Interactive SVG knowledge graph visualizer and source tree inspector with maintainer permission gates.

#### Security Intelligence (CAP-02)

- **SecuritySentinel**: Automated security scanning pipeline combining local pattern-engine scanning with server-side AST authorization policy solving.
- **Evidence Tiers**: Strict grounding levels (`E0` heuristic match, `E1` structural AST match, `E2` verified policy trace, `E3` dynamic execution). Speculative AI outputs are never presented as proven vulnerabilities.
- **Finding Triage & Governance**: Security findings dashboard, severity categorization (Critical, High, Medium, Low), and triage workflow (Confirmed, False Positive, Resolved) with audit logging.

#### Web Application & Design System

- **App Shell & Screen States**: Responsive authenticated application shell featuring gutter rail navigation, command palette (`Cmd/Ctrl+K`), top bar breadcrumbs, floating background job tray, and accessible loading/empty/error states.
- **Public Homepage & Product Narrative**: Editorial marketing homepage featuring interactive Trace timeline sequence, privacy ledger preview, and verified performance characteristics.
- **Code-Native Design System**: Custom cursor, keyboard-first accessibility, focus ring styling, and dark theme tokens built with IBM Plex Sans, Instrument Serif, and JetBrains Mono.

#### VS Code Companion Extension (`devmind-vscode`)

- **Local Scanner**: Zero live database connections (ADR-034); Tree-sitter based AST parsing and rule engine running entirely on the developer's workstation.
- **Companion Pairing**: Secure token-based pairing with cloud workspace (`/api/v1/ext/...`) via system browser OAuth flow.
- **Privacy & Consent Ledger**: Local manifest storing file hash trees and explicit developer upload consent records.
- **Marketplace Packaging**: Bundling target producing standard VSIX distribution artifacts (~55 KB).

#### Backend & Worker Architecture

- **FastAPI Modular Monolith**: High-performance async API with strict layer import boundary enforcement.
- **Distributed Worker Orchestration**: Celery background task processing backed by Upstash Redis message broker and result backend.
- **Multi-Tenant Isolation**: Schema-level tenant isolation scoping every repository query by `workspace_id` and `project_id`.
- **RFC 9457 Problem Details**: Standardized error response catalog across all REST endpoints.

#### Quality & Operations

- **Comprehensive Quality Runner**: `scripts/test-all.mjs` running 13 test suites across frontend, backend, extension, and common modules.
- **Documentation & Brand Auditor**: Automated link, anchor, Mermaid diagram, ADR citation, and brand asset validator (`npm run docs:audit`).
- **Free-Tier Cloud Profile**: Validated zero-cost deployment profile across Vercel Hobby, Render Free Web Service, Neon PostgreSQL Free, and Upstash Redis Free (ADR-046).

### Known Limitations Ledger

1. **Language Tiers**:
   - **Tier 1 (Full AST & Symbol Graph)**: TypeScript, JavaScript, Python.
   - **Tier 2 (Structural Patterns & Secrets)**: Go, Java, Rust, SQL, YAML, Markdown. Full AST symbol indexing for Tier 2 languages is scheduled for Release 1.2.
2. **Zero Live Database Connections**:
   - The VS Code companion never establishes direct connections to production or staging databases (ADR-034). All telemetry and metadata sync flows over authenticated HTTPS REST/SSE APIs.
3. **No In-Extension AI Chat**:
   - In-editor AI chat is intentionally omitted from the extension (ADR-034). Conversational reasoning and RAG traces live in the authenticated web app shell.
4. **Evidence Grounding Boundaries**:
   - Static scans emit evidence up to `E1` locally and `E2` on server verification. Dynamic verification (`E3`) inside virtualization sandboxes is deferred to Release 1.4.
5. **Free Tier Sleep Behavior**:
   - Under the free deployment profile (ADR-046), the Render web service sleeps after 15 minutes of inactivity; initial cold starts take ~30–50 seconds.
6. **Post-MVP Capabilities**:
   - Pull Request Intelligence & ReviewBuddy (CAP-05/CAP-06) follow in Release 1.1 (M11). Bug Recurrence Memory (CAP-03) and Living Documentation (CAP-04) follow in Release 1.2–1.3 (M12).
