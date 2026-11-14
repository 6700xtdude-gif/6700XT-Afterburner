#!/usr/bin/env python3
"""
vocab_prune.py - Prunes Qwen 2.5 Coder 0.5B vocabulary from 151,936 down to 32,768.
Reduces embedding & lm_head footprint from ~76MB (Q4) to ~16.5MB.
Outputs:
- Pruned model checkpoint in safetensors format
- Trimmed tokenizer.json
- draft_to_verifier_id.bin (128 KB lookup table)
"""

import os
import sys
import json
import struct
import torch
from safetensors.torch import load_file, save_file
from transformers import AutoTokenizer

TARGET_VOCAB_SIZE = 32768 # 2^15

def prune_vocabulary(source_dir: str, output_dir: str):
    print("=" * 60)
    print(f"Starting Vocabulary Pruning: 151,936 -> {TARGET_VOCAB_SIZE}")
    print(f"Source: {source_dir}")
    print(f"Output: {output_dir}")
    print("=" * 60)

    os.makedirs(output_dir, exist_ok=True)

    # 1. Load Tokenizer
    print("[Step 1] Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(source_dir)
    original_vocab = tokenizer.get_vocab()
    print(f"Original vocab size: {len(original_vocab)}")

    # 2. Identify tokens to preserve
    # Must preserve:
    # - Special tokens (<|im_start|>, <|im_end|>, <|endoftext|>, etc.)
    # - Byte tokens (<0x00> to <0xFF>)
    # - Top frequency tokens in vocabulary order up to TARGET_VOCAB_SIZE
    special_ids = set(tokenizer.all_special_ids)
    print(f"Found {len(special_ids)} special tokens.")

    # Find byte fallback tokens
    byte_ids = set()
    for token, idx in original_vocab.items():
        if token.startswith("<0x") and token.endswith(">") and len(token) == 6:
            byte_ids.add(idx)
    print(f"Found {len(byte_ids)} byte fallback tokens.")

    # Mandatory set
    mandatory_ids = special_ids.union(byte_ids)

    # Sort remaining vocabulary by original ID (which correlates with frequency in BPE)
    sorted_vocab = sorted(original_vocab.items(), key=lambda x: x[1])

    kept_ids = []
    # Add mandatory first
    for idx in sorted(mandatory_ids):
        if idx not in kept_ids:
            kept_ids.append(idx)

    # Fill up to TARGET_VOCAB_SIZE with top tokens from sorted vocab
    for token, idx in sorted_vocab:
        if len(kept_ids) >= TARGET_VOCAB_SIZE:
            break
        if idx not in mandatory_ids:
            kept_ids.append(idx)

    kept_ids = sorted(kept_ids)
    assert len(kept_ids) == TARGET_VOCAB_SIZE, f"Expected {TARGET_VOCAB_SIZE}, got {len(kept_ids)}"

    print(f"Selected exactly {len(kept_ids)} tokens for pruned vocabulary.")

    # 3. Create mapping lookup table (draft_to_verifier_id.bin)
    # Size: 32,768 * 4 bytes = 131,072 bytes (128 KB)
    map_path = os.path.join(output_dir, "draft_to_verifier_id.bin")
    with open(map_path, "wb") as f:
        for original_id in kept_ids:
            f.write(struct.pack("<I", original_id))
    print(f"Wrote translation lookup table: {map_path} ({os.path.getsize(map_path)} bytes)")

    # 4. Slice Model Weights
    print("[Step 2] Slicing model embedding and LM head weights...")
    model_file = os.path.join(source_dir, "model.safetensors")
    if not os.path.exists(model_file):
        raise FileNotFoundError(f"Model file not found: {model_file}")

    state_dict = load_file(model_file)
    embed_key = "model.embed_tokens.weight"
    lm_head_key = "lm_head.weight"

    old_embed = state_dict[embed_key]
    print(f"Original embed_tokens shape: {old_embed.shape} ({old_embed.dtype})")

    # Slice along vocab dimension (dim 0)
    kept_indices_tensor = torch.tensor(kept_ids, dtype=torch.long)
    new_embed = old_embed[kept_indices_tensor, :].clone()
    print(f"Pruned embed_tokens shape: {new_embed.shape}")

    state_dict[embed_key] = new_embed

    # Handle lm_head if present separately
    if lm_head_key in state_dict:
        old_lm_head = state_dict[lm_head_key]
        print(f"Original lm_head shape: {old_lm_head.shape}")
        state_dict[lm_head_key] = old_lm_head[kept_indices_tensor, :].clone()
        print(f"Pruned lm_head shape: {state_dict[lm_head_key].shape}")

    # 5. Save Pruned Weights
    out_model_file = os.path.join(output_dir, "model.safetensors")
    print(f"Saving pruned safetensors to {out_model_file}...")
    save_file(state_dict, out_model_file)

    # 6. Update config.json
    print("[Step 3] Updating config.json...")
    with open(os.path.join(source_dir, "config.json"), "r", encoding="utf-8") as f:
        config = json.load(f)

    config["vocab_size"] = TARGET_VOCAB_SIZE
    with open(os.path.join(output_dir, "config.json"), "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    # 7. Copy and trim tokenizer files
    print("[Step 4] Copying support files...")
    for fname in ["tokenizer_config.json", "chat_template.json", "generation_config.json"]:
        src = os.path.join(source_dir, fname)
        if os.path.exists(src):
            with open(src, "r", encoding="utf-8") as sf:
                data = sf.read()
            with open(os.path.join(output_dir, fname), "w", encoding="utf-8") as df:
                df.write(data)

    print("\nVocabulary pruning complete! Ready for layer pruning.")

if __name__ == "__main__":
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    if len(sys.argv) < 3:
        src = str(root / "Models" / "Qwen2.5-Coder-0.5B-Instruct")
        dst = str(root / "Models" / "Qwen2.5-Coder-0.5B-VocabPruned")
    else:
        src = sys.argv[1]
        dst = sys.argv[2]
    prune_vocabulary(src, dst)
