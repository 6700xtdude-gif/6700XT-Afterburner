#!/usr/bin/env python3
"""
test_cache_reuse_detail.py
Tests llama-server KV prompt caching & --cache-reuse 64 across:
  1. Turn 1: Cold 1,300-token codebase prompt
  2. Turn 2: Multi-turn follow-up append (reuses 100% of prefix KV cache)
  3. Turn 3: Inserted comment near top of file (tests --cache-reuse 64 KV shifting)
"""
import subprocess
import json
import time
import urllib.request
from pathlib import Path

ROOT_DIR  = Path(__file__).resolve().parent.parent
LLAMA_SRV = str(ROOT_DIR / "bin" / "vulkan" / "llama-server.exe")
MODEL_14B = str(ROOT_DIR / "Models" / "Qwen2.5-Coder-14B-Instruct-GGUF" / "qwen2.5-coder-14b-instruct-q4_k_m.gguf")
DRAFT_05B = str(ROOT_DIR / "Models" / "Qwen2.5-Coder-0.5B-Instruct" / "Qwen2.5-Coder-0.5B-Instruct-Q4_0.gguf")

def run_server_test(use_cache_reuse: bool):
    port = 8089
    cmd = [
        LLAMA_SRV, "-m", MODEL_14B, "-md", DRAFT_05B,
        "--host", "127.0.0.1", "--port", str(port),
        "-ngl", "99", "-ngld", "99",
        "--spec-type", "draft-simple", "--spec-draft-n-max", "3",
        "-fa", "on", "-ctk", "q8_0", "-ctv", "q8_0", "-c", "4096"
    ]
    if use_cache_reuse:
        cmd.extend(["--cache-reuse", "64"])

    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(60):
            try:
                if urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1).status == 200:
                    break
            except Exception:
                time.sleep(0.5)

        body = "\n".join([f"class Node_{i}:\n    def ping(self): return {i}\n" for i in range(80)])
        p1 = "You are an expert coder.\n" + body + "\nQuestion 1: What does Node_1 return?"
        p2_append = p1 + " It returns 1.\nQuestion 2: What does Node_79 return?"
        p3_insert = "You are an expert coder.\n# INSERTED NEW HEADER COMMENT\n" + body + "\nQuestion 1: What does Node_1 return?"

        label_hdr = "WITH --cache-reuse 64" if use_cache_reuse else "WITHOUT --cache-reuse (Default)"
        print(f"\n=== {label_hdr} ===", flush=True)
        for name, p in [
            ("Turn 1 (Cold 1,370-tok Codebase)", p1),
            ("Turn 2 (Multi-Turn Follow-up Append)", p2_append),
            ("Turn 3 (Inserted Comment at Top of File)", p3_insert),
        ]:
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/completion",
                data=json.dumps({"prompt": p, "n_predict": 16, "temperature": 0.0, "cache_prompt": True}).encode(),
                headers={"Content-Type": "application/json"}
            )
            t = json.loads(urllib.request.urlopen(req).read().decode())["timings"]
            p_n = t["prompt_n"]
            p_ms = t["prompt_ms"]
            g_ts = t["predicted_per_second"]
            print(f"  {name:42s}: Evaluated {p_n:4d} tokens in {p_ms:7.1f} ms | Gen: {g_ts:5.1f} t/s", flush=True)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()

if __name__ == "__main__":
    run_server_test(False)
    run_server_test(True)
