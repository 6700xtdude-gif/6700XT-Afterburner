# start_local_server.ps1 - Launch Vulkan Accelerated Local Server for 6700XT-Afterburner
param(
    [ValidateSet("speculative", "moe35b")]
    [string]$Mode = "speculative",
    [int]$K = 3
)

$RootDir = $PSScriptRoot
$BinDir  = Join-Path $RootDir "bin\vulkan"

if ($Mode -eq "speculative") {
    $Host.UI.RawUI.WindowTitle = "6700XT-Afterburner: Dual-Engine Speculative Vulkan Server (RX 6700 XT)"
    $TargetModel = Join-Path $RootDir "Models\Qwen2.5-Coder-7B-Instruct-GGUF\qwen2.5-coder-7b-instruct-q4_k_m.gguf"
    $DraftModel  = Join-Path $RootDir "Models\Qwen2.5-Coder-0.5B-Instruct\Qwen2.5-Coder-0.5B-Instruct-Q4_0.gguf"

    if (-not (Test-Path $TargetModel)) {
        Write-Error "Target model file not found at: $TargetModel"
        exit 1
    }

    Write-Host "==========================================================" -ForegroundColor Cyan
    Write-Host " 6700XT-Afterburner: Dual-Engine Speculative Vulkan Server" -ForegroundColor Yellow
    Write-Host " Endpoint: http://127.0.0.1:8080/v1" -ForegroundColor Green
    Write-Host " Target Model: Qwen 2.5 Coder 7B (Q4_K_M) - 100% in VRAM" -ForegroundColor White
    Write-Host " Draft Engine: Qwen 2.5 Coder 0.5B (Q4_0) - 100% in VRAM (K=$K)" -ForegroundColor White
    Write-Host " Peak Speed:   Up to 95.5 tokens/sec on AMD Radeon RX 6700 XT" -ForegroundColor White
    Write-Host " KV Cache:     Q8_0 + FlashAttention (8k context)" -ForegroundColor White
    Write-Host "==========================================================" -ForegroundColor Cyan

    & "$BinDir\llama-server.exe" `
        -m "$TargetModel" `
        -md "$DraftModel" `
        --host 127.0.0.1 `
        --port 8080 `
        -ngl 99 `
        -ngld 99 `
        --spec-type draft-simple `
        --spec-draft-n-max $K `
        -fa on `
        -ctk q8_0 `
        -ctv q8_0 `
        -c 8192 `
        -t 6
} else {
    $Host.UI.RawUI.WindowTitle = "6700XT-Afterburner: Local Vulkan 35B MoE Server (RX 6700 XT)"
    $ModelPath = Join-Path $RootDir "Models\qwen36-UD-Q4_K_XL\Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf"

    if (-not (Test-Path $ModelPath)) {
        Write-Error "Model file not found at: $ModelPath"
        exit 1
    }

    Write-Host "==========================================================" -ForegroundColor Cyan
    Write-Host " 6700XT-Afterburner: Local Vulkan 35B MoE Server (RX 6700 XT)" -ForegroundColor Yellow
    Write-Host " Endpoint: http://127.0.0.1:8080/v1" -ForegroundColor Green
    Write-Host " Model: Qwen 3.6 35B-A3B (UD-Q4_K_XL)" -ForegroundColor White
    Write-Host " GPU Layers: 16 on RX 6700 XT, remainder in 64GB DDR4" -ForegroundColor White
    Write-Host " KV Cache: Q8_0 + FlashAttention (8k context)" -ForegroundColor White
    Write-Host "==========================================================" -ForegroundColor Cyan

    & "$BinDir\llama-server.exe" `
        -m "$ModelPath" `
        --host 127.0.0.1 `
        --port 8080 `
        -ngl 16 `
        -fa on `
        -ctk q8_0 `
        -ctv q8_0 `
        -c 8192 `
        -t 6
}
