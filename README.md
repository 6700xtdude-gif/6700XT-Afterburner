# 6700XT-Afterburner 🚀

> [!NOTE]
> **Community & Transparency Disclaimer:** This repository, documentation, and benchmark suite were compiled and posted with AI assistance. The author (`6700XT`) is actively learning AI architecture, hardware limits, and local LLM benchmarking. Please take all data, theories, and conclusions with a grain of salt. As empirical validation and domain confidence grow, this notice will be updated.

**Dual-Engine Speculative Decoding & Hardware Reality Audit for the AMD Radeon RX 6700 XT (`Navi 22` / `gfx1031` Vulkan)**

> **Core Mission:** Overcome the 192-bit GDDR6 memory bus bottleneck (~384 GB/s) on the 12 GB AMD Radeon RX 6700 XT by pairing a 100% VRAM-resident **Qwen 2.5 Coder 7B (`Q4_K_M`)** verifier with an ultra-fast **0.5B (`Q4_0`)** stock draft engine—and auditing sub-90 MB L3-resident model surgery inside Navi 22's **96 MB Infinity Cache** (>1 TB/s SRAM) as a rigorous negative result.

---

## 📊 Empirical Benchmark Results (RX 6700 XT 12 GB — Vulkan Backend)

All benchmarks were executed via [`tools/benchmark_speculative_suite.py`](tools/benchmark_speculative_suite.py) at deterministic temperature (`--temp 0.0`, `-fa on`, `-ngl 99 -ngld 99`, `-c 2048`, $N = 128$ generated tokens, `llama.cpp` build `b12374` Vulkan). 

> [!NOTE]
> **Multi-Run Variance & Warmup Methodology:** To guard against single-trial noise, all metrics report **3 timed trials following 1 untimed warmup run**. Mean throughput is reported with empirical spread `[min, max]`. Differences of $\le 1.5\text{--}2.0\text{ t/s}$ on $N=128$ tokens fall within run-to-run variance on Windows WDDM. Raw multi-run JSON results are available in [`MEMORY/BENCHMARK_RESULTS.json`](MEMORY/BENCHMARK_RESULTS.json).

| Workload Category | Mode / Config | Generation Speed (Mean & Spread) | Latency (128 Tok) | Draft Acceptance ($\alpha$) | Speedup vs Baseline |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Structured JSON / Schema**<br>*(Tool calls, schemas, JSON)* | **Baseline Standalone 7B**<br>Speculative ($K=2$)<br>Speculative ($K=3$)<br>Speculative ($K=4$) | 71.9 t/s `[71.8, 71.9]`<br>**95.3 t/s `[94.9, 95.6]`**<br>**92.9 t/s `[92.1, 93.4]`**<br>**93.8 t/s `[93.0, 94.2]`** | 1,771.8 ms<br>**1,330.2 ms**<br>**1,366.9 ms**<br>**1,354.6 ms** | —<br>**94.3%**<br>**89.3%**<br>**92.6%** | Baseline (1.00x)<br>**1.33x (+32.5%)**<br>**1.29x (+29.2%)**<br>**1.30x (+30.5%)** |
| **Code Generation**<br>*(Python Quicksort algorithm)* | **Baseline Standalone 7B**<br>Speculative ($K=2$)<br>Speculative ($K=3$)<br>Speculative ($K=4$) | 72.0 t/s `[71.9, 72.0]`<br>**84.5 t/s `[84.4, 84.6]`**<br>**85.3 t/s `[85.0, 85.5]`**<br>73.8 t/s `[73.1, 74.2]` | 1,779.6 ms<br>**1,516.1 ms**<br>**1,480.7 ms**<br>1,720.9 ms | —<br>**77.0%**<br>**78.8%**<br>66.7% | Baseline (1.00x)<br>**1.17x (+17.4%)**<br>**1.18x (+18.5%)**<br>1.03x (+2.5%) |
| **Technical Reasoning**<br>*(Freeform system architecture)* | **Baseline Standalone 7B**<br>Speculative ($K=2$)<br>Speculative ($K=3$)<br>Speculative ($K=4$) | 71.7 t/s `[71.6, 71.8]`<br>**74.7 t/s `[74.6, 74.8]`**<br>67.9 t/s `[67.2, 68.3]`<br>61.5 t/s `[60.8, 62.1]` | 1,776.3 ms<br>**1,721.6 ms**<br>1,869.8 ms<br>2,063.4 ms | —<br>**61.9%**<br>55.6%<br>51.8% | Baseline (1.00x)<br>**1.04x (+4.2%)**<br>0.95x (-5.3%)<br>0.86x (-14.2%) |

