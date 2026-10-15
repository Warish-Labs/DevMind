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
| typescript | 6.0.3 | npmjs.com/package/typescript | Apache-2.0 | 2026-10-15 |
| eslint | 10.12.0 | npmjs.com/package/eslint | MIT | 2026-10-15 |
| @eslint/js | 10.0.1 | npmjs.com/package/@eslint/js | MIT | 2026-10-15 |
| typescript-eslint | 8.71.2 | npmjs.com/package/typescript-eslint | MIT | 2026-10-15 |
| prettier | 3.9.10 | npmjs.com/package/prettier | MIT | 2026-10-15 |
| husky | 9.1.7 | npmjs.com/package/husky | MIT | 2026-10-15 |
| lint-staged | 17.6.0 | npmjs.com/package/lint-staged | MIT | 2026-10-15 |
| @commitlint/cli | 21.2.3 | npmjs.com/package/@commitlint/cli | MIT | 2026-10-15 |
| @commitlint/config-conventional | 21.2.3 | npmjs.com/package/@commitlint/config-conventional | MIT | 2026-10-15 |
| vitest | 5.0.5 | npmjs.com/package/vitest | MIT | 2026-10-15 |
| zod | 4.6.7 | npmjs.com/package/zod | MIT | 2026-10-15 |
| @types/node | 26.6.5 | npmjs.com/package/@types/node | MIT | 2026-10-15 |
| actions/checkout | 11bd719 (v4.2.2) | github.com/actions/checkout | MIT | 2026-10-15 |
| actions/setup-node | 1d0ff46 (v4.2.0) | github.com/actions/setup-node | MIT | 2026-10-15 |
| pnpm/action-setup | 7088e56 (v4.1.0) | github.com/pnpm/action-setup | MIT | 2026-10-15 |
| actions/upload-artifact | 4cec3d8 (v4.6.1) | github.com/actions/upload-artifact | MIT | 2026-10-15 |
| actions/download-artifact | cc20338 (v4.1.9) | github.com/actions/download-artifact | MIT | 2026-10-15 |
| actions/dependency-review-action | 3b139cf (v4.5.0) | github.com/actions/dependency-review-action | MIT | 2026-10-15 |
| github/codeql-action | a65a038 (v3.28.10) | github.com/github/codeql-action | MIT | 2026-10-15 |
| gitleaks/gitleaks-action | f586c14 (v2.3.8) | github.com/gitleaks/gitleaks-action | MIT | 2026-10-15 |

---

## To be verified when adding (S1 / Subsequent Slices)

The following will be verified from npm/PyPI when the packages are installed during S1 (Next.js scaffold) and subsequent slices. Versions will be added here after verification.

### TypeScript / Client
- `next` — npmjs.com
- `react`, `react-dom` — must match Next.js peer requirement
- `tailwindcss` — npmjs.com
- `@playwright/test` — npmjs.com

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

### Fonts (SIL OFL — self-host)
- Instrument Serif — fonts.google.com or github.com/Instrumental/fonts
- IBM Plex Sans — github.com/IBM/plex
- JetBrains Mono — github.com/JetBrains/JetBrainsMono

All three confirmed OFL at time of brand generation (2026-10-15). Confirm again at implementation (OQ-16).
