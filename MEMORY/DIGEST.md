# Memory Digest — 6700XT-Afterburner

## Active Context & State
- **GitHub Repository:** https://github.com/6700xtdude-gif/6700XT-Afterburner (`main` branch synced with **PR #2**, **PR #3**, and **PR #4** merged, plus YouTube Show script & Infinity Cache hardware compatibility matrix).
- **Host:** Windows 11 Pro, Ryzen 5 5600 (6C/12T), 64 GB DDR4-3200, AMD Radeon RX 6700 XT 12 GB (`Navi 22` / `gfx1031` Vulkan).
- **Active Phase:** Production Ready — Full-VRAM 7B (`99.8 t/s`) & 14B (`64.6 t/s`) Speculative Decoding + Healed 14L / Dory-Looped 19L / Healed 18L Draft Suite.

## Current Production Stack
- **Live Server Launcher (`start_local_server.ps1`):**
  - **Web Chat UI (Humans):** `http://127.0.0.1:8080/`
  - **OpenAI-Compatible API (Agents/Tools):** `http://127.0.0.1:8080/v1`
  - **Launch Modes:**
    - `.\start_local_server.ps1 -Mode healed14l -K 3` (**99.8 t/s** Peak 7B JSON Record!)
    - `.\start_local_server.ps1 -Mode dory19l -K 3` (14 physical layers -> 19 effective layers via 2x recurrent loop)
    - `.\start_local_server.ps1 -Mode healed18l -K 3` (**96.7 t/s** JSON / **77.3 t/s** Python Code on 7B)
    - `.\start_local_server.ps1 -Mode speculative14b -K 3` (100% VRAM 14B Verifier at **64.6 t/s** JSON / **60.9 t/s** Code)
    - `.\start_local_server.ps1 -Mode speculative -K 3` (24L unpruned drafter)
    - `.\start_local_server.ps1 -Mode moe35b` (Hybrid 35B-A3B MoE)
- **Active Models Available:**
  - **14B Verifier (Full-VRAM Heavyweight):** `Models/Qwen2.5-Coder-14B-Instruct-GGUF/qwen2.5-coder-14b-instruct-q4_k_m.gguf` (8.37 GiB, 100% in VRAM, **64.6 t/s JSON (`1.73x`) / 60.9 t/s Code (`1.62x`)** over 37.4 t/s standalone!)
  - **7B Verifier (High-Throughput Target):** `Models/Qwen2.5-Coder-7B-Instruct-GGUF/qwen2.5-coder-7b-instruct-q4_k_m.gguf` (4.68 GB, 100% in VRAM, **99.8 t/s (`1.39x`)** peak with Healed 14L drafter)
  - **Healed 14L Draft (`healed14l`):** `Models/Qwen2.5-Coder-0.5B-L14-Healed/Qwen2.5-Coder-0.5B-L14-Healed-Q4_0.gguf` (243 MiB, 14 ShortGPT layers, **99.8 t/s** on 7B & **64.6 t/s** on 14B) + 32k-distilled 96 MB Infinity Cache edition (`681.3 t/s` standalone)
  - **Dory-Looped 19L Draft (`dory19l`):** `Models/Qwen2.5-Coder-0.5B-Dory19L-Healed/Qwen2.5-Coder-0.5B-Dory19L-Healed-Q4_0.gguf` (279.9 MiB, 14 physical layers with `5..9` weight-tied $2\times$ = 19 effective layers, `KL = 6.78`, **`+7.1%` higher Python Code acceptance** than linear 14L)
  - **Healed 18L Draft (`healed18l`):** `Models/Qwen2.5-Coder-0.5B-L18-Healed/Qwen2.5-Coder-0.5B-L18-Healed-Q4_0.gguf` (282 MiB, 18 layers, `97.82%` teacher agreement, `KL = 1.71`)
  - **Unpruned Baseline Draft (`speculative`):** `Models/Qwen2.5-Coder-0.5B-Instruct/Qwen2.5-Coder-0.5B-Instruct-Q4_0.gguf` (330 MiB, 24 layers)
  - **MoE 35B Verifier (`moe35b`):** `Models/qwen36-UD-Q4_K_XL/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf` (22.8 GB, 15.4 t/s hybrid VRAM/RAM)

## Verified Benchmark Records (RX 6700 XT Vulkan, N=128, Temp=0.0)
- **Standalone 7B Baseline:** `71.4 – 71.7 tokens/sec` (`1,771.8 ms`)
- **Speculative 7B + Healed 14L Surgery Draft ($K=3$):** **`99.8 t/s` JSON (`88.5%` acceptance, `1.39x` ALL-TIME 7B RECORD!)**
- **Speculative 7B + Dory-Looped 19L Draft ($K=3$):** `92.5 t/s` JSON, **`70.9 t/s` Python Code (`56.4%` acceptance, `+7.1%` over Linear 14L using same 14 physical layers!)**
- **Speculative 7B + Healed 18L Surgery Draft ($K=3$):** `96.7 t/s` JSON (`88.5%` acceptance), **`77.3 t/s` Python Code (`63.4%` acceptance)**
- **Standalone 14B Baseline (100% VRAM):** `37.4 – 37.5 tokens/sec`
- **Speculative 14B + Healed 14L Draft ($K=3$):** **`64.6 t/s` JSON (`86.7%` acceptance, `1.73x` ALL-TIME 14B SPEEDUP RECORD!)**
- **Speculative 14B + Unpruned 24L / Healed 18L Draft:** **`60.9 t/s` Python Code (`1.62x` speedup)** / `63.9 t/s` JSON (`1.71x`)
- **Documentation & Show Script:** `docs/YOUTUBE_SCRIPT.md`, `docs/INFINITY_CACHE_HARDWARE_MATRIX.md`, `docs/14B_FULL_VRAM_SPECULATIVE.md`, `docs/DORY_LOOPED_96MB_SURGERY.md`.
