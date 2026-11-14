#!/usr/bin/env python3
"""
benchmark_35b_ngram_and_cache_reuse.py
Tests:
  Part A: Zero-VRAM Tokenizer-Agnostic N-Gram Speculation (--spec-type ngram-simple / ngram-mod / ngram-cache)
          on Qwen3.6-35B-A3B-UD-Q4_K_XL (22.8 GB, 248k qwen35 vocabulary, -ngl 16) across unseen prompts!
  Part B: Prompt Cache Prefix Reuse (--cache-reuse 64) on llama-server (14B + 0.5B), measuring
          Prompt Evaluation & Time-To-First-Token (TTFT) when editing the middle of a large prompt.
"""
import subprocess
import re
import json
import time
import urllib.request
from pathlib import Path

ROOT_DIR   = Path(__file__).resolve().parent.parent
LLAMA_CLI  = str(ROOT_DIR / "bin" / "vulkan" / "llama-cli.exe")
LLAMA_SRV  = str(ROOT_DIR / "bin" / "vulkan" / "llama-server.exe")
MODEL_35B  = str(ROOT_DIR / "Models" / "qwen36-UD-Q4_K_XL" / "Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf")
MODEL_14B  = str(ROOT_DIR / "Models" / "Qwen2.5-Coder-14B-Instruct-GGUF" / "qwen2.5-coder-14b-instruct-q4_k_m.gguf")
DRAFT_05B  = str(ROOT_DIR / "Models" / "Qwen2.5-Coder-0.5B-Instruct" / "Qwen2.5-Coder-0.5B-Instruct-Q4_0.gguf")

UNSEEN_35B_PROMPTS = [
    (
        "Unseen Refactoring (High Context N-Gram Overlap)",
        "Refactor this Python class to add thread safety with threading.RLock, type hints, and docstrings while keeping all method names intact:\n"
        "class OrderRepository:\n"
        "    def __init__(self):\n"
        "        self.orders_by_id = {}\n"
        "        self.orders_by_customer = {}\n"
        "    def add_order(self, order_id, customer_id, total_amount):\n"
        "        self.orders_by_id[order_id] = {'order_id': order_id, 'customer_id': customer_id, 'total_amount': total_amount}\n"
        "        self.orders_by_customer.setdefault(customer_id, []).append(order_id)\n"
        "    def get_order_by_id(self, order_id):\n"
        "        return self.orders_by_id.get(order_id)\n"
        "    def get_orders_by_customer(self, customer_id):\n"
        "        return [self.orders_by_id[oid] for oid in self.orders_by_customer.get(customer_id, [])]\n"
    ),
    (
        "Unseen JSON API Response (Repeated Schema Keys)",
        "Generate a JSON array of 4 server health telemetry objects, where each object has keys: server_id, datacenter_region, gpu_device_name, vram_used_mb, vram_total_mb, status_code."
    ),
]

NGRAM_CONFIGS = [
    ("1. Standalone 35B-A3B Baseline", []),
    ("2. 35B-A3B + ngram-simple (n=3, m=12)", [
        "--spec-type", "ngram-simple",
        "--spec-ngram-simple-size-n", "3",
        "--spec-ngram-simple-size-m", "12",
    ]),
    ("3. 35B-A3B + ngram-mod (match=6, min=4, max=16)", [
        "--spec-type", "ngram-mod",
        "--spec-ngram-mod-n-match", "6",
        "--spec-ngram-mod-n-min", "4",
        "--spec-ngram-mod-n-max", "16",
    ]),
    ("4. 35B-A3B + ngram-cache", [
        "--spec-type", "ngram-cache",
        "--spec-draft-n-max", "8",
    ]),
]

def run_35b_cli(prompt, extra_args, n_predict=96):
    cmd = [
        LLAMA_CLI, "-m", MODEL_35B, "-ngl", "16", "-c", "2048", "-n", str(n_predict),
        "--temp", "0.0", "-st", "-fa", "on", "-ctk", "q8_0", "-ctv", "q8_0", "-t", "6",
        "--reasoning-budget", "0", "--verbose", "-p", prompt
    ] + extra_args
    out = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace").stdout
    m_ts = re.search(r"Generation:\s*([\d\.]+)\s*t/s", out)
    m_ac = re.search(r"draft acceptance\s*=\s*([\d\.]+)\s*\(\s*(\d+)\s*accepted\s*/\s*(\d+)\s*generated\)", out)
    return {
        "gen_ts": float(m_ts.group(1)) if m_ts else None,
        "acc_rate": float(m_ac.group(1)) * 100.0 if m_ac else None,
        "accepted": int(m_ac.group(2)) if m_ac else None,
        "drafted": int(m_ac.group(3)) if m_ac else None,
    }

