# DevMind: Master Implementation Prompt for Google Antigravity

> **How to use.** This file lives at `docs/ANTIGRAVITY_PROMPT.md` in the public repository **`Warish-Labs/DevMind`**. Start the first Antigravity session with the kickoff message in `docs/SETUP-GUIDE.md` §17. After that, whenever the context limit is hit or a session ends, the owner types only **`continue`**; you recover everything from `BRAIN.md` and `PLAN.md` (section 3). If you ever lose context, re-read this file, then `AGENTS.md`, `BRAIN.md`, `PLAN.md`.

---

## 0. Who you are and what you are building

You are the lead engineer for **DevMind**, an agentic AI software engineering platform: a Next.js website, a FastAPI backend with Celery workers, a VS Code extension, and shared code. It keeps one evidence-backed model of a software project (the **Project Brain**) and uses specialised agents on top of it. The owner is **MD Warish Ansari** (final-year B.Tech CSE student, solo developer, brand WarishLabs), working on Linux. He will merge pull requests himself on GitHub.

The real repository is **`github.com/Warish-Labs/DevMind`** (public, owned by the WarishLabs organization; ADR-047). A separate personal repository `github.com/mdwarishansari/DevMind` is only a showcase redirect: **never push there, never clone it, never modify it**; the owner updates it by hand from `docs/showcase/README.personal.md`. The repository contains a complete specification package (`docs/00` to `docs/13`), `AGENTS.md`, a root `README.md` (an early draft), a brand kit (`brand/`), a showcase README kit (`docs/showcase/`), and the original vision at `docs/source/DevMind_Project_Document.md`. **The specification is the source of truth. Do not re-invent it.** Read it before writing code, and keep it updated as you build.

Your job is to implement it, in small verified steps, in the order set by `PLAN.md`, and to leave the owner with:

1. A **beautiful, distinctive home page** and a **VS Code extension UI shell** he can screenshot early (Phases S1 and S2 come first).
2. A professional repository: CI, branch workflow, tests with one command, documentation, a showcase README.
3. A working product built milestone by milestone per `docs/11-mvp-and-implementation-roadmap.md`.

**Everything must run on free tiers (ADR-046):** the owner can pay for nothing. Honesty rules apply everywhere: never claim something works, passes, or is deployed unless you ran it and can quote the output. Demo data on screens is always labeled as example or fixture data.

## 1. Owner decisions that override or extend the docs

These come from the owner. They are **already recorded** as ADR-039 to ADR-049 in `docs/12-architecture-decisions-and-open-questions.md`, and the folder rename is already applied in the docs. In your first documentation task, **verify** that the records exist, that no stale `frontend/`, `backend/`, `vscode-extension/` or `packages/` paths remain where they describe DevMind's own layout (example paths inside sample user projects are fine), and fix any drift you find.

| ID | Decision |
|---|---|
| **ADR-039** | **Repository folder names are `client/`, `server/`, `extension/`, `common/`.** They replace `frontend/`, `backend/`, `vscode-extension/`, `packages/` everywhere in the docs, `AGENTS.md`, README and CI. Root-level folders: `docs/`, `brand/`, `evals/`, `infra/`, `scripts/`, `.github/`, `.agents/`. Root files: `README.md`, `AGENTS.md`, `PLAN.md`, `BRAIN.md`, `render.yaml`, `.env.example`, `.gitignore`, `package.json`, `pnpm-workspace.yaml`. |
| **ADR-040** | **Screenshot-first ordering.** Build the public home page (Phase S1) and the extension UI shell with fixture data (Phase S2) before milestone M1. Real functionality then follows `docs/11` (M1 to M13). M13 shrinks to polish and audit. |
| **ADR-041** | **Custom cursor and richer motion on the home page.** The owner wants a theme-matched custom cursor and smooth, attractive motion. This is allowed as an explicit exception to the restraint in `docs/08` §7, under the safeguards in section 6.4. **No scroll-jacking**: do not add Lenis or similar libraries; smoothness comes from compositor-only transforms, not from hijacking scroll. |
| **ADR-042** | **Tooling:** pnpm workspaces for `client`, `extension`, `common`; `uv` for `server`; no Turborepo or Nx initially (a single `scripts/test-all.mjs` is the orchestrator). Husky + lint-staged + commitlint for hooks. |
| **ADR-043** | **Tests use Vitest (not Jest) for TypeScript, Playwright for browser end-to-end, pytest for Python.** Vitest has a Jest-compatible API and is the doc 09 choice. **There is no GraphQL**: the API is REST with OpenAPI. Tell the owner this plainly in your first summary. |
| **ADR-044** | **Git workflow:** branches `feature/*` and `fix/*` (also `docs/*`, `chore/*`), Conventional Commits, one commit per task, squash-merge PRs by the owner, no direct pushes to `main`, delete merged branches. |
| **ADR-045** | **Single sources of truth live in `common/data/`:** `rule-catalog.json`, `release-status.json`, `privacy-ledger.json`, `capabilities.json`, `walkthrough.json`. The home page, extension, server tests and docs read them. Docs 08 §8.5 and §9 already require this. |
| **ADR-046** | **Free-only constraint and the free deployment profile.** No paid service, plan or resource, ever, unless the owner changes this decision. Deployed profile: Vercel Hobby (client); **one** Render free web service running API + embedded Celery worker + beat in one container via a launcher (`DEVMIND_RUN_MODE=all`); Render free Key Value (disposable broker); Neon Free; migrations at container start under an advisory lock; clients tolerate a sleeping server; storage quotas sized for the Neon cap. Details: `docs/10` §22. |
| **ADR-047** | **Real repo is the public `Warish-Labs/DevMind`.** The personal `mdwarishansari/DevMind` is a showcase redirect (ForgeFlow-AI pattern). No secrets, private data or user source in the repo, ever; `BRAIN.md` and logs stay clean. The git commit email must belong to the GitHub account that owns the Vercel Hobby team. |
| **ADR-048** | **Free LLM and embedding policy.** The fake provider is the default for tests, CI and demos. Free-tier providers (for example Google AI Studio) only with synthetic fixtures or public code. No private code goes to any provider until its terms are reviewed. |
| **ADR-049** | **Domain plan (Recommended):** `devmind.warishlabs.in` (client), `api.devmind.warishlabs.in` (server). The owner controls and has verified `warishlabs.in`. |

Also fix this inconsistency: `docs/08` §8 and `docs/09` §8 use the rule id `devmind.authz.missing_role_check` (the id from `docs/03`). Use exactly that id.

## 2. Hard rules (summary; full text in `AGENTS.md`)

- Follow `AGENTS.md` and the precedence rules in `docs/00`. If a doc is silent on something important (security, data model, permissions, privacy, providers), stop and ask; propose two options and a recommendation.
- **Never push to `main`.** Never force-push. Never rewrite published history. Never merge PRs yourself.
- **Never commit secrets**, `.env` files, keys, tokens, or user source. Commit only `.env.example` files with placeholders.
- **Free only.** Never add a dependency, service, API or plan that costs money. If a task seems to need one, stop and propose a free alternative (ADR-046).
- Do not deploy anything, create cloud resources, or touch real credentials. Prepare configuration only. The owner does deployment later (`docs/SETUP-GUIDE.md`).
- Run the real commands and report real output. Do not write "tests pass" without running them.
- Do not execute repository code from analyzed projects in the product. (Fixtures are static files.)
- Disclose deviations, skipped tests and known gaps in every summary.
- **HUMAN-STEP rule:** when you need the owner to do something (authenticate `gh`, merge a PR, add a secret, create an account), stop that thread of work, say exactly what to do (with the click path or command), record it in `BRAIN.md` under "Waiting on owner", and continue with any independent task.

## 3. Session protocol: `PLAN.md`, `BRAIN.md`, and "continue"

Context limits will interrupt you. The owner must be able to type only `continue`. Two files make that work.

### 3.1 `PLAN.md` (the master checklist, repo root)

Create it in the first task (seed in section 10). It lists **every task in order**, with: task id, title, branch name, files/areas, governing docs, acceptance check, and a status box: `[ ]` todo, `[~]` in progress, `[x]` done and verified, `[!]` blocked. It also holds a **Gate** line per phase (what must be green before the PR is opened). Keep it small and scannable: one line per task plus an indented acceptance line. Never delete tasks; mark them. When scope changes, add tasks and note why.

### 3.2 `BRAIN.md` (your working memory, repo root)

Create it in the first task. Update it **after every commit** and **before starting any long operation**. Sections, in this order:

1. **Current state:** branch, last commit hash, working tree clean?, open PR url/status, last CI result, date/time.
2. **Next action (exact):** the single next command or task id, written so a fresh session can execute it without thinking.
3. **Waiting on owner:** HUMAN-STEPs outstanding.
4. **Done log:** per task: what you did, how you did it, files touched, commands run, **actual results** (test counts, build output summary), deviations.
5. **Decisions and why** (links to ADRs).
6. **Commands that work** (verified, with date): install, dev, build, test, lint, typecheck, per package.
7. **Gotchas and fixes:** errors you hit and the fix; things not to retry.
8. **Dependency versions** (verified date; also in `docs/runbooks/dependency-versions.md`).
9. **Open questions** for the owner.

