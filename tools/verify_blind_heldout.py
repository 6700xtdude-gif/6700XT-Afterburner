#!/usr/bin/env python3
"""
verify_blind_heldout.py
Blind held-out verification benchmark on prompts NEVER used during calibration/distillation.
Compares Standalone 14B/7B against Stock Untouched 0.5B (24L) and Pruned/Healed Draft Models
to guard against calibration overfitting.
"""
import subprocess
import re
import json

LLAMA_CLI = r"C:\Users\6700XT\Documents\Strata\bin\vulkan\llama-cli.exe"
MODEL_14B = r"C:\Users\6700XT\Documents\Strata\Models\Qwen2.5-Coder-14B-Instruct-GGUF\qwen2.5-coder-14b-instruct-q4_k_m.gguf"

DRAFTS = [
    ("Standalone 14B (No Draft)",     None),
    ("Stock Untouched 0.5B (24L)",    r"C:\Users\6700XT\Documents\Strata\Models\Qwen2.5-Coder-0.5B-Instruct\Qwen2.5-Coder-0.5B-Instruct-Q4_0.gguf"),
    ("Healed 18L (Pruned, 6L cut)",   r"C:\Users\6700XT\Documents\Strata\Models\Qwen2.5-Coder-0.5B-L18-Healed\Qwen2.5-Coder-0.5B-L18-Healed-Q4_0.gguf"),
    ("Healed 14L (Pruned, 10L cut)",  r"C:\Users\6700XT\Documents\Strata\Models\Qwen2.5-Coder-0.5B-L14-Healed\Qwen2.5-Coder-0.5B-L14-Healed-Q4_0.gguf"),
    ("Dory-Looped 19L (10L cut+loop)",r"C:\Users\6700XT\Documents\Strata\Models\Qwen2.5-Coder-0.5B-Dory19L-Healed\Qwen2.5-Coder-0.5B-Dory19L-Healed-Q4_0.gguf"),
]

BLIND_PROMPTS = [
    (
        "Unseen Python (Thread-Safe LRU Cache)",
        "Write a Python class for a thread-safe LRU cache using collections.OrderedDict and threading.Lock."
    ),
    (
        "Unseen SQL + Schema (PostgreSQL E-Commerce)",
        "Write a PostgreSQL query using a CTE and window function to find the top 3 highest-spending customers per country in 2026."
    ),
]

def run_one(prompt, draft_path=None, k=3, n_predict=128):
    cmd = [
        LLAMA_CLI, "-m", MODEL_14B, "-ngl", "99", "-c", "2048", "-n", str(n_predict),
        "--temp", "0.0", "-st", "-fa", "on", "-ctk", "q8_0", "-ctv", "q8_0", "--verbose", "-p", prompt
    ]
    if draft_path:
        cmd.extend(["-md", draft_path, "-ngld", "99", "--spec-type", "draft-simple", "--spec-draft-n-max", str(k)])
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
    print("=" * 84)
    print("BLIND HELD-OUT VERIFICATION BENCHMARK (UNSEEN PROMPTS ON 14B VERIFIER)")
    print("=" * 84)
    for title, prompt in BLIND_PROMPTS:
        print(f"\n>>> {title}")
        base_ts = None
        for label, d_path in DRAFTS:
            res = run_one(prompt, d_path)
            if base_ts is None:
                base_ts = res["gen_ts"]
            spd = round(res["gen_ts"] / base_ts, 2) if (res["gen_ts"] and base_ts) else 1.0
            acc_str = f"{res['acc_rate']:5.1f}% ({res['accepted']}/{res['drafted']})" if res["acc_rate"] is not None else "Baseline"
            print(f"  {label:32s}: {res['gen_ts']:5.1f} t/s ({spd:.2f}x) | Acc: {acc_str}")

if __name__ == "__main__":
    main()
