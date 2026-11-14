# Memory Digest

## Active Context & State
- **Project:** Strata (Navi 22 Hardware-Software Co-Design for AMD Radeon RX 6700 XT)
- **Host:** Windows 11 Pro, Ryzen 5 5600, 64 GB DDR4-3200, RX 6700 XT 12 GB.
- **Active Phase:** Phase 5 Complete (Dual-Engine Speculative Server Live on Port 8080 & Agentic Loop Verified).

## Current Status
- **Dual-Engine Speculative Server (Online at http://127.0.0.1:8080/v1):**
  - **Verifier:** `Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf` (4.68 GB, 100% in 12 GB VRAM)
  - **Draft Engine:** `Qwen2.5-Coder-0.5B-Instruct-Q4_0.gguf` (330 MB, 100% in VRAM)
  - **Live Performance:** 56.8 t/s sustained streaming, full 40-token tool formulation in 687 ms.
  - **Draft Acceptance Rate ($\alpha$):** **71.1%** (32/45 accepted)
  - **Prompt Speed:** ~300 tokens/sec
  - **Memory Footprint:** ~5.2 GB total VRAM consumed (leaving 6.8 GB headroom for long KV cache)
- **Local Agentic Capability:** Verified live. Model autonomously formulated PowerShell execution to inspect filesystem, execute command natively on Windows, and synthesize results.
- **MoE Verifier Option B:** `Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf` (22.8 GB, hybrid VRAM/RAM offload).
- **L3-Resident Draft Artifacts:** 14-layer 85.9 MiB Q2_0 model pre-built for custom translation kernel.
- **Runtime Configuration:**
  - Context window: 4,096 tokens (`-c 4096`)
  - VRAM Offload: 16 layers on RX 6700 XT Vulkan, remainder in 64GB DDR4 (`-ngl 16`)
  - KV Cache: `q8_0` with Flash Attention (`-fa on`)
  - Sampling: Temp 0.70, Top-K 40, Top-P 0.95, Min-P 0.05, Seed 42
- **OpenRouter Default:** Set to `openrouter/auto` (tested live).
