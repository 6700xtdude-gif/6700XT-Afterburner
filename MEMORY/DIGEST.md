# Memory Digest — 6700XT-Afterburner

## Active Context & State
- **GitHub Repository:** https://github.com/6700xtdude-gif/6700XT-Afterburner (`main` branch synced, working tree clean).
- **Host:** Windows 11 Pro, Ryzen 5 5600 (6C/12T), 32 GB DDR4-3200 (2x16 GB DIMMs), AMD Radeon RX 6700 XT 12 GB (`Navi 22` / `gfx1031` Vulkan).
- **Active Phase:** Production Ready & Verified — 100% VRAM Resident 27B Speculative Decoding (`Qwen3.8-27B-IQ2_M` verified at **22.61 t/s median**), 35B MoE Hybrid (**16.78 t/s**), 27B Dense Hybrid (**7.54 t/s**), standardized spec-driven benchmarking (`bench/`), and hermetic testing (`tests/`).
- **Server Status:** Active at `http://127.0.0.1:8080/v1` running `Qwen3.8-27B-IQ2_M.gguf` (64k context, MTP speculation enabled, 100% VRAM resident).

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
- **Host Configuration Matrix (32 GB DDR4 vs 64 GB DDR4):**
  - **Qwen 3.8 27B IQ2_M (100% VRAM Saturation + MTP Speculation):**
    - **Overall Median Decode (32 GB):** **`22.61 tokens/sec`** (vs 22.43 t/s on 64 GB, identical silicon throughput)
    - **Structured JSON:** **`24.22 t/s`** (76.0% MTP accept, 163 ms TTFT)
    - **Python Code Generation:** **`23.69 t/s`** (72.6% MTP accept, 176 ms TTFT)
    - **Reasoning / Logic:** **`20.29 t/s`** (55.5% MTP accept, 166 ms TTFT)
    - **Peak Process RSS:** 12,928.9 MB
  - **Qwen 3.6 35B A3B UD-Q4_K_XL (Sparse MoE Hybrid: 16 VRAM / 25 DDR4):**
    - **Overall Median Decode (32 GB):** **`16.78 tokens/sec`** (vs 16.39 t/s on 64 GB)
    - **Peak Process RSS:** 21,530.5 MB (~21.0 GB; fully resident with zero SSD disk paging)
    - **Architectural Advantage:** Streams only ~3.5 GB active parameters/token, 2.23x faster than dense 27B hybrid.
  - **Qwen 3.8 27B UD-Q4_K_XL (Dense Hybrid Offload: 45 VRAM / 20 DDR4):**
    - **Overall Median Decode (32 GB):** **`7.54 tokens/sec`** (vs **6.13 t/s** on 64 GB 4-DIMM, **+23.0% speedup**)
    - **Peak Process RSS:** 20,935.2 MB (~20.4 GB; safely fits in 32 GB RAM with ~5.4 GB headroom)
    - **2-DIMM IMC Advantage:** Ryzen 5 5600 memory controller achieves lower latency and higher effective bandwidth on 2 single-rank DIMMs (1 DPC, 1T command rate) compared to 4 DIMMs.
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
