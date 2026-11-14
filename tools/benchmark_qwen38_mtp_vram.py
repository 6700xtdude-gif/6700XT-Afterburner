#!/usr/bin/env python3
"""
benchmark_qwen38_mtp_vram.py - EXP-019: Qwen 3.8 27B on RX 6700 XT
Approach 1: native MTP self-speculation (--spec-type draft-mtp)
Approach 2: VRAM reclaim (no mmproj, -np 1) + refill (higher -ngl)

For each config: launch llama-server, warm up, run fixed prompts at temp 0,
record decode t/s, draft acceptance, VRAM dedicated/shared, and check the
generated text is identical to the baseline config.
"""
import json, os, subprocess, sys, time, urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SERVER = os.path.join(ROOT, "bin", "vulkan", "llama-server.exe")
MDIR = os.path.join(ROOT, "Models", "Qwen3.8-27B-UD-Q4_K_XL")
MODEL = os.path.join(MDIR, "Qwen3.8-27B-UD-Q4_K_XL.gguf")
MMPROJ = os.path.join(MDIR, "mmproj-BF16.gguf")
PORT = 8091
URL = f"http://127.0.0.1:{PORT}"
OUT = os.path.join(ROOT, "MEMORY", "BENCHMARK_QWEN38_MTP_VRAM.json")
LOGDIR = os.path.join(ROOT, "MEMORY", "logs_exp019")
N_PREDICT = int(os.environ.get("N_PREDICT", "128"))

PROMPTS = {
    "code": "Write a Python class for a thread-safe LRU cache using collections.OrderedDict and threading.Lock. Code only.",
    "json": "Return a JSON object describing a tool call named run_powershell with a command that lists the 5 largest files in C:\\Users. JSON only.",
    "reason": "Explain in three short paragraphs why autoregressive decoding at batch size 1 is memory-bandwidth bound.",
}

COMMON = ["-m", MODEL, "--host", "127.0.0.1", "--port", str(PORT), "-fa", "on",
          "-ctk", "q8_0", "-ctv", "q8_0", "-c", "8192", "--load-mode", "none", "--fit", "off"]

def cfg(name, extra):
    return {"name": name, "args": COMMON + extra}

CONFIGS = [
    # what we served before: mmproj + auto parallel slots, 6 threads
    cfg("A0_served_before_ngl40", ["-ngl", "40", "-t", "6", "--mmproj", MMPROJ]),
    # approach 2: reclaim
    cfg("B1_reclaim_ngl40", ["-ngl", "40", "-t", "4", "-np", "1"]),
    cfg("B2_refill_ngl43", ["-ngl", "43", "-t", "4", "-np", "1"]),
    cfg("B3_refill_ngl45", ["-ngl", "45", "-t", "4", "-np", "1"]),
    cfg("B4_refill_ngl47", ["-ngl", "47", "-t", "4", "-np", "1"]),
]
# approach 1 configs are appended after we know the best refill ngl
MTP_NMAX = [1, 2, 3]

def gpu_mem(pid):
    ps = (f"$d=(Get-Counter '\\GPU Process Memory(pid_{pid}*)\\Dedicated Usage' -EA SilentlyContinue).CounterSamples | Measure-Object CookedValue -Sum;"
          f"$s=(Get-Counter '\\GPU Process Memory(pid_{pid}*)\\Shared Usage' -EA SilentlyContinue).CounterSamples | Measure-Object CookedValue -Sum;"
          "Write-Output (\"{0} {1}\" -f $d.Sum,$s.Sum)")
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=30).stdout.split()
        return round(float(out[0]) / 2**20), round(float(out[1]) / 2**20)
    except Exception:
        return None, None

def post(path, payload, timeout=900):
    req = urllib.request.Request(URL + path, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())

def wait_ready(proc, timeout=240):
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
        time.sleep(1.5)
    return False

def chat(prompt, n):
    return post("/v1/chat/completions", {
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0, "max_tokens": n, "seed": 1,
    })

