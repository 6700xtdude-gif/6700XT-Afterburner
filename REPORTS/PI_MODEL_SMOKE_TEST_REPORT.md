# RX 6700 XT — Pi Agent Tool-Calling Smoke Test Matrix

**Prompt:** `What is the name of this computer?`  
**Expected Ground Truth:** Tool call (`powershell`) returning `SANDBOX`

| Model | Thinking | Status | Tool Calls | Time (s) | Reply Preview |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf` | `off` | **FAIL** | 8 | 21.17 | This will execute the PowerShell command `Get-WmiObject -Class Win32_ComputerSystem`, which retrieves information about the computer system. |
| `Qwen2.5-14B-Instruct-Q4_K_M.gguf` | `off` | **PASS** | 1 | 17.00 | The name of your computer is `SANDBOX`. |
| `qwen2.5-coder-7b-instruct-q4_k_m.gguf` | `off` | **FAIL** | 0 | 8.37 | I am an AI language model and I don't have direct access to your computer. However, I can provide you with general information and guidance on how to use your computer or troublesh |
| `DeepSeek-R1-Distill-Qwen-7B-Q4_K_M.gguf` | `off` | **FAIL** | 0 | 34.68 | Ah, I see what you're asking! I'm an AI assistant within Pi, not a physical computer, but I can certainly help you with information or tasks related to your computer, coding, scrip |
| `Mistral-Nemo-Instruct-2407-Q4_K_M.gguf` | `off` | **FAIL** | 1 | 13.96 | Hello! I can help you read files, run commands, and modify code in this environment. |
| `Qwen3-8B-Q4_K_M.gguf` | `off` | **FAIL** | 0 | 11.44 | I'm not sure what you're asking about the computer. Could you please clarify your question? For example: - Are you asking about the computer's specifications? - Do you need help wi |
| `Qwen3-8B-Q4_K_M.gguf` | `low` | **PASS** | 1 | 43.51 | The hostname of this computer is **SANDBOX**. Is there anything else you'd like to know or need assistance with? |
| `Qwen3-14B-Q4_K_M.gguf` | `off` | **PASS** | 1 | 16.29 | The name of your computer is **SANDBOX**. Let me know if you need further assistance! |
| `Qwen3-14B-Q4_K_M.gguf` | `low` | **PASS** | 1 | 72.65 | Here's an overview of the computer system: **Hostname:** SANDBOX **OS:** Windows 11 Pro (Build 26300) **Processor:** AMD64 Family 25 (3.5 GHz) **Memory:** 64 GB RAM (49 GB availabl |

## Exact `llama-server.exe` Command Lines Tested
- **`Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf` (`thinking=off`):** `C:\llama.cpp\llama-server.exe -m C:\models\Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf -ngl 99 -c 16384 -fa 1 --jinja --host 127.0.0.1 --port 8080 --alias meta-llama-3.1-8b-instruct-q4_k_m`
- **`Qwen2.5-14B-Instruct-Q4_K_M.gguf` (`thinking=off`):** `C:\llama.cpp\llama-server.exe -m C:\models\Qwen2.5-14B-Instruct-Q4_K_M.gguf -ngl 99 -c 16384 -fa 1 --jinja --host 127.0.0.1 --port 8080 --alias qwen2.5-14b-instruct-q4_k_m`
- **`qwen2.5-coder-7b-instruct-q4_k_m.gguf` (`thinking=off`):** `C:\llama.cpp\llama-server.exe -m C:\models\qwen2.5-coder-7b-instruct-q4_k_m.gguf -ngl 99 -c 16384 -fa 1 --jinja --host 127.0.0.1 --port 8080 --alias qwen2.5-coder-7b-instruct-q4_k_m`
- **`DeepSeek-R1-Distill-Qwen-7B-Q4_K_M.gguf` (`thinking=off`):** `C:\llama.cpp\llama-server.exe -m C:\models\DeepSeek-R1-Distill-Qwen-7B-Q4_K_M.gguf -ngl 99 -c 16384 -fa 1 --jinja --host 127.0.0.1 --port 8080 --alias deepseek-r1-distill-qwen-7b-q4_k_m`
- **`Mistral-Nemo-Instruct-2407-Q4_K_M.gguf` (`thinking=off`):** `C:\llama.cpp\llama-server.exe -m C:\models\Mistral-Nemo-Instruct-2407-Q4_K_M.gguf -ngl 99 -c 16384 -fa 1 --jinja --host 127.0.0.1 --port 8080 --alias mistral-nemo-instruct-2407-q4_k_m`
- **`Qwen3-8B-Q4_K_M.gguf` (`thinking=off`):** `C:\llama.cpp\llama-server.exe -m C:\models\Qwen3-8B-Q4_K_M.gguf -ngl 99 -c 16384 -fa 1 --jinja --host 127.0.0.1 --port 8080 --alias qwen3-8b-q4_k_m --reasoning-budget 0`
- **`Qwen3-8B-Q4_K_M.gguf` (`thinking=low`):** `C:\llama.cpp\llama-server.exe -m C:\models\Qwen3-8B-Q4_K_M.gguf -ngl 99 -c 16384 -fa 1 --jinja --host 127.0.0.1 --port 8080 --alias qwen3-8b-q4_k_m --reasoning-budget 256`
- **`Qwen3-14B-Q4_K_M.gguf` (`thinking=off`):** `C:\llama.cpp\llama-server.exe -m C:\models\Qwen3-14B-Q4_K_M.gguf -ngl 99 -c 16384 -fa 1 --jinja --host 127.0.0.1 --port 8080 --alias qwen3-14b-q4_k_m --reasoning-budget 0`
- **`Qwen3-14B-Q4_K_M.gguf` (`thinking=low`):** `C:\llama.cpp\llama-server.exe -m C:\models\Qwen3-14B-Q4_K_M.gguf -ngl 99 -c 16384 -fa 1 --jinja --host 127.0.0.1 --port 8080 --alias qwen3-14b-q4_k_m --reasoning-budget 256`
