#!/usr/bin/env python3
"""AfterBurner Control Center backend server.

Pure Python 3.12 standard library HTTP server on 127.0.0.1:8090 providing:
- Live RX 6700 XT VRAM/Compute, CPU, RAM, and llama-server telemetry
- Model lifecycle controls (start/restart/stop via start_local_server.ps1)
- Local (6700 XT) and Cloud (OpenRouter / Gemini) prompt optimization
- Pi agent one-shot execution (--print) and interactive terminal launcher
"""

from __future__ import annotations

import ctypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
from typing import Any
import urllib.error
import urllib.request

HOST = os.environ.get("AFTERBURNER_HOST", "0.0.0.0")
PORT = 8090


def get_lan_ip() -> str:
    """Return the active local LAN IPv4 address for phone/tablet access."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("10.255.255.255", 1))
        ip = sock.getsockname()[0]
        if ip and not ip.startswith("127."):
            return ip
    except OSError:
        pass
    finally:
        sock.close()
    return "127.0.0.1"
ROOT_DIR = r"C:\Users\6700XT\Documents\Strata"
DASHBOARD_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_HTML_PATH = os.path.join(DASHBOARD_DIR, "index.html")
START_SERVER_SCRIPT = os.path.join(ROOT_DIR, "start_local_server.ps1")
LAUNCH_PI_BAT = os.path.join(ROOT_DIR, "Launch_Pi.bat")

LLAMA_BASE_URL = os.environ.get("AFTERBURNER_LLAMA_URL", "http://127.0.0.1:8080").rstrip("/")
VRAM_TOTAL_MB = 12288

VALID_MODES = {"qwen27b_vram", "qwen27b", "speculative14b"}
VALID_REASONING_BUDGETS = {0, 256, 512, -1}

TELEMETRY_CACHE_TTL_SEC = 1.2
_TELEMETRY_LOCK = threading.Lock()
_TELEMETRY_CACHE: dict[str, Any] = {"timestamp": 0.0, "data": None}
_LAST_CPU_TIMES: tuple[int, int, int] | None = None

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
CREATE_NEW_CONSOLE = getattr(subprocess, "CREATE_NEW_CONSOLE", 0x00000010)

OPTIMIZER_SYSTEM_PROMPT = (
    "You are a prompt optimizer for AfterBurner Pi, an autonomous coding agent running on "
    "Windows PowerShell in C:\\Users\\6700XT\\Documents\\Strata powered by an AMD RX 6700 XT.\n"
    "Rewrite the user's rough request by fixing typos, removing ambiguity, and turning it into a "
    "sharp, action-first prompt with explicit files/commands/verification steps where appropriate.\n"
    "Rules:\n"
    "- Keep it concise and direct.\n"
    "- Preserve the user's exact intent and technical constraints.\n"
    "- Output ONLY the rewritten prompt text. Do not include explanations, labels, or markdown wrappers."
)

_LUID_RE = re.compile(r"(luid_0x[0-9a-f]+_0x[0-9a-f]+_phys_\d+)", re.IGNORECASE)


class _MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


class _FILETIME(ctypes.Structure):
    _fields_ = [
        ("dwLowDateTime", ctypes.c_ulong),
        ("dwHighDateTime", ctypes.c_ulong),
    ]


def _filetime_to_int(ft: _FILETIME) -> int:
    return (ft.dwHighDateTime << 32) | ft.dwLowDateTime


def get_system_memory_info() -> dict[str, float]:
    """Read system RAM usage via Windows GlobalMemoryStatusEx in <0.1ms."""
    if os.name == "nt" and hasattr(ctypes, "windll"):
        try:
            stat = _MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                total_gb = stat.ullTotalPhys / (1024 ** 3)
                used_gb = (stat.ullTotalPhys - stat.ullAvailPhys) / (1024 ** 3)
                pct = (used_gb / total_gb * 100.0) if total_gb > 0 else 0.0
                return {
                    "ramUsedGb": round(used_gb, 2),
                    "ramTotalGb": round(total_gb, 2),
                    "ramPercent": round(pct, 1),
                }
        except Exception:
            pass
    return {"ramUsedGb": 0.0, "ramTotalGb": 0.0, "ramPercent": 0.0}


def get_fallback_cpu_percent() -> float | None:
    """Compute CPU load % from Win32 GetSystemTimes deltas when counter is absent."""
    global _LAST_CPU_TIMES
    if os.name != "nt" or not hasattr(ctypes, "windll"):
        return None
    try:
        idle = _FILETIME()
        kernel = _FILETIME()
        user = _FILETIME()
        if not ctypes.windll.kernel32.GetSystemTimes(
            ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)
        ):
            return None
        cur = (_filetime_to_int(idle), _filetime_to_int(kernel), _filetime_to_int(user))
        prev = _LAST_CPU_TIMES
        _LAST_CPU_TIMES = cur
        if prev is None:
            return None
        d_idle = cur[0] - prev[0]
        d_total = (cur[1] - prev[1]) + (cur[2] - prev[2])
        if d_total <= 0:
            return None
        busy = max(0.0, min(100.0, (1.0 - (d_idle / d_total)) * 100.0))
        return round(busy, 1)
    except Exception:
        return None


def parse_telemetry_counters(samples: list[dict[str, Any]]) -> dict[str, Any]:
    """Parse Windows GPU/CPU counter samples into normalized RX 6700 XT telemetry."""
    adapters: dict[str, dict[str, float]] = {}
    compute_samples: list[tuple[str, float]] = []
    cpu_pct: float | None = None
    avail_mem_mb: float | None = None

    for item in samples:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", "")).lower()
        inst = str(item.get("inst") or "")
        try:
            val = float(item.get("val", 0.0))
        except (TypeError, ValueError):
            continue

        if "gpu adapter memory" in path:
            match = _LUID_RE.search(inst) or _LUID_RE.search(path)
            key = match.group(1).lower() if match else (inst.lower() or "default")
            bucket = adapters.setdefault(key, {"dedicated": 0.0, "shared": 0.0})
            if "dedicated usage" in path:
                bucket["dedicated"] = max(bucket["dedicated"], val)
            elif "shared usage" in path:
                bucket["shared"] = max(bucket["shared"], val)
        elif "gpu engine" in path and "utilization percentage" in path:
            match = _LUID_RE.search(inst) or _LUID_RE.search(path)
            luid = match.group(1).lower() if match else ""
            compute_samples.append((luid, max(0.0, val)))
        elif "processor(_total)" in path and "processor time" in path:
            cpu_pct = max(0.0, min(100.0, val))
        elif "memory" in path and "available mbytes" in path:
            avail_mem_mb = max(0.0, val)

    primary_luid = ""
    dedicated_bytes = 0.0
    shared_bytes = 0.0
    if adapters:
        primary_luid, best = max(
            adapters.items(),
            key=lambda kv: (kv[1]["dedicated"], kv[1]["shared"]),
        )
        dedicated_bytes = best["dedicated"]
        shared_bytes = best["shared"]

    if compute_samples:
        matched = [v for luid, v in compute_samples if primary_luid and luid == primary_luid]
        gpu_compute_raw = sum(matched) if matched else sum(v for _, v in compute_samples)
        gpu_compute_pct = round(max(0.0, min(100.0, gpu_compute_raw)), 1)
    else:
        gpu_compute_pct = 0.0

    vram_used_mb = round(dedicated_bytes / (1024 * 1024), 1)
    shared_used_mb = round(shared_bytes / (1024 * 1024), 1)
    vram_pct = round(max(0.0, min(100.0, (vram_used_mb / VRAM_TOTAL_MB) * 100.0)), 1)

    return {
        "vramUsedMb": vram_used_mb,
        "vramTotalMb": VRAM_TOTAL_MB,
        "vramPercent": vram_pct,
        "sharedGpuUsedMb": shared_used_mb,
        "gpuComputePercent": gpu_compute_pct,
        "cpuPercent": round(cpu_pct, 1) if cpu_pct is not None else None,
        "availMemMb": avail_mem_mb,
        "adapterLuid": primary_luid or None,
    }


def query_windows_counters() -> dict[str, Any]:
    """Query GPU Adapter Memory, GPU Compute %, and CPU % via one short PowerShell call."""
    ps_script = r"""
