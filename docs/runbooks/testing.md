# testing.md

How to run tests and what each layer means. Written for a beginner.

> **DevMind uses Vitest (not Jest) for TypeScript, Playwright for browser end-to-end, and pytest for Python (ADR-043). The API is REST with OpenAPI — there is no GraphQL.**

---

## One command for everything

```bash
pnpm test:all          # same as --fast
pnpm test:all --fast   # lint + typecheck + unit + build + docs checks (no Docker needed)
pnpm test:all --full   # everything + integration (needs Docker) + Playwright e2e + evals
pnpm test:all --only client        # restrict to one area
pnpm test:all --only server        # (server tests added in M1)
pnpm test:all --only extension
pnpm test:all --only common
pnpm test:all --only docs
pnpm test:all --changed            # only packages changed vs origin/main (pre-push hook)
pnpm test:all --ci                 # no colors, machine-readable JSON summary
pnpm test:all --bail               # stop at first failure (default: keep-going)
pnpm verify                        # alias of pnpm test:all --fast
```

Logs go to `reports/<timestamp>/` (git-ignored). A final table shows PASS/FAIL/SKIP with durations.

---

## What each layer means

| Layer | Tool | What it checks |
|---|---|---|
| **Lint** | ESLint, ruff | Style, obvious bugs, no hard-coded hex colors, import order |
| **Typecheck** | tsc --noEmit, pyright | Type errors without producing output |
| **Unit** | Vitest, pytest | Small logic tests with no I/O or network |
| **Build** | Next.js build, esbuild, tsc | That the packages compile to runnable output |
| **Docs** | scripts/docs-links.mjs, brand:check | No broken links, brand assets in sync |
| **Integration** | pytest -m integration | Real database (pgvector) and Redis via Docker service containers |
| **E2E** | Playwright | Real browser against the Next.js dev server |
| **Evals** | custom harness | Quality measurements for scanner, retrieval, and LLM answers |

Steps for areas that do not exist yet show as `SKIP (not created yet)`, not as silent passes.

---

## Running specific tests

```bash
# TypeScript / client
pnpm --filter client test          # Vitest
pnpm --filter client test:e2e      # Playwright

# Extension
pnpm --filter extension test       # Vitest (pure logic)
pnpm --filter extension test:host  # Extension host integration test

# Common
pnpm --filter common test          # Vitest

# Python / server (after M1)
uv run pytest                      # all Python tests
uv run pytest -m "not integration" # unit only (no Docker)
uv run pytest -m integration       # integration (needs Docker)
uv run ruff check .                # lint
uv run ruff format --check .       # format check
uv run pyright                     # type check
```

---

## What to do when a test fails

1. Read the failure output — it usually says exactly what failed and where.
2. If it is a lint error: fix the style issue.
3. If it is a type error: fix the type annotation or the code.
4. If it is a unit test: fix the logic or update the test if the behavior intentionally changed.
5. If it is a Playwright test: check if the page structure changed; run with `--headed` to watch.
6. If it is an integration test: check if Docker is running (`docker compose -f infra/docker-compose.yml up -d`).
7. Record the fix in BRAIN.md §7 "Gotchas and fixes" so it is not forgotten.

---

## CI

Every PR runs all jobs. The single required status check is **`ci-gate`** — it fails if any job fails or is cancelled. Do not add path filters; they cause required checks to stay "pending" forever.

Server jobs (added in M1): `ruff`, `ruff format --check`, `pyright`, `lint-imports`, `pytest -m "not integration"`, and with `--full` `pytest -m integration` and migration tests.
