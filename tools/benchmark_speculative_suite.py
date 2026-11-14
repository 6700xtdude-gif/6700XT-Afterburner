import subprocess
import re
import json
import time
import os
import sys
import statistics
import argparse

LLAMA_CLI = r".\bin\vulkan\llama-cli.exe"
VERIFIER_MODEL = r"Models\Qwen2.5-Coder-7B-Instruct-GGUF\qwen2.5-coder-7b-instruct-q4_k_m.gguf"
DRAFT_MODEL = r"Models\Qwen2.5-Coder-0.5B-Instruct\Qwen2.5-Coder-0.5B-Instruct-Q4_0.gguf"

PROMPTS = [
    {
        "id": "code_quicksort",
        "category": "Code Generation",
        "prompt": "Write a clean, optimized quicksort implementation in Python with comments."
    },
    {
        "id": "json_schema",
        "category": "Structured JSON",
        "prompt": "Output a valid JSON schema representing a user profile with id, username, email, roles, and settings."
    },
    {
        "id": "sys_design",
        "category": "Technical Reasoning",
        "prompt": "Explain the architectural trade-offs between memory bandwidth and cache latency during autoregressive LLM decoding on modern GPUs."
    }
]

def run_single_invocation(prompt_text, n_predict=128, k_draft=None):
    cmd = [
        LLAMA_CLI,
        "-m", VERIFIER_MODEL,
        "-ngl", "99",
        "-c", "2048",
        "-n", str(n_predict),
        "--temp", "0.0",
        "-st",
        "-fa", "on",
        "--verbose",
        "-p", prompt_text
    ]
    if k_draft is not None:
        cmd.extend([
            "-md", DRAFT_MODEL,
            "-ngld", "99",
            "--spec-type", "draft-simple",
            "--spec-draft-n-max", str(k_draft)
        ])
    
    t0 = time.time()
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
    elapsed = time.time() - t0
    output = proc.stdout

    prompt_ts = None
    gen_ts = None
    eval_ms = None
    acceptance_rate = None
    accepted_tokens = None
    generated_draft_tokens = None
    tokens_generated = None

    summary_match = re.search(r"\[\s*Prompt:\s*([\d\.]+)\s*t/s\s*\|\s*Generation:\s*([\d\.]+)\s*t/s\s*\]", output)
    if summary_match:
        prompt_ts = float(summary_match.group(1))
        gen_ts = float(summary_match.group(2))

    p_match = re.search(r"prompt eval time\s*=\s*([\d\.]+)\s*ms\s*/\s*(\d+)\s*tokens.*?([\d\.]+)\s*tokens per second", output)
    if p_match and prompt_ts is None:
        prompt_ts = float(p_match.group(3))

    g_match = re.search(r"(?<!prompt )eval time\s*=\s*([\d\.]+)\s*ms\s*/\s*(\d+)\s*tokens.*?([\d\.]+)\s*tokens per second", output)
    if g_match:
        eval_ms = float(g_match.group(1))
        tokens_generated = int(g_match.group(2))
        if gen_ts is None:
            gen_ts = float(g_match.group(3))

    d_match = re.search(r"draft acceptance\s*=\s*([\d\.]+)\s*\(\s*(\d+)\s*accepted\s*/\s*(\d+)\s*generated\)", output)
    if d_match:
        acceptance_rate = float(d_match.group(1)) * 100.0
        accepted_tokens = int(d_match.group(2))
        generated_draft_tokens = int(d_match.group(3))

    return {
        "k_draft": k_draft,
        "n_predict": n_predict,
        "tokens_generated": tokens_generated,
        "prompt_ts": prompt_ts,
        "gen_ts": gen_ts,
        "eval_ms": eval_ms,
        "total_elapsed_s": round(elapsed, 2),
        "acceptance_rate": acceptance_rate,
        "accepted_tokens": accepted_tokens,
        "generated_draft_tokens": generated_draft_tokens
    }