def run_config(c):
    os.makedirs(LOGDIR, exist_ok=True)
    logf = open(os.path.join(LOGDIR, c["name"] + ".log"), "w", encoding="utf-8", errors="replace")
    print(f"\n=== {c['name']} ===", flush=True)
    t0 = time.time()
    proc = subprocess.Popen([SERVER] + c["args"], stdout=logf, stderr=subprocess.STDOUT)
    res = {"name": c["name"], "args": " ".join(a for a in c["args"] if not a.startswith("C:\\"))}
    try:
        if not wait_ready(proc):
            res["error"] = f"server failed to start (exit={proc.poll()})"
            print("  ", res["error"], flush=True)
            return res
        res["load_s"] = round(time.time() - t0, 1)
        chat("Say OK.", 8)  # warmup
        ded, sh = gpu_mem(proc.pid)
        res["vram_dedicated_mib"], res["vram_shared_mib"] = ded, sh
        res["prompts"] = {}
        for k, p in PROMPTS.items():
            r = chat(p, N_PREDICT)
            tm = r.get("timings", {})
            msg = r["choices"][0]["message"]
            text = (msg.get("reasoning_content") or "") + "\n<<>>\n" + (msg.get("content") or "")
            d = {
                "tg_tps": round(tm.get("predicted_per_second", 0), 2),
                "pp_tps": round(tm.get("prompt_per_second", 0), 2),
                "n": tm.get("predicted_n"),
                "draft_n": tm.get("draft_n"),
                "draft_acc": tm.get("draft_n_accepted"),
                "text": text,
            }
            if d["draft_n"]:
                d["accept_rate"] = round(d["draft_acc"] / d["draft_n"], 3)
            res["prompts"][k] = d
            print(f"  {k:7s} tg={d['tg_tps']:6.2f} t/s  n={d['n']}  draft={d['draft_acc']}/{d['draft_n']}", flush=True)
        tgs = [v["tg_tps"] for v in res["prompts"].values()]
        res["tg_mean"] = round(sum(tgs) / len(tgs), 2)
        print(f"  MEAN tg={res['tg_mean']} t/s | VRAM ded={ded} MiB shared={sh} MiB | load {res['load_s']}s", flush=True)
    except Exception as e:
        res["error"] = repr(e)
        print("  ERROR", e, flush=True)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()
        logf.close()
        time.sleep(3)
    return res

def main():
    results = []
    for c in CONFIGS:
        results.append(run_config(c))
    ok = [r for r in results if r["name"].startswith("B") and "tg_mean" in r]
    best = max(ok, key=lambda r: r["tg_mean"]) if ok else None
    best_ngl = best["args"].split("-ngl ")[1].split()[0] if best else "40"
    print(f"\nBest refill config: {best['name'] if best else None} (ngl {best_ngl})", flush=True)
    # MTP head adds its own context/compute buffers; also try one layer lower in case of spill
    # Verification batches (K+1 tokens) are CPU-compute bound, unlike 1-token decode
    # (bandwidth bound, saturates at 4 threads) -> split -t (decode) from -tb (batch).
    mtp_grid = [(2, 4), (2, 6), (2, 12), (3, 6), (3, 12), (1, 12)]
    for k, tb in mtp_grid:
        results.append(run_config(cfg(f"C_mtp_ngl{best_ngl}_k{k}_tb{tb}",
                                      ["-ngl", best_ngl, "-t", "4", "-tb", str(tb), "-np", "1",
                                       "--spec-type", "draft-mtp", "--spec-draft-n-max", str(k)])))
    if int(best_ngl) > 40:  # MTP context adds VRAM; check one step lower too
        lower = str(int(best_ngl) - 2)
        results.append(run_config(cfg(f"C_mtp_ngl{lower}_k2_tb12",
                                      ["-ngl", lower, "-t", "4", "-tb", "12", "-np", "1",
                                       "--spec-type", "draft-mtp", "--spec-draft-n-max", "2"])))
    # equivalence vs reclaim baseline (same backend, no speculation)
    base = next((r for r in results if r["name"] == "B1_reclaim_ngl40" and "prompts" in r), None)
    for r in results:
        if base and "prompts" in r:
            r["identical_to_B1"] = {k: r["prompts"][k]["text"] == base["prompts"][k]["text"] for k in PROMPTS}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("\n==== SUMMARY ====")
    for r in results:
        if "tg_mean" in r:
            acc = [v.get("accept_rate") for v in r["prompts"].values() if v.get("accept_rate") is not None]
            print(f"{r['name']:28s} tg={r['tg_mean']:6.2f}  ded={r['vram_dedicated_mib']}  shared={r['vram_shared_mib']}  "
                  f"acc={acc if acc else '-'}  identical={r.get('identical_to_B1')}")
        else:
            print(f"{r['name']:28s} ERROR {r.get('error')}")
    print("Saved", OUT)

if __name__ == "__main__":
    main()