$ErrorActionPreference = 'SilentlyContinue'
$samples = @()
$paths = @(
    '\GPU Adapter Memory(*)\Dedicated Usage',
    '\GPU Adapter Memory(*)\Shared Usage',
    '\GPU Engine(*engtype_Compute*)\Utilization Percentage',
    '\Processor(_Total)\% Processor Time'
)
$res = Get-Counter -Counter $paths -ErrorAction SilentlyContinue
if ($res -and $res.CounterSamples) {
    foreach ($s in $res.CounterSamples) {
        $samples += @{
            path = [string]$s.Path
            inst = [string]$s.InstanceName
            val  = [double]$s.CookedValue
        }
    }
}
$hasGpuMem = $samples | Where-Object { $_.path -like '*gpu adapter memory*' }
if (-not $hasGpuMem) {
    $mem = Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUAdapterMemory -ErrorAction SilentlyContinue
    foreach ($m in $mem) {
        $samples += @{ path = 'cim\gpu adapter memory\dedicated usage'; inst = [string]$m.Name; val = [double]$m.DedicatedUsage }
        $samples += @{ path = 'cim\gpu adapter memory\shared usage'; inst = [string]$m.Name; val = [double]$m.SharedUsage }
    }
}
$hasGpuEng = $samples | Where-Object { $_.path -like '*gpu engine*' }
if (-not $hasGpuEng) {
    $eng = Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine -Filter "Name LIKE '%engtype_Compute%'" -ErrorAction SilentlyContinue
    foreach ($e in $eng) {
        $samples += @{ path = 'cim\gpu engine\utilization percentage'; inst = [string]$e.Name; val = [double]$e.UtilizationPercentage }
    }
}
@{ samples = $samples } | ConvertTo-Json -Compress -Depth 3
"""
    raw_samples: list[dict[str, Any]] = []
    warning: str | None = None
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=3.0,
            creationflags=CREATE_NO_WINDOW,
        )
        stdout = proc.stdout.strip()
        if stdout:
            parsed = json.loads(stdout)
            raw_samples = parsed.get("samples") or []
            if isinstance(raw_samples, dict):
                raw_samples = [raw_samples]
    except subprocess.TimeoutExpired:
        warning = "Performance counter query timed out"
    except Exception as exc:
        warning = f"Counter query fallback active: {exc}"

    metrics = parse_telemetry_counters(raw_samples)
    if metrics["cpuPercent"] is None:
        fallback_cpu = get_fallback_cpu_percent()
        metrics["cpuPercent"] = fallback_cpu if fallback_cpu is not None else 0.0
    if warning:
        metrics["warning"] = warning
    return metrics


def _http_get_json(url: str, timeout: float = 1.5) -> tuple[int, Any]:
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return resp.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(body)
        except Exception:
            return exc.code, {"error": body}


def fetch_llama_status(base_url: str = LLAMA_BASE_URL) -> dict[str, Any]:
    """Read /health, /props, and /slots from port 8080 without disrupting inference."""
    status: dict[str, Any] = {
        "online": False,
        "health": "offline",
        "model": None,
        "modelPath": None,
        "nCtx": None,
        "isProcessing": False,
        "slotState": "offline",
        "speculative": False,
        "endpoint": base_url,
    }

    try:
        code, health_data = _http_get_json(f"{base_url}/health", timeout=1.5)
    except Exception:
        return status

    health_text = str(health_data.get("status", "")).lower() if isinstance(health_data, dict) else ""
    if code == 200 and health_text == "ok":
        status["online"] = True
        status["health"] = "ok"
    elif code == 503:
        status["online"] = False
        status["health"] = "loading"
        status["slotState"] = "loading"
        return status
    else:
        status["online"] = code == 200
        status["health"] = health_text or f"http_{code}"

    try:
        p_code, props = _http_get_json(f"{base_url}/props", timeout=1.5)
        if p_code == 200 and isinstance(props, dict):
            model_path = props.get("model_path") or props.get("model_alias") or ""
            status["modelPath"] = model_path or None
            status["model"] = os.path.basename(model_path) if model_path else (props.get("model_alias") or None)
            dgs = props.get("default_generation_settings") or {}
            if isinstance(dgs, dict) and dgs.get("n_ctx"):
                status["nCtx"] = dgs.get("n_ctx")
    except Exception:
        pass

    try:
        s_code, slots = _http_get_json(f"{base_url}/slots", timeout=1.5)
        if s_code == 200 and isinstance(slots, list) and slots:
            slot0 = slots[0] if isinstance(slots[0], dict) else {}
            if slot0.get("n_ctx"):
                status["nCtx"] = slot0["n_ctx"]
            is_proc = bool(slot0.get("is_processing", False))
            status["isProcessing"] = is_proc
            status["speculative"] = bool(slot0.get("speculative", False))
            status["slotState"] = "generating" if is_proc else "idle"
        elif status["online"]:
            status["slotState"] = "idle"
    except Exception:
        if status["online"]:
            status["slotState"] = "idle"

    return status


def get_telemetry(force: bool = False) -> dict[str, Any]:
    """Return cached or freshly sampled hardware + llama-server telemetry."""
    now = time.monotonic()
    with _TELEMETRY_LOCK:
        cached = _TELEMETRY_CACHE.get("data")
        age = now - float(_TELEMETRY_CACHE.get("timestamp", 0.0))
        if not force and cached is not None and age < TELEMETRY_CACHE_TTL_SEC:
            return cached

        hw = query_windows_counters()
        mem = get_system_memory_info()
        llama = fetch_llama_status()

        payload = {
            "timestamp": time.time(),
            "gpu": {
                "name": "AMD Radeon RX 6700 XT",
                "vramUsedMb": hw["vramUsedMb"],
                "vramTotalMb": hw["vramTotalMb"],
                "vramPercent": hw["vramPercent"],
                "sharedUsedMb": hw["sharedGpuUsedMb"],
                "computePercent": hw["gpuComputePercent"],
                "adapterLuid": hw["adapterLuid"],
            },
            "system": {
                "cpuPercent": hw["cpuPercent"],
                "ramUsedGb": mem["ramUsedGb"],
                "ramTotalGb": mem["ramTotalGb"],
                "ramPercent": mem["ramPercent"],
            },
            "server": llama,
            "lanUrl": f"http://{get_lan_ip()}:{PORT}",
        }
        if hw.get("warning"):
            payload["warning"] = hw["warning"]

        _TELEMETRY_CACHE["timestamp"] = time.monotonic()
        _TELEMETRY_CACHE["data"] = payload
        return payload


def stop_llama_server() -> dict[str, Any]:
    """Stop any running llama-server.exe process cleanly to release VRAM."""
    cmd = "Stop-Process -Name 'llama-server' -Force -ErrorAction SilentlyContinue"
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=10,
        creationflags=CREATE_NO_WINDOW,
    )
    time.sleep(0.8)
    with _TELEMETRY_LOCK:
        _TELEMETRY_CACHE["timestamp"] = 0.0
    llama = fetch_llama_status()
    return {
        "ok": True,
        "status": "stopped" if not llama["online"] else "stopping",
        "returncode": proc.returncode,
        "server": llama,
    }


def start_llama_server(mode: str = "qwen27b_vram", reasoning_budget: int = 256) -> dict[str, Any]:
    """Stop existing llama-server.exe, launch detached start_local_server.ps1, wait up to 20s."""
    if mode not in VALID_MODES:
        raise ValueError(f"Unsupported mode '{mode}'. Choose from: {sorted(VALID_MODES)}")
    if reasoning_budget not in VALID_REASONING_BUDGETS:
        raise ValueError(
            f"Unsupported reasoningBudget '{reasoning_budget}'. Choose from: {sorted(VALID_REASONING_BUDGETS)}"
        )

    stop_llama_server()

    ps_args = (
        f'-NoProfile -ExecutionPolicy Bypass -WindowStyle Minimized '
        f'-File "{START_SERVER_SCRIPT}" -Mode {mode} -CtxSize 65536 -ReasoningBudget {reasoning_budget}'
    )
    cmd_line = f'powershell.exe {ps_args}'
    # Escape single quotes for PowerShell string literal
    cmd_escaped = cmd_line.replace("'", "''")
    dir_escaped = ROOT_DIR.replace("'", "''")

    launch_script = (
        f"$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create "
        f"-Arguments @{{ CommandLine = '{cmd_escaped}'; CurrentDirectory = '{dir_escaped}' }}; "
        f"$r | Select-Object ReturnValue, ProcessId | ConvertTo-Json -Compress"
    )
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", launch_script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=10,
        creationflags=CREATE_NO_WINDOW,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Failed to spawn start_local_server.ps1: {proc.stderr.strip()}")

    launch_info = json.loads(proc.stdout.strip() or "{}")
    if launch_info.get("ReturnValue", 1) != 0:
        raise RuntimeError(f"Win32_Process.Create failed with code {launch_info.get('ReturnValue')}")

    deadline = time.monotonic() + 20.0
    latest = fetch_llama_status()
    while time.monotonic() < deadline:
        latest = fetch_llama_status()
        if latest["online"]:
            break
        time.sleep(0.8)

    with _TELEMETRY_LOCK:
        _TELEMETRY_CACHE["timestamp"] = 0.0

    return {
        "ok": True,
        "ready": latest["online"],
        "mode": mode,
        "reasoningBudget": reasoning_budget,
        "launcherPid": launch_info.get("ProcessId"),
        "server": latest,
    }


def optimize_prompt(
    prompt: str,
    engine: str = "local",
    api_key: str = "",
    provider: str = "openrouter",
) -> dict[str, Any]:
    """Rewrite a rough prompt into a sharp AfterBurner Pi prompt via local 6700 XT or cloud."""
    clean_input = (prompt or "").strip()
    if not clean_input:
        raise ValueError("Prompt cannot be empty.")

    engine = (engine or "local").strip().lower()
    provider = (provider or "openrouter").strip().lower()
    supplied_key = (api_key or "").strip()

    if engine == "local":
        payload = {
            "messages": [
                {"role": "system", "content": OPTIMIZER_SYSTEM_PROMPT},
                {"role": "user", "content": clean_input},
            ],
            "max_tokens": 300,
            "temperature": 0.2,
            "reasoning_format": "none",
            "chat_template_kwargs": {"enable_thinking": False},
        }
        req = urllib.request.Request(
            f"{LLAMA_BASE_URL}/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Local server returned HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Cannot reach local llama-server at {LLAMA_BASE_URL}. Load a model first."
            ) from exc

        choices = data.get("choices") or []
        content = ""
        if choices:
            msg = choices[0].get("message") or {}
            content = (msg.get("content") or "").strip()
        if not content:
            raise RuntimeError("Local model returned an empty optimization response.")
        return {"ok": True, "optimizedPrompt": content, "engine": "local", "provider": "6700xt"}

    if engine == "cloud":
        if provider == "gemini":
            key = supplied_key or os.environ.get("GEMINI_API_KEY", "").strip()
            if not key:
                raise ValueError(
                    "No Gemini API key configured. Enter an API key in the UI or set GEMINI_API_KEY."
                )
            gemini_url = (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                "gemini-2.5-flash:generateContent"
            )
            payload = {
                "systemInstruction": {"parts": [{"text": OPTIMIZER_SYSTEM_PROMPT}]},
                "contents": [{"role": "user", "parts": [{"text": clean_input}]}],
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 300},
            }
            req = urllib.request.Request(
                gemini_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "x-goog-api-key": key,
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=45) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"Gemini API HTTP {exc.code}: {detail}") from exc
            except urllib.error.URLError as exc:
                raise RuntimeError(f"Gemini API network error: {exc.reason}") from exc

            candidates = data.get("candidates") or []
            parts = ((candidates[0].get("content") or {}).get("parts") or []) if candidates else []
            content = "".join(str(p.get("text", "")) for p in parts).strip()
            if not content:
                raise RuntimeError("Gemini API returned an empty response.")
            return {"ok": True, "optimizedPrompt": content, "engine": "cloud", "provider": "gemini"}

        if provider == "openrouter":
            key = supplied_key or os.environ.get("OPENROUTER_API_KEY", "").strip()
            if not key:
                raise ValueError(
                    "No OpenRouter API key configured. Enter an API key in the UI or set OPENROUTER_API_KEY."
                )
            payload = {
                "model": "openrouter/auto",
                "messages": [
                    {"role": "system", "content": OPTIMIZER_SYSTEM_PROMPT},
                    {"role": "user", "content": clean_input},
                ],
                "max_tokens": 300,
                "temperature": 0.2,
            }
            req = urllib.request.Request(
                "https://openrouter.ai/api/v1/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "http://127.0.0.1:8090",
                    "X-Title": "AfterBurner Control Center",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=45) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"OpenRouter API HTTP {exc.code}: {detail}") from exc
            except urllib.error.URLError as exc:
                raise RuntimeError(f"OpenRouter API network error: {exc.reason}") from exc

            choices = data.get("choices") or []
            content = ((choices[0].get("message") or {}).get("content") or "").strip() if choices else ""
            if not content:
                raise RuntimeError("OpenRouter returned an empty response.")
            return {"ok": True, "optimizedPrompt": content, "engine": "cloud", "provider": "openrouter"}

        raise ValueError(f"Unsupported cloud provider '{provider}'. Expected 'openrouter' or 'gemini'.")

    raise ValueError(f"Unsupported engine '{engine}'. Expected 'local' or 'cloud'.")


def build_pi_env(base_env: dict[str, str] | None = None) -> dict[str, str]:
    """Return environment with pi-node and .pi/agent/bin prepended to PATH."""
    env = dict(os.environ if base_env is None else base_env)
    local_app_data = env.get("LOCALAPPDATA") or os.path.expanduser(r"~\AppData\Local")
    user_profile = env.get("USERPROFILE") or os.path.expanduser("~")
    extra_dirs = [
        os.path.join(local_app_data, "pi-node", "current"),
        os.path.join(user_profile, ".pi", "agent", "bin"),
    ]
    existing_path = env.get("PATH", "")
    prefix = os.pathsep.join(d for d in extra_dirs if d)
    env["PATH"] = f"{prefix}{os.pathsep}{existing_path}" if existing_path else prefix
    return env


def run_pi_print(prompt: str) -> dict[str, Any]:
    """Run Pi non-interactively with empty closed stdin and return captured output."""
    clean_prompt = (prompt or "").strip()
    if not clean_prompt:
        raise ValueError("Prompt cannot be empty.")

    env = build_pi_env()
    pi_exe = shutil.which("pi", path=env["PATH"]) or "pi"
    cmd = [pi_exe, "--provider", "afterburner", "--model", "default", "--print", clean_prompt]

    t0 = time.perf_counter()
    proc = subprocess.run(
        cmd,
        cwd=ROOT_DIR,
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
        creationflags=CREATE_NO_WINDOW,
    )
    elapsed = round(time.perf_counter() - t0, 2)
    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    combined = stdout.strip()
    if stderr.strip():
        combined = f"{combined}\n\n[stderr]\n{stderr.strip()}" if combined else stderr.strip()

    return {
        "ok": proc.returncode == 0,
        "output": combined,
        "stdout": stdout,
        "stderr": stderr,
        "elapsedSeconds": elapsed,
        "returncode": proc.returncode,
    }


def open_pi_terminal() -> dict[str, Any]:
    """Launch Launch_Pi.bat in a visible detached interactive console window."""
    if not os.path.exists(LAUNCH_PI_BAT):
        raise FileNotFoundError(f"Launcher not found: {LAUNCH_PI_BAT}")

    bat_escaped = LAUNCH_PI_BAT.replace("'", "''")
    dir_escaped = ROOT_DIR.replace("'", "''")
    launch_script = (
        f"$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create "
        f"-Arguments @{{ CommandLine = 'cmd.exe /c \"{bat_escaped}\"'; CurrentDirectory = '{dir_escaped}' }}; "
        f"$r | Select-Object ReturnValue, ProcessId | ConvertTo-Json -Compress"
    )
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", launch_script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=10,
        creationflags=CREATE_NO_WINDOW,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Failed to launch Pi terminal: {proc.stderr.strip()}")
    info = json.loads(proc.stdout.strip() or "{}")
    if info.get("ReturnValue", 1) != 0:
        raise RuntimeError(f"Win32_Process.Create failed with code {info.get('ReturnValue')}")
    return {"ok": True, "pid": info.get("ProcessId")}


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "AfterBurnerDashboard/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress noisy per-poll stdout logging during background operation.
        return

    def _send_json(self, status_code: int, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _send_html(self, path: str) -> None:
        if not os.path.exists(path):
            self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "index.html not found"})
            return
        with open(path, "rb") as fh:
            raw = fh.read()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8", errors="replace")
        if not raw.strip():
            return {}
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("JSON body must be an object.")
        return data

    def do_GET(self) -> None:
        route = self.path.split("?", 1)[0]
        if route in ("/", "/index.html"):
            self._send_html(INDEX_HTML_PATH)
            return
        if route == "/api/telemetry":
            try:
                self._send_json(HTTPStatus.OK, get_telemetry())
            except Exception as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(exc)})
            return
        if route == "/api/health":
            self._send_json(HTTPStatus.OK, {"ok": True, "service": "afterburner-dashboard", "port": PORT})
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": f"Unknown route: {route}"})

    def do_POST(self) -> None:
        route = self.path.split("?", 1)[0]
        try:
            body = self._read_json_body()
        except Exception as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"Invalid JSON: {exc}"})
            return

        try:
            if route == "/api/server/start":
                mode = str(body.get("mode", "qwen27b_vram"))
                budget = int(body.get("reasoningBudget", 256))
                result = start_llama_server(mode=mode, reasoning_budget=budget)
                self._send_json(HTTPStatus.OK, result)
                return
            if route == "/api/server/stop":
                self._send_json(HTTPStatus.OK, stop_llama_server())
                return
            if route == "/api/prompt/optimize":
                result = optimize_prompt(
                    prompt=str(body.get("prompt", "")),
                    engine=str(body.get("engine", "local")),
                    api_key=str(body.get("apiKey", "")),
                    provider=str(body.get("provider", "openrouter")),
                )
                self._send_json(HTTPStatus.OK, result)
                return
            if route == "/api/pi/run":
                result = run_pi_print(prompt=str(body.get("prompt", "")))
                self._send_json(HTTPStatus.OK, result)
                return
            if route == "/api/pi/open-terminal":
                self._send_json(HTTPStatus.OK, open_pi_terminal())
                return
            self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": f"Unknown route: {route}"})
        except ValueError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
        except subprocess.TimeoutExpired:
            self._send_json(HTTPStatus.GATEWAY_TIMEOUT, {"ok": False, "error": "Command timed out."})
        except Exception as exc:
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(exc)})


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def main() -> int:
    server = ReusableThreadingHTTPServer((HOST, PORT), DashboardHandler)
    print(f"AfterBurner Control Center listening on http://{HOST}:{PORT}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
