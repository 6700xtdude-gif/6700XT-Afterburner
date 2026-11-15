<#
.SYNOPSIS
    Print the context packet a session needs before it starts working.

.DESCRIPTION
    Reads the durable ledger and prints a bounded summary: current state, open
    questions, memory health, and gate status. Designed so an agent gets the
    project's real state in under a screen instead of re-deriving it from chat.

    This is a read-only script. It changes nothing.

.PARAMETER MaxDigestLines
    Lines of MEMORY/DIGEST.md to print. Default 40.

.PARAMETER SkipGate
    Skip the conformance gate (it runs the test suite, which takes a moment).

.EXAMPLE
    .\scripts\session_start.ps1
#>
[CmdletBinding()]
param(
    [int]$MaxDigestLines = 40,
    [switch]$SkipGate
)

$ErrorActionPreference = "Continue"
$repo = Split-Path $PSScriptRoot -Parent

function Section($title) {
    Write-Host ""
    Write-Host "=== $title ===" -ForegroundColor Cyan
}

Write-Host "Strata session context" -ForegroundColor White
Write-Host "repo: $repo" -ForegroundColor DarkGray
Write-Host ("time: {0}" -f (Get-Date -Format "yyyy-MM-dd HH:mm")) -ForegroundColor DarkGray

# 1. Current state
Section "CURRENT STATE (MEMORY/DIGEST.md)"
$digest = Join-Path $repo "MEMORY\DIGEST.md"
if (Test-Path -LiteralPath $digest) {
    Get-Content -LiteralPath $digest -TotalCount $MaxDigestLines
    $total = (Get-Content -LiteralPath $digest | Measure-Object -Line).Lines
    if ($total -gt $MaxDigestLines) {
        Write-Host "... ($($total - $MaxDigestLines) more lines, read the file for the rest)" -ForegroundColor DarkGray
    }
} else {
    Write-Host "MISSING: $digest" -ForegroundColor Red
}

# 2. Open questions
Section "OPEN QUESTIONS (MEMORY/GAPS_AND_HYPOTHESES.md)"
$gaps = Join-Path $repo "MEMORY\GAPS_AND_HYPOTHESES.md"
if (Test-Path -LiteralPath $gaps) {
    Get-Content -LiteralPath $gaps -TotalCount 25
} else {
    Write-Host "none recorded" -ForegroundColor DarkGray
}

# 3. Memory health
Section "MEMORY HEALTH (MEMORY/HEALTH.md)"
$health = Join-Path $repo "MEMORY\HEALTH.md"
if (Test-Path -LiteralPath $health) {
    Select-String -LiteralPath $health -Pattern "^## " | ForEach-Object { $_.Line }
    Write-Host "(full report: MEMORY/HEALTH.md)" -ForegroundColor DarkGray
} else {
    Write-Host "not built yet - run: python scripts/memory_build.py" -ForegroundColor Yellow
}

# 4. Git state
Section "GIT STATE"
$branch = (& git -C $repo rev-parse --abbrev-ref HEAD 2>$null)
$dirty  = (& git -C $repo status --porcelain 2>$null)
$counts = (& git -C $repo rev-list --left-right --count "origin/$branch...$branch" 2>$null) -split "\s+"
if ($dirty) { $changeText = "$(($dirty | Measure-Object).Count) uncommitted" } else { $changeText = "clean" }
Write-Host "branch   $branch"
Write-Host "changes  $changeText"
Write-Host "sync     behind $($counts[0]) / ahead $($counts[1])"

# 5. Gate
if (-not $SkipGate) {
    Section "CONFORMANCE GATE"
    & (Join-Path $PSScriptRoot "verify_memory_system.ps1") | Select-Object -Last 3
}

Write-Host ""
Write-Host "Read MEMORY/PROTOCOL.md before writing anything. End with session_end.ps1." -ForegroundColor Yellow
Write-Host ""
