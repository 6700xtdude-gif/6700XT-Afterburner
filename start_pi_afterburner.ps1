# start_pi_afterburner.ps1 - Launch Pi Coding Agent with 6700XT-Afterburner
param(
    [string]$Model = "default",
    [switch]$Unattended
)

# Ensure Pi and Node are in PATH for current session
$env:PATH = "$env:LOCALAPPDATA\pi-node\current;$env:USERPROFILE\.pi\agent\bin;$env:PATH"

# Check if local llama-server is listening on 8080
$healthUri = "http://127.0.0.1:8080/health"
$serverUp = $false
try {
    $res = Invoke-RestMethod -Uri $healthUri -TimeoutSec 2 -ErrorAction Stop
    if ($res.status -eq "ok" -or $res -match "ok") {
        $serverUp = $true
    }
} catch {
    $serverUp = $false
}

if (-not $serverUp) {
    Write-Host "[WARNING] Local llama-server on port 8080 is NOT responding yet!" -ForegroundColor Yellow
    Write-Host "Start your AfterBurner server in another terminal first, for example:" -ForegroundColor Cyan
    Write-Host "  .\start_local_server.ps1 -Mode qwen27b_vram -CtxSize 65536" -ForegroundColor White
    Write-Host ""
} else {
    try {
        $props = Invoke-RestMethod -Uri "http://127.0.0.1:8080/props" -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($props.default_generation_settings.n_ctx) {
            $serverCtx = $props.default_generation_settings.n_ctx
            if ($serverCtx -lt 65536) {
                Write-Host "[ALERT] llama-server running on port 8080 has n_ctx = $serverCtx (< 65536)!" -ForegroundColor Red
                Write-Host "Tool-enabled agents need large context. Relaunch server with: .\start_local_server.ps1 -CtxSize 65536" -ForegroundColor Yellow
                Write-Host ""
            } else {
                Write-Host "[OK] End-to-end verified: llama-server context size is $serverCtx tokens." -ForegroundColor Green
            }
        }
    } catch {}
}

Write-Host "Launching Pi Coding Agent connected to AfterBurner (64k context)..." -ForegroundColor Green
Write-Host "Model ID: $Model (Provider: afterburner)" -ForegroundColor Cyan
Write-Host "Unsandboxed host tools: powershell, read, write, edit, web_search, web_read" -ForegroundColor Cyan
Write-Host ""

if ($Unattended) {
    pi --provider afterburner --model $Model --tui-mode regular
} else {
    pi --provider afterburner --model $Model
}
