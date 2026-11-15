# scripts/launch_afterburner_pi.ps1 - Single-click seamless launcher for AfterBurner + Pi
$ErrorActionPreference = "Continue"

$rootDir = "C:\Users\6700XT\Documents\Strata"
Set-Location $rootDir

# Ensure Pi and Node are in PATH for current session
$env:PATH = "$env:LOCALAPPDATA\pi-node\current;$env:USERPROFILE\.pi\agent\bin;$env:PATH"

$Host.UI.RawUI.WindowTitle = "6700XT AfterBurner Pi Agent"
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "       🚀 6700XT-AfterBurner: Pi Agent Launcher" -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Health check on llama-server (Port 8080)
$healthUri = "http://127.0.0.1:8080/health"
$serverReady = $false

try {
    $res = Invoke-RestMethod -Uri $healthUri -TimeoutSec 2 -ErrorAction Stop
    if ($res.status -eq "ok" -or $res -match "ok") {
        $serverReady = $true
    }
} catch {
    $serverReady = $false
}

if (-not $serverReady) {
    Write-Host "[1/2] Launching 6700 XT Vulkan Server (100% VRAM 27B + MTP)..." -ForegroundColor Yellow
    $serverCmd = "-NoExit -ExecutionPolicy Bypass -Command `"cd '$rootDir'; .\start_local_server.ps1 -Mode qwen27b_vram -CtxSize 65536`""
    Start-Process powershell.exe -ArgumentList $serverCmd -WindowStyle Minimized

    Write-Host "[...] Initializing weights into GDDR6 VRAM..." -NoNewline -ForegroundColor Cyan
    $attempts = 0
    while (-not $serverReady -and $attempts -lt 35) {
        Start-Sleep -Seconds 1
        $attempts++
        Write-Host "." -NoNewline -ForegroundColor Cyan
        try {
            $res = Invoke-RestMethod -Uri $healthUri -TimeoutSec 2 -ErrorAction Stop
            if ($res.status -eq "ok" -or $res -match "ok") {
                $serverReady = $true
            }
        } catch {
            $serverReady = $false
        }
    }
    Write-Host ""
}

if ($serverReady) {
    Write-Host "[2/2] 6700 XT Server is READY! Starting Pi..." -ForegroundColor Green
    Write-Host "----------------------------------------------------------" -ForegroundColor DarkGray
    Write-Host "Hardware: AMD RX 6700 XT (100% VRAM resident | 64k context)" -ForegroundColor DarkCyan
    Write-Host "System Tools: PowerShell, File Read/Write/Edit, Web Search" -ForegroundColor DarkCyan
    Write-Host "----------------------------------------------------------`n" -ForegroundColor DarkGray
    
    # Launch Pi interactive agent
    pi --provider afterburner --model default
} else {
    Write-Host "[ERROR] Server failed to start on port 8080." -ForegroundColor Red
    Write-Host "Please check the minimized server window or run .\start_local_server.ps1 manually." -ForegroundColor Yellow
    Read-Host "Press Enter to exit..."
}
