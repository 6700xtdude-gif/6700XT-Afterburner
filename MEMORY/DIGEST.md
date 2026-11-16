# Memory Digest — 6700XT-Afterburner

## Active Context & State
- **GitHub Repository:** https://github.com/6700xtdude-gif/6700XT-Afterburner (`main` branch synced, working tree clean).
- **Host:** Windows 11 Pro, Ryzen 5 5600 (6C/12T), 64 GB DDR4-3200 (2x32 GB DIMMs; 96 GB 4-DIMM upgrade pending, see `MEMORY/RAM_64gb-2dimm.json`), AMD Radeon RX 6700 XT 12 GB (`Navi 22` / `gfx1031` Vulkan).
- **Active Phase:** Production Ready & Verified — 100% VRAM Resident 27B Speculative Decoding (`Qwen3.8-27B-IQ2_M` verified at **22.61 t/s median**), 35B MoE Hybrid (**16.78 t/s**), 27B Dense Hybrid (**7.54 t/s**), standardized spec-driven benchmarking (`bench/`), and hermetic testing (`tests/`).
- **Server Status:** Configured at `http://127.0.0.1:8080/v1` (`Qwen3.8-27B-IQ2_M.gguf`, 64k context, MTP speculation, 100% VRAM resident). Currently **stopped**; start with `.\start_local_server.ps1 -Mode qwen27b_vram -CtxSize 65536`.

## Memory System (added 2026-11-15)

Durable state lives in git, not in any harness's chat database.

- **Protocol:** `MEMORY/PROTOCOL.md` — the one rule, scope hierarchy, what goes where, session ritual, self-improvement loop.
- **Instruction scopes:** `C:\Users\6700XT\AGENTS.md` (machine) → `C:\Users\6700XT\Documents\AGENTS.md` (documents) → `AGENTS.md` here (project). Vendored `tools/llama.cpp/AGENTS.md` is upstream policy, not project policy.
- **Conformance gate:** `scripts/verify_memory_system.ps1` and `python -m unittest tests.test_memory_contract` (14 tests). Must report `0 fail` before any reimage or hardware change.
- **Backup:** `scripts/backup_memory.ps1` — verified git bundle, WAL-safe `opencode.db` snapshot, Antigravity brain and Pi sessions, plus the out-of-repo AGENTS.md files. 324.7 MB, 10 artifacts.
- **Hardware change record:** `bench/ram_topology.py` writes `MEMORY/RAM_<label>.json` and compares configs.
- **Reimage runbook:** `docs/REIMAGE_RUNBOOK.md`.
- **Vendored-tree rule:** `docs/VENDORED_TREES.md` and `patches/` — local llama.cpp edits are exported, never left dirty.

## Current Execution Status (2026-11-15 Post-Reboot)

- **Hostname:** Verified as `SANDBOX` (`Observed`).
- **Pi Harness:** Natively deployed on Windows (Node.js 22 LTS, Pi v1.5.2). Standing instructions deployed at `~/.pi/agent/AGENTS.md`. `bash` removed from defaultTools, restricted to `["read", "powershell", "edit", "write"]`.
- **llama.cpp Engine:** Vulkan x64 b12427 running `qwen2.5-coder-7b` on `http://127.0.0.1:8080` (33.2 t/s benchmarked).
- **Web Dashboard:** Operational at `http://localhost:3333` with live hardware telemetry, Unload VRAM button, Advanced Settings modal (with Seed randomizer & incrementer), and GitHub benchmark exporter.
- **Model Download Pipeline:**
  1. `DeepSeek-R1-Distill-Qwen-7B-Q4_K_M.gguf` (in progress, ~78%).
  2. `Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf` (queued).
  3. `Qwen2.5-14B-Instruct-Q4_K_M.gguf` (queued).

## Next Actions
1. **Model Evaluation & Benchmark:** Benchmark DeepSeek-R1 Distill 7B reasoning traces and publish results to GitHub benchmark ledger.
2. **Untested Configuration:** Drafter on CPU, verifier on GPU across DDR4-3200 and VRAM tiers.
3. **96 GB Install:** Hardware upgrade planned to 64GB / 96GB.

## Infinity Cache — closed, do not reopen

Falsified by our own data, not by argument: the 91.1 MB `Q2_0` ran **3.1x slower** than the 149.8 MB `Q4_0`, and 895 t/s implies ~80 GB/s against a 384 GB/s bus. The stock 330 MB drafter that *cannot* fit the cache beat every cache-sized variant on held-out prompts. RDNA 2 also exposes no API to pin a buffer in MALL. Details in `MEMORY/LESSONS.md` and EXP-028. The live question is which memory tier to place a drafter in — VRAM or DDR4 — not whether the cache can be used.

## Reading Order

A fresh session reads these in order and stops when it has what it needs.

1. `MEMORY/PROTOCOL.md` — the contract
2. `MEMORY/DIGEST.md` — this file, current state
3. `MEMORY/GAPS_AND_HYPOTHESES.md` — what is still unknown
4. `docs/STRATA_EXECUTION_PLAN_2026-11-13.md` — the architecture plan
5. `docs/PROJECT_9696XT_REPORT.md` — the 96 GB / 2-DIMM efficiency findings
6. `docs/QWEN38_27B_BOTTLENECK_REPORT.md` — where the 27B path saturates
7. `docs/REIMAGE_RUNBOOK.md` — OS and hardware change procedure
8. `docs/VENDORED_TREES.md` — rules for `tools/llama.cpp`
9. `NOTEBOOK/SYSTEM_BASELINE.md` — verified rig facts

Generated, do not hand-edit: `MEMORY/INDEX.json` (machine catalog), `MEMORY/HEALTH.md` (rot report). Rebuild with `python scripts/memory_build.py`.

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