def run_benchmark_run(prompt_text, n_predict=128, k_draft=None, runs=3, warmup=1):
    # Warmup runs to populate OS page cache & GPU pipeline
    for _ in range(warmup):
        run_single_invocation(prompt_text, n_predict=n_predict, k_draft=k_draft)
    
    trials = []
    for _ in range(runs):
        res = run_single_invocation(prompt_text, n_predict=n_predict, k_draft=k_draft)
        trials.append(res)
    
    speeds = [t["gen_ts"] for t in trials if t["gen_ts"] is not None]
    accs = [t["acceptance_rate"] for t in trials if t["acceptance_rate"] is not None]
    evals = [t["eval_ms"] for t in trials if t["eval_ms"] is not None]

    mean_speed = round(statistics.mean(speeds), 1) if speeds else None
    speed_spread = [round(min(speeds), 1), round(max(speeds), 1)] if speeds else None
    std_speed = round(statistics.stdev(speeds), 2) if len(speeds) > 1 else 0.0

    mean_acc = round(statistics.mean(accs), 1) if accs else None
    mean_eval = round(statistics.mean(evals), 1) if evals else None

    # Use first valid trial for structural fields
    base = trials[0] if trials else {}
    base["runs"] = runs
    base["warmup"] = warmup
    base["gen_ts"] = mean_speed
    base["gen_ts_spread"] = speed_spread
    base["gen_ts_std"] = std_speed
    base["all_runs_gen_ts"] = speeds
    base["eval_ms"] = mean_eval
    base["acceptance_rate"] = mean_acc

    return base

def main():
    parser = argparse.ArgumentParser(description="RX 6700 XT Speculative Inference Benchmark Suite with Multi-Run Variance Reporting")
    parser.add_argument("--runs", type=int, default=3, help="Number of measurement runs per configuration (default: 3)")
    parser.add_argument("--warmup", type=int, default=1, help="Number of untimed warmup runs (default: 1)")
    parser.add_argument("--tokens", type=int, default=128, help="Number of tokens to generate (default: 128)")
    args = parser.parse_args()

    print("=" * 80)
    print("6700XT-AFTERBURNER: RX 6700 XT SPECULATIVE INFERENCE BENCHMARK SUITE")
    print(f"Verifier: Qwen2.5-Coder-7B-Instruct (Q4_K_M, 4.36 GiB)")
    print(f"Draft:    Qwen2.5-Coder-0.5B-Instruct (Q4_0, 330 MiB)")
    print(f"Backend:  Vulkan (Direct GPU VRAM offload -ngl 99 -ngld 99)")
    print(f"Variance: {args.runs} measurement runs (with {args.warmup} warmup run), deterministic temp 0.0")
    print("=" * 80)

    results = []

    for p in PROMPTS:
        print(f"\n>>> Running Benchmark: [{p['category']}] '{p['prompt'][:50]}...'")
        
        # 1. Baseline Standalone 7B
        print(f"  Testing Baseline Standalone 7B ({args.runs} runs)...", end="", flush=True)
        baseline = run_benchmark_run(p['prompt'], n_predict=args.tokens, k_draft=None, runs=args.runs, warmup=args.warmup)
        baseline["prompt_id"] = p["id"]
        baseline["category"] = p["category"]
        baseline["type"] = "Baseline 7B"
        baseline["speedup"] = 1.0
        print(f" Mean: {baseline['gen_ts']} t/s (spread: {baseline['gen_ts_spread']}, eval: {baseline['eval_ms']} ms)")
        results.append(baseline)

        # 2. Speculative runs with K = 2, 3, 4
        for k in [2, 3, 4]:
            print(f"  Testing Speculative (K={k}, {args.runs} runs)...", end="", flush=True)
            spec = run_benchmark_run(p['prompt'], n_predict=args.tokens, k_draft=k, runs=args.runs, warmup=args.warmup)
            spec["prompt_id"] = p["id"]
            spec["category"] = p["category"]
            spec["type"] = f"Speculative K={k}"
            if baseline["gen_ts"] and spec["gen_ts"]:
                spec["speedup"] = round(spec["gen_ts"] / baseline["gen_ts"], 2)
            else:
                spec["speedup"] = None
            acc_str = f" | Acc: {spec['acceptance_rate']:.1f}%" if spec['acceptance_rate'] else ""
            print(f" Mean: {spec['gen_ts']} t/s (spread: {spec['gen_ts_spread']}) -> Speedup: {spec['speedup']}x{acc_str}")
            results.append(spec)

    out_path = r"MEMORY/BENCHMARK_RESULTS.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nFull multi-run benchmark data saved to {out_path}")

if __name__ == "__main__":
    main()
