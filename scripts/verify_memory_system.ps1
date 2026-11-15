<#
.SYNOPSIS
    Pre-flight and post-reimage conformance check for the durable-memory system.

.DESCRIPTION
    Verifies the things that must be true before an OS reimage and again after it:

      * the three AGENTS.md scopes exist
      * the git working tree is clean and synced with origin
      * a verified git bundle backup exists and is recent
      * the OpenCode session database has been snapshotted
      * the memory-contract test suite passes
      * the RAM/host topology baseline is recorded
      * no live credentials sit in plaintext under Documents

    Exit code 0 when every FAIL-level check passes. WARN-level findings do not
    change the exit code.

.PARAMETER BackupRoot
    Where backup_memory.ps1 writes. Default D:\backups\strata

.PARAMETER MaxBackupAgeDays
    Age above which a backup is reported stale. Default 7.

.EXAMPLE
    .\verify_memory_system.ps1
    .\verify_memory_system.ps1 -MaxBackupAgeDays 1
#>
[CmdletBinding()]
param(
    [string]$BackupRoot = "D:\backups\strata",
    [int]$MaxBackupAgeDays = 7
)

$ErrorActionPreference = "Continue"
$repo    = Split-Path $PSScriptRoot -Parent
$profileDir = $env:USERPROFILE

$results = New-Object System.Collections.Generic.List[object]

function Add-Result {
    param(
        [string]$Check,
        [ValidateSet("PASS", "WARN", "FAIL")]
        [string]$Status,
        [string]$Detail
    )
    $script:results.Add([pscustomobject]@{ Status = $Status; Check = $Check; Detail = $Detail })
}

function Test-Check {
    param([string]$Name, [scriptblock]$Body)
    try {
        $r = & $Body
        Add-Result -Check $Name -Status $r.Status -Detail $r.Detail
    } catch {
        Add-Result -Check $Name -Status "FAIL" -Detail $_.Exception.Message
    }
}

Write-Host ""
Write-Host "Memory system conformance check" -ForegroundColor Cyan
Write-Host "repo: $repo" -ForegroundColor DarkGray
Write-Host ""

# --- AGENTS.md scopes -------------------------------------------------------
Test-Check "AGENTS.md machine scope" {
    $p = Join-Path $profileDir "AGENTS.md"
    if (Test-Path -LiteralPath $p) {
        [pscustomobject]@{ Status = "PASS"; Detail = "$p ($((Get-Item $p).Length) B)" }
    } else { [pscustomobject]@{ Status = "FAIL"; Detail = "missing $p" } }
}

Test-Check "AGENTS.md documents scope" {
    $p = Join-Path $profileDir "Documents\AGENTS.md"
    if (Test-Path -LiteralPath $p) {
        [pscustomobject]@{ Status = "PASS"; Detail = "$p ($((Get-Item $p).Length) B)" }
    } else { [pscustomobject]@{ Status = "FAIL"; Detail = "missing $p" } }
}

Test-Check "AGENTS.md project scope" {
    $p = Join-Path $repo "AGENTS.md"
    if (Test-Path -LiteralPath $p) {
        [pscustomobject]@{ Status = "PASS"; Detail = "$p ($((Get-Item $p).Length) B)" }
    } else { [pscustomobject]@{ Status = "FAIL"; Detail = "missing $p" } }
}

# --- git state --------------------------------------------------------------
Test-Check "git working tree clean" {
    $dirty = & git -C $repo status --porcelain 2>$null
    if (-not $dirty) { [pscustomobject]@{ Status = "PASS"; Detail = "no uncommitted changes" } }
    else { [pscustomobject]@{ Status = "WARN"; Detail = "$(($dirty | Measure-Object).Count) uncommitted path(s)" } }
}

Test-Check "git synced with origin" {
    & git -C $repo fetch origin --quiet 2>$null
    $counts = (& git -C $repo rev-list --left-right --count "origin/main...main" 2>$null) -split "\s+"
    $behind = [int]$counts[0]; $ahead = [int]$counts[1]
    if ($behind -eq 0 -and $ahead -eq 0) { [pscustomobject]@{ Status = "PASS"; Detail = "main == origin/main" } }
    elseif ($ahead -gt 0) { [pscustomobject]@{ Status = "WARN"; Detail = "$ahead commit(s) not pushed" } }
    else { [pscustomobject]@{ Status = "WARN"; Detail = "$behind commit(s) behind origin" } }
}

Test-Check "vendored patches exported" {
    $p = Join-Path $repo "patches"
    $patches = @(Get-ChildItem -LiteralPath $p -Filter "*.patch" -ErrorAction SilentlyContinue)
    if ($patches.Count -gt 0) { [pscustomobject]@{ Status = "PASS"; Detail = "$($patches.Count) patch(es)" } }
    else { [pscustomobject]@{ Status = "FAIL"; Detail = "no exported patches in $p" } }
}