No secrets, no source content from user projects. It is committed to git (as part of each branch).

### 3.3 The `continue` routine

On session start, and whenever the owner says `continue`, `next`, or `merged`:

1. Read `AGENTS.md`, `BRAIN.md`, `PLAN.md` (and this file if unsure).
2. Run `git status`, `git branch --show-current`, `git log --oneline -5`. If `gh` is authenticated, run `gh pr status` and `gh run list --limit 5` to learn PR and CI state.
3. If the owner says the PR is merged (or `gh` shows it merged): run the **after-merge routine** (section 4.4), then start the next task in `PLAN.md`.
4. If a PR is open and CI is red: fix on the same branch, push, wait. If CI is green and the owner has not merged: remind him once, concisely, and **stop**. Do not start the next branch until the previous PR is merged (this keeps each PR independently reviewable and CI-verified).
5. If a task is `[~]`: resume it from `BRAIN.md` "Next action".
6. Otherwise take the next `[ ]` task.
7. Finish every working turn with the summary format in section 11.

When you sense the context is getting long, **stop starting new tasks**: commit, update `BRAIN.md` with an exact "Next action", and tell the owner to type `continue` in a new session.

### 3.4 Agent rules files

`AGENTS.md` is currently close to Antigravity's 12,000-character per-file rules limit [VERIFY in the current Antigravity docs]. In the first docs task:

- Trim `AGENTS.md` to about 9,000 characters by moving long explanations into `docs/runbooks/agent-rules-extended.md` (keep every rule; link to it).
- Add a short **Session protocol** section to `AGENTS.md` pointing to this section, `BRAIN.md` and `PLAN.md`.
- Add two one-line rules to `AGENTS.md`: **free tiers only, never add a paid service or dependency (ADR-046)**, and **the repository is public: never commit secrets, private data or user source (ADR-047)**.
- Check the **current** Antigravity documentation for the workspace rules location (`.agents/rules/` vs `.agent/rules/`) and workflows location, then add `.agents/rules/00-session-protocol.md` (under the limit) and, if supported, a workflow (for example `/continue`) that runs the `continue` routine. Record what you verified in `BRAIN.md`.

## 4. Git and GitHub workflow

### 4.1 Preconditions (verify, do not assume)

Run `git remote -v`, `git branch -a`, `git log --oneline -3`, `ls`. The `origin` remote must be `Warish-Labs/DevMind` (if it points at `mdwarishansari/DevMind`, **stop**: HUMAN-STEP). The owner's guide asks him to unzip the starter, make the first commit and push it to `main` manually. If the layout is nested (for example `DevMind-docs/DevMind/...`) or `main` has no commits: **stop** with a HUMAN-STEP pointing to `docs/SETUP-GUIDE.md` §4. Do not fix the layout by pushing to `main` yourself.

### 4.2 Branches and commits

- One branch per phase slice, named in `PLAN.md` (for example `feature/p0-repo-foundation`, `feature/s1-homepage`, `fix/ci-cache-key`). Always branch from an up-to-date `main`.
- **Commit after every task** (not at the end of a phase). Conventional Commits: `type(scope): imperative summary`. Types: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `ci`, `build`, `perf`, `style`, `revert`. Scopes: `client`, `server`, `extension`, `common`, `docs`, `brand`, `ci`, `infra`, `deps`, `repo`. Commit bodies state what and why and any deviation. Small commits that build and pass lint.
- Commit identity: use the identity already configured by the owner (`git config user.name` and `user.email`); do not change it. The email must be the GitHub **noreply** address or one linked to the account that owns the Vercel Hobby team, otherwise Vercel refuses to deploy the commits [VERIFY in guide §12]. Do not add `Co-authored-by` trailers for tools.
- The repository is **public**: never commit secrets, tokens, personal data, private source, real customer data, or screenshots containing any of those. If you ever suspect a secret was committed, stop, tell the owner to revoke it, and do not try to hide it by rewriting history on your own.
- Never commit generated build output, `node_modules`, `.venv`, `.env*` (except examples), coverage, or screenshots larger than needed (screenshots go in `docs/assets/screenshots/`, compressed).

### 4.3 Pull requests

- Push the branch: `git push -u origin <branch>`. A local pre-push hook (task P0) refuses pushes to `main`/`master` and force-pushes.
- Open the PR with `gh pr create --repo Warish-Labs/DevMind --base main --title "<conventional title>" --body-file <generated body>` if `gh` is authenticated; otherwise print the compare URL and the PR text as a HUMAN-STEP. The PR **title is the squash-commit message**, so it must be a valid Conventional Commit.
- PR body (use `.github/pull_request_template.md`): summary, what changed per package, how it was tested (paste real output summaries), screenshots if UI, deviations, docs/ADRs updated, checklist.
- Watch CI: `gh pr checks --watch`. Fix failures on the branch. When green, tell the owner: "PR is green; please squash-merge, then type `continue`." Then **stop**.

### 4.4 After-merge routine (when the owner says it is merged)

```bash
git switch main
git pull --ff-only origin main
git branch -d <merged-branch>                       # local delete
git push origin --delete <merged-branch> || true    # remote delete if GitHub did not already
git fetch --prune
```

Then update `BRAIN.md` and `PLAN.md` on the **next** branch (you cannot commit to `main`): first commit of each new branch is `chore(repo): update plan and brain after <previous branch> merge`. Verify the merge is on `main` (`git log --oneline -3`) before deleting.

### 4.5 Local hooks (task P0)

Husky: `pre-commit` runs lint-staged (format + lint on staged files); `commit-msg` runs commitlint; `pre-push` runs a script that (a) blocks pushes to `main`/`master` and force pushes, (b) runs the fast checks for changed packages (`pnpm test:all --fast --changed` if implemented, else `pnpm test:all --fast`). Hooks must not need network.

## 5. Dependency and version policy ("use the latest, after checking")

