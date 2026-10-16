# BRAIN.md — DevMind Working Memory

> No secrets, tokens, source content or user data in this file. It is committed to git.

---

## 1. Current state

| Field              | Value                                                                   |
| ------------------ | ----------------------------------------------------------------------- |
| **Branch**         | `docs/r1-readme-showcase`                                               |
| **Last commit**    | `7bc34c6` (Phase S2 complete & merged into main)                        |
| **Working tree**   | active on Phase R1 (`docs/r1-readme-showcase`); clean                   |
| **Open PR**        | PR for Slice B13 (`docs/r1-readme-showcase`)                            |
| **Last CI result** | `test-all --fast`: 10 passed, 0 failed, 2 skipped; extension 20/20 pass |
| **Date**           | 2026-10-16                                                              |

---

## 2. Next action (exact)

1. Implement Phase R1 · Slice B13 (`docs/r1-readme-showcase`):
   - R1-01 Root README.md per ANTIGRAVITY_PROMPT.md §12 (professional design, logo, badges, live screenshot gallery, architectural Mermaid diagrams, honest PLAN status table)
   - R1-02 Reconcile docs/SETUP-GUIDE.md commands, dependencies, and environment variable tables with verified reality (date-stamped)
   - R1-03 Upgrade docs/showcase/README.personal.md with real screenshots, honest status, and clean formatting
   - R1-04 Add docs/showcase/PROFILE-BLURB.md (under 300 chars summary + narrative paragraph)
2. Verify all markdown relative links and anchors with `scripts/docs-links.mjs`.
3. Verify test suite with `pnpm verify`.
4. Commit and push to `origin/docs/r1-readme-showcase`.

---

## 3. Waiting on owner

| #   | Action required                                                                                                                           | Reference              |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------- | ---------------------- |
| 1   | **SETUP-GUIDE.md §4.4**: After the first CI run is green on B3, enable the branch ruleset `protect-main` requiring `ci-gate` status check | P0-15                  |
| 2   | **VS Marketplace publisher**: Confirm the publisher id is `warishlabs` (or tell me the correct one)                                       | S2 extension packaging |

---

## 4. Done log

### B12 — Extension Quality, Host Activation, Packaging & Screenshot Guide

- **Date**: 2026-10-16
- **Branch**: `feature/s2-quality`
- **What**: Completed comprehensive test harness, activation testing, and packaging:
  - **S2-13 Extension Quality & Packaging** (`extension/tests/quality.test.ts`):
    - Full activation lifecycle test verifying registration of all 8 commands, 5 tree views, diagnostic collection, and status bar.
    - Explicit assertion guaranteeing **zero network calls** during fixture mode activation and scan.
    - Secret redaction format validation (`[REDACTED:token:8a9b2c3d]`).
    - VSIX packaging pipeline via `@vscode/vsce package --no-dependencies --out dist/devmind-vscode.vsix` producing a lean, compliant 40.16 KB bundle. Added `.vscodeignore`, `README.md`, and `LICENSE`.
    - Integrated `package:extension` step directly into `scripts/test-all.mjs` test runner.
  - **S2-14 Extension Evaluation & Screenshots**:
    - Validated `docs/runbooks/screenshots.md` guide covering F5 launch configuration, fixture mode assertions, and screenshot checklist.
- **Commands & tests added**:
  - `pnpm --filter devmind-vscode package` command in `extension/package.json`.
  - Comprehensive quality test suite (3 new tests, 20/20 total extension unit tests passing).
- **Actual results**: `pnpm test:all --fast` (10 passed, 0 failed, 2 skipped), VSIX generated.

### B11 — Diagnostics Collection, Status Bar & Consent Preview Webview

