# Dory-Style Latent-Recurrent Layer Looping for the 96 MB Infinity Cache

## 1. Motivation & Research Background (`NVIDIA Dory1.0-4B`)
Inspired by **NVIDIA Nemotron Labs' `Dory1.0-4B`** looped (latent-recurrent) transformer ([`youtube.com/watch?v=XK_hz11tmuc`](https://www.youtube.com/watch?v=XK_hz11tmuc)), which splits its transformer stack into an **Input Block**, a **Recurrent Middle Block** (looped $1\text{--}4\times$ per token with input anchor re-injection), and an **Output Block**:

* **The Problem on Standard GPUs:** When a 3.67 GB model like Dory1.0-4B loops its middle layers $4\times$, it overflows L3 cache and must stream **~6.9 GB of weights per token** from GDDR6 VRAM, causing a **2.4x–2.6x speed penalty**.
* **Our RX 6700 XT 96 MB Infinity Cache Advantage:** When our 14-layer surgical draft model (`<90 MB` in `Q2_0`) is pinned **100% inside the RX 6700 XT's 96 MB L3 Infinity Cache (>1 TB/s on-die SRAM)**, re-running a middle block of layers does **not** pay the 192-bit GDDR6 VRAM bandwidth penalty—it reads hot cache lines directly from on-die SRAM!

---

## 2. Architecture: 14 Physical Layers $\rightarrow$ 19 Effective Layers (`scripts/test_looped_draft.py`)
Using the 14 highest-importance physical layers identified by our ShortGPT Block Influence profiler (`KEEP_14 = [0, 1, 2, 3, 4, 5, 6, 7, 15, 16, 17, 20, 22, 23]`), we constructed a 3-stage **Dory-Looped 14L** architecture:

1. **Input Block (Physical Layers `0..4`):** 5 layers executed once per token. Also captures the hidden-state `anchor` entering the recurrent core.
2. **Recurrent Block Pass 1 (Physical Layers `5..9`):** 5 middle layers executed once.
3. **Dory Gated Anchor Re-Injection (`DoryReinjectLayer`):** Before Pass 2, blends Pass 1's normalized hidden state with the initial `anchor` state to prevent representation drift and norm explosion:
   $$H_{\text{loop\_in}} = (1 - \sigma(\alpha)) \cdot H_{\text{anchor}} + \sigma(\alpha) \cdot \text{RMSNorm}(H_{\text{pass1}})$$
   *(Adds only `1,792` parameters = **3.5 KB** in BF16!)*
4. **Recurrent Block Pass 2 (Physical Layers `5..9` Shared):** Re-executes the **exact same weight tensors** of layers `5..9`.
5. **Output Block (Physical Layers `10..13`):** 4 layers executed once to project into final vocabulary logits.

---

## 3. Empirical Distillation Results (8 Epochs vs. 24-Layer Teacher)

| 96 MB L3-Budget Architecture (14 Physical Layers) | Effective Depth | Unique Physical Params | Top-1 Teacher Agreement | Teacher KL Divergence |
| :--- | :---: | :---: | :---: | :---: |
| **1. Unhealed Linear 14L** | 14 Passes | 344,908,928 | 52.87% | 273.56 |
| **2. Healed Linear 14L (Seam Distilled)** | 14 Passes | 344,908,928 | 94.43% | 8.35 |
| **3. Dory-Looped 14L (`5 + 5×2 + 4`, Distilled)** | **19 Passes** | **344,910,720 (+3.5 KB)** | **95.30%** | **6.78 (-18.8% lower KL!)** |

### Key Findings:
* **Zero Weight Bloat, +5 Layers of Circuit Depth:** Using the **exact same 14 physical layers** (+3.5 KB gate), looping the 5 middle layers twice reduces Teacher KL divergence by **another 18.8% (`8.35 -> 6.78`)** and lifts Top-1 token agreement to **`95.30%`**.
* **Per-Loop KV Cache Trap Resolved:** Just as highlighted in Dory1.0-4B's `last_loop` KV cache fix, standard HuggingFace `DynamicCache` indexes by `self.layer_idx` and collides when a shared layer object executes twice; running stateless distillation (`use_cache=False`) or assigning distinct KV slot indices for recurrent passes resolves the collision cleanly.

---

## 4. Next Development & Benchmarking Milestones
1. **Export & Quantize Healed 14L + Dory-Unrolled 19L to GGUF (`Q4_0` & `Q2_0`):**
   * Export both the **Healed Linear 14L** (`KL = 8.35`, `<90 MB` in `Q2_0` / `~230 MB` in `Q4_0`) and the **Dory-Looped 14L->19L** models to GGUF with `loop_alpha` folded into the Pass-2 projection weights so stock `llama.cpp` can execute it without custom shaders.
2. **Live RX 6700 XT Vulkan Speculative Benchmark:**
   * Measure live token/sec and draft acceptance rate ($\alpha$) of **Healed 14L** vs. **Dory-Looped 14L** against both the **7B** and **14B** verifiers on RX 6700 XT Vulkan.