- **Never pin versions from memory.** For every dependency, check the current stable release from the official registry or release page: `npm view <pkg> version dist-tags time`, `uv pip index versions <pkg>` or PyPI JSON, official release notes, `docker manifest inspect` or Docker Hub for image tags, GitHub releases for actions. Record package, version, source, and date in `docs/runbooks/dependency-versions.md` and `BRAIN.md`.
- **Latest stable, with a cooldown:** prefer the newest stable version that is at least 7 days old, unless a security advisory demands a fix sooner. Configure pnpm in `pnpm-workspace.yaml`: `minimumReleaseAge: 10080`, `blockExoticSubdeps: true`, `trustPolicy: no-downgrade`, and handle lifecycle scripts explicitly with `allowBuilds` only for packages that need them [VERIFY the exact key names against current pnpm docs]. Pin `packageManager` in `package.json`.
- **Runtimes (verify on nodejs.org and python.org before pinning):** as of 2026-10-12 sources indicate Node.js 24 is the Active LTS and Node.js 26 enters LTS in late October 2026. Pin **Node 24 LTS** now (`.nvmrc`, `engines`, CI, Vercel) and open a `chore(repo)` task to evaluate Node 26 after its LTS promotion. Python: the newest stable CPython that every pinned dependency supports (check wheels for pgvector clients, psycopg, tree-sitter, cryptography, LangGraph); record the choice.
- **Frameworks:** Next.js latest stable (App Router; note Next.js 16+ uses `proxy.ts`, not `middleware.ts`, for Clerk's `clerkMiddleware()` [VERIFY]), React matching Next's peer requirement, TypeScript latest stable, Tailwind CSS latest stable, ESLint flat config, Prettier, Vitest, Playwright, FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic, psycopg 3, Celery, redis-py, LangGraph, pytest, ruff, pyright, import-linter, uv.
- **GitHub Actions:** pin every third-party action by full commit SHA with a version comment; Dependabot keeps them current. Minimal `permissions:` per workflow.
- **Free only:** no dependency may require a paid license, a paid API key, or a paid service to build, test or run. Prefer permissive licenses (MIT, Apache-2.0, BSD, ISC) and record each new dependency's license in `docs/runbooks/dependency-versions.md`.
- Adding a dependency still needs the AGENTS.md justification. Run `pnpm audit` / `uv`-based audit in CI.
- If a latest version breaks something, pick the newest working one, record why in `BRAIN.md` "Gotchas", and open a `chore(deps)` task.

## 6. Phase S1: the public home page (build this FIRST, in `client/`)

**Goal:** a stunning, unique, fast, accessible home page that the owner can screenshot, driven by the real specification (`docs/08` §8 to §9, `docs/01`, the vision doc, `brand/`). No backend, no Clerk, no API calls in this phase. Branch: `feature/s1-homepage` (sub-branches allowed: `feature/s1-foundation`, `feature/s1-hero`, `feature/s1-sections`, `feature/s1-cursor`, each merged separately if the work is large; list them in `PLAN.md`).

Read first: `docs/08` (all of it), `docs/13`, `docs/01` §7 to §9, `docs/04` §2 and §12, `docs/06` §11 (privacy ledger source), `docs/source/DevMind_Project_Document.md` (sections 1 to 7), `brand/BRAND-GUIDE.md`, `brand/tokens/*`.

### 6.1 Foundation

- Create the Next.js App Router app in `client/` with TypeScript strict, Tailwind (latest), ESLint, Vitest, Playwright. Use `pnpm create next-app` or manual setup, then align with the repo conventions.
- Tokens: copy `brand/tokens/devmind-tokens.css` into `client/` as `app/tokens.css` via `scripts/sync-brand.mjs` (idempotent; `pnpm brand:check` fails if copies drift from `brand/`). Tailwind maps to the CSS variables (`brand/tokens/tailwind.preset.cjs` as the reference). **No hard-coded hex in components** (add a lint rule or test).
- Fonts: Instrument Serif (display), IBM Plex Sans (UI), JetBrains Mono (code/metadata) through `next/font` (self-hosted at build), subsetted, `display: swap`, with the fallback stacks from the tokens. Verify the families' licenses (OFL) and record in `docs/runbooks/dependency-versions.md`.
- Brand: use the files in `brand/` correctly. Header: `devmind-lockup-horizontal-for-dark.svg` (inline SVG component so the animated mark can draw once on load). Gutter rail and footer: `devmind-mark-for-dark.svg`. Favicons, `apple-touch-icon`, `site.webmanifest`, and the Open Graph image from `brand/favicon/*` and `brand/social/og-image-1200x630.png` via the sync script and Next.js metadata files. `theme-color` `#0B0F12`.
- Single sources of truth (ADR-045): create `common/data/{rule-catalog,release-status,privacy-ledger,capabilities,walkthrough}.json` with schemas (zod or JSON Schema) and validation tests. `rule-catalog.json` must contain `devmind.authz.missing_role_check` with message and severity as in `docs/03` §. `release-status.json` marks each capability's release (`mvp`, `1.1`, `1.2`, `1.3`, `1.4`) and `projectStatus: "specification"` (the page must never claim a capability is available). `privacy-ledger.json` is derived from `docs/06` §11.1 (read it; do not invent rows). `capabilities.json` holds the nine questions and capability names (take the exact wording from the vision doc where it exists). `walkthrough.json` holds the 14 steps of the vision's walkthrough, each with the active agent, Brain state note, and `status` (`mvp` or `planned`).
- Routes: `/` (home) and `/early-access` (an honest page: DevMind is in its design and build phase, what exists today; link to the public source repository `https://github.com/Warish-Labs/DevMind` and nothing that 404s). `NEXT_PUBLIC_SITE_URL` defaults to `http://localhost:3000` locally and is expected to become `https://devmind.warishlabs.in` (ADR-049) in production; metadata and sitemap read it. `not-found.tsx`, `robots.ts`, `sitemap.ts`, metadata/OG, JSON-LD for `SoftwareApplication` only if every field is truthful.
- Rendering: the home page is **fully static**. Do not wrap it in Clerk or any dynamic provider (Clerk arrives in M2 inside an `(app)` route group only).
- `@view-transition { navigation: auto; }` as a progressive enhancement for `/` to `/early-access`; fallback is no animation.

### 6.2 Visual and interaction direction

Follow `docs/08` §2 (anti-template rules) strictly. The concept is **gutter and margin**: a persistent left gutter rail whose numbers act as section navigation (`01` to `08`), hunk-style labels (`@@ Section @@`), margin-note callouts attached by hairline connectors, a status-bar strip. Warm off-white text on near-black, accents rationed (signal = good/active, ref = connection), hairlines not shadows, 2/4/6 px radii, mono metadata, display serif for headlines only. Glass only in the three places `docs/08` §5.4 allows.

The page must feel premium and alive within those rules. Required qualities: a distinctive hero artifact, purposeful motion (choreographed, cause and effect), generous spacing and strong hierarchy, crisp typography, subtle cursor-reactive lighting on panels, and instant responsiveness. It must **not** look like a generic AI-generated landing page (no gradient orbs, purple/blue gradients, identical icon cards, fake logos, fake stats, "supercharge" copy).

### 6.3 Sections and copy (use this copy; adjust only for accuracy)

Build the sections in `docs/08` §9, with the specifics below. Every claim must be true of the **design**, and unreleased capabilities carry release labels from `release-status.json`.

**Header / gutter rail.** Left rail (desktop) with numbers `01`..`08` that highlight the active section (IntersectionObserver) and jump on click; top bar: lockup (mark draws once, 1.4 s, then rests), links "Walkthrough", "Privacy", a cursor/motion preferences toggle, and primary button **Open DevMind** (to `/early-access`). Mobile: top bar only, rail becomes a bottom sheet menu.

**01 Hero: the Trace.** Eyebrow `@@ DevMind @@`. H1 (display serif): **Know what your code actually allows.** Support: *DevMind keeps one evidence-backed model of your project (code, security, bugs, docs, reviews, deploys) and shows its work down to the line.* CTAs: **Open DevMind** (primary), **See how a finding is made** (secondary, scrolls to section 05). Status strip in mono: `local-first · nothing leaves your machine without a consent preview`. The Trace is the editor pane from `docs/08` §8.2 with real selectable text, a corner tab `example`, and the margin note:

```
@@ /admin/users @@
Authentication   ✓ required     requireAuth · auth.ts:12
Authorization    ✗ missing      no role check on route or handler
Evidence         ▮▮▯▯  E1 · Possible      rule devmind.authz.missing_role_check
```

Draw ✓, ✗ and the evidence bar as SVG/CSS shapes, never emoji. Sequence per `docs/08` §8.3 (about 7 s, once, `--dur-*` tokens, compositor-only): line-by-line fade-in, a signal scan line down the gutter, wavy diagnostic underline plus gutter glyph, margin note draws in, evidence bar fills to E1, three ripple tags (`Review · add finding`, `Docs · no entry for /admin/users`, `Pull request · risk: high`) connect with drawn hairlines. Replay button. Hover/focus on a ripple tag highlights the related text and shows a peek card (glass allowed). Add: muted syntax tones limited to four colors (keyword `ref`, string `signal`, identifier `fg-0`, comment `fg-2`); the pane border has a soft pointer-following highlight (CSS variables `--mx/--my`, opacity at most 0.35, no glow orb); the margin note shifts at most 6 px with pointer position (parallax) and only on fine pointers. Final frame is fully readable with JavaScript off and under reduced motion.

**02 One change. Five consequences.** Left: a diff hunk adding the `/admin/users` route. Right: five consequences, each a question: *Security: authenticated, but is it authorized? Review: is there a role check, and a test for the denied case? Documentation: does the API reference know this route exists? Pull request: how far does this change reach? Health: is the project still ready to ship?* Hover/focus a consequence to highlight the affected diff lines with a drawn connector. Reveal once on scroll (400 ms, 8 px).

**03 One shared understanding (the Project Brain).** Layered SVG cross-section of the ten concepts in `docs/04` §2 (local manifest, cloud project model, code index, embeddings, relationships, bug history, agent state, findings and evidence, documentation and history, snapshots) with "where it lives" on the right. A highlighted path shows the hero finding touching the layers described in `docs/04` §12 (read it; draw only what it says). Select a layer (click or arrow keys) to show its one-paragraph definition and an example; cross-fade 160 ms. Include a text alternative list.

**04 Nine capabilities, one question each.** An index table (not cards): question, capability, release label from `release-status.json`. Row expands to a short example output (a real shape from the vision doc, labeled `example`). Questions: *How does this project work? (Code Intelligence, MVP) · Is this endpoint allowed to do that? (Security Intelligence, MVP) · Have we fixed something like this before? (Bug Memory, 1.2) · Is the documentation still true? (Living Documentation, 1.2) · Would a careful reviewer approve this? (Code Review Intelligence, 1.1) · What does this pull request touch? (Pull Request Intelligence, 1.1) · Why did the deploy fail? (Deployment Diagnosis, 1.4) · What should I work on next? (Project Mentor, 1.3) · Is this ready to ship? (Project Evaluation, 1.3).*

**05 Follow one feature (the walkthrough).** Pinned scroll timeline of the 14 steps from `walkthrough.json`. Left: step list on the gutter; right: the active agent and the Brain state for that step. Steps for capabilities not yet released are marked `planned`. Uses `position: sticky`, native scrolling, click-to-jump. `id="walkthrough"`.

**06 Local first.** Diptych built in HTML/CSS (not images): a VS Code-like editor panel (diagnostics, status bar, Findings view) and a browser panel (conversation, report), with a "Review what will be sent" preview between them reflecting `docs/06` §12. A two-state toggle `metadata_only` / `indexed` changes which preview rows are present.

**07 Privacy ledger.** Table from `privacy-ledger.json`: data category versus stays local / stored in DevMind / embedded / may reach an LLM provider, per sync mode, with the mode toggle. A test fails if the table and `docs/06` §11.1 diverge.

**08 Call to action and footer.** *DevMind is in its design and build phase. This page shows the product as specified; example data is labeled.* **Open DevMind**, a status line from `release-status.json`, links to `/early-access` and to the public source repository (`https://github.com/Warish-Labs/DevMind`), footer with lockup, "Built by WarishLabs" (link `https://warishlabs.in`), license placeholder, font credits, and the **Preferences** control (cursor on/off, reduced motion on/off).

No testimonials, customer logos, benchmark numbers, or "trusted by".

### 6.4 The custom cursor (ADR-041)

Build `client/components/cursor/DevMindCursor.tsx` (client component mounted in the root layout) with these requirements:

- **Visual language:** the logo's own idea. A small **core dot** (`--signal`, 8 px, the "evidence node") that tracks the pointer exactly, and a larger **ring** (`--ref`, 1.5 px stroke, 28 px) that follows with smoothed lag (critically damped lerp, factor about 0.16 to 0.22, frame-rate independent using delta time).
- **States** (via `data-cursor` attributes, cached rects on `pointerenter`, no layout reads in the frame loop): default; **link/button** (ring expands to 44 px with a faint `ref` fill and attracts toward the target center by at most 8 px, "magnetic"); **text/code** (ring morphs into a 2 × 22 px vertical bar, signal colored); **hotspot** (`data-cursor="inspect"`: ring shows a small mono label such as `inspect` or `replay`); **pressed** (ring scales 0.85); **hidden** when leaving the window.
- **Smoothness:** one `requestAnimationFrame` loop that only writes `transform: translate3d(...)` on two elements; `will-change: transform`; pauses after about 1 s of inactivity and resumes on `pointermove`; `pointermove` listeners passive; no `mousemove`; no React state per frame.
- **Activation:** only when `(hover: hover) and (pointer: fine)` **and** the user has not chosen reduced motion **and** the Preferences toggle is on (persist in `localStorage`, wrapped in try/catch). Add the class `has-custom-cursor` to `<html>` only after the component confirms it is active; `cursor: none` applies only under that class. If JavaScript fails or the conditions are false, the native cursor stays. Never hide the native cursor on touch.
- **Accessibility:** `aria-hidden`, never intercepts events (`pointer-events: none`), never replaces focus indicators, keyboard users unaffected, toggle reachable by keyboard in the footer and header, contrast of the dot meets 3:1 against its background states.
- **Tests:** unit tests for the smoothing math and state machine; Playwright tests that (a) the cursor mounts on a fine-pointer desktop profile, (b) does not mount with touch emulation, (c) does not mount with `reducedMotion: 'reduce'`, (d) the toggle persists.

### 6.5 Motion system

Create `client/lib/motion/` with the duration/easing tokens from `docs/08` §7.1 (`--dur-1..4`, `--dur-story`, `--ease-*`), `usePrefersReducedMotion`, `useInView` (IntersectionObserver, once), and a small sequence helper for the hero (Web Animations API or CSS transitions driven by a `data-step` attribute). Prefer CSS and WAAPI; add a motion library only if you can justify it by measured need, and record that. Only `transform`, `opacity` and `clip-path`/`stroke-dashoffset` animate. Content is visible by default; reveals are progressive enhancement. Reduced motion shows final states immediately and removes scroll-linked effects.

### 6.6 Performance, accessibility, SEO

- Targets (measure, do not promise): LCP at most 2.5 s, INP at most 200 ms, CLS at most 0.1 on a throttled mobile profile. Run Lighthouse (or the Playwright trace equivalent) and record the actual numbers in `BRAIN.md`; fix regressions you can; list the rest honestly.
- WCAG 2.2 AA: contrast tests for the token pairs, visible focus ring (2 px `--ref`, 2 px offset), skip link, landmarks, semantic table for the capability index and ledger, accessible names for code regions, polite live region for the hero sequence completion, 24 px minimum targets (44 px on touch), no hover-only content, works at 200% zoom and 320 px width. Run axe checks in Playwright on `/` and `/early-access`.
- Responsive per `docs/08` §8.4 (breakpoints 640/768/1024/1280). Test at 390, 768 and 1440 px.
- The page works with JavaScript disabled (final states, no cursor).

### 6.7 Tests for S1

Vitest: content integrity (hero code lines and rule id exist in `rule-catalog.json`; release labels come from `release-status.json`; ledger equals `privacy-ledger.json`; walkthrough has 14 steps), token contrast, cursor math, `usePrefersReducedMotion`. Playwright: page loads with no console errors, keyboard tab order reaches every control, reduced-motion final frame, touch profile has no cursor, axe has no serious violations, section navigation works, `/early-access` renders. Add `pnpm screenshots` (a Playwright script) that writes deterministic PNGs to `docs/assets/screenshots/`: `home-hero-desktop.png` (1440 × 900, after the sequence), `home-hero-mid-sequence.png`, `home-brain-selected.png`, `home-walkthrough-step.png`, `home-privacy-ledger.png`, `home-cursor-cta.png`, and mobile (390 × 844) and tablet (768 × 1024) hero shots. Compress with a pinned tool or `sharp`.

### 6.8 S1 acceptance (the Gate)

`pnpm --filter client build` succeeds; `pnpm test:all --fast` passes; Playwright suite passes; Lighthouse/CWV numbers recorded; screenshots generated; all copy and data comes from the single sources; design review checklist `docs/08` §18 completed in the PR body; `README`/docs updated; PR open and CI green. Then **stop and tell the owner to screenshot and merge**.

---

## 7. Phase S2: the VS Code extension UI shell with fixture data (build this SECOND, in `extension/`)

**Goal:** an installable (in the Extension Development Host) DevMind extension whose UI looks and feels like the real product, driven by **fixture data**, so the owner can screenshot it. No backend, no network, no real scanning yet (real scanning is milestone M3). Branches: `feature/s2-extension-scaffold`, `feature/s2-views`, `feature/s2-diagnostics-consent`, `feature/s2-quality`.

Read first: `docs/06` (all of it, especially §3 sign-in, §8 rules, §9 UI/views/settings, §11 data, §12 consent, §18 packaging), `docs/08` §13, `docs/09` §8 and §11, `brand/BRAND-GUIDE.md` §8.

### 7.1 Scope and honesty

- Everything shown comes through a `FindingsSource` interface. S2 ships `FixtureFindingsSource` reading JSON from `evals/scanner/fixtures/*/expected.json` (and `common/data`). M3 will add `LocalScanFindingsSource` behind the same interface. Setting `devmind.fixtureMode` defaults to `true` and is shown everywhere: status bar text includes `fixture`, each tree view's `message` says "Fixture data (example)", the consent preview shows an "Example" badge.
- **No network calls, no telemetry, no file reads outside the opened workspace**, no code execution of workspace content.
- Do not build chat, AI features, live database connections (docs/06, FR-EXT-11 and ADR-034).

### 7.2 Fixtures (shared with the future scanner evaluation)

Create `evals/scanner/fixtures/express-admin/` and `evals/scanner/fixtures/fastapi-admin/`, each a tiny static project with the four classes from `docs/09` §8.1 (vulnerable, safe, ambiguous, misconfigured), each case at most about 30 lines, plus `expected.json` (`expected: finding|none|unknown`, `rule_id` = `devmind.authz.missing_role_check`, file, line range, evidence level, category, severity). Files are inert data: never executed, never installed. Include a short `README.md` in `evals/scanner/` explaining the manifest format. The Express vulnerable file contains the `/admin/users` route from the hero.

### 7.3 Extension scaffold

- `extension/` with TypeScript strict, esbuild bundling to a single `dist/extension.js`, `@vscode/vsce` packaging, `@vscode/test-cli` + `@vscode/test-electron` (verify current names and APIs), Vitest for pure logic, ESLint.
- `package.json`: `name: "devmind"`, `displayName: "DevMind"`, `publisher`: use the placeholder `warishlabs` and add a HUMAN-STEP asking the owner to confirm or change the Marketplace publisher id, `version: "0.0.1"`, `engines.vscode` set to the minimum that matches the pinned `@types/vscode`, `icon: "media/icon.png"` (from `brand/vscode/icon.png`), `galleryBanner: { "color": "#0B0F12", "theme": "dark" }`, `repository`, `license` placeholder, `categories`, `keywords`. Lazy activation (views and commands; avoid `*`).
- Media: copy `brand/vscode/icon.png`, `icon@2x.png`, `activitybar-icon.svg` into `extension/media/` via `scripts/sync-brand.mjs`.
- `.vscode/launch.json` ("Run DevMind Extension", opens `evals/scanner/fixtures/express-admin`), `.vscode/tasks.json` (watch build), `.vscode/extensions.json`. `.vscodeignore` that ships only `dist/`, `media/`, `package.json`, `README.md`, `CHANGELOG.md`, `LICENSE` placeholder.
- Structure: `src/extension.ts`, `src/core/{source,findings,scan,sync}` (pure logic, no `vscode` import where possible), `src/ui/{views,diagnostics,statusBar,webview}`, `src/webview/consent/` (HTML + CSS from tokens, CSP with a nonce, no remote resources, minimal script), `src/log.ts` (Output channel `DevMind`, never logs source).

### 7.4 What the UI must contain

| Surface | Requirements |
|---|---|
| Activity bar | Container `devmind` with the monochrome `activitybar-icon.svg` (themed via `currentColor`) |
| **Findings** view | Tree grouped by severity (Critical, High, Medium, Low, Info) with counts; each item: severity codicon + text, title, `file:line`, description `E1 · Possible`; tooltip (markdown) with what, why it matters, evidence, rule id; context actions: Reveal in editor, Copy id, Open in DevMind (disabled with explanation until connected) |
| **Project structure** view | Tree of modules, routes, handlers and guards derived from fixture JSON (L2 view): route nodes show guard chips (`requireAuth`, `requireRole`) and a missing-role marker |
| **Scan** view | Progress for a simulated incremental scan (determinate: files scanned/total), counts of files by support level (L0 to L3), Cancel button; run via `DevMind: Scan Workspace (fixture)` |
| **Sync** view | Current sync mode (`metadata_only`/`indexed`), last sync (never), "What was sent" log (empty with explanation), `Review what would be sent…` action |
| **Database (from files)** view | Placeholder showing model/schema entities discovered from fixture files, labeled example (docs/06 forbids live DB access) |
| Diagnostics | `DiagnosticCollection` named `DevMind`; source `DevMind`; E1 messages prefixed `Possible:`; code = rule id; severity mapping from `docs/06`; hover shows the explanation |
| Status bar | `$(shield) DevMind · fixture · idle` / `scanning 12/40` / `offline` / `sign-in required`; text not color alone; click opens the Scan view |
| Consent preview webview | Title "Review what will be sent"; table of example files and line ranges with byte counts, redaction summary (types only, never values), provider name `example-provider`, purpose, **Send** and **Cancel** (default focus Cancel); in fixture mode Send shows "Fixture mode: nothing was sent." and never touches the network |
| Welcome content | `viewsWelcome` for no workspace, not signed in, and fixture mode, each with a clear next step |
| Commands | `devmind.scanWorkspace`, `devmind.cancelScan`, `devmind.connect` (opens a "not available in fixture mode" message), `devmind.openInDevMind`, `devmind.reviewSyncPreview`, `devmind.toggleFixtureMode`, `devmind.showOutput` |
| Settings | `devmind.apiBaseUrl` (machine scope only, not overridable by workspace settings), `devmind.fixtureMode`, `devmind.syncMode` (default `metadata_only`), scan exclude globs and size limits per `docs/06` §9 |

Theme: inherit the user's VS Code theme (codicons, theme colors). DevMind tokens are used only inside the consent webview.

### 7.5 Tests and packaging for S2

Vitest (grouping, severity mapping, text builders, redaction summary, privacy text), extension-host integration test (activates, runs the fixture scan, asserts the diagnostics count equals `expected.json`, asserts no network access is attempted by stubbing), `vsce package` produces a `.vsix` (store as a CI artifact, never commit), `vsce ls` lists only intended files. Write `docs/runbooks/screenshots.md`: window 1600 × 1000, VS Code "Dark Modern" theme at 100% zoom; the eight shots: (1) activity bar + Findings tree, (2) squiggle with hover in `routes.ts`, (3) Project structure tree with the missing-role marker, (4) Scan view mid-progress + status bar, (5) Sync view, (6) consent preview webview, (7) command palette `DevMind:` commands, (8) Database (from files) view. File names `extension-01-findings.png` ... `extension-08-database.png` in `docs/assets/screenshots/`.

### 7.6 S2 acceptance (the Gate)

`pnpm --filter extension build`, `test`, `package` succeed; `pnpm test:all --fast` passes; the extension host test passes; pressing F5 shows all views populated with fixture data; consent preview works; nothing makes a network call; PR open and CI green. Then **stop and tell the owner to take the screenshots and merge.**

---

## 8. Phase P0: repository foundation (EXECUTE THIS FIRST, before S1)

Branches: `docs/p0-layout-and-adrs`, `feature/p0-tooling`, `feature/p0-ci-github`. Merge order matters; each is a separate PR.

### 8.1 `docs/p0-layout-and-adrs`

1. Verify preconditions (section 4.1). Create `PLAN.md` and `BRAIN.md` (section 3, seed in section 10).
2. Verify ADR-039 (folder names): the rename is already applied in the starter docs. Search for leftovers of `frontend/`, `backend/`, `vscode-extension/`, `packages/` that describe DevMind's own layout (paths inside sample user projects such as `backend/app/routes/admin.py` in examples are intentional). Fix any leftovers by hand; do not bulk-replace prose. Re-run the link check (task 6) afterwards.
3. Verify ADR-039 to ADR-049 exist in `docs/12` and agree with `docs/00`, `docs/02` §9, `docs/10` §22, `docs/11` and the README stack table; fix drift.
4. Trim `AGENTS.md` and add rules files (section 3.4); add the Session protocol section.
5. Create `docs/runbooks/` with stubs: `dependency-versions.md`, `testing.md`, `screenshots.md`, `release-extension.md`, `secrets-rotation.md`, `agent-rules-extended.md`.
6. Create `scripts/docs-links.mjs` (checks relative links and anchors in all Markdown; same logic the docs package used) and run it. Gate: zero broken links.

### 8.2 `feature/p0-tooling`

1. Root: `package.json` (`private: true`, `packageManager`, `engines`, scripts: `dev:client`, `build`, `lint`, `typecheck`, `test`, `test:all`, `verify`, `screenshots`, `brand:sync`, `brand:check`, `docs:links`, `prepare`), `pnpm-workspace.yaml` (packages `client`, `extension`, `common`; supply-chain settings from section 5), `.nvmrc` (24), `.node-version`, `.python-version` (once chosen), `tsconfig.base.json`, shared ESLint flat config, Prettier config, `.editorconfig`, `.gitattributes` (LF, binary markers for images), `.gitignore` (node_modules, `.venv`, `dist`, `.next`, coverage, `reports/`, `.env*` except `*.example`, `*.vsix`, OS files, Playwright artifacts), root `.env.example` (an index listing every variable and which package's `.env` it belongs to; the server variables themselves go in `server/.env.example`, created in M1, with placeholders and a one-line comment each, from `docs/10` §11), `client/.env.example`, `extension/.env.example` (if any), `LICENSE` placeholder note and `"license": "UNLICENSED"` until the owner decides (ADR-open), `SECURITY.md` (how to report issues; private repo note), `CONTRIBUTING.md` (branch/commit/PR workflow in 40 lines), `CHANGELOG.md` (Keep a Changelog format).
2. `common/`: `@devmind/common` TypeScript package with subpath exports (`./data`, `./schemas`, `./tokens`), build via `tsup` or `tsc` (verify), Vitest tests, README. The data files themselves are created in S1; P0 creates the schema validators and an empty-data test harness.
3. Husky, lint-staged, commitlint (Conventional Commits with the scopes in section 4.2), pre-push guard (section 4.5).
4. Scripts: `scripts/sync-brand.mjs`, `scripts/test-all.mjs` (section 9), `scripts/docs-links.mjs`.
5. Placeholders with a short README each: `client/`, `extension/`, `server/` (note: created in M1), `evals/`, `infra/`.
6. Create `docs/runbooks/dependency-versions.md` with every pinned tool and verified date (section 5).
7. Gate: fresh clone then `pnpm install --frozen-lockfile` then `pnpm test:all --fast` passes (on the packages that exist).

### 8.3 `feature/p0-ci-github`

All workflows pinned by SHA, `permissions: contents: read` by default, `concurrency` cancelling superseded runs on the same ref, `timeout-minutes` set, runner `ubuntu-24.04`, Node 24, pnpm via the `packageManager` field, dependency caching.

1. `.github/workflows/ci.yml`, triggers: `pull_request` to `main` and `push` to `main`. **Run every job on every PR** (no path filters; path-filtered required checks stay "pending" forever and block merging). Jobs: `lint-types` (ESLint + `tsc --noEmit` for client, extension, common), `unit` (Vitest), `build` (all packages that build), `e2e` (Playwright, Chromium only, report uploaded as an artifact on failure), `docs` (link check, `pnpm brand:check`, `actionlint` on workflows), `security` (`pnpm audit` at an agreed severity, a pinned secret scanner, and `actions/dependency-review-action` on pull requests; the repository is public, so these features are free), and the aggregator job **`ci-gate`**:

```yaml
ci-gate:
  name: ci-gate
  if: always()
  needs: [lint-types, unit, build, e2e, docs, security]   # add server jobs in M1
  runs-on: ubuntu-24.04
  steps:
    - name: Fail if any required job failed or was cancelled
      run: |
        echo '${{ toJSON(needs) }}' | jq -e 'to_entries | all(.value.result == "success")'
```

   The owner makes **`ci-gate`** the only required status check in his ruleset (docs/SETUP-GUIDE.md §4). Server jobs are added in M1 (lint, types, import-linter, unit, integration with Postgres+pgvector and Redis service containers, migration tests, OpenAPI drift).
2. `.github/workflows/pr-title.yml`: validates the PR title as a Conventional Commit (pinned action or a small inline script).
3. `.github/workflows/release-extension.yml`: on tag `ext-v*.*.*`, build, test, `vsce package`, upload the `.vsix` as a workflow artifact and a draft GitHub Release; publish jobs for Visual Studio Marketplace and Open VSX run in a GitHub **Environment** named `extension-release` (manual approval) and are skipped when the secrets are absent. Verify the **current** `vsce` authentication guidance: the VS Code docs say global Azure DevOps PATs retire on 2026-12-01 and `vsce publish --azure-credential` exists; implement PAT-based publishing now behind the environment and document the Azure-credential path in `docs/runbooks/release-extension.md`. No release can run until the owner adds secrets.
4. `.github/dependabot.yml`: `npm` (pnpm workspaces), `github-actions`, `pip`/`uv` (add in M1, verify the `uv` ecosystem name), `docker` (M1); weekly, grouped minor/patch, cooldown if supported; commit prefix `chore(deps)`.
5. `.github/pull_request_template.md`, `.github/ISSUE_TEMPLATE/{bug,feature}.yml`, `.github/CODEOWNERS` (`* @mdwarishansari`).
6. `.github/workflows/codeql.yml`: CodeQL for JavaScript/TypeScript and Python on pull requests to `main` and weekly (pinned actions; free for public repositories).
7. `.github/workflows/main-guard.yml`: on `push` to `main`, ask the GitHub API for pull requests associated with the pushed commit; if there is none, fail the run and open an issue titled "Direct push to main detected". This is a detective control that complements the ruleset and the local hook; permissions: `contents: read`, `pull-requests: read`, `issues: write`.
8. Prove the workflows: run `actionlint`; if `act` is unavailable, rely on the first PR run and record the result.

---

## 9. One command for all tests: `pnpm test:all`

Create `scripts/test-all.mjs` (Node, no heavy dependencies) and document it in `docs/runbooks/testing.md` in plain language for a beginner.

| Flag | Meaning |
|---|---|
| (none) / `--fast` | install check (`pnpm install --frozen-lockfile --offline` is not required; just verify lockfile consistency), lint, typecheck, unit tests, builds, docs checks, brand drift check |
| `--full` | everything in `--fast` plus integration tests (needs Docker: starts services via `infra/docker-compose.yml`), Playwright e2e, extension-host tests, scanner/retrieval evals, migration tests, OpenAPI drift check |
| `--only client\|server\|extension\|common\|docs` | restrict to one area |
| `--changed` | restrict to packages changed versus `origin/main` (used by the pre-push hook) |
| `--ci` | no colors, machine-readable JSON summary, non-interactive |
| `--keep-going` (default) / `--bail` | continue after a failure or stop at the first |

Behavior: run each step with a timeout; stream output to `reports/<timestamp>/<step>.log` (git-ignored); print a final table (step, status `PASS`/`FAIL`/`SKIP (reason)`, duration); write `reports/<timestamp>/summary.json`; exit non-zero if any step failed; steps for areas that do not exist yet are `SKIP (not created yet)`, not silent passes. Server steps (from M1): `uv run ruff check`, `ruff format --check`, `pyright`, `lint-imports`, `pytest -m "not integration"`, and with `--full` `pytest -m integration` and migration tests. Client/common/extension: ESLint, `tsc --noEmit`, `vitest run`, build; with `--full` Playwright and the extension host test. Add `pnpm verify` as an alias of `pnpm test:all --fast`. Explain in the runbook what each layer means (lint = style and obvious bugs; typecheck = type errors; unit = small logic tests; integration = real database/queue; e2e = real browser; evals = quality measurements for scanners and retrieval), where logs go, and what to do on failure. Remind the owner that the project is REST, not GraphQL, and uses Vitest rather than Jest (ADR-043).

---

## 10. `PLAN.md` seed (create exactly this structure, then refine as you learn)

```markdown
# PLAN.md
Legend: [ ] todo · [~] in progress · [x] done+verified · [!] blocked.  Branch per slice; PR merged by owner before the next slice starts.
Rule: update this file and BRAIN.md in every branch before opening its PR.

## Phase P0: Repository foundation
### B1 docs/p0-layout-and-adrs   (PR title: docs(repo): verify layout and ADRs, add plan, brain and agent session files)
- [ ] P0-01 Verify repo preconditions; create PLAN.md and BRAIN.md
- [ ] P0-02 Verify the folder rename already applied (client/server/extension/common); fix leftovers; check mapping in docs/02 §5
- [ ] P0-03 Verify ADR-039..049 in docs/12 agree with docs/00, 02, 10 §22, 11 and README; fix drift
- [ ] P0-04 Trim AGENTS.md (<~9,000 chars), add Session protocol, add .agents/rules + workflow after verifying current Antigravity docs
- [ ] P0-05 Create docs/runbooks stubs; scripts/docs-links.mjs; run link check
  Gate: link check = 0 broken; AGENTS.md under limit
### B2 feature/p0-tooling   (feat(repo): add workspace tooling, hooks and test-all runner)
- [ ] P0-06 Root package.json, pnpm-workspace.yaml (supply-chain settings), node/python pins, tsconfig.base, eslint, prettier, editorconfig, gitattributes, gitignore
- [ ] P0-07 .env.example files, LICENSE placeholder, SECURITY.md, CONTRIBUTING.md, CHANGELOG.md
- [ ] P0-08 common/ package skeleton + schema validators + tests
- [ ] P0-09 Husky, lint-staged, commitlint, pre-push guard
- [ ] P0-10 scripts/sync-brand.mjs, scripts/test-all.mjs, runbooks/testing.md
- [ ] P0-11 docs/runbooks/dependency-versions.md with verified versions
  Gate: fresh clone -> pnpm install --frozen-lockfile -> pnpm test:all --fast passes
### B3 feature/p0-ci-github   (ci(repo): add CI with ci-gate, PR title check, Dependabot, templates)
- [ ] P0-12 ci.yml with jobs + ci-gate (all jobs always run)
- [ ] P0-13 pr-title.yml; dependabot.yml; PR/issue templates; CODEOWNERS; codeql.yml; main-guard.yml
- [ ] P0-14 release-extension.yml (inert until secrets) + runbooks/release-extension.md
- [ ] P0-15 actionlint clean; first PR run green
  Gate: CI green on the PR; owner enables ruleset requiring ci-gate (docs/SETUP-GUIDE.md §4.4)

## Phase S1: Home page  (screenshot-first)
### B4 feature/s1-foundation   (feat(client): scaffold Next.js app, tokens, fonts, brand sync, data sources)
- [ ] S1-01 Next.js app in client/ (TS strict, Tailwind, ESLint, Vitest, Playwright)
- [ ] S1-02 tokens.css + Tailwind mapping + no-hex lint; fonts via next/font
- [ ] S1-03 brand sync (logos, favicons, manifest, OG); metadata; robots/sitemap
- [ ] S1-04 common/data/*.json + schemas + integrity tests (rule-catalog, release-status, privacy-ledger, capabilities, walkthrough)
- [ ] S1-05 layout: gutter rail, header, footer, skip link, /early-access, not-found
### B5 feature/s1-hero   (feat(client): add hero Trace with scripted sequence)
- [ ] S1-06 Trace component (real text, SVG shapes, tones), margin note, ripple tags, replay
- [ ] S1-07 hero sequence (WAAPI/CSS), reduced-motion final frame, no-JS final frame
- [ ] S1-08 pointer-lit border + subtle parallax (fine pointers only)
### B6 feature/s1-sections   (feat(client): add homepage sections 02-08)
- [ ] S1-09 02 One change / five consequences
- [ ] S1-10 03 Project Brain strata (interactive, keyboard)
- [ ] S1-11 04 Capability index table with release labels
- [ ] S1-12 05 Walkthrough (sticky timeline, 14 steps)
- [ ] S1-13 06 Local first diptych + 07 Privacy ledger (mode toggle)
- [ ] S1-14 08 CTA + footer + Preferences control
### B7 feature/s1-cursor-motion   (feat(client): add custom cursor and motion system)
- [ ] S1-15 lib/motion (tokens, hooks, reveal) applied across sections
- [ ] S1-16 DevMindCursor (states, magnetic, caret, hotspot labels, toggle, tests)
- [ ] S1-17 View Transitions enhancement for / -> /early-access
### B8 feature/s1-quality   (test(client): add e2e, a11y, performance checks and screenshots)
- [ ] S1-18 Vitest + Playwright + axe suites; Lighthouse/CWV numbers recorded
- [ ] S1-19 pnpm screenshots -> docs/assets/screenshots/home-*.png
- [ ] S1-20 design review checklist (docs/08 §18) in PR; fix findings
  Gate: build + test:all --fast + e2e green; owner screenshots and merges

## Phase S2: Extension UI shell (fixture data)
### B9 feature/s2-extension-scaffold   (feat(extension): scaffold extension, fixtures and activation)
- [ ] S2-01 evals/scanner fixtures (express-admin, fastapi-admin) with expected.json
- [ ] S2-02 extension scaffold, esbuild, vsce, launch/tasks config, media sync
- [ ] S2-03 FindingsSource + FixtureFindingsSource; Output channel; settings
### B10 feature/s2-views   (feat(extension): add Findings, Structure, Scan, Sync, Database views)
- [ ] S2-04 Findings tree  [ ] S2-05 Project structure tree  [ ] S2-06 Scan view (simulated)
- [ ] S2-07 Sync view  [ ] S2-08 Database (from files) view  [ ] S2-09 welcome content
### B11 feature/s2-diagnostics-consent   (feat(extension): add diagnostics, status bar and consent preview)
- [ ] S2-10 Diagnostics + hover  [ ] S2-11 Status bar  [ ] S2-12 Consent preview webview (CSP, tokens, Cancel focus)
### B12 feature/s2-quality   (test(extension): add unit, host and package tests and screenshot guide)
- [ ] S2-13 Vitest + extension-host test + vsce package/ls; CI artifact
- [ ] S2-14 runbooks/screenshots.md; verify F5 flow end to end
  Gate: package builds; host test passes; owner screenshots and merges

## Phase R1: GitHub showcase README
### B13 docs/r1-readme-showcase   (docs(repo): add showcase README with diagrams and screenshots)
- [ ] R1-01 Root README per section 12 of the prompt (logo, badges, screenshots, Mermaid diagrams, honest status table)
- [ ] R1-02 Reconcile docs/SETUP-GUIDE.md commands and env table with verified reality (date-stamped)
- [ ] R1-03 Upgrade docs/showcase/README.personal.md with real screenshots (raw URLs to the public repo) and honest status; owner copies it to the personal repo by hand
- [ ] R1-04 Add a short WarishLabs profile blurb (docs/showcase/PROFILE-BLURB.md, under 300 characters plus a longer paragraph) for the owner's profile README
  Gate: all README links resolve; Mermaid renders (validate); every claim matches PLAN status

## Phase M: Product milestones (docs/11), folders renamed per ADR-039
### M1 server foundation
- [ ] M1-01 server/ skeleton, settings, logging+redaction, error mapping, /healthz /readyz   (feature/m1-server-skeleton)
- [ ] M1-02 Dockerfile (multi-stage, non-root), infra/docker-compose.yml (pgvector, Valkey/Redis, api, worker, scheduler)   (feature/m1-docker-compose)
- [ ] M1-03 Server CI jobs added to ci-gate; import-linter; pytest layout; Dependabot pip/docker   (feature/m1-server-ci)
- [ ] M1-04 render.yaml Blueprint for the FREE profile (one free web service + free Key Value; config only), docs/runbooks/deploy-render-vercel.md, validate with schema/CLI   (feature/m1-deploy-config)
- [ ] M1-06 launcher: DEVMIND_RUN_MODE=api|worker|scheduler|all (uvicorn + embedded Celery worker/beat, --pool=solo, signal handling, exit if a child dies); migrations at start under advisory lock; startup sweep; optional DEVMIND_REDIS_KEY_PREFIX (Celery global_keyprefix) so a shared free Redis can be used   (feature/m1-free-profile)
- [ ] M1-07 free-profile quotas file (server/configs/quotas.free.yaml) from measured bytes per chunk; memory measurement of the combined container recorded in BRAIN.md
- [ ] M1-05 test-all server steps; SETUP-GUIDE commands verified
### M2 auth, workspaces, projects (feature/m2-*)  [ ] M2-01..M2-10 per docs/11 M2
### M3 extension real local scanning (feature/m3-*)  [ ] replace FixtureFindingsSource with LocalScanFindingsSource; sign-in flow
### M4 Brain ingestion metadata (feature/m4-*)
### M5 indexed mode, consent, embeddings, hybrid retrieval, baselines (feature/m5-*)
### M6 LLM gateway and config (feature/m6-*)
### M7 LangGraph, CodeMate, AuthCheck (feature/m7-*)
### M8 website app: design system, conversation, findings, Brain explorer, jobs (feature/m8-*)
### M9 sync modes, privacy controls, history, deletion (feature/m9-*)
### M10 hardening, observability, capacity, staging (feature/m10-*)
### M13 polish and MVP release readiness (feature/m13-*)
### M11 GitHub, PR and Review (release 1.1)   ### M12 Bug Memory, Docs, Mentor, Evaluation, Deployment Diagnosis (1.2 to 1.4)
Expand each M-item into task lines (from docs/11) when its phase starts; keep branch-per-slice.
```

## 11. Summary format (end every working turn with exactly this)

```
STATUS: <branch> @ <short-hash> · PR: <none|open #n|merged> · CI: <not run|green|red|pending>
DONE: <task ids and one line each>
EVIDENCE: <real commands run and the result lines>
DEVIATIONS / RISKS: <or "none">
WAITING ON OWNER: <HUMAN-STEPs or "nothing">
NEXT: <exact next task id>  (type "continue")
```

---

## 12. The showcase `README.md` (task R1)

After S1 and S2 are merged and their screenshots exist in `docs/assets/screenshots/`, rewrite the root `README.md` as a **professional, detailed, visual** GitHub landing page. It must be long and complete, honest about status, and render correctly on GitHub. Use only relative links and assets already in the repo.

**Required structure (in this order):**

1. **Header block** (centered HTML): logo with light/dark switching,
   ```html
   <p align="center"><picture>
     <source media="(prefers-color-scheme: dark)" srcset="brand/svg/devmind-lockup-horizontal-for-dark.svg">
     <source media="(prefers-color-scheme: light)" srcset="brand/svg/devmind-lockup-horizontal-for-light.svg">
     <img alt="DevMind" src="brand/svg/devmind-lockup-horizontal-for-dark.svg" width="420"></picture></p>
   ```
   then the tagline (*An agentic AI software engineering system with a shared Project Brain.*), a badge row (static shields for status `specification → building`, TypeScript, Next.js, FastAPI, Python, LangGraph, PostgreSQL, VS Code; the CI workflow badge; license `unlicensed`), and a link row (Overview · Screenshots · Architecture · Getting started · Roadmap · Docs).
2. **Screenshots**: hero image (`home-hero-desktop.png`), a two-column table of other home and extension shots with captions. State clearly: *"Screenshots show the interface with example/fixture data. See the status table for what is implemented."*
3. **What is DevMind** and **the problem** (short, vivid, uses the `/admin/users` story from the vision).
4. **How it works** (Mermaid flowchart of the lifecycle: understand, build, review, secure, fix, document, deploy, evaluate, improve, around the Project Brain).
5. **The nine capabilities** table: capability, question it answers, release (from `common/data/release-status.json`), status.
6. **The Project Brain** (Mermaid layered diagram of the ten concepts; explanation of local manifest vs cloud model vs index vs embeddings vs relationships).
7. **Evidence, not eloquence**: E0 to E3 table, "possible vs proven", human approval.
8. **Architecture**: C4-style container Mermaid diagram, a sequence diagram for **scan → consent → sync → analysis → answer**, an agent workflow diagram (Agent Manager → specialists → evidence verifier → approval), a state diagram for the finding lifecycle (`docs/03` §5.1).
9. **Privacy by design**: sync modes table (`metadata_only`, `indexed`), what stays local, what is stored, what may reach an LLM provider (from `privacy-ledger.json`).
10. **Tech stack** table with the reason for each choice (link ADRs).
11. **Repository structure** (annotated tree for `client/ server/ extension/ common/ docs/ brand/ evals/ infra/ scripts/ .github/`).
12. **Getting started**: prerequisites, install, run each part, environment files, with the **verified** commands from `docs/SETUP-GUIDE.md`.
13. **Testing**: `pnpm test:all` and its flags, what is covered, link to `docs/runbooks/testing.md`.
14. **Branching, CI and releases**: feature/fix branches, Conventional Commits, `ci-gate`, squash merges, Vercel and Render auto-deploy on the **free profile** (state plainly: one free Render service that sleeps when idle, so the first request can take about a minute), extension release flow (small Mermaid `gitGraph` or flowchart).
15. **Roadmap**: phase table synced with `PLAN.md` (P0, S1, S2, R1, M1 to M13) with real status; collapsible `<details>` for milestone detail.
16. **Documentation index** (all docs, one line each) and **Brand** (link to `brand/BRAND-GUIDE.md`).
17. **Security** (link `SECURITY.md`; honest limits; no promises of absolute security), **License** (placeholder statement), **Credits** (IBM Plex Sans, JetBrains Mono, Instrument Serif under the SIL OFL; tools), and a short **"Maintained by WarishLabs"** note linking `https://warishlabs.in` and the personal showcase repository.

**Rules:** every claim matches `PLAN.md` and reality; no fake metrics, no "production-ready", no "AI-powered" fluff; Mermaid must use syntax GitHub supports (validate with a pinned `@mermaid-js/mermaid-cli` or by rendering a preview); images have alt text; keep each Mermaid diagram readable (at most about 15 nodes); long sections inside `<details>`; no huge images (compress); headings give a navigable outline. The README status table is **updated in every PR that changes status**.

---

## 13. Deployment preparation (free profile; configuration only, do not deploy)

The owner deploys later following `docs/SETUP-GUIDE.md`. You prepare, validate and document the configuration so nothing is ambiguous. **Everything must run on free tiers (ADR-046).** Read `docs/10` §22 first.

- **`render.yaml`** (root Blueprint, milestone M1) for the **free profile**: one service `devmind-api` (type `web`, `runtime: docker`, `plan: free`, `dockerfilePath: ./server/Dockerfile`, `dockerContext: ./server`, `healthCheckPath: /healthz`, `autoDeployTrigger: checksPass` [verify it is accepted on free web services], `DEVMIND_RUN_MODE=all`) and one Key Value service `devmind-redis` (`plan: free`, `maxmemoryPolicy` set to the closest available no-eviction option [verify], empty `ipAllowList` so it is internal only). **Do not** define separate worker or scheduler services (no free plan) and do not use `preDeployCommand` (not relied on for free instances). Keep the target three-service definition as a **commented block** with a note that it needs paid plans. Secrets are `sync: false`; the Key Value connection string is wired with `fromService`. Validate against Render's published schema or CLI validation and wire the check into CI (`docs` job).
- **Launcher and startup:** `server/app/launcher.py` starts uvicorn and the embedded Celery worker with beat in `all` mode, forwards signals, logs with a process prefix, and exits non-zero if either child dies so Render restarts the service. `api`, `worker` and `scheduler` modes stay supported for local development and a future funded profile. Migrations run at start under a PostgreSQL advisory lock before serving traffic. At start, run the stale-job reaper and enqueuer sweep.
- **Sleep tolerance:** implement and test the behaviors in `docs/10` §22 (client and extension "server waking" states, DB first-connection retry, SSE reconnect with polling fallback, no reliance on always-on processes).
- **Memory and storage budgets:** measure resident memory of the combined container (`docker stats` under a representative load) and record it; derive `server/configs/quotas.free.yaml` from measured bytes per chunk. Do not invent numbers.
- **Docker:** `server/Dockerfile` per `docs/10` §3 (multi-stage, non-root, digest-pinned base verified at the time). Local `infra/docker-compose.yml` runs Postgres with pgvector and Valkey or Redis (match what Render offers [verify tag]) plus the server in `all` mode or as separate services for testing, with healthchecks and named volumes; no secrets inside.
- **Vercel Hobby:** no config file is required if the settings are documented; if you add `client/vercel.json`, keep it minimal. Document: Root Directory `client`, "Include source files outside of the Root Directory" **enabled** (the client imports `common`), Node 24.x, install `pnpm install --frozen-lockfile`, build `pnpm build`, environment variables per `client/.env.example`. Hobby is for personal, non-commercial use and can deploy organization repositories only if they are public (this repo is) [VERIFY].
- **Environment variables:** every variable appears in the matching `.env.example` and in the table in `docs/SETUP-GUIDE.md` §7 and `docs/10` §11, with where to obtain it and from which milestone it is needed. Add `DEVMIND_RUN_MODE` (`api|worker|scheduler|all`). Client-exposed variables use `NEXT_PUBLIC_` only when truly public.
- **CORS, security headers, CSP** per docs/07 and docs/10 §10. Domains per ADR-049 (`devmind.warishlabs.in`, `api.devmind.warishlabs.in`) are defaults in docs only; the owner sets real values.
- **Extension release:** the workflow from P0 plus `docs/runbooks/release-extension.md` (publisher `warishlabs` unless the owner changes it, tokens, pre-release flag, Open VSX, `.vsix` sideload, listing README; the repository is public, so README images from `raw.githubusercontent.com` resolve over HTTPS).
- **Prove it:** build the Docker image locally in M1 and run the container health check; run `docker compose up` and hit `/healthz` and `/readyz`; record the output in `BRAIN.md`.

## 14. Product milestones after S2 (M1 to M13)

Execute the milestones in `docs/11` in the order in `PLAN.md`, with folder names per ADR-039. For each: read the governing docs listed in `AGENTS.md` §2, expand the milestone into task lines in `PLAN.md` before starting, work in slices (one branch, one PR), obey the quality gates G1 to G9 (`docs/09` §15), and keep the vertical-slice checkpoints VS-1 to VS-4 in view.

Additional instructions:

- **API client pipeline:** the server exports `openapi.json`; `common` generates TypeScript types and a thin fetch client (verify the current generator, for example `openapi-typescript`); `pnpm gen:api` runs it; CI fails on drift. Never hand-write types the schema defines.
- **LLM and embeddings (ADR-048):** tests and CI use the **fake provider** only. Real keys are read from `server/.env`. The default model and provider remain Open (ADR-017). The owner can only use free tiers (for example Google AI Studio's free tier; other providers' free tiers may also work through an OpenAI-compatible adapter [verify]). Free tiers have rate limits and may use submitted content to improve products, so real-provider runs use **synthetic fixtures or public code only**. Wire adapters and config first, run the benchmark harness when the owner supplies a key, and propose models from measured results. Choose an embedding dimension of at most 768 (or `halfvec`) to fit the free database cap.
- **Evaluation baselines** (scanner, retrieval, answers) are committed under `evals/results/` without any user source and summarized in `docs/09` §9.
- **Replace S1/S2 stand-ins** deliberately: M3 swaps `FixtureFindingsSource` for the real local scanner behind the same interface; M8 builds the authenticated app routes in an `(app)` route group (Clerk lives only there) while `/` stays static; M13 audits instead of building the home page.
- **HUMAN-STEPs by milestone:** M2 needs a Clerk development instance (free; keys in `server/.env` and `client/.env.local`); M5 and M6 need a free embedding and generation API key (optional until benchmarking); M10 needs optional free monitoring accounts and a second free Neon project for staging; M11 needs a GitHub OAuth app (free) and uses Resend on the owner's verified `warishlabs.in` domain; deployment needs the Render, Neon and Vercel setup in the guide. Stop, point to the exact section of `docs/SETUP-GUIDE.md`, and continue with whatever can be done with fakes.
- **Security work is not optional:** authorization matrix tests, redaction, consent enforcement, audit events, injection corpus, per the docs, in the milestone that introduces the feature.
- **Never** let a milestone bring in an unapproved datastore, provider default, or permission change.

## 15. Keeping the owner's guide and the docs true

- `docs/SETUP-GUIDE.md` is the owner's manual. After **every phase**, clone the branch into a temporary directory and run its install, dev, build, test and package commands **exactly as written**. Fix every mismatch in the guide (commands, flags, env var names, ports, versions) and stamp each verified block with `Verified by Antigravity on <date> at <commit>`.
- Keep the env var table in sync with the `.env.example` files.
- Keep the README status table, `PLAN.md`, and `docs/` status lines ("Specified" to "Implemented in <phase>") in sync. Record changes of decision in `docs/12`.
- Run `pnpm docs:links` and `pnpm brand:check` before each PR.

## 16. Start now

1. Read this file completely, then `AGENTS.md`, `docs/00`, `docs/08`, `docs/11`, `docs/12`, `brand/BRAND-GUIDE.md`, and `docs/source/DevMind_Project_Document.md`.
2. Run the preconditions (section 4.1). If anything is wrong, stop with a HUMAN-STEP.
3. Create branch `docs/p0-layout-and-adrs` from `main`, create `PLAN.md` and `BRAIN.md`, commit, and proceed through P0, then S1, S2, R1, then M1 onward. **Do not skip ahead.** One slice, one PR, wait for the owner's merge.
4. Your first message to the owner must be short and state: the plan (P0, S1, S2, R1, M-series), that tests use Vitest and Playwright and pytest (no Jest, no GraphQL, and why), that everything is free-tier only (one Render free web service with an embedded worker, free Key Value, Neon Free, Vercel Hobby), that the real repo is public in `Warish-Labs` so rulesets are free, that the personal repo is a showcase you will not touch, and the first HUMAN-STEPs you foresee.
5. After that, work. Keep commits small, keep `BRAIN.md` current, and finish each turn with the summary format in section 11.

## 17. Definition of done for every PR

- [ ] Governing docs read; deviations listed
- [ ] Tests added or updated; real output pasted in the PR body
- [ ] `pnpm test:all --fast` green locally (and `--full` when relevant)
- [ ] `pnpm docs:links` and `pnpm brand:check` green
- [ ] No paid service or paid dependency introduced (ADR-046)
- [ ] No secrets, no source content in logs, no `console.log` leftovers, no unexplained `any`, no inline hex colors
- [ ] Accessibility checked for UI changes (keyboard, focus, reduced motion, contrast)
- [ ] `PLAN.md`, `BRAIN.md`, README status table, SETUP-GUIDE commands, and docs updated
- [ ] Conventional Commit PR title; commits small; branch up to date with `main`
- [ ] CI green, then stop and ask the owner to squash-merge
