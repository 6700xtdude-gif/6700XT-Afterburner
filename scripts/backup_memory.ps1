<#
.SYNOPSIS
    Creates a verified, timestamped backup of every memory store on this machine.

.DESCRIPTION
    Backs up the four places agent state actually lives:
      1. Git repositories        -> git bundle (full history, single file, restorable offline)
      2. OpenCode sessions       -> SQLite online backup of opencode.db (WAL-safe)
      3. Antigravity memory      -> brain/ + conversations/ (chat DBs hold stranded project work)
      4. Pi agent sessions       -> ~/.pi/agent/sessions
    Plus harness config, so a reimaged machine can be rebuilt from one folder.

    Writes manifest.json with byte counts and SHA256 for every artifact, then verifies
    each git bundle with `git bundle verify`.

.PARAMETER Destination
    Backup root. Default D:\backups\strata

.PARAMETER SkipVerify
    Skip the slower hash + bundle verification pass.

.EXAMPLE
    .\backup_memory.ps1
    .\backup_memory.ps1 -Destination "E:\cold-storage"
#>
[CmdletBinding()]
param(
    [string]$Destination = "D:\backups\strata",
    [switch]$SkipVerify
)

$ErrorActionPreference = "Stop"
$stamp   = Get-Date -Format "yyyy-MM-dd_HHmmss"
$root    = Join-Path $Destination $stamp
$profileDir = $env:USERPROFILE

# Repos that get a full history bundle. Keep this list to repos whose history is
# unique to this machine. Vendored clones of public upstreams are re-clonable and
# are recorded as a HEAD sha + diff instead (see $diffRepos), which is faster and
# far smaller than bundling a million-object upstream history.
$repos = @(
    (Join-Path $profileDir "Documents\Strata")
)

$diffRepos = @(
    (Join-Path $profileDir "Documents\Strata\tools\llama.cpp")
)

$sqliteDbs = @(
    (Join-Path $profileDir ".local\share\opencode\opencode.db")
)

$trees = @(
    @{ Name = "antigravity-brain";         Path = (Join-Path $profileDir ".gemini\antigravity\brain") },
    @{ Name = "antigravity-conversations"; Path = (Join-Path $profileDir ".gemini\antigravity\conversations") },
    @{ Name = "pi-sessions";               Path = (Join-Path $profileDir ".pi\agent\sessions") },
    @{ Name = "opencode-config";           Path = (Join-Path $profileDir ".config\opencode") },
    @{ Name = "gemini-config";             Path = (Join-Path $profileDir ".gemini\config") },
    @{ Name = "pi-agent-config";           Path = (Join-Path $profileDir ".pi\agent\models.json"); File = $true },
    @{ Name = "pi-agent-settings";         Path = (Join-Path $profileDir ".pi\agent\settings.json"); File = $true },
    @{ Name = "agents-md-machine";         Path = (Join-Path $profileDir "AGENTS.md"); File = $true },
    @{ Name = "agents-md-documents";       Path = (Join-Path $profileDir "Documents\AGENTS.md"); File = $true }
)

New-Item -ItemType Directory -Force -Path $root | Out-Null
Write-Host "Backup root: $root" -ForegroundColor Cyan

$manifest = [ordered]@{
    createdAt = (Get-Date).ToString("o")
    host      = $env:COMPUTERNAME
    user      = $env:USERNAME
    artifacts = @()
}

function Add-Artifact {
    param([string]$Name, [string]$Path, [string]$Kind)
    if (-not (Test-Path -LiteralPath $Path)) {
        Write-Host "  skip (missing): $Name" -ForegroundColor DarkGray
        return
    }
    $item = Get-Item -LiteralPath $Path
    $bytes = if ($item.PSIsContainer) {
        (Get-ChildItem -LiteralPath $Path -Recurse -Force -ErrorAction SilentlyContinue |
            Measure-Object Length -Sum).Sum
    } else { $item.Length }
    $hash = $null
    if (-not $SkipVerify -and -not $item.PSIsContainer) {
        $hash = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
    }
    $script:manifest.artifacts += [ordered]@{
        name  = $Name
        kind  = $Kind
        path  = $Path
        bytes = [int64]$bytes
        sha256 = $hash
    }
    Write-Host ("  ok  {0,-28} {1,12:N0} bytes" -f $Name, $bytes) -ForegroundColor Green
}

# 1. Git repositories -> bundle
$bundleDir = Join-Path $root "git"
New-Item -ItemType Directory -Force -Path $bundleDir | Out-Null
foreach ($repo in $repos) {
    if (-not (Test-Path (Join-Path $repo ".git"))) { Write-Host "  skip (not a repo): $repo" -ForegroundColor DarkGray; continue }
    $name = Split-Path $repo -Leaf
    $out  = Join-Path $bundleDir "$name.bundle"
    Write-Host "Bundling $repo" -ForegroundColor Cyan
    & git -C $repo bundle create $out --all 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "git bundle failed for $repo" }
    Add-Artifact -Name "git-$name" -Path $out -Kind "git-bundle"
    if (-not $SkipVerify) {
        # git writes bundle progress/verify chatter to stderr; that is not a failure.
        $prevEap = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        $verify = & git -C $repo bundle verify $out 2>&1 | Out-String
        $code   = $LASTEXITCODE
        $ErrorActionPreference = $prevEap
        if ($code -ne 0) { throw "git bundle verify FAILED for $out`n$verify" }
        Write-Host "  verified: $name.bundle" -ForegroundColor Green
    }
}

