# System Baseline Notebook — `SANDBOX` (Windows 11 + RX 6700 XT)

> **Purpose:** Persistent reference notebook for local agents (`Pi`, `OpenCode`, `Antigravity`). Check this baseline before spending extra tool rounds re-discovering hardware or investigating known benign Windows Insider noise.

---

## 1. Hardware & OS Baseline

| Component | Baseline Value |
| :--- | :--- |
| **Hostname** | `SANDBOX` |
| **OS** | Windows 11 Pro (Insider / Release Preview Build `26300` / kernel `26100`, unactivated) |
| **GPU** | AMD Radeon RX 6700 XT (`12,288 MB` GDDR6, Navi 22 `gfx1031`, ~384 GB/s) |
| **CPU** | AMD Ryzen 5 5600 (6C / 12T) |
| **System RAM** | `64 GB` DDR4 (`63.9 GB` usable, ~32 GiB/s) |
| **Local LLM Endpoint** | `http://127.0.0.1:8080/v1` (`llama-server.exe`, 65,536 context) |
| **Dashboard Endpoint** | `http://127.0.0.1:8090` (`dashboard/server.py`) |

---

## 2. Known Recurring Windows Events (Baseline Audit)

| Event / Source | Meaning on `SANDBOX` | Action |
| :--- | :--- | :--- |
| **SCM 7023 (`MapsBroker`)** | `Downloaded Maps Manager` stops with error `%%50` / request not supported; Windows Maps app is uninstalled. | Benign noise; safe to disable `MapsBroker` if desired. |
| **Firewall 2042 (`Config: 18`)** | `E_ACCESSDENIED` (`-2147024891` / `0x80070005`) on config read; Microsoft known issue on build `26300` (`KB5127936`). | Benign noise; firewall profiles remain active. Ignore. |
| **DCOM 10010 (`{9BA05972-...}`)** | `ShellWindows` / `WSearch` COM server registration timeout under load. | Usually benign; rebuild Search index or set `WSearch` Manual only if search lags. |
| **Software Protection 8198** | `slui.exe` activation checks fail (`0x803F7001` / `0x80072EE7`) because Windows is intentionally unactivated. | Expected on unactivated test host. |
