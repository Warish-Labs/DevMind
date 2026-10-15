# @devmind/common

Shared TypeScript library for DevMind (`client`, `extension`, `scripts`).

## Subpath Exports

- `@devmind/common`: Root re-export of all modules
- `@devmind/common/schemas`: Zod schema definitions (`RuleCatalogSchema`, `ReleaseStatusSchema`, `PrivacyLedgerSchema`, etc.)
- `@devmind/common/data`: Validation helpers
- `@devmind/common/tokens`: Design tokens and theme constants

## Development

```bash
# Typecheck
pnpm --filter common typecheck

# Build
pnpm --filter common build

# Test
pnpm --filter common test
```
