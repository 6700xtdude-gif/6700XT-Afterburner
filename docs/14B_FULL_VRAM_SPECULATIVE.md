# 14B Full-VRAM Dual-Engine Speculative Decoding on AMD Radeon RX 6700 XT (12 GB)

## 1. Executive Summary
By pairing **`Qwen2.5-Coder-14B-Instruct-Q4_K_M` (8.37 GiB, 48 layers, 14.77B parameters)** with our **`Qwen2.5-Coder-0.5B` (`Q4_0`)** draft engines (`Healed 18L` at 282 MiB and `Unpruned 24L` at 330 MiB), the entire dual-engine stack fits **100% inside the RX 6700 XT's 12 GB GDDR6 VRAM (~9.45 GiB total footprint including `Q8_0` KV cache)**.

Because a 14.8B dense model streams ~2x more weight bytes per token (`8.37 GiB` vs. `4.36 GiB` for 7B) across the 192-bit GDDR6 bus (~384 GB/s), standalone 14B generation runs at **`37.4 – 37.5 tokens/sec`**. Adding speculative decoding accelerates 14B up to **`63.9 tokens/sec` (`1.71x` speedup, +70.9%)** on structured JSON/tool-calling and **`60.9 tokens/sec` (`1.62x` speedup, +62.4%)** on Python code generation—delivering **14B intelligence at nearly standalone 7B speeds (`71.5 t/s`)** with output **identical at temp 0 in testing** (subject to floating-point order in batched verification).

> [!IMPORTANT]
> **Audit & Generalization Finding:** While the pruned `Healed 14L` drafter achieved 64.6 t/s on JSON prompts matching its calibration data, it collapsed to **43.7 t/s (46.5% acceptance)** on code and **34.2% acceptance** on unseen held-out prompts. In contrast, the **Stock Untouched 24L 0.5B drafter** delivered **60.9 t/s (85.0% acceptance)** on code and generalized at **74.4%–85.6% acceptance** across unseen held-out tasks. The unpruned stock drafter is the clear production choice.

---

## 2. Empirical Benchmark Matrix (`tools/benchmark_14b_vram.py`)

* **Hardware:** AMD Radeon RX 6700 XT 12 GB (`Navi 22` / `gfx1031` Vulkan, `ReBAR: 1`, `Wave32`, `int dot: 1`)
* **Settings:** `--temp 0.0 -ngl 99 -ngld 99 -fa on -ctk q8_0 -ctv q8_0 -c 2048 -n 128`
* **Raw Results:** [`MEMORY/BENCHMARK_14B_RESULTS.json`](../MEMORY/BENCHMARK_14B_RESULTS.json)

| Workload | Configuration | Generation Speed | Prompt Speed | Draft Acceptance ($\alpha$) | Speedup vs. Standalone 14B |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Structured JSON**<br>*(User profile schema)* | **Standalone 14B (`Q4_K_M`)**<br>**14B + Healed 14L 0.5B ($K=3$)**<br>14B + Dory-Looped 19L 0.5B ($K=3$)<br>14B + Healed 18L 0.5B ($K=3$)<br>**14B + Healed 18L 0.5B ($K=4$)**<br>14B + Unpruned 24L 0.5B ($K=3$)<br>14B + Unpruned 24L 0.5B ($K=4$) | 37.4 t/s<br>**64.6 t/s**<br>60.4 t/s<br>63.0 t/s<br>**63.9 t/s**<br>62.3 t/s<br>62.4 t/s | 197.0 t/s<br>**144.2 t/s**<br>138.1 t/s<br>136.5 t/s<br>**143.7 t/s**<br>136.0 t/s<br>139.2 t/s | —<br>**86.7% (91/105)**<br>81.1% (90/111)<br>86.7% (91/105)<br>**89.2% (99/111)**<br>88.5% (92/104)<br>90.0% (99/110) | 1.00x<br>**1.73x (+72.7%)***<br>1.61x (+61.5%)<br>1.68x (+68.4%)<br>**1.71x (+70.9%)**<br>1.67x (+66.6%)<br>1.67x (+66.8%) |
| **Code Generation**<br>*(Python Quicksort)* | **Standalone 14B (`Q4_K_M`)**<br>14B + Healed 14L 0.5B ($K=3$)<br>14B + Dory-Looped 19L 0.5B ($K=3$)<br>14B + Healed 18L 0.5B ($K=3$)<br>14B + Healed 18L 0.5B ($K=4$)<br>**14B + Unpruned 24L 0.5B ($K=3$)**<br>14B + Unpruned 24L 0.5B ($K=4$) | 37.5 t/s<br>43.7 t/s<br>43.0 t/s<br>51.2 t/s<br>47.3 t/s<br>**60.9 t/s**<br>55.2 t/s | 168.9 t/s<br>141.0 t/s<br>137.4 t/s<br>139.2 t/s<br>142.3 t/s<br>**138.8 t/s**<br>133.9 t/s | —<br>46.5% (74/159)<br>48.1% (75/156)<br>62.9% (83/132)<br>58.9% (89/151)<br>**85.0% (91/107)**<br>76.6% (95/124) | 1.00x<br>1.17x (+16.5%)<br>1.15x (+14.7%)<br>1.37x (+36.5%)<br>1.26x (+26.1%)<br>**1.62x (+62.4%)**<br>1.47x (+47.2%) |

---

## 3. Critical Hardware Discovery: Windows WDDM Shared Memory Cliff
During initial testing, an orphaned background `llama-server.exe` holding the 7B model (`4.98 GiB` VRAM) remained resident while the 14B benchmark (`8.37 GiB` VRAM) launched.
* Because total allocation (~13.6 GiB) exceeded physical 12 GB VRAM, **Windows WDDM silently paged ~2 GiB of Vulkan buffers into system DDR4 over PCIe 4.0** ("Shared GPU Memory") without throwing an out-of-memory error.
* That silent spillover dropped standalone 14B throughput from **`37.5 t/s` down to `7.5 t/s` (-80% penalty)** and speculative throughput from **`63.9 t/s` down to `18.9 t/s`**.
* **Rule:** Always ensure no competing LLM server is holding VRAM before launching `speculative14b` so the full ~9.45 GiB stack stays 100% inside dedicated GDDR6 VRAM.

---

## 4. Quick Launch
```powershell
# Download Qwen2.5-Coder-14B-Instruct-Q4_K_M.gguf (8.37 GiB)
python scripts/download_14b_verifier.py

# Launch 14B Speculative Vulkan Server on port 8080
.\start_local_server.ps1 -Mode speculative14b -K 3

# Run the 14B Full-VRAM Benchmark Suite
python tools/benchmark_14b_vram.py
```

---

## 5. Next Development & Benchmarking Milestones
1. **Full 3-Category Horizon Sweep ($K \in \{2, 3, 4, 5, 6\}$):** Because 14B forward passes take ~26.7 ms vs. ~1.1 ms for the 0.5B drafter, test higher draft horizons ($K=5, 6$) on structured JSON and code where $\alpha > 85\%$.
2. **14B-Distilled Draft Engine:** Distill our surgical 0.5B draft models directly against **14B teacher logits** (instead of 0.5B-24L logits) to close the gap between 18L (`62.9%` code acceptance) and 24L (`85.0%` code acceptance) on 14B targets.