---

## 🔬 Key Hardware & Architecture Findings

### 1. Why Stock Speculative Decoding Succeeds on the 192-bit Bus
Autoregressive LLM decoding (`batch_size = 1`) is strictly memory-bandwidth bound. Every single token generated requires streaming ~4.68 GB of 7B weights across the RX 6700 XT's 192-bit GDDR6 bus (~384 GB/s), capping standalone generation around **71.7 tokens/sec**.

By running **stock, untouched `Qwen2.5-Coder-0.5B-Instruct-Q4_0` (330 MB, 24L)** alongside `Qwen2.5-Coder-7B-Instruct-Q4_K_M` (4.68 GB)—consuming just **~5.2 GB of 12 GB VRAM combined**—the 0.5B model drafts $K = 2\text{--}3$ tokens rapidly, and the 7B model verifies them in a single batched forward pass (1 target weight read instead of 3–4).
* **Speedup:** Achieves **95.3 t/s (+32.5%)** on JSON and **85.3 t/s (+18.5%)** on Python code with zero model surgery required.
* **Deterministic Fidelity:** Output is **identical at temp 0 in testing** to standalone 7B. *(Note: While speculative verification guarantees greedy algorithmic equivalence, batched GEMM floating-point accumulation order can introduce minute numerical differences in non-deterministic or different batching regimes).*

---

### 2. Model Surgery & Layer Pruning: A Documented Negative Result
Initially, zero-shot layer pruning (`24L -> 14L`, dropping layers `[8..17]`) was attempted to compress the drafter into Navi 22's **96 MB Infinity Cache** (<90 MB in `Q2_0`). While this pruned model generated tokens at 895 t/s standalone, it produced disastrous speculative performance (`0%` acceptance in `Q2_0`, `21.2%` in `Q4_0`) due to severe logit drift (`KL = 269.41`).

To investigate whether layer surgery could be rehabilitated, we applied ShortGPT Block Influence profiling ([`scripts/profile_layer_importance.py`](scripts/profile_layer_importance.py)) and seam knowledge distillation ([`scripts/heal_draft_model.py`](scripts/heal_draft_model.py)) on a 4-paragraph calibration corpus. While this restored alignment on matching calibration prompts, **systematic generalization testing revealed this to be a negative result**:

> [!WARNING]
> **Audit Finding — Calibration Overfitting on Pruned Drafters ([`tools/verify_blind_heldout.py`](tools/verify_blind_heldout.py)):**
> * **Distillation Overfit:** Pruned drafters (`Healed 14L` and `Dory-Looped 19L`) achieved synthetic high throughput (**99.8 t/s** on 7B, **64.6 t/s** on 14B) **only** on prompts matching their 4-paragraph calibration corpus. 
> * **Generalization Collapse:** When evaluated on **held-out unseen prompts** (e.g., thread-safe LRU cache, Dijkstra, PostgreSQL CTEs), draft acceptance collapsed to **34.2%** on `Healed 14L` and **32.1%** on `Dory 19L`, resulting in throughput (**34.7–37.0 t/s**) that **failed to beat standalone 14B baseline (37.4 t/s)**.
> * **Stock Drafter Superiority:** The unpruned, stock 24-layer `0.5B` drafter generalized robustly across all unseen domains, maintaining **74.4%–85.6% acceptance (55.0–56.6 t/s, 1.51x speedup)** without any fine-tuning.

#### Calibration Prompt Matrix (Single-Prompt Calibration Results vs. Unseen Generalization):

