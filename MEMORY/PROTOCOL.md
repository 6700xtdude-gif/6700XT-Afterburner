# Memory Protocol

The contract every agent and every session follows on this machine. Short by design —
if it does not fit on one screen, it does not get followed.

---

## The one rule

> **Chat history is a cache. Git is memory. If it is not committed, it does not exist.**

OpenCode's `opencode.db`, Pi's `sessions/`, and Antigravity's `brain/` all die with the
OS. `MEMORY/` and `NOTEBOOK/` survive because they are in the repo and the repo is on
GitHub plus a bundle.

---

## Scope hierarchy

Instructions load from the narrowest matching file outward. Do not duplicate rules across
levels — each level says only what the level below cannot know.

| Scope | File | Holds |
|---|---|---|
| Machine | `C:\Users\6700XT\AGENTS.md` | Hardware ground truth, port 8080 guard, shell, working rules, scope note for vendored trees |
| Documents | `C:\Users\6700XT\Documents\AGENTS.md` | Where project memory lives, the four harness stores, backup command |
| Project | `<project>\AGENTS.md` | That project's invariants, layout, and server rules |
| Vendored | `tools/llama.cpp/AGENTS.md` | **Upstream contributor policy. Not project policy.** |

---

## What goes where

| Kind of knowledge | Destination | Lifetime |
|---|---|---|
| Current state: what works, what phase, what the numbers are | `MEMORY/DIGEST.md` (rewrite) | permanent, always current |
| What was tried, in order, including failures | `MEMORY/EXPERIMENT_LOG.md` (append) | permanent, never edited |
| A hard-won rule that would have saved time | `MEMORY/LESSONS.md` (append) | permanent |
| An open question or untested hypothesis | `MEMORY/GAPS_AND_HYPOTHESES.md` | until resolved |
| Verified facts about this specific rig | `NOTEBOOK/SYSTEM_BASELINE.md` | permanent |
| A struggle → fix story worth publishing | `NOTEBOOK/6700XT_YOUTUBE_CHRONICLES.md` | permanent |
| Raw benchmark output | `MEMORY/BENCHMARK_*.json`, `MEMORY/RAM_*.json` | permanent |
| A patch to a vendored tree | `patches/*.patch` | permanent |
| A one-off script or throwaway analysis | nowhere. Delete it. | — |

---

## Session ritual

### Start

1. Read `<project>/AGENTS.md`.
2. Read `<project>/MEMORY/DIGEST.md`.
3. Read `<project>/MEMORY/GAPS_AND_HYPOTHESES.md` if the task is research.
4. Do not re-derive what the digest already records. If the digest is wrong, fix it.

### End

1. Update `MEMORY/DIGEST.md` — replace stale numbers, do not append a second truth.
2. Append to `MEMORY/EXPERIMENT_LOG.md` — date, what was tried, result, why it failed or worked.
3. Append to `MEMORY/LESSONS.md` only if you learned something you would otherwise repeat.
4. `git add -A && git commit` with a message that says *why*, not just *what*.
5. `git push`.

A session that ends without a commit did not happen.

---

## Self-improvement loop

The loop is not "the model gets better". It is "the repo accumulates facts the next session
cannot re-derive cheaply".

```
struggle
  -> capture the failure in EXPERIMENT_LOG.md
  -> distil the rule into LESSONS.md
  -> if it is rig-specific and verified, into NOTEBOOK/SYSTEM_BASELINE.md
  -> if it is a good story, into 6700XT_YOUTUBE_CHRONICLES.md
  -> if it is testable, into tests/ so it cannot silently regress
```

**A lesson that is not backed by a test will regress.** Every fixed bug gets a test in
`tests/` or a row in the benchmark matrix. Every benchmark claim gets a `MEMORY/*.json`.

### The three questions before ending a session

1. What did I learn that the next session would otherwise rediscover the hard way?
2. Is it written down somewhere git tracks?
3. Is there a test that fails if someone breaks it again?

---

## Multi-harness rule

You run OpenCode, Pi, and Google Antigravity against the same projects. They do not share
memory. Treat them as three clients of one database:

- **Git is the database.** `MEMORY/` is the schema.
- Any harness may read the ledger. Only a commit may write it.
- If a harness produces something valuable that lives only in its own store, copy it into
  `docs/` or `MEMORY/` and commit it in the same session.
- A harness that cannot see the ledger gets read-only work.

---

## Conformance standard

Run before any reimage, OS change, or hardware change, and again after:

```powershell
.\scripts\verify_memory_system.ps1
```

It checks the three AGENTS.md scopes, git state, bundle verification, session snapshot,
the contract tests, the RAM baseline, and plaintext credentials. Exit code 0 means the
memory system is intact.

The hermetic subset runs in CI or on any machine with Python:

```powershell
python -m unittest tests.test_memory_contract -v
```

---

## Hardware-change rule

Any change to RAM, storage, or GPU gets recorded before and after:

```powershell
python bench/ram_topology.py --label 64gb-2dimm
python bench/ram_topology.py --label 96gb-4dimm --bench
python bench/ram_topology.py --compare MEMORY/RAM_64gb-2dimm.json MEMORY/RAM_96gb-4dimm.json
```

Capacity is not free on Ryzen 5000. Four DIMMs drop the memory clock, and this rig's
entire thesis is memory-bandwidth-bound decoding. The comparison file is the evidence,
not the impression.
