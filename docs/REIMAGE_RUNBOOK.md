# Reimage Runbook

Windows reimage + 96 GB (4-DIMM) RAM install. Written 2026-11-15, before the wipe.

**Guiding rule:** the repo is the source of truth. If it is not pushed and bundled, assume
it is gone. Model weights are the one thing not in git — decide about them explicitly.

---

## T-0: before you touch the USB stick

Run these in order. Do not skip the gate.

### 1. Conformance gate

```powershell
cd C:\Users\6700XT\Documents\Strata
.\scripts\verify_memory_system.ps1
```

**Requirement: `0 fail`.** A `WARN` on uncommitted files is fine only if you then commit them.
Do not reimage on a failing gate.

### 2. Commit and push everything

```powershell
git add -A
git commit -m "chore: pre-reimage checkpoint"
git push origin main
git status --short          # must be empty
```

### 3. Verified backup

```powershell
.\scripts\backup_memory.ps1 -Destination "D:\backups\strata"
```

Confirm the printed line says `verified: Strata.bundle`.

### 4. Record the pre-reimage baseline

```powershell
python bench\ram_topology.py --label 64gb-2dimm
```

Already captured on 2026-11-15: **64 GB / 2 DIMM / 3200 MHz rated and actual**. If the server
is running, also run a throughput pass so the 96 GB comparison has a speed baseline:

```powershell
python bench\ram_topology.py --label 64gb-2dimm-bench --bench
```

### 5. Decide about the 135 GB of models

`Strata/Models/` is 135.4 GB and is gitignored. D: has ~200 GB free, so a full copy fits with
~65 GB to spare.

