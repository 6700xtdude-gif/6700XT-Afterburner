# 🧠 Infinity Cache, Mega-L2 & 3D V-Cache Hardware Compatibility Matrix

> **Core Principle:** The **6700XT-Afterburner** architecture exploits a universal silicon design pattern in modern GPUs, CPUs, and AI SoCs: **a multi-terabyte-per-second on-die or 3D-stacked SRAM Last-Level Cache (32 MB – 1,152 MB) shielding a narrow off-chip DRAM/GDDR bus.**

By compressing the speculative draft engine into **25 MB – 85 MB** via **ShortGPT Layer Pruning** ([`scripts/profile_layer_importance.py`](../scripts/profile_layer_importance.py)), **Seam Knowledge Distillation** ([`scripts/heal_draft_model.py`](../scripts/heal_draft_model.py)), **Dory-Style Latent-Recurrent Layer Looping** ([`scripts/build_dory_and_14l_healed.py`](../scripts/build_dory_and_14l_healed.py)), and **32k Native Vocabulary Distillation** ([`scripts/distill_32k_dory_and_14l.py`](../scripts/distill_32k_dory_and_14l.py)), draft generation executes at **SRAM cache speeds (>1–3 TB/s)** while the heavy verifier model streams weights across the narrow memory bus only once every $K+1$ tokens.

---

## 1. AMD Radeon RDNA 2, RDNA 3 & RDNA 4 GPUs (32 MB – 128 MB Infinity Cache)

All RDNA 2/3/4 GPUs feature **MALL (Memory-Attached Last-Level) Infinity Cache** and run our Vulkan pipeline (`start_local_server.ps1`) out of the box:

| GPU Family | Architecture | VRAM & Bus Width | Raw Bandwidth | Infinity Cache (SRAM) | Recommended Draft Surgery Tier | Ideal Verifier Target |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **RX 6700 XT / 6750 XT** *(Reference)* | RDNA 2 (`Navi 22`) | 12 GB / 192-bit | 384–432 GB/s | **96 MB** (>1 TB/s) | **Healed 14L / Dory 19L (<85 MB `Q2` or 243 MB `Q4_0`)** | **7B (`99.8 t/s`) / 14B (`64.6 t/s`)** |
| **RX 6800 / 6800 XT / 6900 XT / 6950 XT** | RDNA 2 (`Navi 21`) | 16 GB / 256-bit | 512–576 GB/s | **128 MB** (~1.6–2.0 TB/s) | **Healed 18L / Dory 19L (`Q3_K` / `Q4_0`, ~110 MB)** | **14B `Q5_K_M` or 32B `Q3_K` in 16 GB VRAM** |
| **RX 7900 XTX / 7900 XT** | RDNA 3 (`Navi 31`) | 20–24 GB / 320–384-bit | 800–960 GB/s | **80 MB – 96 MB** | **Healed 14L / Dory 19L (<85 MB)** | **32B Dense `Q4_K_M` or 35B-A3B MoE 100% VRAM** |
| **RX 7900 GRE / 7800 XT / 7700 XT** | RDNA 3 (`Navi 31/32`) | 12–16 GB / 192–256-bit | 432–624 GB/s | **48 MB – 64 MB** | **14L Dory-Looped 32k Vocab (<58 MB)** | **14B `Q4_K_M` (16 GB) / 7B `Q6_K` (12 GB)** |
| **RX 9070 XT / RX 9070** | RDNA 4 (`Navi 48`) | 16 GB / 256-bit | 640 GB/s | **64 MB** (3rd-Gen) | **14L Dory-Looped 32k Vocab (<58 MB)** | **14B `Q5_K_M` / 32B `Q3_K_M`** |
| **RX 7600 XT 16 GB / RX 9060 XT 16 GB** | RDNA 3/4 (`Navi 33/44`) | **16 GB / 128-bit** | **288–320 GB/s** | **32 MB** | **10L–12L Dory-Looped + 16k/32k Vocab (<28 MB)** | **14B `Q4_K_M` (rescues the 128-bit bus!)** |

---

## 2. NVIDIA Ada Lovelace & Blackwell "Mega-L2" GPUs (32 MB – 96 MB L2 SRAM)

Starting with **Ada Lovelace (RTX 40-series)** and **Blackwell (RTX 50-series)**, NVIDIA narrowed memory buses (down to 128-bit/192-bit) and expanded on-die **L2 SRAM cache by 8x–16x** (up to **32 MB–96 MB**):

