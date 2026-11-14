#!/usr/bin/env python3
"""
benchmark_bottleneck1_draft_ceiling.py
Attacks Bottleneck 1 (The Draft Acceptance Ceiling on Unseen Prompts) on the 14B Verifier.
Tests 4 completely unseen, held-out coding & architecture prompts across:
  1. Standalone 14B (Q4_K_M, 8.37 GiB)
  2. 14B + 0.5B Q4_0 (Stock 24L, draft-simple, K=3)
  3. 14B + 0.5B Q4_0 (Multi-Stage ngram-simple,draft-simple, K=5, p-min=0.70)
  4. 14B + 1.5B Q4_0 (Stock 28L, draft-simple, K=3)
  5. 14B + 1.5B Q4_0 (Stock 28L, draft-simple, K=4)
  6. 14B + 1.5B Q4_0 (Multi-Stage ngram-simple,draft-simple, K=5, p-min=0.70)
"""
import subprocess
import re
import json
from pathlib import Path

ROOT_DIR  = Path(__file__).resolve().parent.parent
LLAMA_CLI = str(ROOT_DIR / "bin" / "vulkan" / "llama-cli.exe")
MODEL_14B = str(ROOT_DIR / "Models" / "Qwen2.5-Coder-14B-Instruct-GGUF" / "qwen2.5-coder-14b-instruct-q4_k_m.gguf")
DRAFT_05B = str(ROOT_DIR / "Models" / "Qwen2.5-Coder-0.5B-Instruct" / "Qwen2.5-Coder-0.5B-Instruct-Q4_0.gguf")
DRAFT_15B = str(ROOT_DIR / "Models" / "Qwen2.5-Coder-1.5B-Instruct-GGUF" / "qwen2.5-coder-1.5b-instruct-q4_0.gguf")

# 4 Unseen Held-Out Prompts (Never used in any calibration script)
UNSEEN_PROMPTS = [
    (
        "Unseen Python (LRU Cache)",
        "Write a Python class for a thread-safe LRU cache using collections.OrderedDict and threading.Lock."
    ),
    (
        "Unseen Algorithms (Dijkstra)",
        "Write a clean Python implementation of Dijkstra's shortest path algorithm using heapq with type hints."
    ),
    (
        "Unseen SQL (PostgreSQL Window CTE)",
        "Write a PostgreSQL query using a CTE and DENSE_RANK() window function to find the top 3 highest-spending customers per country in 2026."
    ),
    (
        "Unseen Refactor/Edit (Code Transformation)",
        "Refactor this Python function to use dataclasses, type annotations, and logging instead of dicts and print:\ndef process_order(order):\n    if 'id' not in order or order['total'] <= 0:\n        print('Invalid order')\n        return None\n    tax = order['total'] * 0.0825\n    print('Processed', order['id'], tax)\n    return {'id': order['id'], 'grand_total': order['total'] + tax}"
    ),
]

CONFIGS = [
    ("1. Standalone 14B Baseline", []),
    ("2. 14B + 0.5B (draft-simple, K=3)", [
        "-md", DRAFT_05B, "-ngld", "99", "-ctkd", "q8_0", "-ctvd", "q8_0",
        "--spec-type", "draft-simple", "--spec-draft-n-max", "3"
    ]),
    ("3. 14B + 0.5B (ngram+draft, K=5, p=0.70)", [
        "-md", DRAFT_05B, "-ngld", "99", "-ctkd", "q8_0", "-ctvd", "q8_0",
        "--spec-type", "ngram-simple,draft-simple", "--spec-draft-n-max", "5", "--spec-draft-p-min", "0.70"
    ]),
    ("4. 14B + 1.5B (draft-simple, K=3)", [
        "-md", DRAFT_15B, "-ngld", "99", "-ctkd", "q8_0", "-ctvd", "q8_0",
        "--spec-type", "draft-simple", "--spec-draft-n-max", "3"
    ]),
    ("5. 14B + 1.5B (draft-simple, K=4)", [
        "-md", DRAFT_15B, "-ngld", "99", "-ctkd", "q8_0", "-ctvd", "q8_0",
        "--spec-type", "draft-simple", "--spec-draft-n-max", "4"
    ]),
    ("6. 14B + 1.5B (ngram+draft, K=5, p=0.70)", [
        "-md", DRAFT_15B, "-ngld", "99", "-ctkd", "q8_0", "-ctvd", "q8_0",
        "--spec-type", "ngram-simple,draft-simple", "--spec-draft-n-max", "5", "--spec-draft-p-min", "0.70"
    ]),
]

def run_config(prompt, extra_args, n_predict=128):
    cmd = [
        LLAMA_CLI, "-m", MODEL_14B, "-ngl", "99", "-c", "2048", "-n", str(n_predict),
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
    print("=" * 90)
    print("BOTTLENECK 1 BENCHMARK: 0.5B vs 1.5B DRAFTER + MULTI-STAGE N-GRAM ON UNSEEN PROMPTS (14B)")
    print("=" * 90)

    results = []
    for p_title, p_text in UNSEEN_PROMPTS:
        print(f"\n>>> Prompt: {p_title}")
        base_ts = None
        for c_label, c_args in CONFIGS:
            res = run_config(p_text, c_args)
            if base_ts is None:
                base_ts = res["gen_ts"]
            spd = round(res["gen_ts"] / base_ts, 2) if (res["gen_ts"] and base_ts) else 1.0
            acc_str = f"{res['acc_rate']:5.1f}% ({res['accepted']:3d}/{res['drafted']:3d})" if res["acc_rate"] is not None else "Baseline"
            print(f"  {c_label:42s}: {res['gen_ts']:5.1f} t/s ({spd:.2f}x) | Acc: {acc_str}")
            results.append({
                "prompt": p_title,
                "config": c_label,
                "gen_ts": res["gen_ts"],
                "speedup": spd,
                "acc_rate": res["acc_rate"],
                "accepted": res["accepted"],
                "drafted": res["drafted"],
            })

    out_file = ROOT_DIR / "MEMORY" / "BENCHMARK_BOTTLENECK1_UNSEEN.json"
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved full unseen benchmark results to {out_file}")

if __name__ == "__main__":
    main()
