# AGENTS.md — Strata / 6700XT-Afterburner Developer & Agent Directives

> **Canonical Invariant Anchor:** All autonomous agents, subagents, and human contributors working in this repository must adhere to the rules, hardware limits, and conventions detailed below. Do not guess, deviate, or invent unapproved configurations.

---

## 1. Hardware Ground Truth & Silicon Invariants

| Component | Hardware Specification | Architectural Implication |
| :--- | :--- | :--- |
| **GPU** | AMD Radeon RX 6700 XT 12 GB (Navi 22, `gfx1031`) | 192-bit GDDR6 bus delivering **~384 GB/s** peak memory bandwidth. 96 MB on-die Infinity Cache (>1 TB/s). |
| **CPU** | AMD Ryzen 5 5600 (6 Cores / 12 Threads) | Dual-channel DDR4-3200 system memory delivering **~32 GiB/s** effective bandwidth. |
| **VRAM Limit** | **12,288 MB Total** (~11,200 MB usable for model + KV) | Models larger than ~10.5 GB will spill into DDR4 over PCIe 4.0 x16. |
| **Silicon Choke Rule** | **The DDR4 Cliff (12x penalty)** | When a model spills even a fraction of layers into system RAM, single-token autoregressive decode stalls on the 32 GiB/s DDR4 bus. The GPU completes its slice in ~25 ms and idles for ~190 ms (causing cold ~55 °C temps and <15% GPU load). **Primary directive: Keep models 100% VRAM resident or accelerate hybrid offload via Multi-Token Prediction (MTP) speculation.** |

---

## 2. Scope Boundaries (The Robert Karl Contract)

### ON THE TABLE:
- **100% VRAM Quantization:** Sizing large models (27B+) via importance matrix (`IQ2_M`, sub-3-bit) to guarantee zero DDR4 spilling.
- **Speculative Acceleration:** Leveraging native MTP drafting (`--spec-type draft-mtp -K 2`) or dual-tier cache-resident draft engines (JEV).
- **Asymmetric Threading:** Using `-t 4 -tb 12` during hybrid offload so verification batches saturate all CPU cores while single-token decode avoids thread contention.
- **Interleaved Benchmarking:** Alternating test execution order with warm-up cycles to eliminate OS cache bias and thermal variance.
- **Parity & Correctness Verification:** Token-level distribution and top-20 logit checks to mathematically verify quantization and draft acceptance quality.
- **Hermetic Testing:** Mocked transports and factory fixtures in `tests/` that run in <3 seconds without requiring GPU or model weights.

### NOT ON THE TABLE:
- **No Destructive Operations:** Never delete model files, checkpoints, or cache directories without explicit confirmation.
- **No Invented Linters or CI bloat:** Do not add arbitrary linters, pre-commit hooks, or complex package managers unless requested. Plain Python (`pytest`, standard library) is the standard.
- **No Uninstrumented Benchmarks:** Never quote single-run token rates. Benchmarks must report warm-up state, median timings across rounds, and hardware telemetry (VRAM, temperature).

---

## 3. Standard Ports & Server Architecture

- **Port `8080`:** Default production local `llama-server.exe` instance (OpenAI-compatible REST API at `http://127.0.0.1:8080/v1`).
- **Port `8081`:** Dedicated secondary draft server (reserved for two-process speculative decoding / JEV setups).
- **Launcher:** Always launch through [`start_local_server.ps1`](file:///c:/Users/6700XT/Documents/Strata/start_local_server.ps1):
  ```powershell
  # 100% VRAM 27B model (IQ2_M + MTP speculation, default 64k context)
  .\start_local_server.ps1 -Mode qwen27b_vram -CtxSize 65536

  # Hybrid offload 27B model (Q4_K_XL + MTP speculation, 64k context)
  .\start_local_server.ps1 -Mode qwen27b -CtxSize 65536

  # Verified 14B model (Q4_K_M, 64k context)
  .\start_local_server.ps1 -Mode speculative14b -CtxSize 65536
  ```
- **End-to-End Context Consistency Invariant:** Agent harnesses (such as Pi) pass extensive tool declarations and prompts that exceed 8k tokens on the first call. The server context (`-c $CtxSize`, default 65536) must match the client-side configuration (`models.json: contextWindow: 65536`) to prevent HTTP 400 `exceed_context_size_error`. On 27B models with 64k context, `start_local_server.ps1` automatically applies `-ctk q4_0 -ctv q4_0` to preserve the 12 GB VRAM budget.

---

## 4. Testing & Verification Commands

Run all commands from the repository root:

- **Hermetic Unit Tests (Offline, <3 seconds, no GPU required):**
  ```powershell
  python -m pytest tests/
  ```
- **Run Standardized Head-to-Head Benchmark Suite:**
  ```powershell
  python bench/bench_head_to_head.py --config bench/configs/rx6700xt_evals.json --rounds 3
  ```
- **Verify Quantization & Draft Parity:**
  ```powershell
  python bench/correctness/parity_eval.py --target http://127.0.0.1:8080/v1 --prompt-corpus bench/corpus/standard_prompts.json
  ```
- **Check Live Server Health:**
  ```powershell
  Invoke-RestMethod -Uri http://127.0.0.1:8080/health
  ```