def test_cache_reuse_server(enable_cache_reuse: bool):
    port = 8089
    cmd = [
        LLAMA_SRV, "-m", MODEL_14B, "-md", DRAFT_05B,
        "--host", "127.0.0.1", "--port", str(port),
        "-ngl", "99", "-ngld", "99",
        "--spec-type", "draft-simple", "--spec-draft-n-max", "3",
        "-fa", "on", "-ctk", "q8_0", "-ctv", "q8_0", "-c", "4096", "-t", "6"
    ]
    if enable_cache_reuse:
        cmd.extend(["--cache-reuse", "64"])

    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        # Wait for /health
        for _ in range(60):
            try:
                r = urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1)
                if r.status == 200:
                    break
            except Exception:
                time.sleep(0.5)

        # Build a ~1,200 token codebase context
        header = "You are an expert Python systems architect. Below is the system module:\n\n"
        body_block = "\n".join([
            f"class ServiceNode_{i}:\n"
            f"    def __init__(self, host: str, port: int):\n"
            f"        self.host = host\n"
            f"        self.port = port\n"
            f"        self.healthy = True\n"
            f"    def ping(self) -> dict:\n"
            f"        return {{'node': {i}, 'endpoint': f'{{self.host}}:{{self.port}}', 'ok': self.healthy}}\n"
            for i in range(1, 25)
        ])
        turn1_prompt = header + "VERSION = '1.0.0'\n" + body_block + "\nWrite a 1-line summary of ServiceNode_24."
        # Turn 2 edits a line near the top ("VERSION = '1.0.0'" -> "VERSION = '2.0.0'"), shifting all 24 classes!
        turn2_prompt = header + "VERSION = '2.0.0'\n" + body_block + "\nWrite a 1-line summary of ServiceNode_24."

        def send_req(p_text):
            payload = json.dumps({
                "prompt": p_text,
                "n_predict": 24,
                "temperature": 0.0,
                "cache_prompt": True
            }).encode("utf-8")
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/completion",
                data=payload,
                headers={"Content-Type": "application/json"}
            )
            t0 = time.time()
            resp = json.loads(urllib.request.urlopen(req, timeout=60).read().decode("utf-8"))
            wall_ms = (time.time() - t0) * 1000.0
            timings = resp.get("timings", {})
            return {
                "prompt_ms": round(timings.get("prompt_ms", 0.0), 1),
                "prompt_n": timings.get("prompt_n", 0),
                "predicted_ms": round(timings.get("predicted_ms", 0.0), 1),
                "predicted_per_second": round(timings.get("predicted_per_second", 0.0), 1),
                "wall_ms": round(wall_ms, 1),
            }

        t1 = send_req(turn1_prompt)
        t2 = send_req(turn2_prompt)
        return {"turn1_cold": t1, "turn2_edited_middle": t2}
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()

def main():
    print("=" * 90, flush=True)
    print("PART A: 35B-A3B MoE ZERO-VRAM N-GRAM SPECULATION BENCHMARK (248K VOCAB, -ngl 16)", flush=True)
    print("=" * 90, flush=True)
    results = {"part_a_35b_ngram": [], "part_b_cache_reuse": {}}

    for title, prompt in UNSEEN_35B_PROMPTS:
        print(f"\n>>> Workload: {title}", flush=True)
        base_ts = None
        for label, args in NGRAM_CONFIGS:
            res = run_35b_cli(prompt, args)
            if base_ts is None:
                base_ts = res["gen_ts"]
            spd = round(res["gen_ts"] / base_ts, 2) if (res["gen_ts"] and base_ts) else 1.0
            acc_str = f"{res['acc_rate']:5.1f}% ({res['accepted']}/{res['drafted']})" if res["acc_rate"] is not None else "Baseline"
            print(f"  {label:48s}: {res['gen_ts']:5.1f} t/s ({spd:.2f}x) | Acc: {acc_str}", flush=True)
            results["part_a_35b_ngram"].append({
                "workload": title,
                "config": label,
                "gen_ts": res["gen_ts"],
                "speedup": spd,
                "acc_rate": res["acc_rate"],
                "accepted": res["accepted"],
                "drafted": res["drafted"],
            })

    print("\n" + "=" * 90, flush=True)
    print("PART B: LLAMA-SERVER PROMPT CACHE PREFIX SHIFTING (--cache-reuse 64 on 14B+0.5B)", flush=True)
    print("=" * 90, flush=True)
    for reuse_flag in [False, True]:
        tag = "WITH --cache-reuse 64" if reuse_flag else "WITHOUT --cache-reuse (Default)"
        r = test_cache_reuse_server(reuse_flag)
        results["part_b_cache_reuse"][tag] = r
        t1 = r["turn1_cold"]
        t2 = r["turn2_edited_middle"]
        print(f"  [{tag}]", flush=True)
        print(f"    Turn 1 (Cold Prompt):          Prompt Eval = {t1['prompt_ms']:6.1f} ms ({t1['prompt_n']} tok) | Total Wall = {t1['wall_ms']:6.1f} ms", flush=True)
        print(f"    Turn 2 (Edited Top Line):      Prompt Eval = {t2['prompt_ms']:6.1f} ms ({t2['prompt_n']} tok) | Total Wall = {t2['wall_ms']:6.1f} ms", flush=True)

    out_file = ROOT_DIR / "MEMORY" / "BENCHMARK_35B_NGRAM_AND_CACHE.json"
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved results to {out_file}", flush=True)

if __name__ == "__main__":
    main()
