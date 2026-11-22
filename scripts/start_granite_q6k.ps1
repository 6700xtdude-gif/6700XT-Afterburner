# start_granite_q6k.ps1 - Launch Vulkan Accelerated Local Server for the small tool-calling MoE (IBM Granite 4.0 h-tiny, Q6_K)
# Target: RX 6700 XT (12GB VRAM) - "fits full VRAM, ample KV headroom"
param(
    [int]$CtxSize = 131072,
    [string]$Ctk = "q8_0",
    [string]$Ctv = "q8_0",
    [int]$Port = 8080,
    [string]$BindHost = "0.0.0.0"
)

$ErrorActionPreference = "Stop"
$ModelPath = "C:\models\granite-4.0-h-tiny-Q6_K.gguf"

if (-not (Test-Path $ModelPath)) { Write-Error "Model file not found at: $ModelPath"; exit 1 }

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " 6700XT-Afterburner: Small MoE Tool-Calling Server (Granite 4.0 h-tiny Q6_K)" -ForegroundColor Yellow
Write-Host "  Endpoint: http://$BindHost`:$Port/v1" -ForegroundColor Green
Write-Host "  Model: ibm-granite/granite-4.0-h-tiny-GGUF (granitehybrid MoE, 7B / ~1B active, Q6_K, 5.71 GB)" -ForegroundColor White
Write-Host "  GPU Layers: 99 (ALL on RX 6700 XT GDDR6, 0 in DDR4!)" -ForegroundColor White
Write-Host "  Context: $CtxSize (NoPE -> explicit cap required by model card)" -ForegroundColor White
Write-Host "  KV Cache: $Ctk/$Ctv + FlashAttention" -ForegroundColor White
Write-Host "==========================================================" -ForegroundColor Cyan

& "C:\llama.cpp\llama-server.exe" `
    -m $ModelPath `
    -a granite-4.0-h-tiny-q6_k `
    --host $BindHost `
    --port $Port `
    -ngl 99 `
    -t 6 `
    -c $CtxSize `
    -fa on `
    --jinja `
    --temp 0.0 `
    -ctk $Ctk `
    -ctv $Ctv
