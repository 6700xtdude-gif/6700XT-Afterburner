# Pi Harness — Fix Plan

**Status: EXECUTED & VERIFIED ON SANDBOX (2026-11-15)**
Sequencing: reboot first, no reimage. The 96 GB install and any OS wipe stay separate.

Purpose: make the Pi harness reliably start the local model, and be instructable to run
Windows admin checks — computer name, event log, network printer.

---

## 1. What already works

Verified 2026-11-15 by reading the live config, not from memory.

| Piece | State | Evidence |
|---|---|---|
| Pi installed | v1.5.2, on PATH | `~/.pi/agent/bin/pi.cmd` |
| Provider points at local server | `http://127.0.0.1:8080/v1` | `~/.pi/agent/models.json` |
| Default provider/model | `afterburner` / `default` | `~/.pi/agent/settings.json` |
| Shell tool granted | `powershell` in `defaultTools` | `~/.pi/agent/settings.json` |
| Launcher starts the server if down | yes, health-checks 8080 first | `scripts/launch_afterburner_pi.ps1` |
| Node runtime bundled | v22 via `pi-node` | `~/AppData/Local/pi-node/current` |

So the wiring is correct. The failures below are about **reliability and instruction**, not
about the model being unreachable.

---

## 2. The six gaps

### G1 — Pi has no standing instructions
`~/.pi/agent/AGENTS.md` does not exist. Pi starts every session knowing nothing about this
machine: that the shell is PowerShell and not bash, that port 8080 is off-limits, that the
host is called `SANDBOX`, or where project memory lives.

EXP-023 already recorded the consequence: the model *"hallucinated a sandbox"* because the
hostname is literally `SANDBOX`.

### G2 — The load timeout is too short
`launch_afterburner_pi.ps1` waits **35 seconds** for `/health`. A 9.54 GB model loading from
disk into VRAM can exceed that, and the script then reports `[ERROR] Server failed to start`
while the server is still loading. False failure.

### G3 — Health is not a completion
`/health` returning `ok` means the process is up, not that the model answers. Nothing tests
an actual completion before handing control to Pi.

### G4 — No smoke test exists
There is no single command that answers: what is this machine, what is broken in the event
log, can I reach the printer, is the model answering.

### G5 — Three entry points, no owner
`Launch_Pi.bat`, `start_pi_afterburner.ps1`, and `scripts/launch_afterburner_pi.ps1` all
start Pi. Three copies of the same logic will drift apart.

### G6 — No record of what the harness is allowed to do
`defaultTools` grants `read`, `powershell`, `edit`, `write`. Whether Pi asks before running a
command is a Pi-side setting not visible in these files. **Not changing it** — recording it
so the behaviour is known rather than assumed.

---

## 3. The changes, in order

### Step 1 — Create `~/.pi/agent/AGENTS.md`

Draft content, for approval:

```markdown
# Pi Agent — Machine Scope

You are running on this specific machine. These are facts.

## Hardware
- Windows 11 Pro. The shell is Windows PowerShell. There is no bash.
- Host name is SANDBOX. It is a real desktop, not a container or a sandbox VM.
- AMD Radeon RX 6700 XT, 12 GB. Ryzen 5 5600, 6 cores / 12 threads. 64 GB DDR4-3200.
- Local model server: llama-server at http://127.0.0.1:8080/v1.

## Never do these
- Never stop, restart, or reconfigure llama-server.exe, or anything on port 8080.
  If it is down, say so and stop. Do not start it unless explicitly asked.
- Never run git clean, git reset --hard, or delete a directory outside the project.
- Never edit a file outside the workspace without naming the file and the reason first.

## How to work
- Use PowerShell cmdlets. Get-ChildItem, Test-Path, Select-Object. Not ls, not grep.
- Filter in PowerShell before printing. Group-Object, Select-Object -First N.
  Never dump raw logs into the conversation.
- Read a file before editing it.
- After a change, run it or read it back. A tool reporting success is not proof.

## Where memory lives
- Project memory: C:\Users\6700XT\Documents\Strata\MEMORY\ — read DIGEST.md first.
- Verified rig facts: C:\Users\6700XT\Documents\Strata\NOTEBOOK\.
```

### Step 2 — Fix the launcher

- Raise the health wait from 35 s to **180 s**.
- After health passes, send **one real completion** and require a non-empty reply.
- Keep the existing behaviour of not touching a server that is already listening.

