#!/usr/bin/env python3
"""Unified Head-to-Head & Speculative Benchmark Harness for Strata.

Modeled after Robert Karl's bench_vs_llama.py and Steve Corbett's telemetry conventions.
Drives OpenAI-compatible llama-server instances, measures server-side timings,
tracks hardware metrics (psutil RSS, CPU load, memory deltas), runs interleaved
rounds with warmups, and calculates medians over rounds.
"""

import argparse
import datetime
import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.request

# Ensure local bench directory is in import path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hardware_telemetry import TelemetrySampler


def execute_request(endpoint, prompt, max_tokens, temperature):
    url = f"{endpoint.rstrip('/')}/chat/completions"
    payload = {
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=120) as resp:
        res = json.loads(resp.read().decode("utf-8"))
    t1 = time.time()
    wall_duration = t1 - t0

    # Parse response
    choice = res.get("choices", [{}])[0]
    message = choice.get("message", {})
    content = message.get("content", "")
    reasoning = message.get("reasoning_content", "")
    timings = res.get("timings", {})
    usage = res.get("usage", {})

    pred_per_s = timings.get("predicted_per_second", 0.0)
    prompt_per_s = timings.get("prompt_per_second", 0.0)
    prompt_ms = timings.get("prompt_ms", 0.0)
    pred_n = timings.get("predicted_n", usage.get("completion_tokens", 0))
    prompt_n = timings.get("prompt_n", usage.get("prompt_tokens", 0))
    draft_n = timings.get("draft_n", 0)
    draft_accepted = timings.get("draft_n_accepted", 0)
    accept_rate = (draft_accepted / draft_n * 100.0) if draft_n > 0 else 0.0

    # Fallback to wall-clock if server didn't supply timings
    if pred_per_s == 0.0 and pred_n > 0:
        safe_duration = max(0.001, wall_duration)
        pred_per_s = pred_n / safe_duration

    return {
        "pred_tok_s": round(pred_per_s, 2),
        "prompt_tok_s": round(prompt_per_s, 2),
        "ttft_ms": round(prompt_ms, 2),
        "pred_tokens": pred_n,
        "prompt_tokens": prompt_n,
        "draft_tokens": draft_n,
        "draft_accepted": draft_accepted,
        "accept_rate_pct": round(accept_rate, 1),
        "wall_time_s": round(wall_duration, 2),
        "has_reasoning": bool(reasoning)
    }


