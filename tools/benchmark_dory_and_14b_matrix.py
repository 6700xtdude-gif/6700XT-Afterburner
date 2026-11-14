#!/usr/bin/env python3
"""
benchmark_dory_and_14b_matrix.py
Comprehensive live RX 6700 XT Vulkan benchmark comparing:
  - L14-Healed (Q4_0, 243 MiB, 14 physical layers)
  - Dory19L-Healed (Q4_0, 279 MiB, 14 physical layers -> 19 effective layers via 2x middle loop)
  - L18-Healed (Q4_0, 282 MiB, 18 physical layers)
against BOTH:
  - Target A: Qwen2.5-Coder-7B-Instruct-Q4_K_M (4.36 GiB, 100% VRAM)
  - Target B: Qwen2.5-Coder-14B-Instruct-Q4_K_M (8.37 GiB, 100% VRAM)
"""
import subprocess
import re
import json
import time

LLAMA_CLI = r"C:\Users\6700XT\Documents\Strata\bin\vulkan\llama-cli.exe"
MODEL_7B  = r"C:\Users\6700XT\Documents\Strata\Models\Qwen2.5-Coder-7B-Instruct-GGUF\qwen2.5-coder-7b-instruct-q4_k_m.gguf"
MODEL_14B = r"C:\Users\6700XT\Documents\Strata\Models\Qwen2.5-Coder-14B-Instruct-GGUF\qwen2.5-coder-14b-instruct-q4_k_m.gguf"

DRAFTS = [
    ("Healed 14L (Q4_0)",       r"C:\Users\6700XT\Documents\Strata\Models\Qwen2.5-Coder-0.5B-L14-Healed\Qwen2.5-Coder-0.5B-L14-Healed-Q4_0.gguf"),
    ("Dory-Looped 19L (Q4_0)",  r"C:\Users\6700XT\Documents\Strata\Models\Qwen2.5-Coder-0.5B-Dory19L-Healed\Qwen2.5-Coder-0.5B-Dory19L-Healed-Q4_0.gguf"),
    ("Healed 18L (Q4_0)",       r"C:\Users\6700XT\Documents\Strata\Models\Qwen2.5-Coder-0.5B-L18-Healed\Qwen2.5-Coder-0.5B-L18-Healed-Q4_0.gguf"),
]

PROMPTS = [
    ("Structured JSON", "Output a valid JSON schema representing a user profile with id, username, email, roles, and settings."),
    ("Python Code",     "Write a clean, optimized quicksort implementation in Python with comments."),
]

def run_spec(target_model, prompt_text, draft_model=None, k=3, n_predict=128):
    cmd = [
        LLAMA_CLI,
        "-m", target_model,
        "-ngl", "99",
        "-c", "2048",
        "-n", str(n_predict),
        "--temp", "0.0",
        "-st",
        "-fa", "on",
        "-ctk", "q8_0",
        "-ctv", "q8_0",
        "--verbose",
        "-p", prompt_text
    ]
    if draft_model:
        cmd.extend([
            "-md", draft_model,
            "-ngld", "99",
            "--spec-type", "draft-simple",
            "--spec-draft-n-max", str(k)
        ])

    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
    out = proc.stdout

    gen_ts = None
    acc_rate = None
    accepted = None
    drafted = None

    m_sum = re.search(r"\[\s*Prompt:\s*([\d\.]+)\s*t/s\s*\|\s*Generation:\s*([\d\.]+)\s*t/s\s*\]", out)
    if m_sum:
        gen_ts = float(m_sum.group(2))

    m_acc = re.search(r"draft acceptance\s*=\s*([\d\.]+)\s*\(\s*(\d+)\s*accepted\s*/\s*(\d+)\s*generated\)", out)
    if m_acc:
        acc_rate = float(m_acc.group(1)) * 100.0
        accepted = int(m_acc.group(2))
        drafted = int(m_acc.group(3))

    return {"gen_ts": gen_ts, "acc_rate": acc_rate, "accepted": accepted, "drafted": drafted}

def main():
    print("=" * 88)
    print("6700XT-AFTERBURNER: DORY-LOOPED 19L vs HEALED 14L vs HEALED 18L (7B & 14B VERIFIERS)")
    print("=" * 88)

    matrix = []
    for target_label, target_path, base_json, base_code in [
        ("7B Verifier (4.36 GiB)",  MODEL_7B,  71.7, 71.4),
        ("14B Verifier (8.37 GiB)", MODEL_14B, 37.4, 37.5),
    ]:
        print(f"\n==================== TARGET: {target_label} ====================")
        for cat, prompt in PROMPTS:
            base_ts = base_json if cat == "Structured JSON" else base_code
            print(f"\n  >>> Workload: {cat} (Standalone Baseline: {base_ts:.1f} t/s)")
            for d_label, d_path in DRAFTS:
                res = run_spec(target_path, prompt, draft_model=d_path, k=3)
                spd = round(res["gen_ts"] / base_ts, 2) if res["gen_ts"] else None
                acc_str = f"{res['acc_rate']:5.1f}% ({res['accepted']}/{res['drafted']})" if res["acc_rate"] is not None else "N/A"
                print(f"      - {d_label:24s} (K=3): {res['gen_ts']:6.1f} t/s | Speedup: {spd:.2f}x | Acc: {acc_str}")
                matrix.append({
                    "target": target_label,
                    "workload": cat,
                    "draft": d_label,
                    "k": 3,
                    "gen_ts": res["gen_ts"],
                    "baseline_ts": base_ts,
                    "speedup": spd,
                    "acc_rate": res["acc_rate"],
                    "accepted": res["accepted"],
                    "drafted": res["drafted"]
                })

    out_path = r"C:\Users\6700XT\Documents\Strata\MEMORY\BENCHMARK_DORY_MATRIX.json"
    with open(out_path, "w") as f:
        json.dump(matrix, f, indent=2)
    print(f"\nSaved full matrix to {out_path}")

if __name__ == "__main__":
    main()