| GPU Model | VRAM & Bus Width | Raw Bandwidth | On-Die L2 SRAM | Why It Benefits & CUDA Hardware Pinning Advantage |
| :--- | :--- | :---: | :---: | :--- |
| **RTX 4060 Ti 16 GB / RTX 5060 Ti 16 GB** | **16 GB / 128-bit** | **288–448 GB/s** | **32 MB** | **Highest GPU speedup potential:** 16 GB VRAM fits 14B–24B models, but the 128-bit bus chokes standalone decoding to ~25–30 t/s. A **<28 MB Dory-looped drafter** pinned in the 32 MB L2 cache yields 1.7x–2.1x speedups. |
| **RTX 4070 / 4070 Super / RTX 5070** | 12 GB / 192-bit | 504–672 GB/s | **36 MB – 48 MB** | Direct 12 GB / 192-bit counterparts to the RX 6700 XT. Fits a **<42 MB 14L surgical drafter** inside L2 alongside a 14B `Q4_K_M` verifier. |
| **RTX 4080 / 4090 / RTX 5080 / 5090 / L40S** | 16–32 GB / 256–512-bit | 716–1,792 GB/s | **64 MB – 96 MB** | Matches or equals Navi 22's **96 MB SRAM**. Furthermore, CUDA's `cudaAccessPolicyWindow` API allows **explicitly locking** the <85 MB draft buffer in L2 so verifier streaming reads never evict the draft weights! |

---

## 3. AMD 3D V-Cache CPUs (Ryzen X3D & EPYC-X: 96 MB – 1,152 MB L3 SRAM)

The **largest bandwidth multiplier** for this project occurs on **AMD 3D V-Cache CPUs**, where the ratio between L3 SRAM bandwidth (~1.5–2.5 TB/s) and DDR4/DDR5 system RAM (~50–85 GB/s) is **20x to 35x**:

* **Ryzen 7 5700X3D / 5800X3D / 7800X3D / 9800X3D (96 MB L3 on a Single CCD):**
  * A standard `330 MB` 0.5B draft model overflows the 96 MB 3D V-Cache, thrashing DDR4/DDR5 on every draft step.
  * Our **<85 MB surgical draft model** fits **100% inside the 96 MB 3D V-Cache** on a single CCD, drafting tokens at hundreds of tokens/sec from L3 SRAM with **zero DRAM traffic**, while the CPU (or hybrid GPU+CPU MoE like `Qwen3.6-35B-A3B`) only reads system DDR4/DDR5 once every $K+1$ tokens!
* **Ryzen 9 7950X3D / 9950X3D (128 MB Total L3 — 96 MB on CCD0 + 32 MB on CCD1):**
  * Pinning draft thread affinity to CCD0 locks the <85 MB drafter inside the 96 MB 3D V-Cache chiplet while CCD1 assists with batched target verification.
* **EPYC Milan-X (768 MB L3) & Genoa-X (1,152 MB L3 — 96 MB × 12 CCDs):**
  * Over **1.15 GB of 3D V-Cache** allows either pinning unpruned 0.5B–1.5B draft models inside L3 or layer-sharding a 3B drafter across CCD L3 caches with zero main-memory traffic.

---

## 4. Unified Memory AI APUs & SoCs with System-Level Cache (MALL / SLC)

1. **AMD Ryzen AI Max+ 395 "Strix Halo" (32 MB MALL Infinity Cache + 64 MB Zen 5 L3):**
   * Pairs up to **128 GB of unified LPDDR5X-8000** across a 256-bit bus (**256 GB/s**) with a **40-CU RDNA 3.5 GPU** and a **32 MB on-die MALL Infinity Cache**.
   * Running 32B–70B dense models in unified memory is strictly bound by the 256 GB/s bus (~10–22 t/s). Pairing a **<28 MB Dory-looped drafter** in the 32 MB MALL (or a **<60 MB drafter** in the 64 MB CPU L3) unlocks massive speculative speedups on 70B local models.
2. **Apple Silicon M1/M2/M3/M4 Pro, Max & Ultra (24 MB – 192 MB System-Level Cache):**
   * Apple's M-series architecture relies on a massive hardware **SLC** buffering unified LPDDR5 memory (48–96 MB on Max, up to 192 MB on Ultra). A sub-80 MB surgical draft model stays hot in SLC between target verification sweeps.

---

## 5. Summary of Surgical Recipes by Cache Size

| SRAM Cache Tier | Target Silicon | Surgery Configuration (`scripts/`) | Active Footprint |
| :--- | :--- | :--- | :---: |
| **96 MB – 128 MB Tier** | RX 6700 XT (96 MB), RX 6800/6900 XT (128 MB), RX 7900 XTX (96 MB), Ryzen X3D (96 MB), RTX 4090/5090 (72–96 MB) | **`Healed 14L` or `Dory-Looped 19L`** (`KEEP_14` + 32k Distilled Vocab) | **65 – 87 MB** |
| **64 MB Tier** | RX 9070 XT (64 MB), RX 7800 XT / 7900 GRE (64 MB), RTX 4080 / 5080 (64 MB), Apple M-Max SLC | **`Dory-Looped 14L -> 19L`** (`IQ2_XS` / Hybrid + 32k Vocab) | **48 – 56 MB** |
| **32 MB Tier** | Strix Halo (32 MB MALL), RTX 4060 Ti / 5060 Ti 16GB (32 MB L2), RX 7600 XT / 9060 XT 16GB (32 MB) | **`10L–12L Dory-Looped`** (`2x–3x` middle loop + `IQ2_XXS` + 16k/32k Vocab) | **24 – 28 MB** |
