# 00 · Documentation Index

**Purpose.** A map of the DevMind documentation package: what each document is for, which one is authoritative for what, how decisions are recorded, and in what order to read them.

**Status.** Implemented (MVP through Milestone 13). Milestones M1 through M10 and M13 are fully implemented, tested, and validated. Milestones M11 and M12 represent post-MVP specifications.

---

## 1. Status vocabulary

Decision status (used in [12](12-architecture-decisions-and-open-questions.md)):

| Tag | Meaning |
|---|---|
| **Confirmed** | Fixed by the project owner (the master brief or the source vision). Changing it needs human approval. |
| **Recommended** | A default proposed by this package, not yet validated. |
| **Deferred** | Deliberately outside the first release. |
| **Open** | Needs research or an experiment; an interim default is named. |

Inline markers used in the documents:

| Marker | Meaning |
|---|---|
| `[VERIFY]` | A vendor-specific fact (pricing, limits, scopes, versions, SDK behavior) not verified in this drafting pass. Check official documentation, then record the date in the register in [12](12-architecture-decisions-and-open-questions.md) §5. |
| `[OPEN]` / `OQ-nn` | An unresolved question tracked in [12](12-architecture-decisions-and-open-questions.md) §4. |
| `ADR-nnn` | A decision record in [12](12-architecture-decisions-and-open-questions.md). |
| CAP-nn, FR-xxx-nn, NFR-xxx-nn | Capability and requirement IDs from [01](01-product-requirements.md). |
| M1 to M13 | Milestones in [11](11-mvp-and-implementation-roadmap.md). |

## 2. Document map and authority

| # | File | Purpose | Authoritative for |
|---|---|---|---|
| root | [README.md](../README.md) | Orientation, status, structure | Implementation status summary |
| root | [AGENTS.md](../AGENTS.md) | Operating rules for AI coding agents | Agent behavior and approval boundaries |
| 00 | this file | Map, precedence, reading order | Documentation process |
| 01 | [Product requirements](01-product-requirements.md) | Scope, requirements, MVP | Scope, personas, capabilities, acceptance criteria, non-goals |
| 02 | [System architecture](02-system-architecture.md) | Components and flows | Service boundaries, import rules, job lifecycle, auth flow, repository layout |
| 03 | [Data model and API](03-data-model-and-api.md) | Tables, endpoints, schemas | Entity names, enumerations, state machines, endpoints, error catalog |
| 04 | [Project Brain and retrieval](04-project-brain-and-rag.md) | Knowledge model, indexing, retrieval | Snapshots, chunking, retrieval, staleness |
| 05 | [Agents and LLM workflows](05-agents-and-llm-workflows.md) | LangGraph, agents, LLM configuration | Agent behavior, routing, YAML configuration, evidence rules |
| 06 | [VS Code extension and local scanning](06-vscode-extension-and-local-scanning.md) | Extension behavior | Local scan, manifest, sync modes, consent UX, privacy ledger data |
| 07 | [Security, privacy, threat model](07-security-privacy-and-threat-model.md) | Controls and risks | Data classification, consent, retention proposals, threats |
| 08 | [UI/UX design specification](08-ui-ux-design-specification.md) | Visual identity and screens | Design tokens, screens, motion, accessibility, logo rules (§19) |
| brand | [brand/BRAND-GUIDE.md](../brand/BRAND-GUIDE.md) | Logo and identity assets | File inventory, usage; tokens source copy |
| prompt | [ANTIGRAVITY_PROMPT.md](ANTIGRAVITY_PROMPT.md) | Master implementation prompt for the AI coding agent | Execution order, workflow, phase specifications |
| guide | [SETUP-GUIDE.md](SETUP-GUIDE.md) | Owner's manual: accounts, keys, GitHub, deploy, publish | Human-only steps and free-tier setup |
| showcase | [showcase/](showcase/README.personal.md) | README kit for the personal showcase repo | Redirect README content |
| 09 | [Testing and quality](09-testing-and-quality-strategy.md) | Tests, evaluations, gates | Quality gates, fixtures, evaluation baselines |
| 10 | [Deployment and operations](10-deployment-and-operations.md) | Runbook | Environment variables, deployment, monitoring, recovery |
| 11 | [MVP and roadmap](11-mvp-and-implementation-roadmap.md) | Milestones | Build order and per-milestone acceptance |
| 12 | [Decisions and open questions](12-architecture-decisions-and-open-questions.md) | ADR register | Decision status; wins on conflict |
| 13 | [Glossary](13-glossary-and-domain-terminology.md) | Terms | Terminology |

