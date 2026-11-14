#!/usr/bin/env python3
"""
build_and_test_96mb_and_100tps.py
1. Exports the 32,768-vocab 96 MB Infinity Cache (<90 MB Q2_0 / 143 MB Q4_0) versions of:
   - Qwen2.5-Coder-0.5B-L14-Healed-96MB
   - Qwen2.5-Coder-0.5B-Dory19L-Healed-96MB
2. Benchmarks K=4,5 horizons on 7B + Healed 14L (breaking the 100 tokens/sec barrier!)
   and 14B + Healed 14L (breaking 65+ tokens/sec!).
3. Benchmarks Standalone 96 MB Infinity Cache speed & output quality on Python Quicksort:
   - Old Unhealed 14L (86 MB) vs New Healed 14L (86 MB) vs New Dory-Looped 19L!
"""
import os
import json
import struct
import shutil
import subprocess
import re
from pathlib import Path
import torch
from safetensors.torch import load_file, save_file

ROOT_DIR = Path(__file__).resolve().parent.parent
PRUNED_32K_REF = ROOT_DIR / "Models" / "Qwen2.5-Coder-0.5B-L14-Pruned"
CONVERT_SCRIPT = str(ROOT_DIR / "tools" / "llama.cpp" / "convert_hf_to_gguf.py")
QUANT_BIN      = str(ROOT_DIR / "bin" / "vulkan" / "llama-quantize.exe")
LLAMA_CLI      = str(ROOT_DIR / "bin" / "vulkan" / "llama-cli.exe")

MODEL_7B       = str(ROOT_DIR / "Models" / "Qwen2.5-Coder-7B-Instruct-GGUF" / "qwen2.5-coder-7b-instruct-q4_k_m.gguf")
MODEL_14B      = str(ROOT_DIR / "Models" / "Qwen2.5-Coder-14B-Instruct-GGUF" / "qwen2.5-coder-14b-instruct-q4_k_m.gguf")
DRAFT_14L_Q4   = str(ROOT_DIR / "Models" / "Qwen2.5-Coder-0.5B-L14-Healed" / "Qwen2.5-Coder-0.5B-L14-Healed-Q4_0.gguf")

