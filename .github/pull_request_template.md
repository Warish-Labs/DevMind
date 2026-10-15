## Summary

<!-- Briefly explain the rationale, design decisions, and context for this change. -->

## Scope & Area

- [ ] Client (`client/`)
- [ ] Server (`server/`)
- [ ] Extension (`extension/`)
- [ ] Common (`common/`)
- [ ] Documentation / Brand (`docs/`, `brand/`)
- [ ] Tooling / CI (`.github/`, `scripts/`)

## Acceptance & Verification

- [ ] `pnpm verify` (fast checks) passes
- [ ] Unit / Integration / E2E tests added or updated
- [ ] `pnpm brand:check` clean (no asset or token drift)
- [ ] Documentation updated in `docs/` and `PLAN.md` / `BRAIN.md`

## Security Checklist

- [ ] No secrets, real credentials, or production tokens included (ADR-047)
- [ ] Free-tier limits respected (ADR-046)
- [ ] Untrusted repository content treated as untrusted input (docs/07 §15)
