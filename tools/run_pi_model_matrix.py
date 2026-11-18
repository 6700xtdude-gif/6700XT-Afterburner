"""Automated Pi tool-calling smoke test matrix across all 12GB-fit local GGUFs."""
from __future__ import annotations

import glob
import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path

LLAMA_EXE = r"C:\llama.cpp\llama-server.exe"
LLAMA_DIR = r"C:\llama.cpp"
MODELS_DIR = Path(r"C:\models")
SESSIONS_DIR = Path(os.path.expanduser(r"~\.pi\agent\sessions"))
PI_CMD = os.path.expanduser(r"~\.pi\agent\bin\pi.cmd")
REPORT_PATH = Path(r"C:\Users\6700XT\6700XT-Afterburner\REPORTS\PI_MODEL_SMOKE_TEST_REPORT.md")

PROMPT = "What is the name of this computer?"


def kill_llama() -> None:
    subprocess.run(
        ["taskkill", "/F", "/IM", "llama-server.exe"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(0.6)


def wait_health(timeout_s: float = 45.0) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen("http://127.0.0.1:8080/health", timeout=1.5) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def latest_session_file() -> Path | None:
    files = list(SESSIONS_DIR.rglob("*.jsonl"))
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def parse_session(path: Path) -> dict:
    tool_calls = 0
    tool_results = 0
    final_text = ""
    tool_names: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if obj.get("type") == "message" and isinstance(obj.get("message"), dict):
            msg = obj["message"]
            role = msg.get("role")
            if role == "assistant":
                parts = msg.get("content") or []
                for p in parts:
                    if p.get("type") in ("toolCall", "tool_call"):
                        tool_calls += 1
                        tool_names.append(p.get("name") or p.get("toolName") or "tool")
                    elif p.get("type") == "text":
                        final_text = (p.get("text") or "").strip()
            elif role == "toolResult":
                tool_results += 1
    return {
        "tool_calls": tool_calls,
        "tool_results": tool_results,
        "tool_names": tool_names,
        "final_text": final_text,
    }


def run_case(gguf_name: str, thinking_mode: str, extra_server_args: list[str]) -> dict:
    model_path = MODELS_DIR / gguf_name
    if not model_path.exists():
        return {"model": gguf_name, "thinking": thinking_mode, "status": "MISSING", "notes": "File not found"}

    alias = model_path.stem.lower()
    kill_llama()

    cmd = [
        LLAMA_EXE,
        "-m", str(model_path),
        "-ngl", "99",
        "-c", "16384",
        "-fa", "1",
        "--jinja",
        "--host", "127.0.0.1",
        "--port", "8080",
        "--alias", alias,
        *extra_server_args,
    ]
    proc = subprocess.Popen(cmd, cwd=LLAMA_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        if not wait_health(45.0):
            return {
                "model": gguf_name,
                "thinking": thinking_mode,
                "status": "SERVER_FAIL",
                "cmd": " ".join(cmd),
                "notes": "llama-server did not become healthy within 45s",
            }

        before = latest_session_file()
        before_mtime = before.stat().st_mtime if before else 0.0

        env = os.environ.copy()
        env["PATH"] = f"C:\\Program Files\\nodejs;{os.path.dirname(PI_CMD)};{env.get('PATH', '')}"

        t0 = time.perf_counter()
        pi_cmd = [PI_CMD, "--model", f"local/{alias}", "--thinking", thinking_mode, "--print", PROMPT]
        try:
            res = subprocess.run(
                pi_cmd,
                cwd=r"C:\Users\6700XT",
                env=env,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=90,
            )
            elapsed = round(time.perf_counter() - t0, 2)
            out_text = (res.stdout or "").strip()
        except subprocess.TimeoutExpired:
            elapsed = 90.0
            out_text = "TIMEOUT (90s)"

        after = latest_session_file()
        parsed = {"tool_calls": 0, "tool_results": 0, "tool_names": [], "final_text": out_text}
        if after and after.stat().st_mtime > before_mtime:
            parsed = parse_session(after)

        passed = parsed["tool_calls"] > 0 and "SANDBOX" in (parsed["final_text"] or out_text).upper()
        return {
            "model": gguf_name,
            "thinking": thinking_mode,
            "status": "PASS" if passed else "FAIL",
            "tool_calls": parsed["tool_calls"],
            "tool_results": parsed["tool_results"],
            "elapsed_s": elapsed,
            "cmd": " ".join(cmd),
            "reply": (parsed["final_text"] or out_text).replace("\n", " ")[:220],
        }
    finally:
        proc.terminate()
        kill_llama()


def main() -> None:
    cases = [
        ("Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf", "off", []),
        ("Qwen2.5-14B-Instruct-Q4_K_M.gguf", "off", []),
        ("qwen2.5-coder-7b-instruct-q4_k_m.gguf", "off", []),
        ("DeepSeek-R1-Distill-Qwen-7B-Q4_K_M.gguf", "off", []),
        ("Mistral-Nemo-Instruct-2407-Q4_K_M.gguf", "off", []),
        ("Qwen3-8B-Q4_K_M.gguf", "off", ["--reasoning-budget", "0"]),
        ("Qwen3-8B-Q4_K_M.gguf", "low", ["--reasoning-budget", "256"]),
        ("Qwen3-14B-Q4_K_M.gguf", "off", ["--reasoning-budget", "0"]),
        ("Qwen3-14B-Q4_K_M.gguf", "low", ["--reasoning-budget", "256"]),
    ]

    results = []
    for gguf, think, extra in cases:
        print(f"=== Testing {gguf} (thinking={think}) ===", flush=True)
        r = run_case(gguf, think, extra)
        print(json.dumps(r), flush=True)
        results.append(r)

    lines = [
        "# RX 6700 XT — Pi Agent Tool-Calling Smoke Test Matrix",
        "",
        f"**Prompt:** `{PROMPT}`  ",
        "**Expected Ground Truth:** Tool call (`powershell`) returning `SANDBOX`",
        "",
        "| Model | Thinking | Status | Tool Calls | Time (s) | Reply Preview |",
        "| :--- | :---: | :---: | :---: | :---: | :--- |",
    ]
    for r in results:
        lines.append(
            f"| `{r['model']}` | `{r['thinking']}` | **{r['status']}** | {r.get('tool_calls', 0)} | {r.get('elapsed_s', '-')} | {r.get('reply', r.get('notes', ''))} |"
        )
    lines.append("")
    lines.append("## Exact `llama-server.exe` Command Lines Tested")
    for r in results:
        if r.get("cmd"):
            lines.append(f"- **`{r['model']}` (`thinking={r['thinking']}`):** `{r['cmd']}`")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"WROTE REPORT: {REPORT_PATH}", flush=True)


if __name__ == "__main__":
    main()
