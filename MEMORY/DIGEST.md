# Memory Digest — 6700XT-Afterburner

## Active Context & State
- **GitHub Repository:** https://github.com/6700xtdude-gif/6700XT-Afterburner (`main` branch synced with **PR #2**, **PR #3**, and **PR #4** merged, plus YouTube Show script & Infinity Cache hardware compatibility matrix).
- **Host:** Windows 11 Pro, Ryzen 5 5600 (6C/12T), 64 GB DDR4-3200, AMD Radeon RX 6700 XT 12 GB (`Navi 22` / `gfx1031` Vulkan).
- **Active Phase:** Production Ready — Dual-Engine Speculative Decoding using Stock Untouched 24L Drafter (7B at 95.3 t/s, 14B at 60.9–62.3 t/s) with Model Surgery reframed as a documented negative result following held-out generalization audit.

## Current Production Stack
- **Live Server Launcher (`start_local_server.ps1`):**
  - **Web Chat UI (Humans):** `http://127.0.0.1:8080/`
  - **OpenAI-Compatible API (Agents/Tools):** `http://127.0.0.1:8080/v1`
  - **Launch Modes:**
    - `.\start_local_server.ps1 -Mode speculative -K 2` (Recommended: 7B + Stock Untouched 24L Drafter at **95.3 t/s** JSON / **85.3 t/s** Code)
    - `.\start_local_server.ps1 -Mode speculative14b -K 3` (Recommended: 100% VRAM 14B + Stock Drafter at **62.3 t/s** JSON / **60.9 t/s** Code)
    - `.\start_local_server.ps1 -Mode healed14l -K 3` (Experimental surgery draft: calibration-overfit, 34.2% on unseen prompts)
    - `.\start_local_server.ps1 -Mode dory19l -K 3` (Experimental looped surgery draft: 32.1% on unseen prompts)
    - `.\start_local_server.ps1 -Mode moe35b` (Hybrid 35B-A3B MoE)

## Verified Benchmark Results (RX 6700 XT Vulkan, N=128, Temp=0.0, 3 Runs + 1 Warmup)
- **Standalone 7B Baseline:** `71.7 – 72.0 tokens/sec`
- **Speculative 7B + Stock 24L Drafter ($K=2$):** **`95.3 t/s` JSON `[94.9, 95.6]` (`1.33x`), `84.5 t/s` Code `[84.4, 84.6]` (`1.17x`)**
- **Standalone 14B Baseline (100% VRAM):** `37.4 – 37.5 tokens/sec`
- **Speculative 14B + Stock 24L Drafter ($K=3$):** **`62.3 t/s` JSON (`1.67x`), `60.9 t/s` Code (`1.62x`, 85.0% acc)**
- **Held-Out Generalization Audit (Unseen Prompts):**
  - **Stock Untouched 24L Drafter:** **`55.0 – 56.6 t/s` (74.4% – 85.6% acceptance, 1.51x speedup)**
  - **Healed 18L Drafter:** `48.1 t/s` (57.1% acceptance, 1.26x speedup)
  - **Healed 14L Drafter:** `37.0 t/s` (34.2% acceptance, fails to beat 37.4 t/s baseline)
  - **Dory-Looped 19L Drafter:** `34.7 t/s` (32.1% acceptance, fails to beat baseline)
- **Documentation & Show Script:** `docs/YOUTUBE_SCRIPT.md`, `docs/INFINITY_CACHE_HARDWARE_MATRIX.md`, `docs/14B_FULL_VRAM_SPECULATIVE.md`, `docs/DORY_LOOPED_96MB_SURGERY.md`.
