# DevMind Companion for VS Code

> Continuous Project Brain Companion: local structural analyzer, architectural findings navigator, and privacy-first sync controller.

---

## Overview

The DevMind Companion extension connects your local VS Code workspace with the **DevMind Project Brain**. It performs local, privacy-first structural analysis of endpoints, route guards, and authorization policies without uploading raw source code or connecting to production databases.

## Features

- **Findings View (`devmind.views.findings`)**:
  - Live inspection of authorization invariant violations and security hygiene issues.
  - Grouped by severity (`critical`, `high`, `medium`, `low`, `info`).
  - Evidence levels clearly labeled (`E1 · Possible` vs verified facts).
  - Click any finding to navigate directly to the source file line.

- **Project Structure View (`devmind.views.structure`)**:
  - Architectural breakdown of modules, routes, and API endpoints.
  - Role-guard indicators (`$(shield)` protected vs `$(alert)` missing role guard).

- **Scan Status View (`devmind.views.scan`)**:
  - Real-time scanner state, rule engine version (`v1.0.0`), and analyzed file metrics.
  - Transparent audit of skipped/protected paths (`.env`, lockfiles, build artifacts).

- **Sync & Privacy View (`devmind.views.sync`)**:
  - Displays synchronization mode (`metadata_only` by default).
  - Explicit audit ledger showing what leaves the machine and what stays local.

- **Database from Files View (`devmind.views.database`)**:
  - Statically extracted schema models from Prisma, SQLAlchemy, and migration files.
  - **Zero live database connections** strictly enforced (ADR-034).

- **Interactive Consent Preview (`devmind.reviewSync`)**:
  - Strict CSP-isolated webview panel providing verification before any metadata transmission.
  - Default focus on **Cancel** for maximum safety.

## Architectural Constraints & Privacy Guarantees

1. **Zero Silent Uploads (ADR-022)**: Operates in `metadata_only` mode by default. Raw code chunks never leave your workstation without explicit consent.
2. **Zero Live Database Connections (ADR-034)**: Never reads database connection strings or connects to live databases.
3. **Automated Secret Redaction (ADR-047)**: Credentials in code are masked as `[REDACTED:secret:hash8]` prior to hashing.
4. **Offline & Fixture First**: In `fixtureMode` (default for evaluation), all analysis and sync receipts are simulated locally with zero network calls.

## Extension Commands

| Command                 | Title                                 |
| ----------------------- | ------------------------------------- |
| `devmind.scanWorkspace` | Run local workspace scan              |
| `devmind.cancelScan`    | Cancel active workspace scan          |
| `devmind.openFindings`  | Focus Findings view                   |
| `devmind.showLogs`      | Show DevMind Output Channel           |
| `devmind.syncNow`       | Trigger Project Brain synchronization |
| `devmind.reviewSync`    | Open Consent Preview Webview          |
| `devmind.refreshAll`    | Refresh all DevMind companion views   |

## License

Apache-2.0
