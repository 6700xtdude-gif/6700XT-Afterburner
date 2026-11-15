# Memory Framework

The standard for running AI agents bare metal on this machine. Written from the
2026-11-15 audit, not from theory. Every failure named here happened on this rig.

---

## 1. Where it went wrong

Five mistakes, in order of how much damage each one could have done.

### 1.1 Chat history was treated as memory

Four harnesses each kept a private store on this disk:

| Harness | Store | Survives reimage |
|---|---|---|
| OpenCode | `~/.local/share/opencode/opencode.db` | no |
| Pi | `~/.pi/agent/sessions/` | no |
| Antigravity | `~/.gemini/antigravity/brain/` | no |
| Git | `Strata/MEMORY/` | yes |

The first three are caches with a chat UI. They look like memory because they replay
conversations, but they are tied to one install. Three real project artifacts —
an execution plan, a bottleneck report, a storyboard — existed *only* inside Antigravity's
brain folders. A reimage would have erased them silently.

**Rule:** a store you cannot `git clone` is a cache. Caches may be deleted at any time.

### 1.2 One agent could write outside its workspace

Antigravity was configured with `permissionPreset: TURBO`, `autoExecutionPolicy: EAGER`,
and `nonWorkspaceFileAccessPolicy: ALLOW`, with the terminal sandbox off. That is an agent
that can rewrite any file under `C:\Users\6700XT` without asking.

That is the likely source of the "all my projects are messed up" feeling. Note the
distinction: **workspace-scoped write is productivity; profile-scoped write is a blast
radius.** Multiple agents is fine. Multiple agents with unscoped write is not.

### 1.3 Unique work lived in a gitignored tree

`tools/llama.cpp/` is excluded by `.gitignore`. A +3 line patch to
`conversion/base.py` — registering the pruned model's hash — lived there. `git status`
never showed it. One `git clean -xfd` and it was gone.

**Rule:** vendored trees hold no unique work. Export a patch or it does not exist.

### 1.4 Credentials lived in plaintext files

A GitHub classic PAT with `delete_repo` sat in `Not_A_Token.txt`. An OpenRouter key sat in
an MCP config. Both were live. Neither was the credential the tools actually used.

**Rule:** credentials go in Windows Credential Manager or the environment. Never a file in
`Documents`, because `Documents` is what gets backed up and synced.

### 1.5 A second harness was installed before the first had a backup

The repo was never backed up independently. There was no bundle, no copy of `opencode.db`,
no export of any harness store. The only copy of the project's history was one `.git`
directory on the drive that was about to be wiped.

**Rule:** backup is a script you can run, not a habit you intend to have.

---

## 2. What you got right

GitHub was never the problem. It did exactly what a centralized repo is for: it held the
one copy of truth that survived. Multiple agents pushing to one repo is correct and
desirable.

The gap was that **code was centralized and process state was not.** GitHub cannot store
what you never commit. The fix is not fewer agents — it is one committed ledger that all
of them read and write through.

---

## 3. The bare-metal standard

Nine rules. They apply to any agent on any project on this machine.

1. **One repo per project. One ledger inside it.** `MEMORY/` is the schema; git is the database.
2. **Agents get workspace-scoped write.** Anything outside the workspace is read-only unless you say otherwise, per file.
3. **Vendored code holds no unique work.** Patches in `patches/`, always.
4. **Credentials in the OS store or env.** Never a file under `Documents`.
5. **Every claim has an artifact.** A throughput number without a JSON file is a rumour. The builder enforces this.
6. **Every fixed bug gets a test.** A lesson without a test regresses.
7. **Backup is executable.** `scripts/backup_memory.ps1`, verified, run before any OS or hardware change.
8. **One writer, many readers.** When several harnesses are installed, designate one as the session that commits. Others read the ledger and report back.
9. **Reimage is a rehearsal, not an event.** The conformance gate runs before and after; if it is green both times, the wipe is boring.

---

## 4. Memory layers and authority

Not all memory is equal. When two sources disagree, the higher row wins.

