#!/usr/bin/env python3
"""
layer_prune.py - Prunes Qwen 2.5 0.5B from 24 layers down to 14 layers.
Drops redundant intermediate transformer blocks (layers 8 through 17).
Re-indexes remaining layers 18..23 to 8..13.
Reduces model body parameters by ~41.7%, reaching ~235M total parameters.
"""

import os
import sys
import json
import torch
from safetensors.torch import load_file, save_file

KEEP_ORIGINAL_LAYERS = [0, 1, 2, 3, 4, 5, 6, 7, 18, 19, 20, 21, 22, 23] # 14 layers total
TARGET_LAYER_COUNT = len(KEEP_ORIGINAL_LAYERS)

def prune_layers(source_dir: str, output_dir: str):
    print("=" * 60)
    print(f"Starting Layer Pruning: 24 Layers -> {TARGET_LAYER_COUNT} Layers")
    print(f"Keeping layers: {KEEP_ORIGINAL_LAYERS}")
    print(f"Source: {source_dir}")
    print(f"Output: {output_dir}")
    print("=" * 60)

    os.makedirs(output_dir, exist_ok=True)

    # 1. Load weights
    model_file = os.path.join(source_dir, "model.safetensors")
    if not os.path.exists(model_file):
        raise FileNotFoundError(f"Model file not found: {model_file}")

    print("[Step 1] Loading state dict...")
    state_dict = load_file(model_file)
    print(f"Loaded {len(state_dict)} tensors.")

    # 2. Build layer remapping dict
    # layer_map[old_idx] = new_idx
    layer_map = {old_idx: new_idx for new_idx, old_idx in enumerate(KEEP_ORIGINAL_LAYERS)}

    pruned_state_dict = {}

    print("[Step 2] Filtering and re-indexing layers...")
    for key, tensor in state_dict.items():
        # Check if key belongs to a transformer layer: model.layers.<idx>.<sublayer>
        if key.startswith("model.layers."):
            parts = key.split(".")
            layer_idx = int(parts[2])
            if layer_idx in layer_map:
                new_idx = layer_map[layer_idx]
                parts[2] = str(new_idx)
                new_key = ".".join(parts)
                pruned_state_dict[new_key] = tensor
            else:
                # Layer is pruned/dropped
                pass
        else:
            # Embeddings, norm, lm_head, etc.
            pruned_state_dict[key] = tensor

    print(f"Pruned state dict has {len(pruned_state_dict)} tensors (was {len(state_dict)}).")

    # 3. Save pruned safetensors
    out_model_file = os.path.join(output_dir, "model.safetensors")
    print(f"[Step 3] Saving pruned safetensors to {out_model_file}...")
    save_file(pruned_state_dict, out_model_file)

    # 4. Update config.json
    print("[Step 4] Updating config.json with new layer count...")
    with open(os.path.join(source_dir, "config.json"), "r", encoding="utf-8") as f:
        config = json.load(f)

    config["num_hidden_layers"] = TARGET_LAYER_COUNT
    with open(os.path.join(output_dir, "config.json"), "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    # 5. Copy remaining support files
    for fname in os.listdir(source_dir):
        if fname not in ["model.safetensors", "config.json"]:
            src_f = os.path.join(source_dir, fname)
            dst_f = os.path.join(output_dir, fname)
            if os.path.isfile(src_f):
                with open(src_f, "rb") as rf:
                    with open(dst_f, "wb") as wf:
                        wf.write(rf.read())

    print("\nLayer pruning complete! The model now has 14 layers (~235M parameters).")

if __name__ == "__main__":
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    if len(sys.argv) < 3:
        src = str(root / "Models" / "Qwen2.5-Coder-0.5B-VocabPruned")
        dst = str(root / "Models" / "Qwen2.5-Coder-0.5B-L14-Pruned")
    else:
        src = sys.argv[1]
        dst = sys.argv[2]
    prune_layers(src, dst)