# --- backups ----------------------------------------------------------------
Test-Check "git bundle backup recent" {
    if (-not (Test-Path -LiteralPath $BackupRoot)) {
        return [pscustomobject]@{ Status = "FAIL"; Detail = "no backup root at $BackupRoot" }
    }
    $latest = Get-ChildItem -LiteralPath $BackupRoot -Directory -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $latest) { return [pscustomobject]@{ Status = "FAIL"; Detail = "backup root is empty" } }
    $ageDays = ((Get-Date) - $latest.LastWriteTime).TotalDays
    $bundle = Get-ChildItem -LiteralPath $latest.FullName -Recurse -Filter "*.bundle" -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $bundle) { return [pscustomobject]@{ Status = "FAIL"; Detail = "latest backup has no .bundle" } }
    $prev = $ErrorActionPreference; $ErrorActionPreference = "Continue"
    & git -C $repo bundle verify $bundle.FullName 2>&1 | Out-Null
    $code = $LASTEXITCODE
    $ErrorActionPreference = $prev
    if ($code -ne 0) { return [pscustomobject]@{ Status = "FAIL"; Detail = "bundle failed verification: $($bundle.Name)" } }
    $status = if ($ageDays -le $MaxBackupAgeDays) { "PASS" } else { "WARN" }
    [pscustomobject]@{ Status = $status; Detail = "$($latest.Name), $([math]::Round($ageDays,1)) d old, verified" }
}

Test-Check "opencode session snapshot exists" {
    if (-not (Test-Path -LiteralPath $BackupRoot)) {
        return [pscustomobject]@{ Status = "FAIL"; Detail = "no backup root" }
    }
    $db = Get-ChildItem -LiteralPath $BackupRoot -Recurse -Filter "opencode.db" -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($db -and $db.Length -gt 1MB) {
        [pscustomobject]@{ Status = "PASS"; Detail = "$([math]::Round($db.Length/1MB,1)) MB" }
    } else { [pscustomobject]@{ Status = "FAIL"; Detail = "no opencode.db snapshot over 1 MB" } }
}

# --- tests ------------------------------------------------------------------
$prevLoc = Get-Location
Set-Location $repo
try {
    $out = & python -m unittest tests.test_memory_contract 2>&1 | Out-String
    if ($LASTEXITCODE -eq 0) {
        $m = [regex]::Match($out, "Ran (\d+) tests")
        Add-Result -Check "memory contract tests" -Status "PASS" -Detail $(if ($m.Success) { "$($m.Groups[1].Value) tests" } else { "ok" })
    } else {
        $tail = ($out -split "`n" | Where-Object { $_ -match "FAIL|Error" } | Select-Object -First 3) -join " "
        Add-Result -Check "memory contract tests" -Status "FAIL" -Detail $tail.Trim()
    }
} finally { Set-Location $prevLoc }

# --- host baseline ----------------------------------------------------------
Test-Check "RAM topology baseline recorded" {
    $files = @(Get-ChildItem -LiteralPath (Join-Path $repo "MEMORY") -Filter "RAM_*.json" -ErrorAction SilentlyContinue)
    if ($files.Count -eq 0) { return [pscustomobject]@{ Status = "FAIL"; Detail = "run bench/ram_topology.py --label <config>" } }
    $latest = $files | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    $j = Get-Content -LiteralPath $latest.FullName -Raw | ConvertFrom-Json
    [pscustomobject]@{ Status = "PASS"; Detail = "$($j.label): $($j.memory.totalGB) GB / $($j.memory.dimmCount) DIMM / $($j.memory.speedActualMHz) MHz" }
}

Test-Check "local model server" {
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:8080/v1/models" -UseBasicParsing -TimeoutSec 3
        [pscustomobject]@{ Status = "PASS"; Detail = "HTTP $($r.StatusCode) on 8080" }
    } catch {
        [pscustomobject]@{ Status = "WARN"; Detail = "llama-server not running (fine if intentional)" }
    }
}

# --- secrets ----------------------------------------------------------------
Test-Check "no plaintext credentials under Documents" {
    $hits = @()
    foreach ($pat in @("ghp_[A-Za-z0-9]{36}", "gho_[A-Za-z0-9]{36}", "sk-or-v1-[a-f0-9]{64}", "sk-ant-[A-Za-z0-9\-_]{32,}")) {
        $hits += Get-ChildItem -LiteralPath (Join-Path $profileDir "Documents") -Recurse -File -Force -ErrorAction SilentlyContinue |
            Where-Object { $_.Length -lt 1MB -and $_.Extension -notin ".exe", ".dll", ".png", ".jpg", ".mp4", ".gguf", ".zip", ".db", ".bundle" } |
            Select-String -Pattern $pat -List -ErrorAction SilentlyContinue
    }
    if ($hits.Count -eq 0) { [pscustomobject]@{ Status = "PASS"; Detail = "no token patterns found" } }
    else { [pscustomobject]@{ Status = "FAIL"; Detail = "$($hits.Count) file(s): $(($hits | ForEach-Object { $_.Path } | Select-Object -Unique) -join ', ')" } }
}

# --- report -----------------------------------------------------------------
$results | Format-Table -AutoSize -Property Status, Check, Detail
$fails = @($results | Where-Object Status -eq "FAIL")
$warns = @($results | Where-Object Status -eq "WARN")
Write-Host ("{0} pass, {1} warn, {2} fail" -f @($results | Where-Object Status -eq "PASS").Count, $warns.Count, $fails.Count) -ForegroundColor $(if ($fails.Count) { "Red" } elseif ($warns.Count) { "Yellow" } else { "Green" })

if ($fails.Count -gt 0) { exit 1 } else { exit 0 }