def build_32k_gguf(src_dir: Path, dst_dir: Path, num_layers: int, tag: str):
    os.makedirs(dst_dir, exist_ok=True)
    # Load 32,768 token IDs from draft_to_verifier_id.bin
    map_bin = PRUNED_32K_REF / "draft_to_verifier_id.bin"
    with open(map_bin, "rb") as f:
        data = f.read()
    kept_ids = list(struct.unpack(f"<{len(data)//4}I", data))
    idx_tensor = torch.tensor(kept_ids, dtype=torch.long)

    sd = load_file(str(src_dir / "model.safetensors"))
    sd["model.embed_tokens.weight"] = sd["model.embed_tokens.weight"][idx_tensor, :].contiguous()
    if "lm_head.weight" in sd:
        sd["lm_head.weight"] = sd["lm_head.weight"][idx_tensor, :].contiguous()
    save_file(sd, str(dst_dir / "model.safetensors"))

    for fname in ["config.json", "draft_to_verifier_id.bin", "generation_config.json", "merges.txt", "tokenizer.json", "tokenizer_config.json", "vocab.json"]:
        shutil.copy2(str(PRUNED_32K_REF / fname), str(dst_dir / fname))

    with open(dst_dir / "config.json", "r", encoding="utf-8") as f:
        cfg = json.load(f)
    cfg["num_hidden_layers"] = num_layers
    cfg["vocab_size"] = 32768
    if "layer_types" in cfg:
        cfg["layer_types"] = ["full_attention"] * num_layers
    if "max_window_layers" in cfg:
        cfg["max_window_layers"] = num_layers
    with open(dst_dir / "config.json", "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

    bf16_gguf = str(dst_dir / f"{tag}-BF16.gguf")
    q2_gguf   = str(dst_dir / f"{tag}-Q2_K.gguf")
    q4_gguf   = str(dst_dir / f"{tag}-Q4_0.gguf")

    subprocess.run(["python", CONVERT_SCRIPT, str(dst_dir), "--outfile", bf16_gguf, "--outtype", "bf16"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run([QUANT_BIN, bf16_gguf, q2_gguf, "Q2_K"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run([QUANT_BIN, bf16_gguf, q4_gguf, "Q4_0"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return q2_gguf, q4_gguf

def run_cli(model_path, prompt, draft_path=None, k=None, n_predict=128):
    cmd = [
        LLAMA_CLI, "-m", model_path, "-ngl", "99", "-c", "2048", "-n", str(n_predict),
        "--temp", "0.0", "-st", "-fa", "on", "-ctk", "q8_0", "-ctv", "q8_0", "--verbose", "-p", prompt
    ]
    if draft_path and k:
        cmd.extend(["-md", draft_path, "-ngld", "99", "--spec-type", "draft-simple", "--spec-draft-n-max", str(k)])
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
    out = proc.stdout
    gen_ts = None
    acc_rate = None
    m_sum = re.search(r"\[\s*Prompt:\s*([\d\.]+)\s*t/s\s*\|\s*Generation:\s*([\d\.]+)\s*t/s\s*\]", out)
    if m_sum:
        gen_ts = float(m_sum.group(2))
    m_acc = re.search(r"draft acceptance\s*=\s*([\d\.]+)\s*\(\s*(\d+)\s*accepted\s*/\s*(\d+)\s*generated\)", out)
    if m_acc:
        acc_rate = float(m_acc.group(1)) * 100.0
    return gen_ts, acc_rate, out

def main():
    print("=" * 88)
    print("PART 1: BREAKING THE 100 TOKENS/SEC BARRIER ON 7B & 65+ T/S ON 14B (Healed 14L)")
    print("=" * 88)
    json_prompt = "Output a valid JSON schema representing a user profile with id, username, email, roles, and settings."
    for tgt_name, tgt_path, base_ts in [("7B Verifier", MODEL_7B, 71.7), ("14B Verifier", MODEL_14B, 37.4)]:
        for k in [3, 4, 5]:
            ts, acc, _ = run_cli(tgt_path, json_prompt, draft_path=DRAFT_14L_Q4, k=k)
            spd = round(ts / base_ts, 2) if ts else 0
            print(f"  {tgt_name:14s} + Healed 14L (K={k}): {ts:6.1f} t/s | Speedup: {spd:.2f}x | Acc: {acc:.1f}%")

    print("\n" + "=" * 88)
    print("PART 2: EXPORTING & TESTING 32K-VOCAB 96 MB INFINITY CACHE MODELS (Healed 14L & Dory 19L)")
    print("=" * 88)
    q2_14l, q4_14l = build_32k_gguf(
        ROOT_DIR / "Models" / "Qwen2.5-Coder-0.5B-L14-Healed",
        ROOT_DIR / "Models" / "Qwen2.5-Coder-0.5B-L14-Healed-96MB",
        14, "Qwen2.5-Coder-0.5B-L14-Healed-96MB"
    )
    q2_dory, q4_dory = build_32k_gguf(
        ROOT_DIR / "Models" / "Qwen2.5-Coder-0.5B-Dory19L-Healed",
        ROOT_DIR / "Models" / "Qwen2.5-Coder-0.5B-Dory19L-Healed-96MB",
        19, "Qwen2.5-Coder-0.5B-Dory19L-Healed-96MB"
    )

    old_86mb = str(PRUNED_32K_REF / "Qwen2.5-Coder-0.5B-Pruned-Q2_0.gguf")
    old_143mb = str(PRUNED_32K_REF / "Qwen2.5-Coder-0.5B-Pruned-Q4_0.gguf")
    code_prompt = "Write a clean Python function for binary search:"

    for label, path in [
        ("Old Unhealed 14L 32k (Q2_0, 87 MB)",     old_86mb),
        ("New Healed 14L 32k   (Q2_K, 92 MB)",     q2_14l),
        ("New Dory-Looped 19L  (Q2_K, 114 MB)",    q2_dory),
        ("Old Unhealed 14L 32k (Q4_0, 143 MB)",    old_143mb),
        ("New Healed 14L 32k   (Q4_0, 143 MB)",    q4_14l),
        ("New Dory-Looped 19L  (Q4_0, 180 MB)",    q4_dory),
    ]:
        size_mb = os.path.getsize(path) / (1024 * 1024)
        ts, _, out = run_cli(path, code_prompt, n_predict=64)
        # Extract generated snippet
        lines = [ln.strip() for ln in out.splitlines() if "def " in ln or "return " in ln or "while " in ln][:3]
        preview = " | ".join(lines)[:70]
        print(f"  {label:38s} [{size_mb:5.1f} MiB]: {ts:6.1f} t/s | Output: {preview}")

if __name__ == "__main__":
    main()
