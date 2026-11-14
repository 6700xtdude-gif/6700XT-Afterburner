#!/usr/bin/env python3
"""
profile_layer_importance.py - ShortGPT Block Influence (BI) & Residual Sensitivity Profiler
Measures the exact angular distance: BI(l) = 1 - cos_sim(X_in, X_out) across all 24 layers
of Qwen2.5-Coder-0.5B-Instruct on code & JSON calibration samples.
"""
import os
import json
from pathlib import Path
import torch
import torch.nn.functional as F
from transformers import AutoModelForCausalLM, AutoTokenizer

ROOT_DIR = Path(__file__).resolve().parent.parent
MODEL_DIR = str(ROOT_DIR / "Models" / "Qwen2.5-Coder-0.5B-Instruct")

CALIBRATION_PROMPTS = [
    "Write a clean, optimized quicksort implementation in Python:\n```python\ndef quicksort(arr):\n    if len(arr) <= 1:\n        return arr\n    pivot = arr[len(arr) // 2]\n    left = [x for x in arr if x < pivot]\n    middle = [x for x in arr if x == pivot]\n    right = [x for x in arr if x > pivot]\n    return quicksort(left) + middle + quicksort(right)\n```",
    '{"$schema": "http://json-schema.org/draft-07/schema#", "title": "UserProfile", "type": "object", "properties": {"id": {"type": "integer"}, "username": {"type": "string"}, "email": {"type": "string", "format": "email"}, "roles": {"type": "array", "items": {"type": "string"}}}, "required": ["id", "username", "email"]}',
    "def binary_search(arr: list[int], target: int) -> int:\n    low, high = 0, len(arr) - 1\n    while low <= high:\n        mid = (low + high) // 2\n        if arr[mid] == target:\n            return mid\n        elif arr[mid] < target:\n            low = mid + 1\n        else:\n            high = mid - 1\n    return -1",
    "<|im_start|>system\nYou are a helpful coding assistant.<|im_end|>\n<|im_start|>user\nWrite a JSON object for an API response.<|im_end|>\n<|im_start|>assistant\n```json\n{\n  \"status\": \"success\",\n  \"code\": 200,\n  \"data\": {\n    \"items\": [1, 2, 3],\n    \"count\": 3\n  }\n}\n```"
]

def main():
    print("=" * 72)
    print("6700XT-AFTERBURNER: NEURAL LAYER IMPORTANCE PROFILER (ShortGPT BI)")
    print(f"Model: {MODEL_DIR}")
    print("=" * 72)

    tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_DIR,
        torch_dtype=torch.float32,
        device_map="cpu"
    )
    model.eval()

    num_layers = model.config.num_hidden_layers
    bi_scores = torch.zeros(num_layers)
    rel_mag_scores = torch.zeros(num_layers)
    total_tokens = 0

    with torch.no_grad():
        for text in CALIBRATION_PROMPTS:
            inputs = tokenizer(text, return_tensors="pt")
            out = model(**inputs, output_hidden_states=True)
            # hidden_states has num_layers + 1 elements: [embed_out, layer_0_out, ..., layer_23_out]
            hs = out.hidden_states
            seq_len = inputs["input_ids"].shape[1]
            total_tokens += seq_len

            for l in range(num_layers):
                x_in = hs[l][0]       # [seq_len, hidden_dim]
                x_out = hs[l + 1][0]  # [seq_len, hidden_dim]
                cos_sim = F.cosine_similarity(x_in, x_out, dim=-1) # [seq_len]
                bi = (1.0 - cos_sim).sum().item()
                bi_scores[l] += bi

                delta_norm = (x_out - x_in).norm(dim=-1) / (x_in.norm(dim=-1) + 1e-6)
                rel_mag_scores[l] += delta_norm.sum().item()

    bi_scores /= total_tokens
    rel_mag_scores /= total_tokens

    print(f"\nEvaluated across {len(CALIBRATION_PROMPTS)} sequences ({total_tokens} tokens):\n")
    print(f"{'Layer':<8} | {'Block Influence (1 - cos)':<26} | {'Rel Residual Delta':<20} | {'Redundancy Rank'}")
    print("-" * 76)

    ranked = torch.argsort(bi_scores).tolist() # ascending BI = most redundant first
    rank_map = {layer_idx: rank + 1 for rank, layer_idx in enumerate(ranked)}

    for l in range(num_layers):
        marker = " <-- MOST REDUNDANT" if rank_map[l] <= 8 else ""
        print(f"blk.{l:<4} | {bi_scores[l].item():<26.6f} | {rel_mag_scores[l].item():<20.4f} | #{rank_map[l]:<2}{marker}")

    print("\nTop 10 Most Redundant Layers (Safe to Prune Order):")
    print("  ", ranked[:10])

    # Also test single-layer and multi-layer logit KL-divergence / top-1 match vs full 24L model!
    print("\nEvaluating Leave-One-Out Top-1 Token Agreement vs Full 24-Layer Teacher:")
    # Get full teacher predictions on all calibration tokens
    teacher_preds = []
    for text in CALIBRATION_PROMPTS:
        inputs = tokenizer(text, return_tensors="pt")
        with torch.no_grad():
            logits = model(**inputs).logits
            teacher_preds.append((inputs, logits.argmax(dim=-1)))

    loo_agreement = {}
    orig_layers = list(model.model.layers)
    for drop_l in range(num_layers):
        model.model.layers = torch.nn.ModuleList([orig_layers[i] for i in range(num_layers) if i != drop_l])
        matches = 0
        count = 0
        with torch.no_grad():
            for inputs, t_pred in teacher_preds:
                s_pred = model(**inputs).logits.argmax(dim=-1)
                matches += (s_pred == t_pred).sum().item()
                count += t_pred.numel()
        loo_agreement[drop_l] = (matches / count) * 100.0

    model.model.layers = torch.nn.ModuleList(orig_layers)

    loo_ranked = sorted(loo_agreement.items(), key=lambda x: x[1], reverse=True)
    print("\nLayers Ranked by Leave-One-Out Top-1 Token Match with 24L Teacher:")
    for l, acc in loo_ranked:
        print(f"  Drop blk.{l:<2} -> {acc:6.2f}% exact top-1 token match (BI={bi_scores[l].item():.4f})")

if __name__ == "__main__":
    main()