| Draft Engine Variant | Calibration Teacher KL | Calibration Acc ($\alpha$) (JSON / Code) | Calibration Speed (JSON / Code) | Held-Out Unseen Acc ($\alpha$) | Held-Out Unseen Speed | Real-World Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Stock Untouched 24L (`Q4_0`)** | **0.00** | **88.5% / 78.8%** | **95.3 t/s / 85.3 t/s** | **74.4% – 85.6%** | **55.0 – 56.6 t/s (1.51x)** | **Production Recommended** |
| **Healed 18L (6L cut, Distilled)** | 1.71 | 88.5% / 63.4% | 96.7 t/s / 77.3 t/s | 57.1% | 48.1 t/s (1.26x) | Degraded Generalization |
| **Healed 14L (10L cut, Distilled)** | 8.35 | 88.5% / 49.3% | 99.8 t/s / 67.9 t/s | 34.2% | 37.0 t/s (0.99x) | **Failed Negative Result** (Overfit) |
| **Dory-Looped 19L (10L cut+loop)** | 6.78 | 85.8% / 56.4% | 92.5 t/s / 70.9 t/s | 32.1% | 34.7 t/s (0.93x) | **Failed Negative Result** (Overfit) |

*(Note: Differences like 95.3 vs 96.7 t/s on JSON are within normal run-to-run variance of $\pm 1.5$ t/s and should not be interpreted as performance advantages).*

---

### 3. Scaling Up to 14B in 100% VRAM (Stock Drafter Dominates Code)
Because speculative decoding amortizes target weight reads across accepted tokens, speedup ratios scale even higher on larger models that still fit inside the RX 6700 XT's 12 GB VRAM (`Qwen2.5-Coder-14B-Instruct-Q4_K_M`, 8.37 GiB + 0.33 GiB stock drafter = ~9.45 GiB total via [`tools/benchmark_14b_vram.py`](tools/benchmark_14b_vram.py) & [`docs/14B_FULL_VRAM_SPECULATIVE.md`](docs/14B_FULL_VRAM_SPECULATIVE.md)):

| 14B Configuration (RX 6700 XT 12 GB Vulkan) | Structured JSON Speed ($\alpha$) | Python Code Speed ($\alpha$) | Real Speedup vs. Standalone 14B | Generalization Integrity |
| :--- | :---: | :---: | :---: | :--- |
| **Standalone 14B (`Q4_K_M`, 48L, 8.37 GiB)** | 37.4 t/s (—) | 37.5 t/s (—) | Baseline (1.00x) | Baseline |
| **14B + Stock Untouched 24L 0.5B ($K=3$)** | **62.3 t/s (88.5%)** | **60.9 t/s (85.0%)** | **1.67x (JSON) / 1.62x (Code)** | **Superior Generalization** |
| **14B + Healed 18L 0.5B Draft ($K=3$)** | 63.0 t/s (86.7%) | 51.2 t/s (62.9%) | 1.68x (JSON) / 1.37x (Code) | Moderate Degradation |
| **14B + Healed 14L 0.5B Draft ($K=3$)** | 64.6 t/s (86.7%)* | 43.7 t/s (46.5%) | 1.73x (JSON)* / 1.17x (Code) | *Overfit to Calibration Prompts |

*On Python code generation, the **stock untouched 24L drafter achieves 60.9 t/s versus only 43.7 t/s for the healed 14L drafter**—a +39.4% advantage for the stock model over the surgical model. Layer surgery does not justify itself in general code workloads.*

---

### 4. Hardware Reality Check: Infinity Cache Residency vs. Execution Overhead
Initial surgical goals were guided by the hypothesis that fitting a model below Navi 22's **96 MB Infinity Cache** would allow generation at on-die SRAM speeds (>1 TB/s). However, hardware analysis reveals this claim was unsubstantiated:

1. **Bandwidth Discrepancy:** The 14-layer ~90 MB model ran at **895 tokens/sec** standalone. At 90 MB per forward pass, 895 t/s equates to streaming only ~80.5 GB/s of weights. This is **far below the ~4,000 tokens/sec that the 384 GB/s GDDR6 bus would theoretically permit**, and orders of magnitude below the >1,000 GB/s bandwidth of on-die SRAM.
2. **Overhead Bounds:** At batch size 1 with small parameter counts, inference latency on Vulkan is bounded by **kernel launch overhead, pipeline dispatch, and sequential layer sync latency**, not memory bandwidth. 
3. **Absence of Cache Hardware Counters:** Actual cache residency inside AMD's MALL (Memory-Attached Last-Level) cache cannot be asserted from generation speed alone; doing so requires hardware performance counter profiling (e.g., via AMD Radeon GPU Profiler / RGP or `rocprofiler` tracking L3 hit/miss rates). 

