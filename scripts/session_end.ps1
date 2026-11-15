<#
.SYNOPSIS
    Close a session: gate, rebuild the memory index, commit, push.

.DESCRIPTION
    Enforces the end-of-session ritual from MEMORY/PROTOCOL.md. It refuses to
    commit while the conformance gate is red, so a broken memory system cannot be
    pushed and then trusted by the next session.

    Steps:
      1. run the conformance gate
      2. rebuild MEMORY/INDEX.json and MEMORY/HEALTH.md
      3. show what changed
      4. stage, commit with your message, push
      5. print the new HEAD and remaining health warnings

.PARAMETER Message
    Commit message. Required unless -DryRun.

.PARAMETER DryRun
    Run the gate and the builder, show the diff, change nothing.

.PARAMETER AllowWarn
    Commit even if the gate reports warnings. Default is to commit on warnings but
    never on failures, so this flag is only needed to override that.

.EXAMPLE
    .\scripts\session_end.ps1 -Message "bench: record 96GB 4-DIMM matrix"
    .\scripts\session_end.ps1 -DryRun
#>
[CmdletBinding()]
param(
    [string]$Message,
    [switch]$DryRun
)

$ErrorActionPreference = "Continue"
$repo = Split-Path $PSScriptRoot -Parent
Set-Location $repo

Write-Host ""
Write-Host "Session close" -ForegroundColor White
Write-Host ""

# 1. Gate
Write-Host "[1/5] conformance gate" -ForegroundColor Cyan
$gateOut = & (Join-Path $PSScriptRoot "verify_memory_system.ps1") 2>&1 | Out-String
$gateCode = $LASTEXITCODE
($gateOut -split "`n" | Where-Object { $_ -match "^(PASS|WARN|FAIL)\s" }) | ForEach-Object { Write-Host "      $_" }
if ($gateCode -ne 0) {
    Write-Host ""
    Write-Host "GATE FAILED. Fix the FAIL rows above before closing the session." -ForegroundColor Red
    Write-Host "A broken memory system must not be committed." -ForegroundColor Red
    exit 1
}
Write-Host "      gate green" -ForegroundColor Green

# 2. Rebuild index
Write-Host "[2/5] rebuild memory index" -ForegroundColor Cyan
& python (Join-Path $PSScriptRoot "memory_build.py")
if ($LASTEXITCODE -ne 0) {
    Write-Host "builder failed" -ForegroundColor Red
    exit 1
}

# 3. Show the change
Write-Host "[3/5] staged changes" -ForegroundColor Cyan
& git add -A 2>$null
$staged = & git status --porcelain
if (-not $staged) {
    Write-Host "      nothing to commit - session ended with no changes" -ForegroundColor Yellow
    exit 0
}
& git diff --cached --stat 2>$null

if ($DryRun) {
    Write-Host ""
    Write-Host "dry run: no commit made" -ForegroundColor Yellow
    exit 0
}

# 4. Commit
if (-not $Message) {
    Write-Host ""
    Write-Host "-Message is required to commit. Nothing was committed." -ForegroundColor Red
    exit 1
}
Write-Host "[4/5] commit" -ForegroundColor Cyan
& git commit -q -m $Message 2>$null
if ($LASTEXITCODE -ne 0) { Write-Host "commit failed" -ForegroundColor Red; exit 1 }

# 5. Push
Write-Host "[5/5] push" -ForegroundColor Cyan
$prev = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& git push origin HEAD 2>&1 | Out-Null
$pushCode = $LASTEXITCODE
$ErrorActionPreference = $prev
if ($pushCode -ne 0) {
    Write-Host "      commit is local only - push failed. Run: git push origin HEAD" -ForegroundColor Yellow
} else {
    Write-Host "      pushed" -ForegroundColor Green
}

$head = (& git rev-parse --short HEAD).Trim()
Write-Host ""
Write-Host "HEAD $head" -ForegroundColor Green
Write-Host ""

# Remaining health notes
$health = Join-Path $repo "MEMORY\HEALTH.md"
if (Test-Path -LiteralPath $health) {
    $warnLines = Select-String -LiteralPath $health -Pattern "^## (Orphans|Stale|Unsourced numbers|Archive candidates) \(([1-9]\d*)\)" -AllMatches
    if ($warnLines) {
        Write-Host "Memory health still has open items:" -ForegroundColor Yellow
        $warnLines | ForEach-Object { Write-Host "  $($_.Line)" -ForegroundColor Yellow }
        Write-Host "  see MEMORY/HEALTH.md" -ForegroundColor DarkGray
    }
}
