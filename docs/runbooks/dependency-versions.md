# dependency-versions.md

All pinned dependencies with verified source, version, license, and date.
Updated in every branch that adds or changes a dependency (AGENTS.md §11, ANTIGRAVITY_PROMPT.md §5).

> **Rule:** Never pin a version from memory. Verify from the official registry before adding.

---

## Runtime pinning policy

- **Node.js**: Active LTS. Currently Node 24 (`.nvmrc`, `engines.node`, CI, Vercel).
- **Python**: newest stable CPython supported by all pinned deps (check wheels for psycopg, tree-sitter, cryptography, LangGraph).
- **pnpm**: latest stable via `packageManager` field in `package.json`.
- **Frameworks**: latest stable that is ≥7 days old (pnpm `minimumReleaseAge: 10080`).

---

## Verified versions (2026-10-15)

| Package | Version | Registry/Source | License | Date verified |
|---|---|---|---|---|
| Node.js | 24.22.0 | nodejs.org (Active LTS) | MIT | 2026-10-15 |
| pnpm | 12.11.2 | get.pnpm.io | MIT | 2026-10-15 |
| uv | 0.12.17 | installed on machine | Apache-2.0 | 2026-10-15 |
| corepack | 0.36.0 | bundled with Node 24 | MIT | 2026-10-15 |

---

## To be verified when adding (P0-B2 / S1)

The following will be verified from npm/PyPI when the packages are installed during B2 (tooling) and S1 (Next.js scaffold). Versions will be added here after verification.

### TypeScript / Client
- `typescript` — npmjs.com
- `next` — npmjs.com
- `react`, `react-dom` — must match Next.js peer requirement
- `tailwindcss` — npmjs.com
- `eslint` — npmjs.com
- `vitest` — npmjs.com
- `@playwright/test` — npmjs.com
- `tsup` — npmjs.com (for common/ build)
- `zod` — npmjs.com

### Extension
- `@vscode/vsce` — npmjs.com
- `@types/vscode` — npmjs.com (pins `engines.vscode`)
- `@vscode/test-cli` — npmjs.com
- `esbuild` — npmjs.com

### Python / Server
- `fastapi` — pypi.org
- `pydantic` — pypi.org (v2 required)
- `sqlalchemy` — pypi.org (2.x required)
- `alembic` — pypi.org
- `psycopg` — pypi.org (v3 required)
- `celery` — pypi.org
- `redis` — pypi.org
- `langgraph` — pypi.org (pin carefully; API evolves)
- `ruff` — pypi.org
- `pyright` — npmjs.com or pypi.org
- `pytest` — pypi.org
- `structlog` — pypi.org

### GitHub Actions (pin by SHA)
- `actions/checkout` — github.com/actions/checkout
- `actions/setup-node` — github.com/actions/setup-node
- `pnpm/action-setup` — github.com/pnpm/action-setup
- `actions/cache` — github.com/actions/cache
- `actions/upload-artifact` — github.com/actions/upload-artifact
- `actions/dependency-review-action` — github.com/actions/dependency-review-action
- `github/codeql-action` — github.com/github/codeql-action

### Fonts (SIL OFL — self-host)
- Instrument Serif — fonts.google.com or github.com/Instrumental/fonts
- IBM Plex Sans — github.com/IBM/plex
- JetBrains Mono — github.com/JetBrains/JetBrainsMono

All three confirmed OFL at time of brand generation (2026-10-15). Confirm again at implementation (OQ-16).
