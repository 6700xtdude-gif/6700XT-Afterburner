#!/usr/bin/env python3
"""
distill_32k_dory_and_14l.py
Fixes the 32k-vocab chat-template token split bug (where 'assistant' token 77091 was split
into [395, 11202] by the 32k tokenizer without distillation):
Distills both the 14-Layer 96MB model and the Dory-Looped 19-Layer 96MB model directly on
32k-tokenized sequences against the 24-layer Teacher's hidden states and 32k-sliced logits!
"""
import os
import json
import copy
import struct
import subprocess
from pathlib import Path
import torch
import torch.nn as nn
import torch.nn.functional as F
from safetensors.torch import load_file, save_file
from transformers import AutoModelForCausalLM, AutoTokenizer

ROOT_DIR = Path(__file__).resolve().parent.parent
TEACHER_DIR = ROOT_DIR / "Models" / "Qwen2.5-Coder-0.5B-Instruct"
PRUNED_32K_REF = ROOT_DIR / "Models" / "Qwen2.5-Coder-0.5B-L14-Pruned"
DIR_14L_96M = ROOT_DIR / "Models" / "Qwen2.5-Coder-0.5B-L14-Healed-96MB"
DIR_DORY_96M = ROOT_DIR / "Models" / "Qwen2.5-Coder-0.5B-Dory19L-Healed-96MB"
CONVERT_SCRIPT = str(ROOT_DIR / "tools" / "llama.cpp" / "convert_hf_to_gguf.py")
QUANT_BIN      = str(ROOT_DIR / "bin" / "vulkan" / "llama-quantize.exe")

PAIRS = [
    (
        "Write a clean Python function for binary search.",
        "Here is a clean Python function for binary search:\n\n```python\ndef binary_search(arr, target):\n    low, high = 0, len(arr) - 1\n    while low <= high:\n        mid = (low + high) // 2\n        if arr[mid] == target:\n            return mid\n        elif arr[mid] < target:\n            low = mid + 1\n        else:\n            high = mid - 1\n    return -1\n```"
    ),
    (
        "Write a clean, optimized quicksort implementation in Python with comments.",
        "Certainly! Below is a clean implementation of Quicksort in Python:\n\n```python\ndef quicksort(arr):\n    if len(arr) <= 1:\n        return arr\n    pivot = arr[len(arr) // 2]\n    left = [x for x in arr if x < pivot]\n    middle = [x for x in arr if x == pivot]\n    right = [x for x in arr if x > pivot]\n    return quicksort(left) + middle + quicksort(right)\n```"
    ),
    (
        "Output a valid JSON schema representing a user profile with id, username, email, roles, and settings.",
        "```json\n{\n  \"$schema\": \"http://json-schema.org/draft-07/schema#\",\n  \"title\": \"UserProfile\",\n  \"type\": \"object\",\n  \"properties\": {\n    \"id\": { \"type\": \"integer\" },\n    \"username\": { \"type\": \"string\" },\n    \"email\": { \"type\": \"string\", \"format\": \"email\" },\n    \"roles\": { \"type\": \"array\", \"items\": { \"type\": \"string\" } },\n    \"settings\": { \"type\": \"object\" }\n  },\n  \"required\": [\"id\", \"username\", \"email\"]\n}\n```"
    ),
]