| Option | Do this if |
|---|---|
| **Copy all of `Models/` to `D:\models\`** | You have the space and want zero re-download time |
| Copy only custom/pruned GGUFs, re-download stock ones | Space is tight |

```powershell
robocopy "C:\Users\6700XT\Documents\Strata\Models" "D:\models" /E /NFL /NDL /NJH /NJS /NP
```

Anything you produced yourself (pruned, distilled, healed, quantized in-repo) is **not
re-downloadable** and must be copied. Stock Hugging Face downloads can be re-fetched.

### 6. Capture the software inventory

```powershell
winget export -o "D:\backups\winget-packages.json"
Get-CimInstance Win32_VideoController | Select-Object Name, DriverVersion, DriverDate
Get-ComputerInfo | Out-File "D:\backups\systeminfo.txt"
```

Write down the AMD Adrenalin version and the tuning profile (VRAM 2112–2150 MHz, fast timings,
1125–1160 mV, +15% power limit, fan curve 65–75%). It is in `PLAN.md` §5, but confirm what is
actually loaded before you wipe.

### 7. Credentials to re-create afterwards

These were revoked on 2026-11-15 and are intentionally dead:

- GitHub classic PAT (`ghp_…`, scopes included `delete_repo`) — **revoked**, verified 401
- OpenRouter key `AntiGravity (997)` — **deleted**, verified 401

`~/.gemini/config/mcp_config.json` still contains the dead OpenRouter string. It will 401 until
you paste a new key. That is expected, not a bug.

Do **not** put either replacement in a `.txt` file. Use Windows Credential Manager for git and
an environment variable for OpenRouter.

---

## The RAM change

Target: 96 GB across 4 DIMMs, accepting a lower memory clock.

On Ryzen 5000 the Infinity Fabric and memory controller are rated for 2 DIMMs at 3200 MT/s.
Four dual-rank DIMMs typically force 2933, 2666, or 2400. This rig is bandwidth-bound on
decode, so the throughput cost is real and must be measured, not argued about.

Install order that matters:

1. **Slots A2/B2 first.** The two 32 GB sticks go in the primary pair, not the secondary.
2. Populate **A1/B1** with the second pair.
3. Enable **DOCP/XMP**, then set the resulting clock manually if the board drops it.
4. Re-check **Resizable BAR** is still on.
5. Verify in BIOS that all 96 GB is visible before booting Windows.

---

## T+0: after Windows is installed

### 1. Toolchain

```powershell
winget install --id Git.Git -e
winget install --id GitHub.cli -e
winget install --id Python.Python.3.12 -e
winget import -i "D:\backups\winget-packages.json"
gh auth login
```

### 2. Restore the repo

Preferred (GitHub is reachable):

```powershell
git clone https://github.com/6700xtdude-gif/6700XT-Afterburner.git C:\Users\6700XT\Documents\Strata
```

Offline fallback (from the bundle):

```powershell
git clone D:\backups\strata\<timestamp>\git\Strata.bundle C:\Users\6700XT\Documents\Strata
git -C C:\Users\6700XT\Documents\Strata remote set-url origin https://github.com/6700xtdude-gif/6700XT-Afterburner.git
```

### 3. Restore the out-of-repo rules files

`AGENTS.md` at machine and Documents scope are **not** in the repo. Copy them back:

```powershell
Copy-Item "D:\backups\strata\<timestamp>\state\agents-md-machine\AGENTS.md"   "C:\Users\6700XT\AGENTS.md"
Copy-Item "D:\backups\strata\<timestamp>\state\agents-md-documents\AGENTS.md" "C:\Users\6700XT\Documents\AGENTS.md"
```

(If the backup predates those files, re-create them from `MEMORY/PROTOCOL.md`.)

### 4. Restore agent state you actually want

Only if you want the old conversations back. None of it is required for the system to work.

```powershell
# OpenCode sessions
Copy-Item "D:\backups\strata\<timestamp>\sqlite\opencode.db" "C:\Users\6700XT\.local\share\opencode\opencode.db"
# Pi sessions
robocopy "D:\backups\strata\<timestamp>\state\pi-sessions" "C:\Users\6700XT\.pi\agent\sessions" /E
```

### 5. Rebuild the vendored tree

```powershell
git clone https://github.com/ggml-org/llama.cpp C:\Users\6700XT\Documents\Strata\tools\llama.cpp
git -C C:\Users\6700XT\Documents\Strata\tools\llama.cpp checkout 61dbf492
git -C C:\Users\6700XT\Documents\Strata\tools\llama.cpp apply C:\Users\6700XT\Documents\Strata\patches\0001-qwen25-coder-0.5b-pruned-hash.patch
```

### 6. Restore models

```powershell
robocopy "D:\models" "C:\Users\6700XT\Documents\Strata\Models" /E /NFL /NDL /NJH /NJS /NP
```

### 7. Re-wire OpenCode

`~/.config/opencode/opencode.json` is in the backup. It defines the `afterburner` provider on
`http://127.0.0.1:8080/v1`. Copy it back, or re-create from `MEMORY/PROTOCOL.md`.

### 8. Conformance gate, again

```powershell
cd C:\Users\6700XT\Documents\Strata
.\scripts\verify_memory_system.ps1
```

**Requirement: `0 fail`.** This is the proof the memory system came back, not a feeling.

### 9. Record the 96 GB baseline

```powershell
python bench\ram_topology.py --label 96gb-4dimm --bench
python bench\ram_topology.py --compare MEMORY\RAM_64gb-2dimm.json MEMORY\RAM_96gb-4dimm.json
```

Commit both JSON files. That comparison is the answer to "did the extra RAM cost me speed, and
how much".

---

## What is not covered here

- Antigravity reinstall and its plugin set — your call, and its config holds the dead key
- Browser profiles, email, and anything outside `Documents`
- BitLocker / Secure Boot / TPM state — capture recovery keys before wiping

---

## Rollback

If the new install is worse than the old one, the bundle restores the exact repo state at
commit `a36892f` or later, and `D:\backups` restores the agent stores. Nothing in this plan is
one-way except the wipe itself.