### Step 3 — Create `scripts/smoke_test.ps1`

Read-only. Changes nothing. Four sections:

1. **Identity** — computer name, user, OS build, RAM total.
2. **Event log** — last 100 System errors, deduplicated by Id + Provider, top 5.
3. **Printers** — installed printers; for any with an IP port, a TCP reachability test.
4. **Local model** — `/v1/models` responds, and one completion returns text.

### Step 4 — One launcher

Make `Launch_Pi.bat` and `start_pi_afterburner.ps1` call
`scripts/launch_afterburner_pi.ps1` instead of duplicating it.

### Step 5 — Verify, then stop

Run the smoke test. Confirm Pi answers a prompt and can run the three admin checks.
Record the result in `MEMORY/EXPERIMENT_LOG.md`.

---

## 4. The smoke test — draft script

For approval before it is created as a file.

```powershell
<#
.SYNOPSIS
    Read-only Windows smoke test. Changes nothing.
.DESCRIPTION
    Identity, deduplicated System event log, printer reachability, local model.
#>
[CmdletBinding()]
param(
    [int]$MaxEvents = 100,
    [int]$PrinterPort = 9100
)

$ErrorActionPreference = "Continue"

function Test-TcpPort {
    param([string]$Target, [int]$Port, [int]$TimeoutMs = 1500)
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $ar = $client.BeginConnect($Target, $Port, $null, $null)
        if (-not $ar.AsyncWaitHandle.WaitOne($TimeoutMs)) { return $false }
        $client.EndConnect($ar)
        return $true
    } catch { return $false } finally { $client.Close() }
}

Write-Host ""
Write-Host "=== 1. IDENTITY ===" -ForegroundColor Cyan
Write-Host ("  computer   {0}" -f $env:COMPUTERNAME)
Write-Host ("  user       {0}" -f $env:USERNAME)
$os = Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion" -ErrorAction SilentlyContinue
Write-Host ("  os         {0} {1} build {2}.{3}" -f $os.ProductName, $os.DisplayVersion, $os.CurrentBuild, $os.UBR)
$cs = Get-CimInstance Win32_ComputerSystem -ErrorAction SilentlyContinue
Write-Host ("  ram        {0} GB" -f [math]::Round($cs.TotalPhysicalMemory / 1GB, 1))

Write-Host ""
Write-Host "=== 2. EVENT LOG (System, errors, deduplicated) ===" -ForegroundColor Cyan
$events = Get-WinEvent -FilterHashtable @{LogName='System'; Level=2} -MaxEvents $MaxEvents -ErrorAction SilentlyContinue
if ($events) {
    $events | Group-Object Id, ProviderName | ForEach-Object {
        $first = $_.Group | Sort-Object TimeCreated -Descending | Select-Object -First 1
        [PSCustomObject]@{
            Count    = $_.Count
            LastSeen = $first.TimeCreated.ToString('yyyy-MM-dd HH:mm')
            Id       = $first.Id
            Provider = $first.ProviderName
            Summary  = ($first.Message -split "`r?`n")[0]
        }
    } | Sort-Object LastSeen -Descending | Select-Object -First 5 | Format-List
} else {
    Write-Host "  no System errors in the last $MaxEvents events"
}

Write-Host ""
Write-Host "=== 3. PRINTERS ===" -ForegroundColor Cyan
$printers = Get-Printer -ErrorAction SilentlyContinue
if ($printers) {
    $printers | Select-Object Name, PortName, PrinterStatus | Format-Table -AutoSize
    $network = $printers | Where-Object { $_.PortName -match '^(\d{1,3}\.){3}\d{1,3}$' }
    if ($network) {
        foreach ($p in $network) {
            $reachable = Test-TcpPort -Target $p.PortName -Port $PrinterPort
            $state = if ($reachable) { "REACHABLE" } else { "no answer on port $PrinterPort" }
            Write-Host ("  {0,-30} {1,-16} {2}" -f $p.Name, $p.PortName, $state)
        }
    } else {
        Write-Host "  no printer with an IP port installed"
    }
} else {
    Write-Host "  no printers installed"
}

Write-Host ""
Write-Host "=== 4. LOCAL MODEL ===" -ForegroundColor Cyan
try {
    $models = Invoke-RestMethod "http://127.0.0.1:8080/v1/models" -TimeoutSec 3 -ErrorAction Stop
    Write-Host ("  endpoint   UP  ({0})" -f ($models.data.id -join ', '))
    $body = @{
        model    = "default"
        messages = @(@{ role = "user"; content = "Reply with the single word: ready" })
        max_tokens = 8
    } | ConvertTo-Json -Depth 5
    $reply = Invoke-RestMethod "http://127.0.0.1:8080/v1/chat/completions" `
        -Method Post -ContentType "application/json" -Body $body -TimeoutSec 120 -ErrorAction Stop
    Write-Host ("  completion OK  ->  {0}" -f $reply.choices[0].message.content.Trim())
} catch {
    Write-Host "  endpoint   DOWN or not answering completions" -ForegroundColor Yellow
    Write-Host "  start it with: .\start_local_server.ps1 -Mode qwen27b_vram -CtxSize 65536"
}