def main():
    print("=" * 84)
    print("32K-VOCAB NATIVE DISTILLATION FOR 96 MB INFINITY CACHE (L14 & DORY 19L)")
    print("=" * 84)

    with open(PRUNED_32K_REF / "draft_to_verifier_id.bin", "rb") as f:
        data = f.read()
    kept_ids = list(struct.unpack(f"<{len(data)//4}I", data))
    kept_tensor = torch.tensor(kept_ids, dtype=torch.long)

    tok32 = AutoTokenizer.from_pretrained(str(PRUNED_32K_REF))
    teacher = AutoModelForCausalLM.from_pretrained(str(TEACHER_DIR), dtype=torch.float32, device_map="cpu")
    teacher.eval()

    # Build aligned 32k token sequences -> map each 32k token ID back to its exact 152k token ID via kept_ids!
    # That way the 24-layer Teacher runs on the exact same token sequence and provides exact per-position targets!
    batches = []
    with torch.no_grad():
        for user_q, asst_a in PAIRS:
            full_text = f"<|im_start|>system\nYou are a helpful assistant.<|im_end|>\n<|im_start|>user\n{user_q}<|im_end|>\n<|im_start|>assistant\n{asst_a}<|im_end|>"
            ids_32k = tok32.encode(full_text, return_tensors="pt")
            # Map 32k IDs -> 152k IDs so teacher processes the exact same subword sequence!
            ids_152k = kept_tensor[ids_32k]
            t_out = teacher(input_ids=ids_152k, output_hidden_states=True)
            # Slice teacher logits to 32k vocab!
            t_logits_32k = t_out.logits[:, :, kept_tensor].detach()
            t_top1_32k = t_logits_32k.argmax(dim=-1).detach()
            t_hid = t_out.hidden_states[-1].detach()
            batches.append((ids_32k, t_logits_32k, t_top1_32k, t_hid))

    for label, model_dir, num_layers, is_dory in [
        ("Healed 14L 96MB",      DIR_14L_96M,  14, False),
        ("Dory-Looped 19L 96MB", DIR_DORY_96M, 19, True),
    ]:
        print(f"\n>>> Distilling {label} ({num_layers} effective layers, 32k vocab)...")
        m = AutoModelForCausalLM.from_pretrained(str(model_dir), dtype=torch.float32, device_map="cpu")
        if is_dory:
            # Re-tie Pass 2 layers [10..14] to Pass 1 layers [5..9] during training!
            for offset in range(5):
                p1 = m.model.layers[5 + offset]
                p2 = m.model.layers[10 + offset]
                p2.self_attn.q_proj = p1.self_attn.q_proj
                p2.self_attn.k_proj = p1.self_attn.k_proj
                p2.self_attn.v_proj = p1.self_attn.v_proj
                p2.self_attn.o_proj = p1.self_attn.o_proj
                p2.mlp = p1.mlp

        params = []
        for n, p in m.model.named_parameters():
            if any(k in n for k in ["embed_tokens", "norm", "o_proj", "down_proj", "q_proj", "v_proj"]):
                p.requires_grad = True
                if all(p is not ex for ex in params):
                    params.append(p)
            else:
                p.requires_grad = False

        opt = torch.optim.AdamW(params, lr=1e-4, weight_decay=0.01)
        m.train()
        for ep in range(12):
            for ids_32k, t_logits_32k, t_top1_32k, t_hid in batches:
                opt.zero_grad()
                out = m(input_ids=ids_32k, use_cache=False, output_hidden_states=True)
                s_logits = out.logits
                s_hid = out.hidden_states[-1]
                T = 1.5
                top_v, top_idx = torch.topk(t_logits_32k, k=128, dim=-1)
                s_top_v = torch.gather(s_logits, -1, top_idx)
                kl = F.kl_div(F.log_softmax(s_top_v / T, dim=-1), F.softmax(top_v / T, dim=-1), reduction="batchmean") * (T * T)
                ce = F.cross_entropy(s_logits[:, :-1, :].reshape(-1, 32768), ids_32k[:, 1:].reshape(-1))
                cos = (1.0 - F.cosine_similarity(s_hid, t_hid, dim=-1)).mean()
                loss = kl + 0.5 * ce + 2.0 * cos
                loss.backward()
                torch.nn.utils.clip_grad_norm_(params, 1.0)
                opt.step()

        m.eval()
        matches, total = 0, 0
        with torch.no_grad():
            for ids_32k, _, t_top1_32k, _ in batches:
                pred = m(input_ids=ids_32k, use_cache=False).logits.argmax(dim=-1)
                matches += (pred == t_top1_32k).sum().item()
                total += t_top1_32k.numel()
        print(f"    Post-Distill 32k Top-1 Agreement: {matches/total*100:.2f}%")

        # Save safetensors & re-quantize BF16 -> Q4_0 and Q2_K
        m_bf16 = copy.deepcopy(m).to(torch.bfloat16)
        sd = {k: v.detach().clone().contiguous() for k, v in m_bf16.state_dict().items() if k != "lm_head.weight"}
        save_file(sd, str(model_dir / "model.safetensors"))

        tag = model_dir.name
        bf16_p = str(model_dir / f"{tag}-BF16.gguf")
        q4_p   = str(model_dir / f"{tag}-Q4_0.gguf")
        q2k_p  = str(model_dir / f"{tag}-Q2_K.gguf")
        subprocess.run(["python", CONVERT_SCRIPT, str(model_dir), "--outfile", bf16_p, "--outtype", "bf16"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run([QUANT_BIN, bf16_p, q4_p, "Q4_0"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run([QUANT_BIN, bf16_p, q2k_p, "Q2_K"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"    Exported {q4_p} & {q2k_p}")

if __name__ == "__main__":
    main()