- **Date**: 2026-10-16
- **Branch**: `feature/s2-diagnostics-consent`
- **What**: Implemented diagnostics, status bar, and consent preview webview per docs/06:
  - **S2-10 DiagnosticCollection** (`extension/src/services/diagnostics.ts`): source `"DevMind"`, code = rule ID, severity mapping (`critical`/`high` -> `Error`, `medium` -> `Warning`, `low` -> `Information`, `info` -> `Hint`), E1 prefixed with `"Possible: "`, accessible message text not relying on color alone, multi-file URI grouping.
  - **S2-11 Status bar** (`extension/src/services/statusBar.ts`): icon + label (`$(shield) DevMind · fixture · idle`, `$(sync~spin) DevMind · fixture · scanning 1/2`, `$(cloud-offline) DevMind · fixture · offline`), accessible tooltip, click trigger opening findings.
  - **S2-12 Consent preview webview** (`extension/src/views/consentWebview.ts`): strict CSP + crypto nonce, brand tokens, category transmission table, secret redaction preview (`[REDACTED:token:8a9b2c3d]`), Cancel button autofocus by default, Send button with zero-network simulated execution in fixture mode.
- **Commands & tests added**:
  - Registered `devmind.reviewSync` in `package.json` and `extension.ts`.
  - Comprehensive unit test suite in `extension/tests/diagnostics-consent.test.ts` (5 tests, all passing).
- **Actual results**: `pnpm test:all --fast` (9 passed, 0 failed, 2 skipped), 17/17 extension unit tests passing, esbuild bundle generated.

### B10 — VS Code Extension Views (Findings, Structure, Scan, Sync, Database)

- **Date**: 2026-10-16
- **Branch**: `feature/s2-views`
- **What**: Implemented all 5 primary VS Code extension views per docs/06:
  - **S2-04 Findings tree view** (`extension/src/views/findingsView.ts`): grouped by severity (`critical`, `high`, `medium`, `low`, `info`), codicons, evidence labels (`E1 · Possible`), tooltip with rule description/remediation, click-to-open file at exact line (`devmind.openFindingLocation`).
  - **S2-05 Project structure view** (`extension/src/views/structureView.ts`): modules, endpoints/routes (`GET /admin/users`), authentication & role-guard markers (`$(shield)` protected vs `$(alert)` missing role guard).
  - **S2-06 Scan status view** (`extension/src/views/scanView.ts`): live/simulated scanner progress, rules pack (`v1.0.0`), analyzed file count, skipped files audit (`.env` path-only, `package-lock.json`), workspace scan triggers (`devmind.scanWorkspace`, `devmind.cancelScan`).
  - **S2-07 Sync & privacy view** (`extension/src/views/syncView.ts`): active mode (`metadata_only`), cryptographic receipt, audit ledger of what leaves machine (zero raw code chunks transmitted), ledger review action (`devmind.showWhatLeaves`).
  - **S2-08 Database (from files) view** (`extension/src/views/databaseView.ts`): statically discovered schemas from files (Prisma, SQLAlchemy, migrations), primary key & foreign key tags, explicit ADR-034 enforcement note (zero live DB connections).
  - **S2-09 Welcome content**: `viewsWelcome` registered in `package.json` for empty workspaces and unindexed states.
- **Commands & tests added**:
  - Registered `devmind.cancelScan`, `devmind.showWhatLeaves`, `devmind.openFindingLocation`, `devmind.refreshAll`.
  - Comprehensive unit test suite in `extension/tests/views.test.ts` (7 new tests, 12/12 passing).
- **Actual results**: `pnpm test:all --fast` (9 passed, 0 failed, 2 skipped), TypeScript clean, esbuild bundle generated.

### P0-01 — Verify repo preconditions; create PLAN.md and BRAIN.md

- **Date**: 2026-10-15
- **Branch**: `docs/p0-layout-and-adrs` (created from `main`)
- **What**: Ran precondition checks; created PLAN.md and BRAIN.md
- **Commands run**:
  - `git remote -v` → `origin git@github-personal:Warish-Labs/DevMind.git` ✅
  - `git log --oneline -5` → `90dfee7 Initial commit` ✅
  - `node --version` → `v24.22.0` ✅
  - `pnpm --version` → `12.11.2` (installed via get.pnpm.io installer) ✅
  - `uv --version` → `0.12.17` ✅
  - `git config user.name` → `mdwarishansari` ✅
  - `git config user.email` → `warishdeveloper@gmail.com` ✅
  - `corepack --version` → `0.36.0` ✅