def run_benchmark(config_path, rounds_override=None, out_dir="bench/reports"):
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    endpoint = cfg.get("endpoint", "http://127.0.0.1:8080/v1")
    corpus_file = cfg.get("corpus_file", "bench/corpus/standard_prompts.json")
    rounds = rounds_override or cfg.get("rounds", 3)
    warmup = cfg.get("warmup", True)

    with open(corpus_file, "r", encoding="utf-8") as f:
        prompts = json.load(f)

    # Verify server availability
    try:
        health_url = f"{endpoint.split('/v1')[0]}/health"
        with urllib.request.urlopen(health_url, timeout=5) as r:
            pass
    except Exception as e:
        print(f"[ERROR] Target server is not reachable at {endpoint}: {e}")
        sys.exit(1)

    print(f"=== Starting Strata Benchmark: {cfg.get('name', 'Benchmark')} ===")
    print(f"Target: {endpoint} | Prompts: {len(prompts)} | Rounds: {rounds} (Warmup: {warmup})")

    # Warmup
    if warmup:
        print("\n[Warmup] Warming up engine caches and Vulkan pipeline...")
        execute_request(endpoint, "Warm up the cache with a short sentence.", max_tokens=16, temperature=0.0)
        time.sleep(1.0)

    results_by_prompt = {p["id"]: [] for p in prompts}

    for r in range(rounds):
        round_idx = r + 1
        print(f"\n--- Round {round_idx} of {rounds} ---")
        
        # Interleave order every other round to cancel cache bias
        current_prompts = list(prompts)
        if r % 2 == 1:
            current_prompts.reverse()

        for p in current_prompts:
            pid = p["id"]
            p_text = p["prompt"]
            m_tok = p.get("max_tokens", 128)
            temp = p.get("temperature", 0.2)

            telemetry = TelemetrySampler(interval_s=0.1)
            telemetry.start()
            
            try:
                metrics = execute_request(endpoint, p_text, m_tok, temp)
            finally:
                telemetry.stop()

            telem_summary = telemetry.summary()
            metrics.update(telem_summary)
            metrics["round"] = round_idx
            results_by_prompt[pid].append(metrics)

            draft_info = f" (MTP Accept: {metrics['accept_rate_pct']}%)" if metrics["draft_tokens"] > 0 else ""
            print(f"  [{pid}] Decode: {metrics['pred_tok_s']} t/s | TTFT: {metrics['ttft_ms']} ms | RSS: {metrics['proc_rss_mb_peak']} MB{draft_info}")

        # Cooldown between rounds
        time.sleep(1.0)

    # Compute summary medians
    summary = []
    for p in prompts:
        pid = p["id"]
        runs = results_by_prompt[pid]
        decode_rates = [r["pred_tok_s"] for r in runs]
        ttfts = [r["ttft_ms"] for r in runs]
        accepts = [r["accept_rate_pct"] for r in runs if r["draft_tokens"] > 0]
        rss_peaks = [r["proc_rss_mb_peak"] for r in runs]

        summary.append({
            "id": pid,
            "category": p.get("category", "general"),
            "decode_t_s_median": round(statistics.median(decode_rates), 2),
            "decode_t_s_std": round(statistics.stdev(decode_rates), 2) if len(decode_rates) > 1 else 0.0,
            "ttft_ms_median": round(statistics.median(ttfts), 2),
            "accept_rate_median": round(statistics.median(accepts), 1) if accepts else None,
            "proc_rss_mb_peak": round(max(rss_peaks), 1)
        })

    # Overall benchmark speed
    all_decodes = [r["pred_tok_s"] for pid in results_by_prompt for r in results_by_prompt[pid]]
    overall_median = round(statistics.median(all_decodes), 2)

    os.makedirs(out_dir, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = os.path.join(out_dir, f"benchmark_{ts}.json")
    md_file = os.path.join(out_dir, f"benchmark_{ts}.md")

    full_report = {
        "config": cfg,
        "timestamp": ts,
        "overall_decode_median": overall_median,
        "summary": summary,
        "raw_runs": results_by_prompt
    }

    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(full_report, f, indent=2)

    # Format Markdown summary
    md_content = f"""# Benchmark Report — {cfg.get('name', 'Strata Eval')}

* **Date:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
* **Endpoint:** `{endpoint}`
* **Rounds:** {rounds} (Interleaved with Warmup)
* **Overall Median Decode:** **{overall_median} tokens/sec**

## Prompt Breakdown (Medians Across Rounds)

| ID | Category | Decode (t/s) | StdDev | TTFT (ms) | MTP Accept Rate | Peak RSS (MB) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
"""
    for s in summary:
        acc_str = f"{s['accept_rate_median']}%" if s['accept_rate_median'] is not None else "N/A"
        md_content += f"| `{s['id']}` | {s['category']} | **{s['decode_t_s_median']}** | ±{s['decode_t_s_std']} | {s['ttft_ms_median']} | {acc_str} | {s['proc_rss_mb_peak']} MB |\n"

    with open(md_file, "w", encoding="utf-8") as f:
        f.write(md_content)

    print(f"\n=== Benchmark Complete ===")
    print(f"Overall Median: {overall_median} t/s")
    print(f"JSON Report: {report_file}")
    print(f"Markdown Summary: {md_file}")
    return full_report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Strata Unified Benchmark Harness")
    parser.add_argument("--config", default="bench/configs/rx6700xt_evals.json", help="Path to JSON config")
    parser.add_argument("--rounds", type=int, default=None, help="Override round count")
    parser.add_argument("--out", default="bench/reports", help="Output directory")
    args = parser.parse_args()

    run_benchmark(args.config, args.rounds, args.out)
