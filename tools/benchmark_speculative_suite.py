import subprocess
import re
import json
import time
import os
import sys

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

def run_benchmark_run(prompt_text, n_predict=128, k_draft=None):
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

    # Parse metrics
    # Prompt eval: prompt eval time =     135.08 ms /    33 tokens (    4.09 ms per token,   244.30 tokens per second)
    # Eval time:        eval time =     874.40 ms /    64 tokens (   13.88 ms per token,    72.05 tokens per second)
    # Draft acceptance: draft acceptance = 0.86538 (   45 accepted /    52 generated)
    prompt_ts = None
    gen_ts = None
    eval_ms = None
    acceptance_rate = None
    accepted_tokens = None
    generated_draft_tokens = None
    tokens_generated = None

    # Parse Generation line: [ Prompt: 259.5 t/s | Generation: 95.6 t/s ]
    summary_match = re.search(r"\[\s*Prompt:\s*([\d\.]+)\s*t/s\s*\|\s*Generation:\s*([\d\.]+)\s*t/s\s*\]", output)
    if summary_match:
        prompt_ts = float(summary_match.group(1))
        gen_ts = float(summary_match.group(2))

    # Parse slot print_timing for detailed ms
    p_match = re.search(r"prompt eval time\s*=\s*([\d\.]+)\s*ms\s*/\s*(\d+)\s*tokens.*?([\d\.]+)\s*tokens per second", output)
    if p_match and prompt_ts is None:
        prompt_ts = float(p_match.group(3))

    # Match eval time that is NOT preceded by 'prompt '
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

def main():
    print("=" * 80)
    print("6700XT-AFTERBURNER: RX 6700 XT SPECULATIVE INFERENCE BENCHMARK SUITE")
    print("Verifier: Qwen2.5-Coder-7B-Instruct (Q4_K_M, 4.36 GiB)")
    print("Draft:    Qwen2.5-Coder-0.5B-Instruct (Q4_0, 330 MiB)")
    print("Backend:  Vulkan (Direct GPU VRAM offload -ngl 99 -ngld 99)")
    print("=" * 80)

    results = []

    for p in PROMPTS:
        print(f"\n>>> Running Benchmark: [{p['category']}] '{p['prompt'][:50]}...'")
        
        # 1. Baseline Standalone 7B
        print("  Testing Baseline Standalone 7B...", end="", flush=True)
        baseline = run_benchmark_run(p['prompt'], n_predict=128, k_draft=None)
        baseline["prompt_id"] = p["id"]
        baseline["category"] = p["category"]
        baseline["type"] = "Baseline 7B"
        baseline["speedup"] = 1.0
        print(f" Done: {baseline['gen_ts']} t/s ({baseline['eval_ms']} ms)")
        results.append(baseline)

        # 2. Speculative runs with K = 2, 3, 4, 5
        for k in [2, 3, 4]:
            print(f"  Testing Speculative (K={k})...", end="", flush=True)
            spec = run_benchmark_run(p['prompt'], n_predict=128, k_draft=k)
            spec["prompt_id"] = p["id"]
            spec["category"] = p["category"]
            spec["type"] = f"Speculative K={k}"
            if baseline["gen_ts"] and spec["gen_ts"]:
                spec["speedup"] = round(spec["gen_ts"] / baseline["gen_ts"], 2)
            else:
                spec["speedup"] = None
            acc_str = f" | Acc: {spec['acceptance_rate']:.1f}%" if spec['acceptance_rate'] else ""
            print(f" Done: {spec['gen_ts']} t/s ({spec['eval_ms']} ms) -> Speedup: {spec['speedup']}x{acc_str}")
            results.append(spec)

    # Save results to JSON
    out_path = r"MEMORY/BENCHMARK_RESULTS.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nFull benchmark data saved to {out_path}")

if __name__ == "__main__":
    main()
