# 6700XT-Afterburner 🚀

**Dual-Engine Speculative Decoding & 96 MB Infinity Cache Model Surgery for the AMD Radeon RX 6700 XT (`Navi 22` / `gfx1031` Vulkan)**

> **Core Mission:** Overcome the 192-bit GDDR6 memory bus bottleneck (~384 GB/s) on the 12 GB AMD Radeon RX 6700 XT by pairing a 100% VRAM-resident **Qwen 2.5 Coder 7B (`Q4_K_M`)** verifier with an ultra-fast **0.5B (`Q4_0`)** draft engine—and exploring sub-90 MB L3-resident model surgery inside Navi 22's **96 MB Infinity Cache** (>1 TB/s SRAM).

---

## 📊 Empirical Benchmark Results (RX 6700 XT 12 GB — Vulkan Backend)

All benchmarks were executed via [tools/benchmark_speculative_suite.py](tools/benchmark_speculative_suite.py) at deterministic temperature (`--temp 0.0`, `-fa on`, `-ngl 99 -ngld 99`) over $N = 128$ generated tokens (`llama.cpp` build `b12374` Vulkan). Raw JSON results are available in [MEMORY/BENCHMARK_RESULTS.json](MEMORY/BENCHMARK_RESULTS.json).

| Workload Category | Mode / Config | Generation Speed | Latency (128 Tok) | Draft Acceptance ($\alpha$) | Speedup vs Baseline |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Structured JSON / Schema**<br>*(Tool calls, schemas, JSON)* | **Baseline Standalone 7B**<br>Speculative ($K=2$)<br>Speculative ($K=3$)<br>Speculative ($K=4$) | 71.7 t/s<br>**95.5 t/s**<br>**92.9 t/s**<br>**93.8 t/s** | 1,771.8 ms<br>**1,330.2 ms**<br>**1,366.9 ms**<br>**1,354.6 ms** | —<br>**94.3%**<br>**89.3%**<br>**92.6%** | Baseline (1.00x)<br>**1.33x (+33.2%)**<br>**1.30x (+29.6%)**<br>**1.31x (+30.8%)** |
| **Code Generation**<br>*(Python Quicksort algorithm)* | **Baseline Standalone 7B**<br>Speculative ($K=2$)<br>Speculative ($K=3$)<br>Speculative ($K=4$) | 71.4 t/s<br>**83.8 t/s**<br>**85.8 t/s**<br>73.8 t/s | 1,779.6 ms<br>**1,516.1 ms**<br>**1,480.7 ms**<br>1,720.9 ms | —<br>**77.0%**<br>**78.8%**<br>66.7% | Baseline (1.00x)<br>**1.17x (+17.4%)**<br>**1.20x (+20.2%)**<br>1.03x (+3.4%) |
| **Technical Reasoning**<br>*(Freeform system architecture)* | **Baseline Standalone 7B**<br>Speculative ($K=2$)<br>Speculative ($K=3$)<br>Speculative ($K=4$) | 71.5 t/s<br>**73.8 t/s**<br>67.9 t/s<br>61.5 t/s | 1,776.3 ms<br>**1,721.6 ms**<br>1,869.8 ms<br>2,063.4 ms | —<br>**61.9%**<br>55.6%<br>51.8% | Baseline (1.00x)<br>**1.03x (+3.2%)**<br>0.95x (-5.0%)<br>0.86x (-14.0%) |

---

## 🔬 Key Hardware & Architecture Findings

### 1. Why Speculative Decoding Works on the 192-bit Bus
Autoregressive LLM generation (`batch_size = 1`) is strictly memory-bandwidth bound. Every single token requires streaming ~4.68 GB of 7B weights across the RX 6700 XT's 192-bit GDDR6 bus (~384 GB/s), capping standalone generation around **71.5 tokens/sec**.

By running `Qwen2.5-Coder-0.5B-Instruct-Q4_0` (330 MB) alongside `Qwen2.5-Coder-7B-Instruct-Q4_K_M` (4.68 GB)—consuming just **~5.2 GB of 12 GB VRAM combined**—the 0.5B model rapidly drafts $K = 2\text{--}3$ tokens, and the 7B model verifies all of them in a **single parallel forward pass** (1 weight read instead of 3–4).
* **Result:** Up to **95.5 tokens/sec (+33.2%)** on JSON/tool-calling and **85.8 tokens/sec (+20.2%)** on Python code, with **100% mathematically identical output** to standalone 7B.

