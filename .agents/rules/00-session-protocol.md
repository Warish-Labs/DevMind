# Agent Session Protocol

This file is read by Google Antigravity at the start of every session.

## Quick recovery

If the context is new or was lost, read in this order:
1. `AGENTS.md` (rules)
2. `BRAIN.md` (current state, next action, waiting on owner)
3. `PLAN.md` (all tasks and their status)
4. `docs/ANTIGRAVITY_PROMPT.md` (if deeper context is needed)

## The `continue` routine

When the owner types `continue`, `next`, or `merged`:

1. Read `AGENTS.md`, `BRAIN.md`, `PLAN.md`.
2. Run: `git status` · `git branch --show-current` · `git log --oneline -5`
3. If a PR is merged: run the after-merge routine (ANTIGRAVITY_PROMPT.md §4.4), start the next task.
4. If a task is `[~]` in PLAN.md: resume from BRAIN.md "Next action".
5. Otherwise take the next `[ ]` task.
6. End every turn with the STATUS/DONE/EVIDENCE/DEVIATIONS/WAITING/NEXT summary format (ANTIGRAVITY_PROMPT.md §11).

## HUMAN-STEP rule

When the owner must act (merge PR, add secret, create account, click in a UI):
- Stop that thread.
- State exactly what to do (command or click path).
- Record it in BRAIN.md §3 "Waiting on owner".
- Continue with any independent work.

## One PR at a time

Do not start the next branch until the previous PR is squash-merged. Each PR must be independently reviewable.

## Free only

Never add a dependency, service, API key or plan that costs money (ADR-046). If a task seems to require one, stop and propose a free alternative.

## Public repository

The repository is public. Never commit secrets, tokens, real keys, private data, user source code, or real customer data. Rotate any accidentally committed secret immediately (tell the owner; do not try to hide it by rewriting history alone).
