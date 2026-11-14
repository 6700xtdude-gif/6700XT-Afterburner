# Lessons Learned

## Windows 11 Smart App Control (SAC) & Local AI Binaries
- **Lesson:** Windows 11 with Smart App Control enabled (`VerifiedAndReputablePolicyState = 1`) uses kernel Code Integrity to block unsigned, third-party compiled binaries (e.g. `llama.cpp` GitHub releases).
- **Verification:** Observed in `Microsoft-Windows-CodeIntegrity/Operational` Event Log ID 3077/3118 when invoking `llama-cli.exe`.
- **Impact:** Local LLM development and custom Vulkan shader binary forks require either disabling Smart App Control or running exclusively through signed host runtimes (e.g., Python).

## Cross-Model Vocabulary Alignment in Speculative Decoding
- **Lesson:** Autoregressive speculative verification engines (`llama.cpp`, `vLLM`) enforce strict vocabulary identity (`vocab_type`, `n_vocab`, `bos`, `eos`). Slicing or pairing models across generational boundaries (e.g., Qwen 2.5 with 152k vocab vs. Qwen 3.5/3.6 with 248k vocab) triggers instant compatibility rejection unless a bridge mapping kernel (`draft_to_verifier_id.bin`) is interposed.
- **Verification:** Observed `common_specu: draft model vocab type must match target model to use speculation`. Pairing dense Qwen 2.5 Coder 7B with Qwen 2.5 0.5B achieved immediate `vocab_cmpt = 1` and 71.1% acceptance rate.

## VRAM Co-Location & Navi 22 Infinity Cache Impact
- **Lesson:** When both target and draft models fit 100% device-local in 12 GB VRAM (5.2 GB combined for 7B Q4 + 0.5B Q4), the 192-bit GDDR6 memory bus bottleneck is dramatically reduced. Verification runs at 50–70+ tokens/sec sustained latency, returning complete agentic tool responses in under 700 ms.

## End-to-End Context Window Consistency (Agent Harness -> Inference Server)
- **Lesson:** Agentic harnesses (e.g., Pi, Claude Code) inject extensive multi-tool system instructions, schemas (PowerShell, Bash, search), and repository context that quickly exceed 8k tokens on turn 1 (e.g. 8,679+ tokens). If the inference server (`llama-server.exe`) is launched with a legacy `-c 8192` window, incoming requests immediately trigger HTTP 400 (`exceed_context_size_error: request exceeds the available context size`).
- **Invariant:** The context window size must be identical end-to-end between the client configuration (`models.json: contextWindow: 65536`) and the server launcher (`start_local_server.ps1 -CtxSize 65536` -> `llama-server.exe -c 65536`).
- **Silicon & KV Cache Rule:** On the 12 GB VRAM budget of the RX 6700 XT, running a 64k context window on 27B/14B models requires KV cache quantization (`-ctk q4_0 -ctv q4_0` or `-ctk q8_0 -ctv q8_0`) with Flash Attention (`-fa on`) so that KV cache allocation does not spill into DDR4 or trigger Vulkan device OOM.

## DDR4 Bandwidth Cliff vs. Memory Capacity (32GB vs 64GB Invariant)
- **Lesson:** Autoregressive single-token decode is strictly memory bandwidth-bound. Dual-channel DDR4-3200 delivers ~32 GiB/s regardless of whether 32GB or 64GB capacity is installed. Spilling dense layers into DDR4 incurs a 12x latency penalty (~165 ms CPU read vs ~26 ms GPU read). Upgrading capacity does not improve decode speed for dense models.
- **Capacity Value:** 64GB capacity is strictly necessary for holding 20GB+ MoE weights (e.g., Qwen 3.6 35B A3B) alongside operating system, browser, and 64k KV caches, preventing catastrophic Windows NVMe SSD paging thrash (<1 t/s) and enabling offline quantization of 50GB+ BF16 sources without memory exhaustion.

## Windows Pagefile Paging & LLM Memory Overcommit
- **Lesson:** When Windows manages the pagefile dynamically, rapid memory commits during model loading or context expansion can trigger latency spikes. A manual pre-allocated pagefile (1.5x min / 3x max) stabilizes virtual commit limits, but requires a system reboot. If working set fits within physical RAM, pagefile configuration has negligible effect on tokens/sec.


## Native MTP (Multi-Token Prediction) Speculation vs. Separate Drafter
- **Lesson:** Cross-generational model pairing (e.g. Qwen 2.5 drafter with Qwen 3.8 verifier) is blocked by vocabulary mismatches (152k vs 248k). Native MTP draft heads (e.g. `blk.64` in Qwen 3.8) eliminate this issue by sharing the base model's exact embeddings and vocabulary.
- **Verification:** Using `--spec-type draft-mtp` achieved 74%–81% draft acceptance without loading a separate secondary GGUF or managing two processes.

## Quantizing Speculative Heads (The Missing Imatrix Blk.64 Trap)
- **Lesson:** Downstream importance matrices provided by model hubs often profile only the core transformer layers (blocks 0..63) and omit the extra MTP layer (`blk.64`). In sub-3-bit quantization (`IQ2_M`), `llama-quantize` aborts with an error if any tensor is missing an imatrix entry.
- **Fix:** Pass `--tensor-type "blk.64.*=q4_K"`. This quantizes the MTP head into Q4_K (which does not require an imatrix), adding only ~93 MB to the file footprint while improving draft accuracy.

## Reasoning Models & Quality Verification Gates
- **Lesson:** Modern reasoning models (e.g. Qwen 3.8) output extended chain-of-thought traces inside `<think>` or `reasoning_content` before generating the final answer. Testing with short token limits (`max_tokens <= 128`) causes the model to exhaust its budget inside the thinking phase, leaving `content` empty and causing syntax or schema checkers to fail.
- **Rule:** Quality gates must set sufficient headroom (`max_tokens >= 512`) and parse the final emitted `content` rather than the thinking trace.