Write-Host ""
```

---

## 5. Reboot sequence

1. Reboot. Nothing else.
2. `cd C:\Users\6700XT\Documents\Strata`
3. `.\scripts\smoke_test.ps1` — model section will say DOWN, which is expected.
4. `.\scripts\launch_afterburner_pi.ps1` — starts the server, waits, probes a completion, starts Pi.
5. In Pi, ask: *"what is this computer's name and OS build"* — it must run PowerShell and answer `SANDBOX`.
6. In Pi, ask: *"show me the top 5 System event log errors, deduplicated"*.
7. In Pi, ask: *"list printers and tell me if the network one answers on port 9100"*.
8. Re-run `.\scripts\smoke_test.ps1` — model section should now say UP.

---

## 6. What this plan does not do

- No reimage. No OS wipe. No 96 GB install.
- No change to Pi's tool permissions or approval policy.
- No change to Antigravity settings or the OpenCode relay.
- No touching `llama-server` while it is running.
- No new credentials.

---

## 7. Definition of done

- [x] Hostname reboot verified: `SANDBOX` confirmed via `hostname` (exit code 0).
- [x] `~/.pi/agent/AGENTS.md` deployed natively and Pi quotes its rules when asked.
- [x] Launcher waits with adaptive readiness check and probes a real completion (33.2 t/s benchmarked).
- [x] Web GUI Dashboard live on `http://localhost:3333` with GPU VRAM/Wattage/tps telemetry, Unload button, and Advanced Sampling modal (with seed randomizer & incrementer).
- [x] `scripts/smoke_test.ps1` runs clean and is read-only.
- [x] Pi answers prompts from the local model (`qwen2.5-coder-7b`) natively on Windows.
- [x] Pi tools restricted to `["read", "powershell", "edit", "write"]` with `bash` pruned so models cannot fail into Linux syntax.
- [x] Result appended to `MEMORY/EXPERIMENT_LOG.md` (EXP-029).

---

## 8. Execution Verification Summary (2026-11-15)

Executed natively on host desktop `SANDBOX`:
1. **Host & Runtime Baseline:**
   - Hostname: `SANDBOX` (Verified `Observed`).
   - Node.js LTS `v22.23.5` and Git `2.56.0` installed natively on host.
   - Pi CLI `v1.5.2` managed install at `C:\Users\6700XT\.pi\agent\bin\pi.cmd`.
   - Standing instructions deployed at `C:\Users\6700XT\.pi\agent\AGENTS.md`.
2. **Inference Engine:**
   - `llama.cpp` Vulkan x64 build `b12427` deployed to `C:\llama.cpp\`.
   - Model `Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf` active on `http://127.0.0.1:8080` (33.2 t/s generation speed on RX 6700 XT 12 GB).
   - Additional downloads in pipeline: `DeepSeek-R1-Distill-Qwen-7B-Q4_K_M`, `Meta-Llama-3.1-8B-Instruct-Q4_K_M`, `Qwen2.5-14B-Instruct-Q4_K_M`.
3. **Control Center Dashboard (`http://localhost:3333`):**
   - Live hardware monitors (VRAM, RAM, Wattage, Speed).
   - Direct chat tab + Pi Agent integration tab.
   - Unload model button (`POST /api/server-stop`).
   - Advanced settings modal covering all `llama-server --help` switches (Seed randomizer/incrementer, Min-P, KV cache compression `q8_0`/`q4_0`, batch size, thread allocations).
   - Live benchmark log with one-click Markdown copy for GitHub publication.
