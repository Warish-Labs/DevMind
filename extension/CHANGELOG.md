# Changelog — DevMind Companion for VS Code

All notable changes to the DevMind Companion extension (`WarishLabs.devmind-vscode`) are documented in this file.
The project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) and VS Code Extension Marketplace publishing standards.

---

## [0.1.2] — 2026-10-25

### Added

- **Marketplace Release Readiness**: Added complete marketplace manifests (`homepage`, `bugs`, `qna`, `keywords`, and gallery categorization) per `docs/06` §18.
- **Pre-Release Packaging**: Added `package:pre-release` script targeting the VS Code Marketplace and Open VSX pre-release distribution channels (`vsce package --pre-release`).
- **Interactive Consent Preview Webview**: CSP-isolated preview panel displaying files, ranges, byte counts, and redacted sensitive parameters with default focus on **Cancel**.
- **Static Schema Extraction**: Added Database from Files view (`devmind.views.database`) inspecting Prisma, SQLAlchemy, and migration schemas without live database connections (ADR-034).

### Changed

- Standardized licensing metadata across `package.json`, `README.md`, and `LICENSE` to MIT.
- Hardened secret redaction matching ADR-047 (`[REDACTED:type:hash8]`).

---

## [0.1.1] — 2026-10-22

### Added

- **Local AST Scan Rule Engine**: Initial deterministic detectors for missing authentication guards (`SEC-AUTH-001`) and exposed secrets (`SEC-KEY-002`).
- **Offline Fixture Mode**: Added `devmind.fixtureMode` setting for air-gapped evaluation and unit test execution without backend connectivity.
- **VS Code Diagnostics Synchronization**: Real-time diagnostic underlines linked to SARIF rules with `E1 · Possible` tags for heuristic matches.

---

## [0.1.0] — 2026-10-18

### Added

- **Initial Preview Release**:
  - Left Activity Bar container with custom DevMind companion icon.
  - Tree views: Findings (`devmind.views.findings`), Project Structure (`devmind.views.structure`), Scan Status (`devmind.views.scan`), and Sync Ledger (`devmind.views.sync`).
  - Strict privacy defaults: `metadata_only` synchronization active by default (ADR-022).
  - Token isolation: stored exclusively in VS Code `SecretStorage`.

---

## Known Limitations Ledger (v0.1.x)

1. **Language Tier Support**:
   - **Tier 1 (Full AST & Symbol Analysis)**: TypeScript, JavaScript, Python.
   - **Tier 2 (Structural & Secret Hashing Only)**: Go, Java, Rust, SQL, YAML, Markdown. AST symbols and dependency call-graphs are not extracted for Tier 2 files in v0.1.
2. **Zero Live Database Connections (ADR-034)**:
   - DevMind intentionally does not connect to live databases or read connection strings. Schemas are discovered statically from files only.
3. **No Extension Chat (ADR-034 / FR-EXT-11)**:
   - Deep AI code conversations live on the DevMind web application. The companion focuses strictly on local scanning, structural diagnostics, and consented synchronization.
