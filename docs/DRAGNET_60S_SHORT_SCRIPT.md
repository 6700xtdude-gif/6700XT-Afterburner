# 🎬 Technical Breakdown: Anatomy of a Local LLM Prompt (RX 6700 XT)
**Format:** YouTube Short / Vertical Video (60 Seconds, 9:16)  
**Style:** High-density technical procedural ("Just the facts" — clinical, dry, rapid, zero fluff)  
**Target Cadence:** ~140 words (~2.3 words/sec)  
**Hardware Subject:** AMD Radeon RX 6700 XT 12 GB (`Navi 22` / 40 CUs / 96 MB Infinity Cache)

---

### [0:00 – 0:06] 1. THE INPUT
* **VISUAL:** Close crop on terminal screen. Blinking cursor. A keystroke executes:  
  `> "What is the name of this computer?"`  
  A waveform monitor spikes at the bottom of the screen.
* **VOICE (Dry, precise):**  
  > *"You enter the query: 'What is the name of this computer?' Hit Enter. Here is the path through the silicon."*

---

### [0:06 – 0:18] 2. TOKENIZATION & VRAM RESIDENCY
* **VISUAL:** The text string fractures into discrete numeric blocks: `[2061, 374, 279, 1438, 311, 428, 9063, 30]`. Camera slides into the GPU board: GDDR6 memory packages highlight solid cyan.
* **VOICE:**  
  > *"First: Tokenization. Text converts into integer IDs, mapped directly to embedding vectors. The RX 6700 XT's 12 Gigabytes of GDDR6 keeps the entire weight table resident on-card, eliminating PCIe transfer bottlenecks."*

---

### [0:18 – 0:32] 3. PROMPT PREFILL (COMPUTE-BOUND)
* **VISUAL:** Parallel data streams ignite across all 40 RDNA 2 Compute Units on the die. Frequency counter pegs at `2,550 MHz`. Matrix multiplication overlay.
* **VOICE:**  
  > *"Second: Prefill. The GPU processes the entire prompt at once. This phase is compute-bound. Forty RDNA 2 Compute Units execute dual-issue FP16 matrix instructions at 2.5 Gigahertz, calculating multi-head attention across every token simultaneously."*

---

### [0:32 – 0:46] 4. KV CACHE & INFINITY CACHE (MEMORY-BOUND)
* **VISUAL:** Attention vectors write into the KV cache. An animation contrasts the narrow 192-bit external bus with the on-die 96 MB Infinity Cache ring glowing gold.
* **VOICE:**  
  > *"Third: The KV Cache. Attention vectors are stored in memory. From here, every generated token becomes memory-bandwidth bound. AMD’s 96 Megabyte on-die Infinity Cache intercepts the access requests, delivering over one Terabyte per second of effective SRAM throughput."*

---

### [0:46 – 0:58] 5. AUTOREGRESSIVE DECODE (OUTPUT)
* **VISUAL:** Word-by-word streaming generation in terminal:  
  `"This system is Strata."`  
  Telemetry readout: `72.4 Tok/s | VRAM: 5.1 GiB | Power: 138 W`.
* **VOICE:**  
  > *"Fourth: Token generation. One forward pass per token. Weights stream, logits get evaluated, next word predicted: 'This system is Strata.' 72 tokens per second on local desktop silicon."*

---

### [0:58 – 1:00] END CARD
* **VISUAL:** Clean spec card: `RX 6700 XT | 12GB GDDR6 | 96MB Infinity Cache | 40 CUs`. Cut to black.

---

## ⏱️ Script Metrics
* **Total Word Count:** 143 words
* **Banned Words Avoided:** 0 occurrences of "honest", "honestly", "truth", "actually", "game-changer", "unleash", or cop/booking slang.
* **Technical Accuracy:** Explicitly separates Compute-bound Prefill from Memory-bound Decode.
