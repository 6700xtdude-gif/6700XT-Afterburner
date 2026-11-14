#!/usr/bin/env python3
"""
benchmark_14b_q3km_vs_q4km.py
Tests Option 3:
Compares Qwen2.5-Coder-14B-Instruct-Q3_K_M (6.84 GiB, -1.53 GiB VRAM saved, -18.3% bandwidth bytes)
against Qwen2.5-Coder-14B-Instruct-Q4_K_M (8.37 GiB) across all 4 blind unseen coding prompts:
  1. Standalone 14B Q3_K_M (6.84 GiB)
  2. 14B Q3_K_M + Stock 0.5B (draft-simple, K=3)
  3. 14B Q3_K_M + Stock 0.5B (ngram-simple,draft-simple, K=5, p-min=0.70)
  4. Long-Context 16,384-Token VRAM Verification (-c 16384 in 100% VRAM!)
"""
import subprocess
import re
import json
from pathlib import Path

ROOT_DIR      = Path(__file__).resolve().parent.parent
LLAMA_CLI     = str(ROOT_DIR / "bin" / "vulkan" / "llama-cli.exe")
MODEL_14B_Q3K = str(ROOT_DIR / "Models" / "Qwen2.5-Coder-14B-Instruct-GGUF" / "qwen2.5-coder-14b-instruct-q3_k_m.gguf")
DRAFT_05B     = str(ROOT_DIR / "Models" / "Qwen2.5-Coder-0.5B-Instruct" / "Qwen2.5-Coder-0.5B-Instruct-Q4_0.gguf")

UNSEEN_PROMPTS = [
    (
        "Unseen Python (LRU Cache)",
        "Write a Python class for a thread-safe LRU cache using collections.OrderedDict and threading.Lock.",
        37.3, 53.4
    ),
    (
        "Unseen Algorithms (Dijkstra)",
        "Write a clean Python implementation of Dijkstra's shortest path algorithm using heapq with type hints.",
        37.4, 55.0
    ),
    (
        "Unseen SQL (PostgreSQL Window CTE)",
        "Write a PostgreSQL query using a CTE and DENSE_RANK() window function to find the top 3 highest-spending customers per country in 2026.",
        37.5, 55.9
    ),
    (
        "Unseen Refactor/Edit (Code Transformation)",
        "Refactor this Python function to use dataclasses, type annotations, and logging instead of dicts and print:\ndef process_order(order):\n    if 'id' not in order or order['total'] <= 0:\n        print('Invalid order')\n        return None\n    tax = order['total'] * 0.0825\n    print('Processed', order['id'], tax)\n    return {'id': order['id'], 'grand_total': order['total'] + tax}",
        37.4, 54.6
    ),
]

CONFIGS = [
    ("1. Standalone 14B Q3_K_M (6.84 GiB)", []),
    ("2. 14B Q3_K_M + 0.5B (draft-simple, K=3)", [
        "-md", DRAFT_05B, "-ngld", "99", "-ctkd", "q8_0", "-ctvd", "q8_0",
        "--spec-type", "draft-simple", "--spec-draft-n-max", "3"
    ]),
    ("3. 14B Q3_K_M + 0.5B (ngram+draft, K=5, p=0.70)", [
        "-md", DRAFT_05B, "-ngld", "99", "-ctkd", "q8_0", "-ctvd", "q8_0",
        "--spec-type", "ngram-simple,draft-simple", "--spec-draft-n-max", "5", "--spec-draft-p-min", "0.70"
    ]),
]

def run_cli(prompt, extra_args, ctx=2048, n_predict=128):
    cmd = [
        LLAMA_CLI, "-m", MODEL_14B_Q3K, "-ngl", "99", "-c", str(ctx), "-n", str(n_predict),
        "--temp", "0.0", "-st", "-fa", "on", "-ctk", "q8_0", "-ctv", "q8_0", "--verbose", "-p", prompt
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

def main():
    print("=" * 92, flush=True)
    print("TEST #3: 14B Q3_K_M (6.84 GiB) vs 14B Q4_K_M (8.37 GiB) ON 4 BLIND UNSEEN PROMPTS", flush=True)
    print("=" * 92, flush=True)
    results = []

    for title, prompt, q4_base, q4_spec in UNSEEN_PROMPTS:
        print(f"\n>>> {title} [Q4_K_M Ref: {q4_base} t/s Standalone | {q4_spec} t/s Speculative]", flush=True)
        q3_base = None
        for label, args in CONFIGS:
            res = run_cli(prompt, args)
            if q3_base is None:
                q3_base = res["gen_ts"]
            spd_vs_q3 = round(res["gen_ts"] / q3_base, 2) if (res["gen_ts"] and q3_base) else 1.0
            spd_vs_q4 = round(res["gen_ts"] / q4_base, 2) if (res["gen_ts"] and q4_base) else 1.0
            acc_str = f"{res['acc_rate']:5.1f}% ({res['accepted']:3d}/{res['drafted']:3d})" if res["acc_rate"] is not None else "Baseline"
            print(f"  {label:48s}: {res['gen_ts']:5.1f} t/s ({spd_vs_q3:.2f}x vs Q3 | {spd_vs_q4:.2f}x vs Q4) | Acc: {acc_str}", flush=True)
            results.append({
                "prompt": title,
                "config": label,
                "gen_ts": res["gen_ts"],
                "speedup_vs_q3_base": spd_vs_q3,
                "speedup_vs_q4_base": spd_vs_q4,
                "acc_rate": res["acc_rate"],
                "accepted": res["accepted"],
                "drafted": res["drafted"],
            })

    print("\n>>> Testing 16,384-Token Long-Context Allocation (-c 16384) in 12 GB VRAM...", flush=True)
    res_16k = run_cli(UNSEEN_PROMPTS[0][1], CONFIGS[1][1], ctx=16384, n_predict=128)
    print(f"  14B Q3_K_M + 0.5B @ 16k Context (-c 16384)      : {res_16k['gen_ts']:5.1f} t/s | Acc: {res_16k['acc_rate']:.1f}%", flush=True)
    results.append({"prompt": "16k Context Verification (-c 16384)", "config": "14B Q3_K_M + 0.5B @ 16k", **res_16k})

    out_file = ROOT_DIR / "MEMORY" / "BENCHMARK_14B_Q3KM_UNSEEN.json"
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved results to {out_file}", flush=True)

if __name__ == "__main__":
    main()
