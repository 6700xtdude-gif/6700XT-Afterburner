# Gaps and Hypotheses

## HYP-001: Disabling Smart App Control unblocks all native llama.cpp Vulkan executables
- **Hypothesis:** Once Smart App Control is disabled in Windows Security, `llama-bench.exe` and `llama-cli.exe` will launch immediately and successfully bind to the AMD proprietary Vulkan driver (`vulkaninfo` device 0: AMD Radeon RX 6700 XT).
- **Status:** Unverified; awaiting owner decision on Windows Security configuration.

## GAP-001: Model Surgery Environment Dependencies
- **Gap:** Python 3.12 is installed, but domain packages (`torch`, `transformers`, `accelerate`, `sentencepiece`, `gguf`) are not yet installed in Python.
- **Plan:** Install these packages into the native Python 3.12 environment when ready for Phase 2 surgery scripts.
