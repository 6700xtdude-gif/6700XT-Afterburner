# 🎬 CACHE ME IF YOU CAN: Project 6700XT-Afterburner (Full Production Script & Iteration Log)

> **Show Title:** *Silicon Surgery — Episode 01: "Cache Me If You Can: Turning a 96 MB Gaming L3 Cache into a 1 TB/s AI Afterburner"*  
> **Target Hardware:** AMD Radeon RX 6700 XT 12 GB (`Navi 22` / `gfx1031` Vulkan) + 96 MB Infinity Cache  
> **Companion Repo:** [`6700xtdude-gif/6700XT-Afterburner`](https://github.com/6700xtdude-gif/6700XT-Afterburner)

---

## 🗺️ Engineering Iteration Scoreboard (Act-by-Act Progression)

| Iteration / Act | GitHub Milestone | Architecture / Surgery State | 7B Verifier Speed ($\alpha$) | 14B Verifier Speed ($\alpha$) | Key Engineering Discovery |
| :--- | :--- | :--- | :---: | :---: | :--- |
| **Iteration 0 (Act I)** | `df7e530` (`main`) | **Standalone Dense Baseline** (`Q4_K_M`, 100% VRAM) | 71.7 t/s (—) | 37.4 t/s (—) | Bound by the 192-bit GDDR6 bus (~384 GB/s). |
| **Iteration 1 (Act II)** | `df7e530` (`main`) | **Twin-Engine Speculative** (`24L 0.5B Q4_0` Draft, 330 MiB) | **95.5 t/s** (`94.3%` JSON)<br>**85.8 t/s** (`78.8%` Code) | 62.4 t/s (`90.0%` JSON)<br>**60.9 t/s** (`85.0%` Code) | 1 weight read verifies $K+1$ tokens; 0% quality loss. |
| **Iteration 2 (Act III–IVa)** | Issue `#1` | **Naive 96 MB Lobotomy** (`24L -> 14L`, cut `[8..17]`, 32k Vocab `Q2_0`, 85.9 MB) | 17.0 t/s (`0.0%` Q2_0)<br>45.8 t/s (`21.2%` Q4_0) | — | **895.4 t/s** standalone inside 96 MB L3, but cutting `blk.16` (`BI=0.094`) caused `KL = 269.41` & chat token `"assistant"` (`77091`) split. |
| **Iteration 3 (Act IVb)** | **PR #2** (`fa759c8`) | **ShortGPT + Seam Distillation (`Healed 18L`)** (`[9..13, 18]` cut, `KL = 1.71`) | **96.7 t/s** (`88.5%` JSON)<br>**77.3 t/s** (`63.4%` Code) | **63.9 t/s** (`89.2%` JSON)<br>51.2 t/s (`62.9%` Code) | Teacher agreement jumped `38.9% -> 97.82%` in 8 epochs of seam distillation. |
| **Iteration 4 (Act V)** | **PR #3** (`f238c8a`) | **14B Full-VRAM Speculative** (`Qwen2.5-Coder-14B Q4_K_M`, 8.37 GiB + Drafter = ~9.45 GiB) | — | **64.6 t/s (`1.73x` JSON!)**<br>**60.9 t/s (`1.62x` Code!)** | **14.8B running at 7B speeds!** Exposed Windows WDDM Shared Memory cliff (`37.5 -> 7.5 t/s` if >12 GB). |
| **Iteration 5 (Act VI)** | **PR #4** (`4c0e53b`) | **`Healed 14L` & `Dory-Looped 19L`** (`5 In + 5×2 Recurrent + 4 Out`, same 14 physical layers) | **99.8 t/s (`1.39x` Peak!)**<br>Dory Code: `49.3% -> 56.4%` (`+7.1%` Acc!) | **64.6 t/s (`1.73x` Peak!)**<br>Dory Code: `46.5% -> 48.1%` | Shallower `Healed 14L` hits **99.8 t/s** on JSON; Dory looping adds 5 layers of coding circuit depth with zero extra weight memory. |
| **Iteration 6 (Act VII)** | **PR #4** (`4c0e53b`) | **Native 32k-Vocab Chat Distillation** (`distill_32k_dory_and_14l.py`) | **681.3 t/s** Standalone (`Healed 14L 32k`) | **560.7 t/s** Standalone (`Dory 19L 32k`) | Solved missing `"assistant"` token (`ID 77091 -> [395, 11202]`), reaching `95.16%` teacher agreement. |

---

## 🎙️ Full Production Script

### [COLD OPEN]
* **[VISUAL / B-ROLL]:** *Fast-cut macro shots of an AMD Radeon RX 6700 XT Fighter spinning up; GPU-Z sensor logs spiking; Vulkan terminal flying past 99.8 tokens/second; synthwave bassline drops.*
* **HOST:**
  > *"What if I told you that your midrange $300 gaming GPU has a 1-Terabyte-per-second supercomputer hiding inside its silicon—and the only reason your local AI feels slow is because it's stuck in traffic on a 192-bit highway? Welcome back to Silicon Surgery. Today, we're strapping twin-turbo afterburners onto an AMD Radeon RX 6700 XT, performing open-brain surgery on a neural network, looping its middle layers like NVIDIA's newest lab experiment, and making a 14.8-Billion-parameter coding monster run at 7B speeds."*

---

### [ACT I: THE 192-BIT BOTTLENECK]
* **[ON-SCREEN GRAPHIC]:** *Diagram showing `4.68 GB (7B Weights)` squeezing through a `192-bit GDDR6 Pipe (384 GB/s)` once for every single generated word.*
* **HOST:**
  > *"Here's the dirty secret of running LLMs locally: generating tokens one by one isn't compute-bound—it's **memory-bandwidth bound**. Every single word our 7-Billion-parameter Qwen 2.5 Coder writes forces the RX 6700 XT to haul **4.68 Gigabytes** of weights across a 192-bit GDDR6 bus running at 384 GB/s. Even with 40 RDNA 2 Compute Units sitting right there, that physics speed limit locks us at **71.5 tokens per second** (`EXP-005`). And if we load a **14.8-Billion-parameter** model (`8.37 GiB`)? It drops in half to **37.4 tokens per second**."*

---

### [ACT II: THE TWIN-ENGINE HUSTLE (SPECULATIVE DECODING)]
* **[ON-SCREEN GRAPHIC]:** *Split-screen animation: Tiny `0.5B Q4_0 (330 MB)` sprinter drafting 3 tokens -> Giant `7B Q4_K_M (4.68 GB)` verifier stamping all 3 in a single parallel matrix multiply.*
* **HOST:**
  > *"So how do we cheat the speed of light? **Speculative Decoding** ([README.md](../README.md)). We park a tiny **0.5-Billion-parameter draft engine** (`330 MB`) right next to the 7B giant inside our 12 GB of VRAM. The little guy guesses $K=3$ tokens at lightning speed, and the 7B model checks all 3 guesses in **a single memory read**. Instead of hauling 4.68 GB across the bus four times, we haul it **once**.*
  > *Result? Boom: **95.5 tokens per second** on JSON tool calls (`+33.2%`) and **85.8 tokens per second** on Python code (`+20.2%`)—with **zero** loss in intelligence, because the 7B verifier mathematically guarantees every single token."*

---

### [ACT III: BRAIN SURGERY FOR THE 96 MB INFINITY CACHE]
* **[ON-SCREEN GRAPHIC]:** *Die shot of AMD Navi 22 highlighting the 96 MB Infinity Cache SRAM ring (>1,000 GB/s) vs. external GDDR6 chips (384 GB/s).*
* **HOST:**
  > *"Then we got greedy. The RX 6700 XT has a secret weapon AMD built for 1440p gaming: **96 Megabytes of Infinity Cache**—on-die L3 SRAM running at over **1,000 GB/s**. Our 0.5B draft model is 330 MB—just a little too fat to stay pinned in that cache. If we can shrink it under 90 MB, the draft engine never even has to touch GDDR6 VRAM!*
  > *So in [`scripts/vocab_prune.py`](../scripts/vocab_prune.py) and [`scripts/layer_prune.py`](../scripts/layer_prune.py), we took a scalpel to the model: sliced the vocabulary from 151,936 down to 32,768, chopped out 10 middle layers (`[8..17]`), and quantized to 2-bit (`Q2_0`). It shrank to **85.9 Megabytes** and screamed at **895.4 tokens per second** standalone inside the Infinity Cache!"*

---

### [ACT IV: THE LOBOTOMY DISASTER & THE SHORTGPT DISTILLATION HEAL (`PR #2`)]
* **[ON-SCREEN GRAPHIC]:** *Red alert banner: `Issue #1: 0.0% Acceptance Rate (KL Divergence = 269.41)` -> Green MRI heatmap from `profile_layer_importance.py` showing `blk.16` spike -> `KL = 1.71 (97.82% Teacher Agreement)`.*
* **HOST:**
  > *"Wait—plot twist! When we hooked our 86 MB speed demon up to the 7B verifier... **0% speculative acceptance** ([`EXP-011`](../MEMORY/EXPERIMENT_LOG.md)). Even in 4-bit `Q4_0`, acceptance cratered to `21.2%` (`45.8 t/s`). We didn't build a draft engine—we gave it a lobotomy!*
  > *Why? To find out, we built a neural MRI scanner ([`scripts/profile_layer_importance.py`](../scripts/profile_layer_importance.py)) using **ShortGPT Block Influence** (`1 - cos_sim(X_in, X_out)`). Look at the scan: blindly chopping layers 8 through 17 severed **Layer 16** (`BI = 0.0941`), a critical structural bridge near the end of the network, warping the output logits (`KL = 269.41`).*
  > *When we moved the surgical cut to the true redundant valley—layers `[9, 10, 11, 12, 13, 18]`—and ran [`scripts/heal_draft_model.py`](../scripts/heal_draft_model.py) to stitch the surgical seams (`o_proj`, `down_proj`, `LayerNorm`) back together using **Top-128 Logit KL + Hidden-State Cosine Knowledge Distillation**, watch what happened in 8 epochs: Teacher agreement rocketed from **38.9% to 97.82%**, KL divergence crashed from **269.41 down to 1.71**, and on live RX 6700 XT silicon (`PR #2`), our healed 18-layer drafter hit **96.7 tokens per second**!"*

---

### [ACT V: THE 14.8-BILLION-PARAMETER MONSTER IN 12 GB VRAM (`PR #3`)]
* **[ON-SCREEN GRAPHIC]:** *VRAM gauge filling to `9.45 GiB / 12.0 GiB` (`8.37 GiB 14B Verifier + 0.28 GiB Healed Drafter + Q8_0 KV Cache`). Bar chart jumping from `37.4 t/s` -> `64.6 t/s (1.73x)`.*
* **HOST:**
  > *"Next, we asked: if speculative decoding saves memory bandwidth on a 7B model, what happens when we push the RX 6700 XT's 12 GB VRAM to the absolute limit with **`Qwen2.5-Coder-14B-Instruct-Q4_K_M`** (`8.37 GiB`, 48 layers, 14.77B parameters)?*
  > *First, we hit a classic Windows hardware trap ([`docs/14B_FULL_VRAM_SPECULATIVE.md`](../docs/14B_FULL_VRAM_SPECULATIVE.md)): when an old 7B background server was still holding 5 GB of VRAM, Windows WDDM didn't crash—it silently paged 2 GB of the 14B model into system DDR4 over PCIe, tanking speed from `37.5 t/s` down to `7.5 t/s`! Once we cleared VRAM so the entire `9.45 GiB` dual-engine stack lived 100% in GDDR6, look at [`tools/benchmark_14b_vram.py`](../tools/benchmark_14b_vram.py):*
  > *Standalone 14B runs at **37.4 tokens/sec**. Strap on our surgical draft engine? **64.6 tokens/sec on JSON (`1.73x speedup — +72.7%!`)** and **60.9 tokens/sec on Python code (`1.62x speedup`)**. Our 12 GB RX 6700 XT is now running a **14.8-Billion-parameter** model nearly as fast as a standalone 7B model!"*

---

### [ACT VI: ENTER NVIDIA DORY — LOOPING LAYERS INSIDE THE 96 MB INFINITY CACHE (`PR #4`)]
* **[ON-SCREEN GRAPHIC]:** *Animation of `Dory1.0-4B` (`Input [0..4] -> Recurrent [5..9] x 2 Loops with Gated Anchor Re-Injection -> Output [10..13]`) staying 100% inside the 96 MB Infinity Cache.*
* **HOST:**
  > *"Then we saw Kai's breakdown of NVIDIA Nemotron Labs' **`Dory1.0-4B`** ([`youtube.com/watch?v=XK_hz11tmuc`](https://www.youtube.com/watch?v=XK_hz11tmuc))—a model that re-runs its own middle layers up to 4 times per token to gain reasoning and coding depth without adding a single byte of file size.*
  > *Here's the catch on normal GPUs: Dory-4B is 3.67 GB. It doesn't fit in L3 cache! So looping it 4 times forces the GPU to re-read 6.9 GB from VRAM per token—a 2.4x speed penalty. **But what if the model fits inside our 96 MB Infinity Cache?!** Inside 1 TB/s on-die SRAM, re-running middle layers doesn't touch GDDR6 VRAM!*
  > *In [`scripts/test_looped_draft.py`](../scripts/test_looped_draft.py) and [`scripts/build_dory_and_14l_healed.py`](../scripts/build_dory_and_14l_healed.py), we took our 14 physical ShortGPT layers (`KEEP_14`) and built two head-to-head contenders:*
  > *1. **`Healed 14L` (14 Linear Passes):** Because it's 22% shallower than 18L while keeping `88.5%` JSON acceptance, it shattered our all-time speed records on both verifiers: **99.8 tokens/sec (`1.39x`) on 7B** and **64.6 tokens/sec (`1.73x`) on 14B**!*
  > *2. **`Dory-Looped 19L` (5 Input + 5×2 Recurrent + 4 Output = 19 Effective Passes from the Exact Same 14 Physical Layers):** Adding that second recurrent pass over layers `5..9` cut Teacher KL divergence by another **18.8% (`8.35 -> 6.78`)** and lifted live **7B Python Code acceptance from `49.3%` (`67.9 t/s`) up to `56.4%` (`70.9 t/s`, +7.1% acceptance)**—proving on real silicon that looping middle layers buys coding circuit depth for free!"*

---

### [ACT VII: THE CASE OF THE MISSING `"assistant"` TOKEN (`ID 77091`)]
* **[ON-SCREEN GRAPHIC]:** *Tokenizer debugger zoom-in: `<|im_start|>assistant\n` -> 152k ID `[151644, 77091, 198]` vs. 32k ID `[32755, 395 ("ass"), 11202 ("istant"), 198]`.*
* **HOST:**
  > *"There was one mystery left. Why did our 32,768-vocabulary models write gibberish whenever we used a chat prompt? We ran a token diff and found the smoking gun: in Qwen 2.5, the word `assistant` inside `<|im_start|>assistant\n` is **Token ID 77091**! When `vocab_prune.py` kept the first 32,754 tokens, `77091` got deleted, splitting `assistant` into two sub-tokens (`[395, 11202]`) that the un-distilled embeddings had never seen after `<|im_start|>`!*
  > *Once we built [`scripts/distill_32k_dory_and_14l.py`](../scripts/distill_32k_dory_and_14l.py) to distill the 32k models directly on 32k-tokenized chat sequences (`95.16%` teacher agreement), our ultra-compact 32k models started spitting out clean Python binary search functions at **560 to 681 tokens per second**!"*

---

### [ACT VIII: WHAT OTHER "INFINITY CACHE" CHIPS CAN RUN THIS? (OUTRO)]
* **[ON-SCREEN GRAPHIC]:** *Hardware Tier Matrix showing AMD RDNA 2/3/4 (32–128 MB MALL), NVIDIA Ada/Blackwell (32–96 MB L2), AMD Ryzen X3D / EPYC-X (96–1,152 MB 3D V-Cache), and Ryzen AI Max+ 395 Strix Halo (32 MB MALL).*
* **HOST:**
  > *"And the best part? This isn't just an RX 6700 XT trick ([`docs/INFINITY_CACHE_HARDWARE_MATRIX.md`](INFINITY_CACHE_HARDWARE_MATRIX.md)). Every chip built around a massive SRAM cache shielding a narrow memory bus can run this exact playbook:*
  > *- **AMD RDNA 2, 3 & 4 GPUs:** From the 128 MB Infinity Cache on RX 6800/6900 XT to the 64 MB RX 9070 XT and 128-bit RX 7600 XT / 9060 XT 16GB.*
  > *- **NVIDIA's 128-Bit 'Mega-L2' Cards:** The **RTX 4060 Ti 16GB** and **RTX 5060 Ti 16GB** pack 16 GB of VRAM behind a tiny 128-bit bus buffered by **32 MB of L2 SRAM**—and CUDA even lets you hardware-pin our surgical drafter inside L2!*
  > *- **AMD Ryzen X3D & EPYC-X CPUs:** A **Ryzen 7 5800X3D, 7800X3D, or 9800X3D** has **96 MB of 3D V-Cache** running at >2 TB/s sitting in front of 50–85 GB/s system RAM—meaning our <85 MB surgical draft model runs 100% inside CPU L3 cache with a 25x bandwidth advantage!*
  > *- **AMD Strix Halo (`Ryzen AI Max+ 395`) & Apple Silicon (`M-Max/Ultra`):** Unified memory monsters where a 32–96 MB MALL/SLC cache can feed a surgical drafter while 70B models live in unified LPDDR5X.*
  > *All the code, surgical scripts, and benchmarks are live on GitHub right now. Clone the repo, fire up `start_local_server.ps1`, and I'll catch you in the next episode of Silicon Surgery!"*