### 2. Healing the Surgery: ShortGPT Profiling + Knowledge Distillation (**96.7 tokens/sec Record!**)
Initially, zero-shot layer pruning (`24 -> 14` layers, blindly dropping `[8..17]` in `Q2_0`) achieved **895.4 tokens/sec** standalone inside the **96 MB Infinity Cache**, but suffered `0%` speculative acceptance (`21.2%` in `Q4_0`) because cutting `blk.16` (`BI = 0.0941`) shifted output logits away from the 7B verifier (`KL = 269.41`).

To solve [Issue #1](https://github.com/6700xtdude-gif/6700XT-Afterburner/issues/1), we built a two-part surgical healing pipeline:
1. **Neural Layer Importance Profiler ([`scripts/profile_layer_importance.py`](scripts/profile_layer_importance.py)):**
   * Measured ShortGPT Block Influence (`1 - cos_sim(X_in, X_out)`) and Leave-One-Out token agreement across all 24 layers, identifying `[9, 10, 11, 12, 13, 18]` as the true low-influence redundant valley (`24 -> 18` layers, `-25%` depth).
2. **Seam Knowledge Distillation Healer ([`scripts/heal_draft_model.py`](scripts/heal_draft_model.py)):**
   * Tuned the seam projections (`o_proj`, `down_proj`, `LayerNorm`) using Top-128 Logit KL-Divergence + Hidden-State Cosine Alignment against the 24-layer Teacher, lifting teacher token agreement from **`38.94%` (naive 14L) -> `73.22%` (unhealed 18L) -> `97.82%` (healed 18L, `KL = 1.71`)**!

| Draft Engine Surgery State | Teacher KL Div | Speculative Acceptance ($\alpha$) | RX 6700 XT Speed (JSON / Code) | vs. Standalone 7B (`71.7 t/s`) |
| :--- | :---: | :---: | :---: | :---: |
| **Unhealed 14L (`Q2_0`, `[8..17]` cut)** | 269.41 | 0.0% | 17.0 t/s | 0.24x (Failed) |
| **Unhealed 14L (`Q4_0`, `[8..17]` cut)** | 269.41 | 21.2% | 45.8 t/s | 0.64x (Slowdown) |
| **Healed 18L (`Q4_0`, BI + Distillation, $K=3$)** | **1.71** | **88.5% (JSON) / 63.4% (Code)** | **96.7 t/s (JSON) / 77.3 t/s (Code)** | **1.35x (+34.9% Peak Record!)** |
| **Healed 18L (`Q4_0`, BI + Distillation, $K=4$)** | **1.71** | **89.2% (mean burst = 4.54 tok)** | **95.4 t/s (JSON)** | **1.33x (+33.1%)** |

### 3. Scaling Up to 14B in 100% VRAM (**1.71x Speedup — 14B Running at 7B Speeds!**)
Because speculative decoding amortizes target weight reads across multiple drafted tokens, the speedup ratio scales even higher on larger dense models that still fit inside the RX 6700 XT's 12 GB VRAM (`Qwen2.5-Coder-14B-Instruct-Q4_K_M`, 8.37 GiB + 0.28 GiB drafter = ~9.45 GiB total via [`tools/benchmark_14b_vram.py`](tools/benchmark_14b_vram.py)):

| 14B Full-VRAM Configuration (RX 6700 XT 12 GB) | Structured JSON Speed ($\alpha$) | Python Code Speed ($\alpha$) | Speedup vs. Standalone 14B |
| :--- | :---: | :---: | :---: |
| **Standalone 14B (`Q4_K_M`, 48L, 8.37 GiB)** | 37.4 t/s (—) | 37.5 t/s (—) | Baseline (1.00x) |
| **14B + Healed 18L 0.5B Draft ($K=3$)** | **63.0 t/s (86.7%)** | **51.2 t/s (62.9%)** | **1.68x (JSON) / 1.37x (Code)** |
| **14B + Healed 18L 0.5B Draft ($K=4$)** | **63.9 t/s (89.2%)** | 47.3 t/s (58.9%) | **1.71x (+70.9% JSON Record!)** |
| **14B + Unpruned 24L 0.5B Draft ($K=3$)** | 62.3 t/s (88.5%) | **60.9 t/s (85.0%)** | **1.67x (JSON) / 1.62x (+62.4% Code!)** |

### 4. Dory-Style Latent-Recurrent Layer Looping inside the 96 MB Infinity Cache
Inspired by NVIDIA's **Dory1.0-4B** looped transformer, [`scripts/test_looped_draft.py`](scripts/test_looped_draft.py) converts our 14-layer (<90 MB `Q2_0`) Infinity Cache architecture into a **19-effective-layer Looped Transformer** by looping the 5 middle layers (`5..9`) twice with a 3.5 KB gated anchor re-injection (`loop_alpha` + `loop_norm`):
* **Unhealed Linear 14L (14 Passes):** `52.87%` Teacher Agreement (`KL = 273.56`)
* **Distilled Linear 14L (14 Passes):** `94.43%` Teacher Agreement (`KL = 8.35`)
* **Distilled Dory-Looped 14L (19 Effective Passes, Same 14L Physical Weights):** **`95.30%` Teacher Agreement (`KL = 6.78`, -18.8% lower KL divergence!)**

### 5. Cross-Generation Tokenizer Barrier (Qwen 2.5 vs. Qwen 3.5/3.6)
When pairing `Qwen3.6-35B-A3B` (248k `qwen35` vocabulary) with `Qwen2.5-0.5B` (152k `qwen2` vocabulary), stock `llama.cpp` rejects speculation (`common_specu: the target and draft vocabs are not compatible`). Bridging Qwen 2.5 drafters to Qwen 3.6 MoE targets requires runtime token ID remapping via `draft_to_verifier_id.bin`.

---

## 🛠️ Repository Structure

* [`start_local_server.ps1`](start_local_server.ps1) — Turnkey PowerShell launcher for the RX 6700 XT Vulkan `llama-server` (`-Mode speculative` for 95.5 t/s 7B+0.5B, or `-Mode moe35b` for hybrid 35B-A3B).
* [`tools/benchmark_speculative_suite.py`](tools/benchmark_speculative_suite.py) — Automated A/B benchmark suite testing standalone vs. speculative horizons ($K \in \{2, 3, 4\}$) across Code, JSON, and Reasoning.
* [`tools/llm_bridge_mcp.py`](tools/llm_bridge_mcp.py) — Zero-dependency MCP (Model Context Protocol) server bridging the local RX 6700 XT Vulkan server and OpenRouter into agentic IDEs.
* [`tools/test_local_tool_calling.py`](tools/test_local_tool_calling.py) — End-to-end agentic tool-calling test harness (autonomous Windows PowerShell execution in <700 ms).
* [`scripts/vocab_prune.py`](scripts/vocab_prune.py) & [`scripts/layer_prune.py`](scripts/layer_prune.py) — Model surgery scripts for slicing vocabulary and transformer layers to fit inside the 96 MB Infinity Cache.
* [`MEMORY/`](MEMORY/) — Complete engineering lab notebook ([`EXPERIMENT_LOG.md`](MEMORY/EXPERIMENT_LOG.md), [`LESSONS.md`](MEMORY/LESSONS.md), [`BENCHMARK_RESULTS.json`](MEMORY/BENCHMARK_RESULTS.json)).

---

## ⚡ Quick Start (Windows 11 + RX 6700 XT)

1. **Download Official Vulkan `llama.cpp` Binaries:**
   Extract the Windows Vulkan x64 release of `llama.cpp` into `bin/vulkan/`.
2. **Download Models:**
   ```powershell
   python scripts/download_7b_verifier.py
   python scripts/download_base_draft.py
   ```
3. **Launch the Speculative Vulkan Server:**
   ```powershell
   .\start_local_server.ps1 -Mode speculative -K 3
   ```
4. **Run the Benchmark Suite:**
   ```powershell
   python tools/benchmark_speculative_suite.py
   ```
