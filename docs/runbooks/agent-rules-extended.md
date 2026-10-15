# agent-rules-extended.md

Extended detail for rules summarized in `AGENTS.md`. Referenced by §1 source-of-truth policy.

## §1 Source-of-truth policy (extended)

**Precedence chain:**
```
docs/12 (architecture decisions, ADRs)
  > the area's authoritative document (see §2 table)
    > docs/01 (PRD and acceptance criteria)
      > docs/02 (architecture and structure)
        > other documents
          > summaries in AGENTS.md and README
```

When documents disagree: report the contradiction in your PR body; do not silently pick one side.

**Decision statuses** (docs/12 §1):
- **Confirmed** — fixed by owner; you may not change it. Propose a superseding ADR and get explicit approval.
- **Recommended** — default; may be changed only through a superseding ADR with owner approval.
- **Deferred** — deliberately out of v1; do not build early.
- **Open** — unresolved; use the interim default named in the entry. Never decide silently.

**Gaps:** if a requirement is missing, ambiguous, or marked `Open` in docs/12: stop, state what is missing and why it matters, give two options with trade-offs, make a recommendation, and wait for a decision. Continue only with the parts that do not depend on the answer.

## §6 Environment variables (extended)

Every variable in the system must appear in both:
1. The appropriate `.env.example` file (with a `REPLACE_ME` placeholder and a one-line comment explaining what it is and how to get it).
2. The env var table in `docs/10-deployment-and-operations.md` §11.

The variable name convention:
- `DEVMIND_` prefix for all server variables (except Clerk which uses their own names).
- `NEXT_PUBLIC_` prefix for client variables that are safe to expose in the browser.
- No `NEXT_PUBLIC_` prefix for server-only variables in the client (build will fail appropriately).

Variables that are secrets (API keys, tokens, passwords) must **never** appear in:
- Git history (even if in a "deleted" commit)
- Log output
- Error messages sent to users
- LLM prompts or completions

Non-secret behavior (model names, routing thresholds, feature flags) belongs in versioned YAML under `server/configs/` and is committed to the repository.

## §7 Migrations (extended)

**Never edit an applied migration.** If a migration has been applied (even only to a local database), create a new migration to fix it.

**Expand → Migrate → Contract pattern:**
1. **Expand**: add new columns/tables as nullable or with defaults; old code still works.
2. **Migrate**: backfill data; deploy new code that reads both old and new schema.
3. **Contract**: remove old columns/tables in a subsequent migration after all old code is gone.

Migrations that need human approval:
- Locking large tables (any migration that does `ALTER TABLE ... RENAME COLUMN` or changes types without `USING`).
- Changing embedding vector dimensions (requires re-embedding all chunks).
- Deleting data (even via `DROP COLUMN`).
- Any migration targeting a non-local database (staging or production).

**Migration testing**: every migration must have a test that runs `upgrade head` and `downgrade -1` on a clean database.

## §8 API compatibility (extended)

**Route audiences are strict:**
- `/api/v1/...` — accepts only Clerk bearer tokens (browser and website clients).
- `/api/v1/ext/...` — accepts only DevMind extension tokens (issued by the API, not Clerk).
- A single route must never accept both token types.

**Backward compatibility within v1:**
- You may add new optional request fields, new response fields, and new endpoints.
- You may not remove or rename fields, change types, or change semantics.
- Breaking changes need a new major version (`/api/v2`) and an ADR.

**Route permission declaration:**
Every mutating route (POST, PUT, PATCH, DELETE) must declare in docs/03:
- Required permission (from the permission table in docs/03 §4.2).
- Idempotency behavior (is it safe to retry? what is the natural key?).
- Error codes (from the error catalog in docs/03 §10.1).

A CI check fails any route that lacks a declared permission.

## §10 Project Brain and LLM adapter changes (extended)

**Chunking changes** (docs/04):
- Any change to chunking strategy, chunk size, overlap, or language handling invalidates all existing chunks.
- Required: updated docs/04, a re-embedding plan (create a new embedding space or re-index), retrieval evaluation results before and after.
- Never apply chunking changes to production data without a migration plan reviewed by the owner.

**Embedding model/dimension changes:**
- Must be a new embedding space (new `embedding_space_id`) — do not mutate the existing one.
- Requires updating `chunk_embeddings` schema or adding a new partition.
- Dimension ≤ 768 or use `halfvec` to fit within the Neon free storage cap (ADR-046).

**Provider adapter changes:**
Required before merging:
1. Adapter contract tests (both happy path and all failure modes: rate limit, timeout, invalid output, wrong schema).
2. Fault-injection test for each failure mode.
3. Capability validation test (does the adapter handle structured output? tool calling?).
4. A recorded evaluation run with the `benchmark` harness.

**Evidence requirements:** Never lower the evidence level required to produce a finding. The rules are in docs/07 §evidence and docs/09 §8. If a change would weaken evidence requirements, it needs an ADR and owner approval.
