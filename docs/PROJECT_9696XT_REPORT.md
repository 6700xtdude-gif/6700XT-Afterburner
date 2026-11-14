# ⚡ Project 9696XT: High-Context Local LLM Inference Audit
**Hardware Reality, Memory Hierarchies & Empirical Benchmarks on the AMD Radeon RX 6700 XT**

> **Companion Repository:** [`6700xtdude-gif/6700XT-Afterburner`](https://github.com/6700xtdude-gif/6700XT-Afterburner)  
> **Community Origin:** Inspired by and responding to **Alex (@AlexFP16)** on YouTube: [*“Qwen 3.6 35B on 12GB VRAM: Strata vs llama.cpp Tested”*](https://www.youtube.com/watch?v=EudtrgdS4JU).

---

## 🏎️ Why "9696XT"? The Twin-96 Silicon Architecture

The name **9696XT** captures the two distinct 96-tier memory boundaries of this bare-metal rig paired with the AMD Radeon RX 6700 XT:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        PROJECT 9696XT SILICON TOPOLOGY                  │
└────────────────────────────────────────────────────────────────────────┘
  [96 MB On-Die Infinity Cache] ──> >1,000 GB/s SRAM (Navi 22 MALL)
           ▲
           │ 192-bit GDDR6 Bus (~384 GB/s)
           ▼
  [12,288 MB GDDR6 VRAM]        ──> 100% VRAM Saturation Tier (22.4+ t/s)
           ▲
           │ PCIe 4.0 x16 (~31.5 GB/s Direct CPU Lanes)
           ▼
  [96 GB System DDR4-3200]      ──> Zero-Disk-Paging High-Capacity Buffer (32 GiB/s)
```

1. **`96 MB` Infinity Cache:** The on-die L3 SRAM cache on AMD Navi 22 (`gfx1031`), delivering **>1 Terabyte/second** bandwidth directly on the GPU die to shield the 192-bit GDDR6 memory bus.
2. **`96 GB` System RAM:** A massive dual-channel DDR4 memory pool (combining $2 \times 32\text{ GB}$ and $2 \times 16\text{ GB}$ modules) providing the capacity to hold **20 GB to 45 GB model weights (up to 70B parameters)** and **64k–128k context KV caches** purely in physical memory with **zero NVMe SSD disk paging**.
3. **`XT`:** The **AMD Radeon RX 6700 XT 12 GB**, powered by the Vulkan backend with native Flash Attention and Multi-Token Prediction (MTP) speculation.

---

## 📺 Community Context: Responding to Alex (@AlexFP16)

In his landmark investigation (*[Qwen 3.6 35B on 12GB VRAM: Strata vs llama.cpp Tested](https://www.youtube.com/watch?v=EudtrgdS4JU)*), **Alex (@AlexFP16)** tested the Unsloth Qwen 3.6 35B A3B UD-Q4_K_XL file on an **RTX 3060 12GB + AMD Ryzen 5 5600 + 64GB DDR4**. 

Alex discovered:
1. Strata's official ~1.5x speedup claim was benchmarked on a **20-thread CPU**; on a 6-core Ryzen 5600, Strata only offloaded 3 experts per layer to VRAM, leaving the 6-core CPU bandwidth-choked in DDR4 (~29 t/s decode, 32 t/s 4-way batch).
2. Strata 0.2.12 MTP speculation drafted 0 tokens (0% acceptance).
3. `llama.cpp` PR #30966 (computing MoE cache misses in DDR4 without PCIe transfers) lifted decode to **51 t/s**, and with MTP speculation reached **67 t/s**.

We committed to running a comprehensive, reproducible benchmark suite on the **exact same host CPU (Ryzen 5 5600, 6 cores)** and identical high-capacity memory architecture, comparing Alex's NVIDIA Ampere CUDA setup against our **AMD RDNA2 Vulkan rig (RX 6700 XT 12GB + 96MB Infinity Cache)**.

---

## 📊 Empirical Benchmark Matrix (Standardized Eval Matrix, 3 Rounds + Warmup)

All tests were executed on native Windows 11 Pro bare-metal using the standardized evaluation harness ([`bench/bench_head_to_head.py`](../bench/bench_head_to_head.py)) driving `llama-server.exe` (build 12374 Vulkan) with a **verified 65,536 (64k) context window**.

| Architecture / Model Regime | Memory Allocation Strategy | Overall Median Decode | Structured JSON | Python Code | Peak Process RSS | Key Silicon Bottleneck |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **100% VRAM 27B**<br>`Qwen3.8-27B-IQ2_M` | 65/65 Layers on RX 6700 XT GDDR6 ($0\text{ in DDR4}$)<br>MTP Speculation ($K=2$, 32 GB / 64 GB) | **22.61 t/s** | **24.22 t/s** | **23.69 t/s** | 12,929 MB | **Bypasses DDR4 entirely.** Pure GDDR6 + 96MB Infinity Cache speed. |
| **35B MoE Hybrid (32 GB)**<br>`Qwen3.6-35B-A3B UD-Q4_K_XL` *(Alex's Model)* | 16 Layers in VRAM, 25 in 32GB DDR4<br>Sparse routing ($8/256$ active experts, 2 DIMMs) | **16.78 t/s** | **16.81 t/s** | **16.77 t/s** | 21,531 MB | **Sparse Expert Advantage:** Reads only ~3.5 GB active parameters/tok; zero disk thrashing. |
| **35B MoE Hybrid (64 GB)**<br>`Qwen3.6-35B-A3B UD-Q4_K_XL` | 16 Layers in VRAM, 25 in 64GB DDR4<br>Sparse routing ($8/256$ active experts, 4 DIMMs) | **16.39 t/s** | **16.47 t/s** | **16.47 t/s** | 21,469 MB | **High Capacity Pool:** 100% resident in physical memory with extensive headroom. |
| **27B Dense Hybrid (32 GB, 2-DIMM)**<br>`Qwen3.8-27B UD-Q4_K_XL` | 45 Layers in VRAM, 20 in 32GB DDR4<br>MTP Speculation ($K=2$, `tb=12`, 1 DPC / 1T) | **7.54 t/s** | **8.64 t/s** | **7.59 t/s** | 20,935 MB | **2-DIMM IMC Advantage:** 1 DPC operation delivers **+23.0% speedup** over 4 DIMMs. |
| **27B Dense Hybrid (64 GB Fixed)**<br>`Qwen3.8-27B UD-Q4_K_XL` | 45 Layers in VRAM, 20 in 64GB DDR4<br>Manual Pagefile (32 GB / 96 GB, 4 DIMMs) | **6.13 t/s** | **6.45 t/s** | **6.15 t/s** | 22,098 MB | **The DDR4 Cliff:** Streams 27B weights every token through 32 GiB/s DDR4 bus. |
| **27B Dense Hybrid (64 GB Managed)**<br>`Qwen3.8-27B UD-Q4_K_XL` | 45 Layers in VRAM, 20 in 64GB DDR4<br>Dynamic Windows Pagefile | **5.77 t/s** | **6.46 t/s** | **5.90 t/s** | 21,523 MB | **Kernel Commit Jitter:** Dynamic Windows page allocation adds ~5.8% micro-variance. |

---

## 🔬 Core Engineering Discoveries

### 1. The Sparse MoE Speed Paradox: Why 35B is 2.23x to 2.67x Faster than 27B
* In a dense model (`Qwen 3.8 27B`), autoregressive decode must stream **all 27 billion parameters** on every single token. Spilling 20 layers into DDR4 stalls the GPU for ~130–165 ms while the CPU reads weights across the 32 GiB/s bus (**6.13 to 7.54 t/s**).
* In a Mixture of Experts model (`Qwen 3.6 35B A3B`), although the file is 21.27 GB on disk, **only 8 out of 256 experts are activated per token (~3.5 GB active parameters)**.
* Because only a small slice of experts must be fetched from DDR4 per token, memory bus pressure is drastically reduced, allowing generation to scream at **16.78 tokens/sec**—a **2.23x speedup over the smaller dense model**.

### 2. The 32 GB vs 64 GB Reality & The 2-DIMM IMC Efficiency Uplift
* **The 2-DIMM Advantage (+23.0% Speedup):** On the Ryzen 5 5600, running 2 single-rank DIMMs (1 DPC, 1T command rate) allows the Integrated Memory Controller (IMC) to operate with significantly lower latency and tighter subtimings than 4 DIMMs (2 DPC). This lifts dense hybrid offload from **6.13 t/s $\rightarrow$ 7.54 t/s**, with structured JSON reaching **8.64 t/s**.
* **Memory Headroom & Working Set Bounds:** Both large hybrid models (`Qwen 3.6 35B MoE` at **21.5 GB** and `Qwen 3.8 27B` at **20.9 GB**) successfully fit within a clean 32 GB system (with 26.3 GB free physical RAM at boot), leaving ~5.4 GB to 7.8 GB of headroom without triggering catastrophic NVMe SSD swapping.
* **When 64 GB / 96 GB is Essential:** 64 GB+ becomes mandatory when expanding to massive **64k–128k context KV caches** on hybrid models or running multi-agent swarms with concurrent heavy processes, which would otherwise spill beyond 32 GB.

### 3. The 100% VRAM Saturation Triumph
By quantizing Qwen 3.8 27B to `IQ2_M` with an importance matrix and preserving the native MTP drafting head in `Q4_K` ([`EXP-020`](../MEMORY/EXPERIMENT_LOG.md)), the entire 27B model fits inside the RX 6700 XT's 12 GB VRAM.
* **Speed:** Generation jumps from **6.13–7.54 t/s $\rightarrow$ 22.61 t/s (a 3.0x to 3.7x speedup)**.
* **Latency:** Output starts in under 170 ms TTFT with ~76% speculative draft acceptance.
* **Hardware Independence:** 100% VRAM execution bypasses DDR4 entirely, delivering identical ~22.6 t/s whether the host has 32 GB or 64 GB RAM.

---

## 💬 Community Response Draft for Alex (@AlexFP16)

Copy-paste comment for [Alex's YouTube Video](https://www.youtube.com/watch?v=EudtrgdS4JU):

> *"Hey Alex! I saw your video testing Strata on the 3060 and promised I'd report back with empirical data from our Ryzen 5 5600 rig.*  
> *We have the **exact same host CPU (Ryzen 5 5600, 6 cores)**, tested across both 64GB and 32GB DDR4, paired with an **AMD Radeon RX 6700 XT 12GB (384 GB/s + 96MB Infinity Cache under Vulkan)**.*  
> 
> *We ran standardized 3-round benchmarks on your exact Unsloth Qwen 3.6 35B A3B UD-Q4_K_XL file and Qwen 3.8 27B, and posted the full raw telemetry, JSON reports, and hardware audit to GitHub:*  
> *🔗 https://github.com/6700xtdude-gif/6700XT-Afterburner/blob/main/docs/PROJECT_9696XT_REPORT.md*  
> 
> *Here is what we discovered on the AMD/Vulkan side:*  
> *1. **The MoE Speed Advantage:** On hybrid offload (16 layers on the 6700 XT, 25 in DDR4), Qwen 3.6 35B hits **16.78 tokens/sec** steady state with 120 ms TTFT! Because only 8 of 256 experts are active per token (~3.5 GB active parameters), it completely bypasses the DDR4 bandwidth cliff that chokes dense 27B models.*  
> *2. **The 2-DIMM IMC Discovery:** When testing 32GB (2x16GB, 1 DPC) vs 64GB (4x16GB, 2 DPC), the Ryzen 5600's memory controller delivered a **+23% speedup on dense hybrid offload (7.54 t/s vs 6.13 t/s)** due to 1T command rate and lower latency.*  
> *3. **100% VRAM Saturation:** Sizing Qwen 3.8 27B down to IQ2_M + MTP speculation to fit 100% inside the 6700 XT's 12GB VRAM rocketed decode speed to **22.61 tokens/sec (3.0x faster than DDR4 hybrid)**.*  
> 
> *Awesome video highlighting the 20-thread vs 6-core thread disparity—gave us the exact direction we needed for Project 9696XT!"*