---

### 5. Dory-Style Looping Generalization Audit
The attempt to convert the 14-layer physical drafter into a 19-effective-layer drafter via latent-recurrent looping (`[5..9]` looped $2\times$ with a 3.5 KB gated anchor re-injection) showed a modest calibration-prompt acceptance gain (lifting Python Quicksort acceptance from 49.3% to 56.4%, +7.1%).

However, **this gain rested entirely on a single prompt**. When evaluated across diverse held-out tasks (e.g., unseen database queries, concurrency primitives, and algorithmic reasoning in [`tools/verify_blind_heldout.py`](tools/verify_blind_heldout.py)), the Dory-looped model showed no statistically significant generalization benefit over linear 14L (32.1% vs 34.2%), and remained drastically inferior to the stock 24L drafter (74.4%–85.6%).

---

### 6. Cross-Generation Tokenizer Barrier
When pairing `Qwen3.6-35B-A3B` (248k `qwen35` vocabulary) with `Qwen2.5-0.5B` (152k `qwen2` vocabulary), stock `llama.cpp` rejects speculation (`common_specu: the target and draft vocabs are not compatible`). Bridging Qwen 2.5 drafters to Qwen 3.6 MoE targets requires runtime token ID remapping via `draft_to_verifier_id.bin`.

---

