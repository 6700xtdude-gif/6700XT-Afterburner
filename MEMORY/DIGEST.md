# Memory Digest — 6700XT-Afterburner

## Active Context & State
- **GitHub Repository:** https://github.com/6700xtdude-gif/6700XT-Afterburner (`main` branch synced, Issue #1 resolved & closed via PR #2).
- **Host:** Windows 11 Pro, Ryzen 5 5600 (6C/12T), 64 GB DDR4-3200, AMD Radeon RX 6700 XT 12 GB (`Navi 22` / `gfx1031` Vulkan).
- **Active Phase:** Production Ready — Healed 18L Dual-Engine Speculative Server Live on Port 8080.

## Current Production Stack
- **Live Server:**
  - **Web Chat UI (Humans):** `http://127.0.0.1:8080/`
  - **OpenAI-Compatible API (Agents/Tools):** `http://127.0.0.1:8080/v1`
  - **Launch Command:** `.\start_local_server.ps1 -Mode healed18l -K 3` (also supports `-Mode speculative` for 24L drafter and `-Mode moe35b` for 35B-A3B).
- **Active Models in VRAM (~5.1 GB combined out of 12 GB):**
  - **Verifier (Target):** `Models/Qwen2.5-Coder-7B-Instruct-GGUF/qwen2.5-coder-7b-instruct-q4_k_m.gguf` (4.68 GB, 100% in VRAM)
  - **Healed Surgery Draft (`healed18l`):** `Models/Qwen2.5-Coder-0.5B-L18-Healed/Qwen2.5-Coder-0.5B-L18-Healed-Q4_0.gguf` (282 MiB, 18 layers `[0..8, 14..17, 19..23]`, healed via Seam Knowledge Distillation, `97.82%` teacher agreement, `KL = 1.71`)
  - **Unpruned Baseline Draft (`speculative`):** `Models/Qwen2.5-Coder-0.5B-Instruct/Qwen2.5-Coder-0.5B-Instruct-Q4_0.gguf` (330 MiB, 24 layers)
  - **L3-Resident 86 MB Prototype:** `Models/Qwen2.5-Coder-0.5B-L14-Pruned/Qwen2.5-Coder-0.5B-Pruned-Q2_0.gguf` (85.9 MiB, 14 layers + 32k vocab, 895.4 t/s standalone)
  - **MoE 35B Verifier (`moe35b`):** `Models/qwen36-UD-Q4_K_XL/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf` (22.8 GB, 15.4 t/s hybrid VRAM/RAM)

## Verified Benchmark Records (RX 6700 XT Vulkan, N=128, Temp=0.0)
- **Standalone 7B Baseline:** `71.4 – 71.7 tokens/sec` (`1,771.8 ms`)
- **Speculative 7B + Unpruned 24L Draft ($K=2,3$):** `95.5 t/s` JSON (`94.3%` acceptance, `1.33x`), `85.8 t/s` Python Code (`78.8%` acceptance, `1.20x`)
- **Speculative 7B + Healed 18L Surgery Draft ($K=3$):** **`96.7 t/s` JSON (`88.5%` acceptance, `1,313.7 ms`, `1.35x` Peak Record!)**, `77.3 t/s` Python Code (`63.4%` acceptance)
- **MCP Bridge (`llm-bridge`):** Active via `tools/llm_bridge_mcp.py` (`local_llm_chat`, `local_llm_status`, `openrouter_chat` with `openrouter/auto`).