| Layer | Location | Authority | Who writes |
|---|---|---|---|
| Measurements | `MEMORY/*.json`, `bench/reports/*.json` | **Highest.** Raw output. | benchmark scripts |
| Guarantees | `tests/` | High. Executable truth. | you, when fixing a bug |
| Curated state | `MEMORY/DIGEST.md` | High, but derived. | a human or the committing agent |
| History | `MEMORY/EXPERIMENT_LOG.md` | Append-only. Never edited. | any session |
| Rules | `AGENTS.md` (machine → documents → project) | Binding on behaviour. | you |
| Rig facts | `NOTEBOOK/` | High for this machine specifically. | a verified session |
| Design docs | `docs/` | Medium. May be stale. | any session |
| Chat stores | `opencode.db`, `.pi/`, `.gemini/` | **Lowest.** Evidence, not truth. | the harness |

**The digest is derived, not authoritative.** If `DIGEST.md` says 22.61 t/s and
`bench/reports/benchmark_20261114_165514.json` says 22.43, the JSON wins and the digest
gets corrected.

---

## 5. How memory builds itself

Four mechanisms, in order of how much manual effort they remove.

### 5.1 The builder (`scripts/memory_build.py`)

Regenerates two files from what already exists:

- `MEMORY/INDEX.json` — every artifact with kind, age, sha256, title, summary
- `MEMORY/HEALTH.md` — the four rot modes

It never invents a fact and never rewrites the ledger. It reports; you decide.

The four rot modes it detects:

| Mode | Meaning | Why it matters |
|---|---|---|
| **Orphans** | prose no entry point links to | an agent will never read it, so it is dead weight |
| **Stale** | docs untouched past a threshold | the digest is lying about what is current |
| **Unsourced** | numbers in the digest with no JSON behind them | an unverifiable claim is a rumour |
| **Archive candidates** | negative results still in context | you keep re-litigating a dead end |

Run it at the end of any session that added or changed files.

### 5.2 The session ritual (`scripts/session_start.ps1`, `scripts/session_end.ps1`)

Start prints the context packet: digest head, open gaps, health summary, gate status.
End runs the gate, rebuilds the index, and commits — refusing to commit on a red gate.

### 5.3 The conformance gate (`scripts/verify_memory_system.ps1`)

Twelve checks over the things that must be true for the system to be intact. Exit 1 on
any failure. This is what makes "is my memory okay?" a question with an answer.

### 5.4 The contract tests (`tests/test_memory_contract.py`)

Fourteen hermetic assertions. They fail if someone deletes an AGENTS.md scope, leaves a
secret in the tree, or removes the exported patch. Cheap, fast, no GPU.

---

## 6. What is safe to carry over

The triage standard. Apply it to every file before a reimage.

| Verdict | What | Why |
|---|---|---|
| **Carry** | source code, `tests/`, `docs/`, `patches/`, `MEMORY/*.json`, `MEMORY/*.md`, `NOTEBOOK/`, all `AGENTS.md` | small, verified, and the only thing that is actually yours |
| **Carry as bytes** | `Models/` (135.4 GB) | not in git and not re-derivable if you pruned or quantized it yourself |
| **Carry as evidence, do not load** | `opencode.db`, `.pi/agent/sessions/`, `.gemini/antigravity/brain/` | may contain a stranded idea; archive it, do not put it in context |
| **Do not carry** | `bin/`, build output, `__pycache__/`, `*.log`, caches | regenerable, and they mislead agents into thinking a build is current |
| **Never carry** | credentials, tokens, `service.json`, anything with `ghp_` or `sk-or-v1-` | rotate at the provider instead |

The test for "carry": *if this file vanished and I had to recreate it, would I lose
something I cannot regenerate in ten minutes?* If no, do not carry it.

---

## 7. Forgetting the bad

You asked to start with the good times and forget the bad. Do not delete the bad —
quarantine it. Deleted failures get re-run; quarantined failures get cited.

The rule:

1. A dead end moves from `docs/` to `MEMORY/ARCHIVE/<topic>.md`.
2. It gets a header line: what was tried, what happened, why it stopped.
3. It is **excluded from the digest and from the reading order**, so no agent loads it
   into context by default.
4. It is still in git, so the YouTube chronicles and future-you can find it.

`MEMORY/ARCHIVE/` is the difference between "forgot" and "decided not to revisit".

The builder flags candidates automatically: any doc whose title or summary reads as a
negative result, superseded, deprecated, or abandoned shows up in `HEALTH.md` under
Archive candidates.

---

## 8. The loop, in one line

```
work → EXPERIMENT_LOG → LESSONS → (test | benchmark JSON) → DIGEST → INDEX/HEALTH → next session
```

If a link in that chain is missing, the memory is a story rather than a fact.