### 7. High-Context 27B/35B Inference & Project 9696XT Audit
Empirical audit of high-context, large-parameter models on the RX 6700 XT 12GB + Ryzen 5 5600:
* **100% VRAM 27B Saturation:** `Qwen3.8-27B-IQ2_M` with native MTP speculation fits entirely inside 12 GB GDDR6 (65/65 layers on GPU), delivering **`22.26–22.61 tokens/sec`** decode (JSON **24.25 t/s**, Code **23.15–23.7 t/s**) with 160 ms TTFT.
* **Sparse MoE Hybrid Offload:** `Qwen3.6-35B-A3B UD-Q4_K_XL` (Alex's model) achieves **`16.78 tokens/sec`** on 32 GB 2-DIMM and **`16.26 tokens/sec`** on 64 GB 2-DIMM (with ~40 GB free RAM headroom) on Vulkan with 115–124 ms TTFT, streaming only ~3.5 GB active parameters/token.
* **The 2-DIMM Memory Controller Advantage:** On the Ryzen 5 5600, running 2 single-rank DIMMs (`2x16GB`, 1 DPC, 1T command rate) yields **`7.54 tokens/sec`** on dense 27B hybrid offload—a **+23.0% speedup** over 4-DIMM kits (**6.13 t/s**)—while dual-rank `2x32GB` (64 GB 2-DIMM) runs at **`5.50 t/s`** with 38+ GB free physical margin for 64k+ context workloads.
* Full report: [`docs/PROJECT_9696XT_REPORT.md`](docs/PROJECT_9696XT_REPORT.md).

---

### 8. AfterBurner Local Control Center, Pi Agent & Windows Launchers
Zero-dependency local tooling built specifically for native Windows 11 administration on the RX 6700 XT (`http://127.0.0.1:8090`):
* **AfterBurner Telemetry Dashboard ([`dashboard/server.py`](dashboard/server.py), [`dashboard/index.html`](dashboard/index.html), [`Launch_Dashboard.bat`](Launch_Dashboard.bat)):** Real-time local web control panel bound for localhost/LAN access with GPU/VRAM/KV-cache telemetry, locked-dimension 4-mode chart tiles (`BAR`, `GAUGE`, `GRAPH`, `HIST`), prompt staging with spellcheck, and browser **Auto-Speak TTS**.
* **Windows-Native Pi Agent & Server Launchers ([`Launch_Pi.bat`](Launch_Pi.bat), [`start_local_server.ps1`](start_local_server.ps1), [`start_pi_afterburner.ps1`](start_pi_afterburner.ps1), [`scripts/launch_afterburner_pi.ps1`](scripts/launch_afterburner_pi.ps1)):** Windows PowerShell and `.bat` launchers running `llama-server.exe` (`-Mode qwen27b_vram`) at **65,536 (64k) context** with `--reasoning-budget 256` (preserving inter-turn `<think>` traces without context runaway).
* **CoreAudio Device Switcher ([`scripts/switch_audio_mode.ps1`](scripts/switch_audio_mode.ps1)):** Windows COM toggle isolating default playback/communications to a Bluetooth headset or switching back to monitor audio.

---

## 🛠️ Repository Structure

* [`start_local_server.ps1`](start_local_server.ps1) — Production Windows PowerShell launcher for the RX 6700 XT Vulkan `llama-server.exe` (`-Mode qwen27b_vram`, `qwen27b`, `moe35b`, `speculative`, or `speculative14b`).
* [`Launch_Dashboard.bat`](Launch_Dashboard.bat) & [`dashboard/`](dashboard/) — Windows launcher and zero-dependency Python/HTML local telemetry dashboard + Pi voice/prompt control center.
* [`Launch_Pi.bat`](Launch_Pi.bat), [`start_pi_afterburner.ps1`](start_pi_afterburner.ps1) & [`scripts/launch_afterburner_pi.ps1`](scripts/launch_afterburner_pi.ps1) — Windows launchers for the Pi coding agent connected to `http://127.0.0.1:8080/v1`.
* [`scripts/switch_audio_mode.ps1`](scripts/switch_audio_mode.ps1) — Windows CoreAudio COM toggle for headset vs. monitor audio routing.
* [`tests/test_dashboard_server.py`](tests/test_dashboard_server.py) — Unit tests for the AfterBurner telemetry dashboard server.
* [`tools/benchmark_speculative_suite.py`](tools/benchmark_speculative_suite.py) — Automated benchmark suite with multi-run variance testing (warmup + 3 runs, mean and min/max spread) across Code, JSON, and Reasoning.
* [`tools/verify_blind_heldout.py`](tools/verify_blind_heldout.py) — Rigorous blind generalization audit testing stock vs surgical models across unseen held-out tasks.
* [`tools/llm_bridge_mcp.py`](tools/llm_bridge_mcp.py) — Zero-dependency MCP server bridging local RX 6700 XT Vulkan models into agentic IDEs.
* [`tools/test_local_tool_calling.py`](tools/test_local_tool_calling.py) — End-to-end agentic tool-calling test harness (PowerShell tool calls executed in <700 ms).
* [`scripts/vocab_prune.py`](scripts/vocab_prune.py) & [`scripts/layer_prune.py`](scripts/layer_prune.py) — Model surgery scripts for slicing vocabulary and transformer layers (documented negative result).
* [`docs/14B_FULL_VRAM_SPECULATIVE.md`](docs/14B_FULL_VRAM_SPECULATIVE.md) — 14B full-VRAM empirical guide and Windows WDDM paging cliff analysis.
* [`docs/DORY_LOOPED_96MB_SURGERY.md`](docs/DORY_LOOPED_96MB_SURGERY.md) — Architecture and negative result audit of Dory-style layer looping.
* [`docs/INFINITY_CACHE_HARDWARE_MATRIX.md`](docs/INFINITY_CACHE_HARDWARE_MATRIX.md) — Hardware analysis comparing cache bandwidth vs kernel overhead across modern architectures.
* [`MEMORY/`](MEMORY/) — Complete engineering lab notebook ([`EXPERIMENT_LOG.md`](MEMORY/EXPERIMENT_LOG.md), [`LESSONS.md`](MEMORY/LESSONS.md), [`BENCHMARK_RESULTS.json`](MEMORY/BENCHMARK_RESULTS.json)).

---

## ⚡ Quick Start (Windows 11 + RX 6700 XT)

1. **Download Official Vulkan `llama.cpp` Binaries:**
   Extract the Windows Vulkan x64 release of `llama.cpp` into `bin/vulkan/`.
2. **Download Verified Stock Models:**
   ```powershell
   python scripts/download_7b_verifier.py
   python scripts/download_base_draft.py
   ```
3. **Launch the Verified Dual-Engine Server (Stock Drafter):**
   ```powershell
   .\start_local_server.ps1 -Mode speculative -K 2
   ```
4. **Run the Multi-Run Benchmark Suite with Variance Reporting:**
   ```powershell
   python tools/benchmark_speculative_suite.py --runs 3 --warmup 1
   ```