The source vision is `DevMind_Project_Document.md`. It is preserved in spirit; where a document extends it, the document says so.

## 3. Precedence when documents disagree

1. [12](12-architecture-decisions-and-open-questions.md) for the status and content of a decision.
2. The authoritative document for that area (table above).
3. [01](01-product-requirements.md) for scope; [02](02-system-architecture.md) for structure.
4. All other documents.
5. Summaries in the README and AGENTS.md.

The execution plan (`PLAN.md`) and agent memory (`BRAIN.md`) live at the repository root once created. A contradiction is a documentation bug. Fix the lower-precedence document, and if the decision changed, add or update an ADR.

## 4. Reading order

**New developer:** README, 01 (§1 to §9, §14), 02, 04, 03, 05, 06, 07, 11, 12, 09, 10, 08; 13 as a reference.

**AI coding agent starting a task:** AGENTS.md; 13; the governing documents for the task ([AGENTS.md](../AGENTS.md) §2); the task's milestone in 11; the `Open` items in 12 that touch the task.

**Frontend work:** 08, 03 (browser API), 01, 09 §5. **Extension work:** 06, 03 (extension API), 07, 04 §4. **Backend and AI work:** 02, 03, 04, 05, 07, 09.

## 5. What is not settled

Authoritative list: [12](12-architecture-decisions-and-open-questions.md) §2 and §4. In summary: generation provider(s) and models (ADR-017); retention defaults and provider data terms (ADR-026); managed Redis provider (ADR-031); extension manifest store (ADR-033); MVP breadth (ADR-038); plus open questions OQ-01 to OQ-18 (embedding model, scanner rule licensing, RLS adoption, GitHub App timing, checkpointer through pooled connections, SSE behind proxies, error-monitoring vendor, font licensing, grammar packaging, the "Functionality" health dimension).

## 6. How decisions and changes are recorded

1. Propose the change in a pull request that edits the authoritative document.
2. Add or update the ADR in 12 using the template in 12 §6 (status `Proposed`, then updated after human approval).
3. Update dependent documents (see the "also update" column in [AGENTS.md](../AGENTS.md) §2).
4. Reference the ADR ID in the pull request and in affected documents.

## 7. How the documentation evolves with the code

- Documents describe **intended** behavior until code exists, then **actual** behavior. When a milestone lands, update the status of the affected sections and record deviations ([11](11-mvp-and-implementation-roadmap.md) §2.2).
- FastAPI's generated OpenAPI becomes the machine-readable truth for endpoints; document 03 keeps the rationale, permissions and state machines.
- Vendor facts are re-verified when a milestone depends on them; record the date in 12 §5.
- Evaluation baselines are recorded in `evals/results/` and summarized in [09](09-testing-and-quality-strategy.md) §9.

## 8. Documentation audit checklist

Run at milestone M13 and each release:

- Terms match [13](13-glossary-and-domain-terminology.md).
- Endpoint, entity, enumeration, job-type, agent and capability names match 03 and 05 exactly.
- No `Open` item is silently assumed elsewhere.
- Every user-facing requirement in 01 has acceptance criteria and a test or evaluation in 09.
- Security-relevant behavior in 02, 03, 05, 06 matches 07.
- UI claims in 08 (release labels, privacy ledger, hero rule IDs) come from single sources of truth and match 01 and 06.
- Milestone dependencies in 11 respect 02.
