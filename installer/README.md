# 6700XT-Afterburner Cross-Platform Installer (`Go` + `charmbracelet/huh`)

Standalone zero-dependency (`CGO_ENABLED=0`) TUI installer for Windows 11 (`amd64`) and Linux (`amd64` — Ubuntu, Linux Mint, Omarchy) tailored to the **AMD Radeon RX 6700 XT (12 GB GDDR6 / Navi 22 / `gfx1031`)**.

## Features

1. **Hardware & Driver Check (`--check`):**
   - **Windows:** Detects RX 6700 XT (`VEN_1002&DEV_73DF`), RAM, Smart App Control (`SAC`), PowerShell execution policy, `vulkaninfo`, `llama.cpp`, `node`, `pi`, and `uv`.
   - **Linux:** Inspects `/sys/class/drm/card*/device/{vendor,device}` (`0x1002:0x73df`), `lspci`, `/proc/meminfo`, `vulkaninfo`, and `rocminfo`.
2. **Official `llama.cpp` Vulkan Installer:** Queries recent `ggml-org/llama.cpp` GitHub releases for `bin-win-vulkan-x64.zip` or `bin-ubuntu-vulkan-x64.tar.gz` and unpacks into `<install-dir>/bin/vulkan/`.
3. **Curated RX 6700 XT 12 GB GGUF Downloader:** Resumable HTTP `Range` downloads from Hugging Face (`Qwen2.5-Coder-7B` + `0.5B` stock drafter, `Qwen2.5-Coder-14B`, `Qwen3-8B`, `Qwen3-14B`).
4. **Pi (`pi.dev`) + Launchers:** Installs Pi cleanly, writes UTF-8 (no BOM) `models.json` (`32K` context), `settings.json` (`powershell` on Windows without `bash`; `bash` on Linux), `AGENTS.md`, and generates router (`-c 32768 -ctk q4_0 -ctv q4_0`), speculative, and Open WebUI (`uvx`, port `3000`) launchers.

## Build from Windows (PowerShell)

```powershell
.\build.ps1
```

This runs `go vet ./...`, `go test -v ./...`, and outputs:
- `dist/rx6700xt-installer-windows-amd64.exe`
- `dist/rx6700xt-installer-linux-amd64`
- `dist/SHA256SUMS.txt`

## Platform Notes

- **Linux ROCm (`gfx1031`):** Vulkan works out of the box with `mesa-vulkan-drivers` and `vulkan-tools`. If you also use ROCm tools on RDNA 2 (`gfx1031`), set `HSA_OVERRIDE_GFX_VERSION=10.3.0`.
- **Windows Smart App Control (`SAC = 1`):** Windows Smart App Control checks Authenticode signatures and cloud reputation on any compiled `.exe` regardless of language (`Go`, `PS2EXE`, `Nuitka`, C++). Unsigned binaries run normally where `SAC = 0`, while `SAC = 1` machines require code signing (e.g., SignPath or Azure Trusted Signing) or a `.cmd` script wrapper.
