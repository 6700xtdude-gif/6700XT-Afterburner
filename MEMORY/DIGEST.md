# Memory Digest — 6700XT-Afterburner

## Active Context & State
- **GitHub Repository:** https://github.com/6700xtdude-gif/6700XT-Afterburner (`main` branch synced, working tree clean).
- **Host:** Windows 11 Pro, Ryzen 5 5600 (6C/12T), 64 GB DDR4-3200, AMD Radeon RX 6700 XT 12 GB (`Navi 22` / `gfx1031` Vulkan).
- **Active Phase:** Production Ready & Verified — 100% VRAM Resident 27B Speculative Decoding (`Qwen3.8-27B-IQ2_M` re-verified at **22.43–22.83 t/s median**), Dual-Engine 7B/14B setups (7B at 95.3 t/s, 14B at 60.9–62.3 t/s), standardized spec-driven benchmarking (`bench/`), and hermetic testing (`tests/`).
- **Server Status:** All background processes cleanly stopped; port 8080 and 12 GB GDDR6 VRAM free for clean launch.

## Current Production Stack
- **Governance Anchor ([`AGENTS.md`](file:///c:/Users/6700XT/Documents/Strata/AGENTS.md)):**
  - Defines hardware ground truth, "The Robert Karl Contract" (`ON THE TABLE` vs `NOT ON THE TABLE`), standard ports, and hermetic testing commands.
- **Live Server Launcher (`start_local_server.ps1`):**
  - **Web Chat UI (Humans):** `http://127.0.0.1:8080/`
  - **OpenAI-Compatible API (Agents/Tools):** `http://127.0.0.1:8080/v1`
  - **Default Parameters:** `-CtxSize 65536` (64k context default end-to-end), auto-guard `-ctk q4_0 -ctv q4_0` for $\ge$32k context on 27B models.
  - **Launch Modes:**
    - `.\start_local_server.ps1 -Mode qwen27b_vram -CtxSize 65536` (Recommended 27B: 100% VRAM IQ2_M + MTP speculation at **22.5–25.1 t/s**)
    - `.\start_local_server.ps1 -Mode qwen27b -CtxSize 65536` (Hybrid offload: UD-Q4_K_XL + MTP speculation at **6.3–7.1 t/s**)
    - `.\start_local_server.ps1 -Mode speculative -K 2` (Recommended 7B: 7B + Stock Drafter at **95.3 t/s** JSON / **85.3 t/s** Code)
    - `.\start_local_server.ps1 -Mode speculative14b -K 3` (Recommended 14B: 100% VRAM 14B + Stock Drafter at **62.3 t/s** JSON / **60.9 t/s** Code)
    - `.\start_local_server.ps1 -Mode moe35b` (Hybrid 35B-A3B MoE)
- **Benchmarking & Testing Infrastructure:**
  - `bench/bench_head_to_head.py`: Server-side HTTP benchmark harness with interleaved rounds, warmups, and hardware telemetry.
  - `bench/correctness/parity_eval.py`: Quality gate testing determinism, JSON schema integrity, and Python AST validity.
  - `tests/`: Hermetic test suite (`python -m unittest discover tests`) passing 11/11 tests in 12 ms with zero external/GPU dependencies.
  - `tools/llm_bridge_mcp.py`: Native MCP bridge exposing local llama-server and OpenRouter with `<think>` tag extraction.

## Verified Benchmark Results (RX 6700 XT Vulkan, N=128, Temp=0.0, Interleaved Runs + Warmup)
- **Qwen 3.8 27B (100% VRAM IQ2_M + MTP Speculation):**
  - **Overall Median Decode:** **`22.83 tokens/sec`** (5.7x speedup over 4.0 t/s DDR4 hybrid baseline)
  - **Structured JSON:** **`24.24 t/s`** (76.0% MTP draft acceptance, 174 ms TTFT)
  - **Python Code Generation:** **`24.20 t/s`** (75.7% MTP draft acceptance, 168 ms TTFT)
  - **Reasoning / Logic:** **`19.89 t/s`** (53.4% MTP draft acceptance, 170 ms TTFT)
- **Standalone 7B Baseline:** `71.7 – 72.0 tokens/sec`
- **Speculative 7B + Stock 24L Drafter ($K=2$):** **`95.3 t/s` JSON `[94.9, 95.6]` (`1.33x`), `84.5 t/s` Code `[84.4, 84.6]` (`1.17x`)**
- **Standalone 14B Baseline (100% VRAM):** `37.4 – 37.5 tokens/sec`
- **Speculative 14B + Stock 24L Drafter ($K=3$):** **`62.3 t/s` JSON (`1.67x`), `60.9 t/s` Code (`1.62x`, 85.0% acc)**
- **Held-Out Generalization Audit (Unseen Prompts):**
  - **Stock Untouched 24L Drafter:** **`55.0 – 56.6 t/s` (74.4% – 85.6% acceptance, 1.51x speedup)**
  - **Healed 18L Drafter:** `48.1 t/s` (57.1% acceptance, 1.26x speedup)
  - **Healed 14L Drafter:** `37.0 t/s` (34.2% acceptance, fails to beat 37.4 t/s baseline)
- **Documentation & Scripts:**
  - `docs/YOUTUBE_SCRIPT.md`, `docs/INFINITY_CACHE_HARDWARE_MATRIX.md`, `docs/14B_FULL_VRAM_SPECULATIVE.md`, `docs/DORY_LOOPED_96MB_SURGERY.md`, `docs/DRAGNET_60S_SHORT_SCRIPT.md`.
