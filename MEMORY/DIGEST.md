# Memory Digest — 6700XT-Afterburner

## Active Context & State
- **GitHub Repository:** https://github.com/6700xtdude-gif/6700XT-Afterburner (`main` branch synced, Issue #1 resolved & closed via PR #2).
- **Host:** Windows 11 Pro, Ryzen 5 5600 (6C/12T), 64 GB DDR4-3200, AMD Radeon RX 6700 XT 12 GB (`Navi 22` / `gfx1031` Vulkan).
- **Active Phase:** Production Ready — Healed 18L Dual-Engine Speculative Server Live on Port 8080.

## Current Production Stack
- **Live Server:**
  - **Web Chat UI (Humans):** `http://127.0.0.1:8080/`
  - **OpenAI-Compatible API (Agents/Tools):** `http://127.0.0.1:8080/v1`
  - **Launch Command:** `.\start_local_server.ps1 -Mode healed18l -K 3` (also supports `-Mode speculative14b` for 100% VRAM 14B+18L at 63.9 t/s, `-Mode speculative` for 24L drafter, and `-Mode moe35b` for 35B-A3B).
- **Active Models Available:**
  - **14B Verifier (Full-VRAM Heavyweight):** `Models/Qwen2.5-Coder-14B-Instruct-GGUF/qwen2.5-coder-14b-instruct-q4_k_m.gguf` (8.37 GiB, 100% in VRAM, **63.9 t/s JSON / 60.9 t/s Code** with speculative decoding — **1.71x speedup** over 37.4 t/s standalone!)
  - **7B Verifier (High-Throughput Target):** `Models/Qwen2.5-Coder-7B-Instruct-GGUF/qwen2.5-coder-7b-instruct-q4_k_m.gguf` (4.68 GB, 100% in VRAM, **96.7 t/s** peak with Healed 18L drafter)
  - **Healed Surgery Draft (`healed18l`):** `Models/Qwen2.5-Coder-0.5B-L18-Healed/Qwen2.5-Coder-0.5B-L18-Healed-Q4_0.gguf` (282 MiB, 18 layers `[0..8, 14..17, 19..23]`, healed via Seam Knowledge Distillation, `97.82%` teacher agreement, `KL = 1.71`)
  - **Unpruned Baseline Draft (`speculative`):** `Models/Qwen2.5-Coder-0.5B-Instruct/Qwen2.5-Coder-0.5B-Instruct-Q4_0.gguf` (330 MiB, 24 layers)
  - **L3-Resident 86 MB Prototype & Dory-Looped 14L (`scripts/test_looped_draft.py`):** 14 physical layers looped to 19 effective layers via Dory anchor re-injection (`95.30%` teacher agreement, `KL = 6.78`).
  - **MoE 35B Verifier (`moe35b`):** `Models/qwen36-UD-Q4_K_XL/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf` (22.8 GB, 15.4 t/s hybrid VRAM/RAM)

## Verified Benchmark Records (RX 6700 XT Vulkan, N=128, Temp=0.0)
- **Standalone 7B Baseline:** `71.4 – 71.7 tokens/sec` (`1,771.8 ms`)
- **Speculative 7B + Healed 18L Surgery Draft ($K=3$):** **`96.7 t/s` JSON (`88.5%` acceptance, `1.35x` Peak 7B Speed!)**, `77.3 t/s` Python Code
- **Standalone 14B Baseline (100% VRAM):** `37.4 – 37.5 tokens/sec`
- **Speculative 14B + Healed 18L Draft ($K=4$):** **`63.9 t/s` JSON (`89.2%` acceptance, `1.71x` Speedup Ratio!)**, **`60.9 t/s` Python Code (`1.62x` with 24L draft / `51.2 t/s` with 18L draft)**
- **MCP Bridge (`llm-bridge`):** Active via `tools/llm_bridge_mcp.py` (`local_llm_chat`, `local_llm_status`, `openrouter_chat` with `openrouter/auto`).
