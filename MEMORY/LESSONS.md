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
