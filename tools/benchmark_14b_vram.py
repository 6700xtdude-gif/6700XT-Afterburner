#!/usr/bin/env python3
"""
benchmark_14b_vram.py - Full 12 GB VRAM Benchmark for Qwen2.5-Coder-14B-Instruct (Q4_K_M, 8.37 GiB)
Compares:
  1. Standalone 14B (100% in VRAM, -ngl 99)
  2. Speculative 14B + Healed 18L 0.5B Draft (-ngl 99 -ngld 99, K=3, K=4)
  3. Speculative 14B + Unpruned 24L 0.5B Draft (-ngl 99 -ngld 99, K=3, K=4)
"""
import subprocess
import re
import json
import time

LLAMA_CLI = r"C:\Users\6700XT\Documents\Strata\bin\vulkan\llama-cli.exe"
MODEL_14B = r"C:\Users\6700XT\Documents\Strata\Models\Qwen2.5-Coder-14B-Instruct-GGUF\qwen2.5-coder-14b-instruct-q4_k_m.gguf"
DRAFT_18L = r"C:\Users\6700XT\Documents\Strata\Models\Qwen2.5-Coder-0.5B-L18-Healed\Qwen2.5-Coder-0.5B-L18-Healed-Q4_0.gguf"
DRAFT_24L = r"C:\Users\6700XT\Documents\Strata\Models\Qwen2.5-Coder-0.5B-Instruct\Qwen2.5-Coder-0.5B-Instruct-Q4_0.gguf"

PROMPTS = [
    {
        "id": "json_schema",
        "category": "Structured JSON",
        "prompt": "Output a valid JSON schema representing a user profile with id, username, email, roles, and settings."
    },
    {
        "id": "code_quicksort",
        "category": "Code Generation",
        "prompt": "Write a clean, optimized quicksort implementation in Python with comments."
    }
]

def run_bench(prompt_text, draft_model=None, k_draft=None, n_predict=128):
    cmd = [
        LLAMA_CLI,
        "-m", MODEL_14B,
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
    if draft_model and k_draft:
        cmd.extend([
            "-md", draft_model,
            "-ngld", "99",
            "--spec-type", "draft-simple",
            "--spec-draft-n-max", str(k_draft)
        ])

    t0 = time.time()
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
    elapsed = time.time() - t0
    out = proc.stdout

    gen_ts = None
    prompt_ts = None
    eval_ms = None
    acc_rate = None
    accepted = None
    drafted = None

    summary_match = re.search(r"\[\s*Prompt:\s*([\d\.]+)\s*t/s\s*\|\s*Generation:\s*([\d\.]+)\s*t/s\s*\]", out)
    if summary_match:
        prompt_ts = float(summary_match.group(1))
        gen_ts = float(summary_match.group(2))

    g_match = re.search(r"(?<!prompt )eval time\s*=\s*([\d\.]+)\s*ms\s*/\s*(\d+)\s*tokens.*?([\d\.]+)\s*tokens per second", out)
    if g_match:
        eval_ms = float(g_match.group(1))
        if gen_ts is None:
            gen_ts = float(g_match.group(3))

    d_match = re.search(r"draft acceptance\s*=\s*([\d\.]+)\s*\(\s*(\d+)\s*accepted\s*/\s*(\d+)\s*generated\)", out)
    if d_match:
        acc_rate = float(d_match.group(1)) * 100.0
        accepted = int(d_match.group(2))
        drafted = int(d_match.group(3))
    else:
        # Newer llama.cpp speculative stats format:
        # draft acceptance rate = 0.88500 (  100 accepted /   113 drafted) or similar
        d_match2 = re.search(r"accepted\s+(\d+)\s*/\s*(\d+)\s+drafted\s+\(([\d\.]+)%\)", out)
        if d_match2:
            accepted = int(d_match2.group(1))
            drafted = int(d_match2.group(2))
            acc_rate = float(d_match2.group(3))

    return {
        "prompt_ts": prompt_ts,
        "gen_ts": gen_ts,
        "eval_ms": eval_ms,
        "acc_rate": acc_rate,
        "accepted": accepted,
        "drafted": drafted,
        "elapsed_s": round(elapsed, 2)
    }

def main():
    print("=" * 84)
    print("6700XT-AFTERBURNER: 14B FULL-VRAM SPECULATIVE BENCHMARK (RX 6700 XT 12 GB)")
    print("Target: Qwen2.5-Coder-14B-Instruct-Q4_K_M (8.37 GiB, 48 Layers, 100% in VRAM)")
    print("=" * 84)

    all_results = []
    for p in PROMPTS:
        print(f"\n>>> Workload: [{p['category']}]")
        base = run_bench(p["prompt"])
        print(f"  [1] Standalone 14B:                 {base['gen_ts']:6.1f} t/s (Prompt: {base['prompt_ts']} t/s)")
        base["config"] = "Standalone 14B"
        base["category"] = p["category"]
        base["speedup"] = 1.0
        all_results.append(base)

        for label, d_path in [("Healed 18L 0.5B", DRAFT_18L), ("Unpruned 24L 0.5B", DRAFT_24L)]:
            for k in [3, 4]:
                res = run_bench(p["prompt"], draft_model=d_path, k_draft=k)
                spd = round(res["gen_ts"] / base["gen_ts"], 2) if (res["gen_ts"] and base["gen_ts"]) else None
                acc_s = f" | Acc: {res['acc_rate']:.1f}% ({res['accepted']}/{res['drafted']})" if res["acc_rate"] is not None else ""
                print(f"  [*] 14B + {label} (K={k}): {res['gen_ts']:6.1f} t/s -> {spd}x speedup{acc_s}")
                res["config"] = f"14B + {label} (K={k})"
                res["category"] = p["category"]
                res["speedup"] = spd
                all_results.append(res)

    out_file = r"C:\Users\6700XT\Documents\Strata\MEMORY\BENCHMARK_14B_RESULTS.json"
    with open(out_file, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nSaved 14B benchmark results to {out_file}")

if __name__ == "__main__":
    main()