# 1b. Vendored repos -> HEAD sha + working diff (history is re-clonable upstream)
$patchDir = Join-Path $root "patches"
New-Item -ItemType Directory -Force -Path $patchDir | Out-Null
foreach ($repo in $diffRepos) {
    if (-not (Test-Path (Join-Path $repo ".git"))) { Write-Host "  skip (not a repo): $repo" -ForegroundColor DarkGray; continue }
    $name = Split-Path $repo -Leaf
    $head  = (& git -C $repo rev-parse HEAD).Trim()
    $remot = (& git -C $repo remote get-url origin 2>$null)
    $diff  = & git -C $repo diff 2>&1
    $out   = Join-Path $patchDir "$name-working.diff"
    if ($diff) { Set-Content -LiteralPath $out -Value $diff -Encoding UTF8 }
    $stampFile = Join-Path $patchDir "$name-repo.txt"
    @(
        "repo:    $repo"
        "remote:  $remot"
        "head:    $head"
        "dirty:   $(if ($diff) { 'yes' } else { 'no' })"
        "restore: git clone $remot $name; git -C $name checkout $head"
        "apply:   git -C $name apply $name-working.diff"
    ) | Set-Content -LiteralPath $stampFile -Encoding UTF8
    Write-Host ("  ok  {0,-28} head {1}  dirty={2}" -f "$name-repo", $head.Substring(0,8), [bool]$diff) -ForegroundColor Green
    Add-Artifact -Name "repo-$name-diff" -Path $(if ($diff) { $out } else { $stampFile }) -Kind "patch"
}

# 2. SQLite -> consistent online backup
$dbDir = Join-Path $root "sqlite"
New-Item -ItemType Directory -Force -Path $dbDir | Out-Null
foreach ($db in $sqliteDbs) {
    if (-not (Test-Path -LiteralPath $db)) { Write-Host "  skip (missing): $db" -ForegroundColor DarkGray; continue }
    $name = [System.IO.Path]::GetFileNameWithoutExtension($db)
    $out  = Join-Path $dbDir "$name.db"
    Write-Host "Snapshotting $db" -ForegroundColor Cyan
    $py = @"
import sqlite3, sys
src, dst = sys.argv[1], sys.argv[2]
s = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
d = sqlite3.connect(dst)
s.backup(d)
d.close(); s.close()
print("ok")
"@
    $tmp = Join-Path $env:TEMP "sqlite_backup.py"
    Set-Content -LiteralPath $tmp -Value $py -Encoding UTF8
    & python $tmp $db $out
    if ($LASTEXITCODE -ne 0) { throw "sqlite backup failed for $db" }
    Add-Artifact -Name "sqlite-$name" -Path $out -Kind "sqlite-backup"
}

# 3. State trees
$stateDir = Join-Path $root "state"
New-Item -ItemType Directory -Force -Path $stateDir | Out-Null
foreach ($t in $trees) {
    $dest = Join-Path $stateDir $t.Name
    if (-not (Test-Path -LiteralPath $t.Path)) { Write-Host "  skip (missing): $($t.Name)" -ForegroundColor DarkGray; continue }
    Write-Host "Copying $($t.Name)" -ForegroundColor Cyan
    if ($t.File) {
        Copy-Item -LiteralPath $t.Path -Destination $dest -Force
    } else {
        robocopy $t.Path $dest /E /NFL /NDL /NJH /NJS /NP /R:1 /W:1 | Out-Null
        if ($LASTEXITCODE -ge 8) { throw "robocopy failed for $($t.Path) (exit $LASTEXITCODE)" }
    }
    Add-Artifact -Name $t.Name -Path $dest -Kind "state-tree"
}

# 4. Manifest
$manifestPath = Join-Path $root "manifest.json"
$manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $manifestPath -Encoding UTF8

$totalBytes = 0
foreach ($a in $manifest.artifacts) { $totalBytes += [int64]$a.bytes }
Write-Host ""
Write-Host ("Backup complete: {0:N0} artifacts, {1:N1} MB" -f $manifest.artifacts.Count, ($totalBytes/1MB)) -ForegroundColor Cyan
Write-Host "Manifest: $manifestPath" -ForegroundColor Cyan
Write-Host ""
Write-Host "Restore a repo with:" -ForegroundColor Yellow
Write-Host "  git clone <bundle> <target-dir>" -ForegroundColor Yellow
