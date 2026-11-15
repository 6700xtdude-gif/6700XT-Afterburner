# Clean Start

After the reimage, this is the path that restores **truth** and deliberately leaves
**state** behind. `docs/REIMAGE_RUNBOOK.md` is the full restore. This is the selective one.

The difference matters: full restore brings back every conversation, every stale config, and
every dead end. Clean start brings back the repo, the rules, and the models, and lets the
harnesses start empty.

---

## 0. The principle

| Restore | Because |
|---|---|
| **Truth** — repo, `MEMORY/`, `NOTEBOOK/`, `docs/`, `tests/`, `patches/`, `AGENTS.md` | small, verified, and the only thing that is actually yours |
| **Bytes** — `Models/` | not re-derivable if you pruned or quantized it yourself |
| **Not state** — chat databases, harness configs, caches, build output | they encode the mess you are trying to leave behind |

If you would not miss it in ten minutes, do not restore it.

---

## 1. Base install

```powershell
winget install --id Git.Git -e
winget install --id GitHub.cli -e
winget install --id Python.Python.3.12 -e
gh auth login
```

Install the GPU driver and confirm **Resizable BAR** is on. Do not install a second agent
harness yet. One writer at a time.

---

## 2. Restore the repo

```powershell
git clone https://github.com/6700xtdude-gif/6700XT-Afterburner.git C:\Users\6700XT\Documents\Strata
```

Offline fallback:

```powershell
git clone D:\backups\strata\<timestamp>\git\Strata.bundle C:\Users\6700XT\Documents\Strata
git -C C:\Users\6700XT\Documents\Strata remote set-url origin https://github.com/6700xtdude-gif/6700XT-Afterburner.git
```

The clone already contains `MEMORY/`, `NOTEBOOK/`, `docs/`, `tests/`, `patches/`, and the
project `AGENTS.md`. That is most of the memory system.

---

## 3. Restore the out-of-repo rules

These two files are not in the repo, so they need copying back:

```powershell
Copy-Item "D:\backups\strata\<timestamp>\state\agents-md-machine\AGENTS.md"   "C:\Users\6700XT\AGENTS.md"
Copy-Item "D:\backups\strata\<timestamp>\state\agents-md-documents\AGENTS.md" "C:\Users\6700XT\Documents\AGENTS.md"
```

Without them, a session started in any directory other than `Strata` runs with no machine
context at all. That was one of the original gaps.

---

## 4. Restore the models

```powershell
robocopy "D:\models" "C:\Users\6700XT\Documents\Strata\Models" /E /NFL /NDL /NJH /NJS /NP
```

Verify one file before trusting the copy:

```powershell
Get-ChildItem .\Models\*.gguf | Measure-Object Length -Sum | Select-Object Count, @{n='GB';e={[math]::Round($_.Sum/1GB,2)}}
```

---

## 5. Rebuild the vendored tree

```powershell
git clone https://github.com/ggml-org/llama.cpp .\tools\llama.cpp
git -C .\tools\llama.cpp checkout 61dbf492
git -C .\tools\llama.cpp apply .\patches\0001-qwen25-coder-0.5b-pruned-hash.patch
```

The patch is why this step exists. Without it, `convert_hf_to_gguf.py` will not recognise the
pruned 0.5B model and you will spend an evening re-diagnosing it.

---

## 6. Point OpenCode at the local server

Recreate `~/.config/opencode/opencode.json` with the `afterburner` provider on
`http://127.0.0.1:8080/v1` (the block is in the backup, or in `MEMORY/PROTOCOL.md`).
Start the server first:

```powershell
.\start_local_server.ps1 -Mode qwen27b_vram -CtxSize 65536
```

Then `/models` should list `afterburner/default`.

---

## 7. Prove the memory came back

```powershell
cd C:\Users\6700XT\Documents\Strata
.\scripts\verify_memory_system.ps1
```

**Requirement: `0 fail`.** One `WARN` for uncommitted files is acceptable; anything else is
not. If this passes, the memory system survived the wipe — that is the whole point of the
exercise.

Then run the contract tests directly:

```powershell
python -m unittest tests.test_memory_contract -v
```

---

## 8. The 96 GB comparison

```powershell
python bench\ram_topology.py --label 96gb-4dimm --bench
python bench\ram_topology.py --compare MEMORY\RAM_64gb-2dimm.json MEMORY\RAM_96gb-4dimm.json
```

Commit both JSON files. Expected shape of the result, from `MEMORY/FRAMEWORK.md` §4 and the
existing 32 GB vs 64 GB work:

- **VRAM-resident models** (27B IQ2_M, 100% on GPU): throughput should be essentially unchanged. Host RAM clock barely matters when nothing spills.
- **Hybrid offload** (35B MoE, 27B Q4): throughput should drop with the 4-DIMM clock. This is the path that pays for the extra capacity.
- **Load time** should improve, because the OS has more page cache headroom.

If the hybrid path drops more than about 8%, consider running the 96 GB kit at 2666 with
tighter timings rather than 2933 loose. Measure both if the board allows it.

---

## 9. Forget the bad

After the gate is green and the comparison is committed, do one pruning pass:

```powershell
python scripts\memory_build.py --stale-days 14
Get-Content MEMORY\HEALTH.md
```

Then act on what it reports:

- **Archive candidates** → `git mv docs\<x>.md MEMORY\ARCHIVE\` with the header block from `MEMORY/ARCHIVE/README.md`
- **Orphans** → link them from `MEMORY/DIGEST.md` or archive them
- **Unsourced numbers** → either find the artifact or delete the claim

This is the step that turns "forget the bad" from a wish into a repo state. The failures stay
in git for the YouTube chronicles; they stop loading into every future session.

---

## 10. Definition of done

- [ ] `verify_memory_system.ps1` reports `0 fail`
- [ ] `python -m unittest discover tests` is all green
- [ ] `MEMORY/RAM_96gb-4dimm.json` committed
- [ ] `git status` clean and pushed
- [ ] `MEMORY/HEALTH.md` shows no orphans and no unsourced numbers
- [ ] exactly one agent harness installed, with the others added only after a green gate

When those six are true, you have not restored the old machine. You have a smaller, verified
one that knows what it is.
