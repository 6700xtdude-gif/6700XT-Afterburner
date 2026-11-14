# start_local_server.ps1 - Launch Vulkan Accelerated Local Server for 6700XT-Afterburner
param(
    [ValidateSet("speculative", "healed18l", "healed14l", "dory19l", "speculative14b", "moe35b", "qwen27b", "qwen27b_vram")]
    [string]$Mode = "qwen27b_vram",
    [int]$K = 3
)

$RootDir = $PSScriptRoot
$BinDir  = Join-Path $RootDir "bin\vulkan"

if ($Mode -eq "qwen27b_vram") {
    $Host.UI.RawUI.WindowTitle = "6700XT-Afterburner: 100% VRAM Vulkan 27B Server (RX 6700 XT)"
    $ModelPath = Join-Path $RootDir "Models\Qwen3.8-27B-UD-Q4_K_XL\Qwen3.8-27B-IQ2_M.gguf"

    if (-not (Test-Path $ModelPath)) {
        Write-Error "Model file not found at: $ModelPath"
        exit 1
    }

    Write-Host "==========================================================" -ForegroundColor Cyan
    Write-Host " 6700XT-Afterburner: 100% VRAM Vulkan 27B Server (RX 6700 XT)" -ForegroundColor Yellow
    Write-Host " Endpoint: http://127.0.0.1:8080/v1" -ForegroundColor Green
    Write-Host " Model: Qwen 3.8 27B (IQ2_M + Q4_K MTP Head, 100% in VRAM)" -ForegroundColor White
    Write-Host " GPU Layers: 65/65 (ALL on RX 6700 XT GDDR6, 0 in DDR4!)" -ForegroundColor White
    Write-Host " Speculation: Native Multi-Token Prediction (K=2)" -ForegroundColor White
    Write-Host " Speed: Up to 25.1 tokens/sec on Navi 22 (6.25x speedup!)" -ForegroundColor White
    Write-Host " KV Cache: Q8_0 + FlashAttention (8k context)" -ForegroundColor White
    Write-Host "==========================================================" -ForegroundColor Cyan

    & "$BinDir\llama-server.exe" `
        -m "$ModelPath" `
        --host 127.0.0.1 `
        --port 8080 `
        -ngl 99 `
        -t 6 `
        -np 1 `
        --spec-type draft-mtp `
        --spec-draft-n-max 2 `
        -fa on `
        -ctk q8_0 `
        -ctv q8_0 `
        -c 8192
} elseif ($Mode -eq "qwen27b") {
    $Host.UI.RawUI.WindowTitle = "6700XT-Afterburner: Local Vulkan 27B Hybrid Server (RX 6700 XT)"
    $ModelPath = Join-Path $RootDir "Models\Qwen3.8-27B-UD-Q4_K_XL\Qwen3.8-27B-UD-Q4_K_XL.gguf"

    if (-not (Test-Path $ModelPath)) {
        Write-Error "Model file not found at: $ModelPath"
        exit 1
    }

    Write-Host "==========================================================" -ForegroundColor Cyan
    Write-Host " 6700XT-Afterburner: Local Vulkan 27B Hybrid Server (RX 6700 XT)" -ForegroundColor Yellow
    Write-Host " Endpoint: http://127.0.0.1:8080/v1" -ForegroundColor Green
    Write-Host " Model: Qwen 3.8 27B (UD-Q4_K_XL, MTP Speculative Enabled)" -ForegroundColor White
    Write-Host " GPU Layers: 45 on RX 6700 XT VRAM, remainder in 64GB DDR4" -ForegroundColor White
    Write-Host " Speculation: Native Multi-Token Prediction (K=2, tb=12)" -ForegroundColor White
    Write-Host " KV Cache: Q8_0 + FlashAttention (8k context) + Cache-Reuse" -ForegroundColor White
    Write-Host "==========================================================" -ForegroundColor Cyan

    & "$BinDir\llama-server.exe" `
        -m "$ModelPath" `
        --host 127.0.0.1 `
        --port 8080 `
        -ngl 45 `
        -t 4 `
        -tb 12 `
        -np 1 `
        --spec-type draft-mtp `
        --spec-draft-n-max 2 `
        -fa on `
        -ctk q8_0 `
        -ctv q8_0 `
        -c 8192 `
        --cache-reuse 64
} elseif ($Mode -eq "moe35b") {
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
} else {
    $Host.UI.RawUI.WindowTitle = "6700XT-Afterburner: Dual-Engine Speculative Vulkan Server (RX 6700 XT)"
    if ($Mode -eq "speculative14b") {
        $TargetModel = Join-Path $RootDir "Models\Qwen2.5-Coder-14B-Instruct-GGUF\qwen2.5-coder-14b-instruct-q4_k_m.gguf"
        $DraftModel  = Join-Path $RootDir "Models\Qwen2.5-Coder-0.5B-Instruct\Qwen2.5-Coder-0.5B-Instruct-Q4_0.gguf"
    } else {
        $TargetModel = Join-Path $RootDir "Models\Qwen2.5-Coder-7B-Instruct-GGUF\qwen2.5-coder-7b-instruct-q4_k_m.gguf"
        if ($Mode -eq "healed14l") {
            $DraftModel = Join-Path $RootDir "Models\Qwen2.5-Coder-0.5B-L14-Healed\Qwen2.5-Coder-0.5B-L14-Healed-Q4_0.gguf"
        } elseif ($Mode -eq "dory19l") {
            $DraftModel = Join-Path $RootDir "Models\Qwen2.5-Coder-0.5B-Dory19L-Healed\Qwen2.5-Coder-0.5B-Dory19L-Healed-Q4_0.gguf"
        } elseif ($Mode -eq "healed18l") {
            $DraftModel = Join-Path $RootDir "Models\Qwen2.5-Coder-0.5B-L18-Healed\Qwen2.5-Coder-0.5B-L18-Healed-Q4_0.gguf"
        } else {
            $DraftModel = Join-Path $RootDir "Models\Qwen2.5-Coder-0.5B-Instruct\Qwen2.5-Coder-0.5B-Instruct-Q4_0.gguf"
        }
    }

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
}
