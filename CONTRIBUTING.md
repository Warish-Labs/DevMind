# Contributing to DevMind

Thank you for your interest in contributing to DevMind!

## Workflow Guidelines

1. **Branch Naming**:
   - `feature/<name>` for new capabilities
   - `fix/<name>` for bug fixes
   - `docs/<name>` for documentation updates
   - `chore/<name>` for maintenance and dependency updates
   - Never push directly to `main`.

2. **Conventional Commits**:
   - Format: `type(scope): imperative summary`
   - Allowed types: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `ci`, `build`, `perf`, `style`, `revert`.
   - Allowed scopes: `client`, `server`, `extension`, `common`, `docs`, `brand`, `ci`, `infra`, `deps`, `repo`.
   - Example: `feat(client): implement custom cursor component`

3. **Development & Checks**:
   - Install dependencies: `pnpm install`
   - Run linter: `pnpm lint`
   - Run typecheck: `pnpm typecheck`
   - Run fast test suite: `pnpm test:all --fast`
   - Validate doc links: `pnpm docs:links`

4. **Pull Requests**:
   - Ensure all local checks and pre-push hooks pass.
   - PR title must be a valid Conventional Commit (it becomes the squash commit message).
   - Fill out the PR template with summary, tested evidence, and deviations.
   - Squash-merge into `main` once CI check `ci-gate` is green.

5. **Security & Privacy Rules**:
   - Never commit credentials, `.env` files, or customer source code.
   - All external services must adhere to the free-tier only constraint (ADR-046).
