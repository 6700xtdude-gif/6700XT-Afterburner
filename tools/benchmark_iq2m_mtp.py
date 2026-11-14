#!/usr/bin/env python3
"""
benchmark_iq2m_mtp.py - Benchmark Qwen 3.8 27B IQ2_M (100% VRAM) Standalone vs MTP Speculative
"""
import json, os, subprocess, sys, time, urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SERVER = os.path.join(ROOT, "bin", "vulkan", "llama-server.exe")
MODEL = os.path.join(ROOT, "Models", "Qwen3.8-27B-UD-Q4_K_XL", "Qwen3.8-27B-IQ2_M.gguf")
PORT = 8092
URL = f"http://127.0.0.1:{PORT}"
OUT = os.path.join(ROOT, "MEMORY", "BENCHMARK_QWEN38_IQ2M_RESULTS.json")

PROMPTS = {
    "code": "Write a Python class for a thread-safe LRU cache using collections.OrderedDict and threading.Lock. Code only.",
    "json": "Return a JSON object describing a tool call named run_powershell with a command that lists the 5 largest files in C:\\Users. JSON only.",
    "reason": "Explain in three short paragraphs why autoregressive decoding at batch size 1 is memory-bandwidth bound.",
}

CONFIGS = [
    {
        "name": "IQ2M_Standalone_NGL99",
        "args": ["-m", MODEL, "--host", "127.0.0.1", "--port", str(PORT),
                 "-ngl", "99", "-fa", "on", "-ctk", "q8_0", "-ctv", "q8_0",
                 "-c", "8192", "-np", "1", "-t", "6"]
    },
    {
        "name": "IQ2M_MTP_Speculative_K2",
        "args": ["-m", MODEL, "--host", "127.0.0.1", "--port", str(PORT),
                 "-ngl", "99", "-fa", "on", "-ctk", "q8_0", "-ctv", "q8_0",
                 "-c", "8192", "-np", "1", "-t", "6",
                 "--spec-type", "draft-mtp", "--spec-draft-n-max", "2"]
    }
]

def wait_ready(proc, timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if proc.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(URL + "/health", timeout=2) as r:
                if json.loads(r.read().decode()).get("status") == "ok":
                    return True
        except Exception:
            pass
        time.sleep(1.0)
    return False

def chat(prompt, n=128):
    req = urllib.request.Request(
        URL + "/v1/chat/completions",
        data=json.dumps({
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0, "max_tokens": n, "seed": 1,
        }).encode(),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode())

def run_test(c):
    print(f"\n=== Testing {c['name']} ===")
    proc = subprocess.Popen([SERVER] + c["args"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    res = {"name": c["name"], "prompts": {}}
    try:
        if not wait_ready(proc):
            res["error"] = "Failed to start"
            return res
        chat("Say OK.", 8)  # warmup
        for k, p in PROMPTS.items():
            r = chat(p, 128)
            tm = r.get("timings", {})
            choice = r["choices"][0]["message"]
            content = choice.get("content", "")
            reasoning = choice.get("reasoning_content", "")
            d = {
                "tg_tps": round(tm.get("predicted_per_second", 0), 2),
                "pp_tps": round(tm.get("prompt_per_second", 0), 2),
                "n": tm.get("predicted_n"),
                "draft_n": tm.get("draft_n"),
                "draft_acc": tm.get("draft_n_accepted"),
                "sample_output": (content or reasoning)[:120]
            }
            if d["draft_n"]:
                d["accept_rate"] = round(d["draft_acc"] / d["draft_n"], 3)
            res["prompts"][k] = d
            print(f"  {k:7s}: {d['tg_tps']:6.2f} t/s | draft: {d.get('draft_acc')}/{d.get('draft_n')} | sample: {repr(d['sample_output'][:50])}")
        tgs = [v["tg_tps"] for v in res["prompts"].values()]
        res["mean_tps"] = round(sum(tgs) / len(tgs), 2)
        print(f"  MEAN: {res['mean_tps']} tokens/sec")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        time.sleep(2)
    return res

def main():
    results = []
    for c in CONFIGS:
        results.append(run_test(c))
    with open(OUT, "w") as f:
        json.dump(results, f, indent=2)
    print("\nSaved", OUT)

if __name__ == "__main__":
    main()
