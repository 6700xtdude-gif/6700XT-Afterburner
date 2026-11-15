# Archive

Dead ends, superseded approaches, and negative results. Kept for evidence, excluded from
default context.

## Why this exists

Deleting a failure means it gets re-run six months later. Keeping it in `docs/` means every
new session loads it and wastes context re-litigating it. The archive is the third option:
out of the way, still findable.

## The rule

Move a doc here when it is one of these:

- a **negative result** — tried it, measured it, it did not work
- **superseded** — a newer approach replaced it
- **abandoned** — stopped for a reason that is still valid

Do not move anything here while it is still the current answer to a live question.

## The move

1. `git mv docs/<topic>.md MEMORY/ARCHIVE/<topic>.md`
2. Add or correct a header block:

```markdown
> **Archived 2026-11-15.** Tried <approach>. Result: <what actually happened>.
> Stopped because <reason>. Do not re-run unless <condition changes>.
> Evidence: <path to JSON or commit>.
```

3. Remove it from `MEMORY/DIGEST.md` and the reading order.
4. Run `python scripts/memory_build.py` and confirm it no longer appears under
   Archive candidates.

## What stays out

- `MEMORY/PROTOCOL.md`, `MEMORY/FRAMEWORK.md`, `MEMORY/DIGEST.md` — the contract and current state, never archived
- `NOTEBOOK/SYSTEM_BASELINE.md` — verified facts about the rig, never archived
- benchmark JSON — raw evidence, stays in `MEMORY/` or `bench/reports/` regardless of outcome

## What is already known to belong here

Nothing yet. The 2026-11-15 audit found no archived candidates: every doc in `docs/` is
still the current answer to a live question. The loop-96MB surgery work is a negative
result in spirit and is already recorded as one in `MEMORY/EXPERIMENT_LOG.md`; move it
here if a future session starts treating it as a live plan.