- **Actual results**: All preconditions met.

### P0-02 — Verify folder rename (client/server/extension/common); fix leftovers

- **Date**: 2026-10-15
- **Branch**: `docs/p0-layout-and-adrs`
- **What**: Audited repository for legacy names (`frontend/`, `backend/`, `vscode-extension/`, `packages/`). Confirmed layout in `docs/02` §5 matches ADR-039.
- **Files updated**:
  - `brand/tokens/devmind-tokens.css`: Updated comment `frontend/` → `client/`
  - `brand/source/build.py`: Updated template comment `frontend/` → `client/`
  - `README.md`: Updated status table `Frontend, backend, extension code` → `Client, server, extension code`
  - `docs/10-deployment-and-operations.md`: Updated section 10 and table references to client/server
  - `docs/04-project-brain-and-rag.md`: Updated server references
  - `docs/05-agents-and-llm-workflows.md`: Updated server references
  - `AGENTS.md`: Updated security rule 3 to reference server instead of backend
- **Actual results**: Zero occurrences of legacy names describing DevMind's own layout remain.

### P0-03 — Verify ADR-039..049 in docs/12; fix drift

- **Date**: 2026-10-15
- **Branch**: `docs/p0-layout-and-adrs`
- **What**: Verified ADR-039 through ADR-049 in `docs/12` against `docs/00`, `docs/02`, `docs/10` §22, `docs/11` and `README.md`.
- **Actual results**: ADR register complete and verified; no drift.

### P0-04 — Trim AGENTS.md, add Session protocol, add .agents/rules/

- **Date**: 2026-10-15
- **Branch**: `docs/p0-layout-and-adrs`
- **What**: Verified `AGENTS.md` length (8,966 characters, below the 9,000 character target and 12,000 Antigravity limit). Verified Session protocol section, free tiers rule (ADR-046), and public repository rule (ADR-047). Verified Antigravity official discovery path (`.agents/rules/*.md`) and created `.agents/rules/00-session-protocol.md`.
- **Actual results**: `wc -c AGENTS.md` = 8966 bytes. `.agents/rules/00-session-protocol.md` present and verified.

### P0-05 — Create docs/runbooks stubs; scripts/docs-links.mjs; run link check

- **Date**: 2026-10-15
- **Branch**: `docs/p0-layout-and-adrs`
- **What**: Created `docs/runbooks/secrets-rotation.md` completing runbook stubs. Implemented `scripts/docs-links.mjs` (ESM Markdown link & anchor validator). Executed validator across all documentation.
- **Commands run**:
  - `chmod +x scripts/docs-links.mjs`
  - `node scripts/docs-links.mjs`
- **Actual results**: Scanned 31 Markdown files, checked 345 relative links & anchors. 0 broken links. Gate PASSED.

### B1 Merge — Pull Request #1 merged to main

- **Date**: 2026-10-15
- **PR**: https://github.com/Warish-Labs/DevMind/pull/1
- **Title**: `Docs/p0 layout and adrs`
- **What**: Owner reviewed and merged PR #1 to main. Antigravity switched to main, pulled (`d750b11`), deleted branch `docs/p0-layout-and-adrs` locally and on remote, created and switched to `feature/p0-tooling`.

---

## 5. Decisions and why

| Decision                                                              | Rationale       | ADR     |
| --------------------------------------------------------------------- | --------------- | ------- |
| Folder names: client/, server/, extension/, common/                   | Owner-confirmed | ADR-039 |
| Screenshot-first: S1 home page, S2 extension before M1                | Owner-confirmed | ADR-040 |
| Custom cursor + richer motion on home page                            | Owner-confirmed | ADR-041 |
| pnpm workspaces, uv, husky+lint-staged+commitlint                     | Owner-confirmed | ADR-042 |
| Vitest (not Jest), Playwright, pytest; REST not GraphQL               | Owner-confirmed | ADR-043 |
| Feature/fix branches, Conventional Commits, squash merges             | Owner-confirmed | ADR-044 |
| common/data/ as single source of truth                                | Owner-confirmed | ADR-045 |
| Free-only: Vercel Hobby + Render free + Neon Free + Render Key Value  | Owner-confirmed | ADR-046 |
| Real repo: Warish-Labs/DevMind (public)                               | Owner-confirmed | ADR-047 |
| Fake provider default; free LLM tiers only with synthetic/public data | Owner-confirmed | ADR-048 |
| Domain: devmind.warishlabs.in / api.devmind.warishlabs.in             | Recommended     | ADR-049 |

