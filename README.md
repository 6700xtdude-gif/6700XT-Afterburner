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

### 2. The 96 MB Infinity Cache Surgery Experiment (895.4 tokens/sec)
We also built a two-stage model surgery pipeline ([scripts/vocab_prune.py](scripts/vocab_prune.py) + [scripts/layer_prune.py](scripts/layer_prune.py)) to compress Qwen 2.5 Coder 0.5B so it fits **100% inside the RX 6700 XT's 96 MB Infinity Cache (L3 SRAM)**:
1. **Vocabulary Slicing (`151,936 -> 32,768` tokens):** Strips rare multilingual tokens while preserving all special tokens, byte fallbacks, and top 32k code/English tokens, plus generating a 128 KB `draft_to_verifier_id.bin` lookup table.
2. **Layer Slicing (`24 -> 14` layers):** Drops 10 intermediate blocks (`layers 8..17`) and re-indexes `[0..7, 18..23] -> [0..13]`.
3. **Quantization (`Q2_0`, 85.9 MiB):**
   * **Standalone Speed:** Hits **895.4 tokens/sec** generation and **16,875 tokens/sec** prompt processing on the RX 6700 XT!
   * **The Zero-Shot Surgery Discovery (See Issue #1):** While the 14-layer pruned model runs at nearly 900 t/s standalone, removing 10 layers *without* a post-pruning LoRA / knowledge distillation "healing" pass shifts its output logits enough that the 7B verifier rejects its drafts ($\alpha \to 0\%$). Using the intact 24-layer `0.5B-Q4_0` (330 MB) drafter immediately restores **78.8%–94.3% acceptance**. Healing the 14-layer 86 MB model via distillation is tracked as our next milestone!

### 3. Cross-Generation Tokenizer Barrier (Qwen 2.5 vs. Qwen 3.5/3.6)
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