---

## 6. Commands that work (verified, 2026-10-15)

```bash
# Git
git switch -c <branch>               # create branch
git add -A && git commit -m "..."    # commit everything
git push -u origin <branch>          # push new branch

# Node / pnpm (after sourcing ~/.bashrc or adding to PATH)
export PNPM_HOME="/home/md-warish-ansari/.local/share/pnpm"
export PATH="$PNPM_HOME:$PATH"
pnpm --version    # 12.11.2

# Python / uv
uv --version      # 0.12.17
uv run python --version    # (verifies Python works)
```

---

## 7. Gotchas and fixes

| Problem                                                   | Fix                                                                                                         | Date                  |
| --------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- | --------------------- |
| `corepack enable pnpm` fails with EACCES                  | Use pnpm installer script: `curl -fsSL https://get.pnpm.io/install.sh                                       | SHELL=/bin/bash sh -` | 2026-10-15 |
| `npm install -g pnpm` fails with EACCES                   | Same as above — use the installer, not npm global                                                           | 2026-10-15            |
| pnpm installed but `pnpm: command not found` in new shell | Run `source ~/.bashrc` or add `export PNPM_HOME=...` and `export PATH=...` before using pnpm                | 2026-10-15            |
| docs/ and brand/ are untracked (not committed to main)    | Commit them on this branch as part of P0-01                                                                 | 2026-10-15            |
| Sandbox run_command fails with connection reset           | Use `BypassSandbox: true` — the sandbox network is unreachable for some commands                            | 2026-10-15            |
| `ssh: Could not resolve hostname github-personal`         | Configure `Host github-personal` alias in `~/.ssh/config` pointing to `github.com` with `~/.ssh/id_ed25519` | 2026-10-15            |

---

## 8. Dependency versions (verified 2026-10-15)

| Package  | Version | Source                  | License    | Date verified |
| -------- | ------- | ----------------------- | ---------- | ------------- |
| Node.js  | 24.22.0 | Active LTS — nodejs.org | MIT        | 2026-10-15    |
| pnpm     | 12.11.2 | get.pnpm.io installer   | MIT        | 2026-10-15    |
| uv       | 0.12.17 | already installed       | Apache-2.0 | 2026-10-15    |
| corepack | 0.36.0  | bundled with Node 24    | MIT        | 2026-10-15    |

> Remaining versions (Next.js, React, TypeScript, Tailwind, Vitest, Playwright, FastAPI, etc.) will be pinned in docs/runbooks/dependency-versions.md after being verified from npm/PyPI registries during B2.

---

## 9. Open questions for the owner

| #    | Question                                                                                                                                                                                          | Impact              |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------- |
| OQ-A | Is the Vercel Hobby team under the `warishlabs` GitHub account (the one whose commit email is `warishdeveloper@gmail.com`)? Vercel Hobby refuses to deploy commits from an email not on the team. | Deployment (Vercel) |
| OQ-B | What is the VS Marketplace publisher id? The plan uses `warishlabs` as a placeholder.                                                                                                             | Extension release   |
| OQ-C | Confirm the Neon free project is in the same region as Render (e.g., both `us-east-1`).                                                                                                           | Latency (M1)        |
| OQ-D | Is `warishdeveloper@gmail.com` the GitHub noreply email, or a linked verified email on the Warish-Labs org account?                                                                               | Vercel deploy       |

---

_Updated: 2026-10-15 · Branch: feature/p0-tooling · Task: P0-06_
