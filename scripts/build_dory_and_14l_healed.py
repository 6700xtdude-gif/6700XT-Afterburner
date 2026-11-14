#!/usr/bin/env python3
"""
build_dory_and_14l_healed.py
Builds and exports two GGUF-compatible surgical models from the 14 physical ShortGPT layers
(KEEP_14 = [0, 1, 2, 3, 4, 5, 6, 7, 15, 16, 17, 20, 22, 23]):
  1. Models/Qwen2.5-Coder-0.5B-L14-Healed (14 layers, Seam Distilled)
  2. Models/Qwen2.5-Coder-0.5B-Dory19L-Healed (14 physical layers -> 19 effective layers via
     2x Weight-Tied Recurrent Middle Block [5..9] with independent per-pass RMSNorm scales)
"""
import os
import json
import copy
import time
from pathlib import Path
import torch
import torch.nn as nn
import torch.nn.functional as F
from safetensors.torch import save_file
from transformers import AutoModelForCausalLM, AutoTokenizer

ROOT_DIR = Path(__file__).resolve().parent.parent
TEACHER_DIR = str(ROOT_DIR / "Models" / "Qwen2.5-Coder-0.5B-Instruct")
OUT_14L_DIR = str(ROOT_DIR / "Models" / "Qwen2.5-Coder-0.5B-L14-Healed")
OUT_DORY19L_DIR = str(ROOT_DIR / "Models" / "Qwen2.5-Coder-0.5B-Dory19L-Healed")

KEEP_14 = [0, 1, 2, 3, 4, 5, 6, 7, 15, 16, 17, 20, 22, 23]

CALIBRATION_TEXTS = [
    "<|im_start|>system\nYou are Qwen, created by Alibaba Cloud. You are a helpful assistant.<|im_end|>\n<|im_start|>user\nWrite a clean, optimized quicksort implementation in Python with comments.<|im_end|>\n<|im_start|>assistant\nCertainly! Below is a clean, optimized implementation of the Quicksort algorithm in Python, complete with comments explaining each part:\n\n```python\ndef quicksort(arr):\n    # Base case: if the array has 0 or 1 elements, it is already sorted\n    if len(arr) <= 1:\n        return arr\n    \n    # Choose the middle element as the pivot\n    pivot = arr[len(arr) // 2]\n    \n    # Partition the array into three sub-arrays\n    left = [x for x in arr if x < pivot]\n    middle = [x for x in arr if x == pivot]\n    right = [x for x in arr if x > pivot]\n    \n    # Recursively sort left and right, then combine\n    return quicksort(left) + middle + quicksort(right)\n```",
    "<|im_start|>system\nYou are Qwen, created by Alibaba Cloud. You are a helpful assistant.<|im_end|>\n<|im_start|>user\nOutput a valid JSON schema representing a user profile with id, username, email, roles, and settings.<|im_end|>\n<|im_start|>assistant\nCertainly! Below is a valid JSON schema representing a user profile:\n\n```json\n{\n  \"$schema\": \"http://json-schema.org/draft-07/schema#\",\n  \"title\": \"UserProfile\",\n  \"type\": \"object\",\n  \"properties\": {\n    \"id\": {\n      \"type\": \"integer\",\n      \"description\": \"Unique identifier for the user\"\n    },\n    \"username\": {\n      \"type\": \"string\"\n    },\n    \"email\": {\n      \"type\": \"string\",\n      \"format\": \"email\"\n    },\n    \"roles\": {\n      \"type\": \"array\",\n      \"items\": {\n        \"type\": \"string\"\n      }\n    },\n    \"settings\": {\n      \"type\": \"object\"\n    }\n  },\n  \"required\": [\"id\", \"username\", \"email\"]\n}\n```",
    "<|im_start|>system\nYou are Qwen, created by Alibaba Cloud. You are a helpful assistant.<|im_end|>\n<|im_start|>user\nExplain the architectural trade-offs between memory bandwidth and cache latency during autoregressive LLM decoding on modern GPUs.<|im_end|>\n<|im_start|>assistant\nDuring autoregressive LLM decoding, token generation is primarily memory-bandwidth bound because each forward pass requires loading all model weights from VRAM into compute units to generate a single token. High-speed SRAM caches like AMD Infinity Cache reduce latency and amplify effective bandwidth when active weights fit inside the cache.",
    "<|im_start|>system\nYou are Qwen, created by Alibaba Cloud. You are a helpful assistant.<|im_end|>\n<|im_start|>user\nWrite a Python function to implement binary search and merge sort.<|im_end|>\n<|im_start|>assistant\nCertainly! Here is an implementation of binary search in Python:\n\n```python\ndef binary_search(arr, target):\n    low, high = 0, len(arr) - 1\n    while low <= high:\n        mid = (low + high) // 2\n        if arr[mid] == target:\n            return mid\n        elif arr[mid] < target:\n            low = mid + 1\n        else:\n            high = mid - 1\n    return -1\n```"
]

def eval_metrics(model, teacher_batches):
    matches = 0
    total = 0
    kl_sum = 0.0
    with torch.no_grad():
        for input_ids, t_logits, t_top1, _ in teacher_batches:
            s_logits = model(input_ids=input_ids, use_cache=False).logits
            s_top1 = s_logits.argmax(dim=-1)
            matches += (s_top1 == t_top1).sum().item()
            total += t_top1.numel()
            top_v, top_idx = torch.topk(t_logits, k=64, dim=-1)
            s_top_v = torch.gather(s_logits, -1, top_idx)
            t_prob = F.softmax(top_v, dim=-1)
            s_log_prob = F.log_softmax(s_top_v, dim=-1)
            kl = F.kl_div(s_log_prob, t_prob, reduction="batchmean").item()
            kl_sum += kl
    return (matches / total) * 100.0, kl_sum / len(teacher_batches)

def train_distill(model, params, teacher_batches, epochs=10):
    opt = torch.optim.AdamW(params, lr=8e-5, weight_decay=0.01)
    model.train()
    for _ in range(epochs):
        for input_ids, t_logits, _, t_hid in teacher_batches:
            opt.zero_grad()
            out = model(input_ids=input_ids, use_cache=False, output_hidden_states=True)
            s_logits = out.logits
            s_hid = out.hidden_states[-1]
            T = 1.5
            top_v, top_idx = torch.topk(t_logits, k=128, dim=-1)
            s_top_v = torch.gather(s_logits, -1, top_idx)
            t_prob = F.softmax(top_v / T, dim=-1)
            s_log_prob = F.log_softmax(s_top_v / T, dim=-1)
            kl_loss = F.kl_div(s_log_prob, t_prob, reduction="batchmean") * (T * T)
            cos_loss = (1.0 - F.cosine_similarity(s_hid, t_hid, dim=-1)).mean()
            mse_loss = F.mse_loss(s_hid, t_hid)
            loss = kl_loss + 2.0 * cos_loss + 0.05 * mse_loss
            loss.backward()
            torch.nn.utils.clip_grad_norm_(params, 1.0)
            opt.step()
    model.eval()

def save_hf_checkpoint(model, source_dir, output_dir, num_layers):
    os.makedirs(output_dir, exist_ok=True)
    model_bf16 = copy.deepcopy(model).to(torch.bfloat16)
    state_dict = {}
    for k, v in model_bf16.state_dict().items():
        if k == "lm_head.weight":
            continue
        # Clone to decouple shared storage when exporting unrolled GGUF tensors
        state_dict[k] = v.detach().clone().contiguous()

    save_file(state_dict, os.path.join(output_dir, "model.safetensors"))

    with open(os.path.join(source_dir, "config.json"), "r", encoding="utf-8") as f:
        config = json.load(f)
    config["num_hidden_layers"] = num_layers
    if "layer_types" in config and isinstance(config["layer_types"], list):
        config["layer_types"] = ["full_attention"] * num_layers
    if "max_window_layers" in config:
        config["max_window_layers"] = num_layers

    with open(os.path.join(output_dir, "config.json"), "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    for fname in os.listdir(source_dir):
        if fname not in ["model.safetensors", "config.json"] and not fname.endswith(".gguf"):
            src_f = os.path.join(source_dir, fname)
            dst_f = os.path.join(output_dir, fname)
            if os.path.isfile(src_f):
                with open(src_f, "rb") as rf, open(dst_f, "wb") as wf:
                    wf.write(rf.read())

def main():
    t0 = time.time()
    print("=" * 80)
    print("BUILDING & EXPORTING HEALED 14L + DORY WEIGHT-TIED 19L CHECKPOINTS")
    print("=" * 80)

    tokenizer = AutoTokenizer.from_pretrained(TEACHER_DIR)
    teacher = AutoModelForCausalLM.from_pretrained(TEACHER_DIR, dtype=torch.float32, device_map="cpu")
    teacher.eval()

    teacher_batches = []
    with torch.no_grad():
        for text in CALIBRATION_TEXTS:
            inp = tokenizer(text, return_tensors="pt")["input_ids"]
            out = teacher(input_ids=inp, output_hidden_states=True)
            teacher_batches.append((inp, out.logits.detach(), out.logits.argmax(dim=-1).detach(), out.hidden_states[-1].detach()))

    orig_layers = list(teacher.model.layers)

    # 1. Build & Distill Optimal Linear 14L
    print("\n[1] Distilling Optimal Linear 14L (KEEP_14)...")
    model_14l = copy.deepcopy(teacher)
    model_14l.model.layers = nn.ModuleList([copy.deepcopy(orig_layers[i]) for i in KEEP_14])
    for idx, layer in enumerate(model_14l.model.layers):
        layer.self_attn.layer_idx = idx

    pre_14_acc, pre_14_kl = eval_metrics(model_14l, teacher_batches)
    params_14l = []
    for n, p in model_14l.model.named_parameters():
        if any(k in n for k in ["norm", "o_proj", "down_proj"]):
            p.requires_grad = True
            params_14l.append(p)
        else:
            p.requires_grad = False

    train_distill(model_14l, params_14l, teacher_batches, epochs=10)
    post_14_acc, post_14_kl = eval_metrics(model_14l, teacher_batches)
    print(f"    Linear 14L: Pre-Heal = {pre_14_acc:.2f}% (KL={pre_14_kl:.2f}) -> Post-Heal = {post_14_acc:.2f}% (KL={post_14_kl:.2f})")
    save_hf_checkpoint(model_14l, TEACHER_DIR, OUT_14L_DIR, 14)
    print(f"    Saved to {OUT_14L_DIR}")

    # 2. Build & Distill Weight-Tied Dory 14L->19L (Standard Qwen2 Layers for Zero-Patch GGUF Execution!)
    print("\n[2] Distilling Weight-Tied Dory 14L->19L (5 Input + 5x2 Tied Recurrent + 4 Output)...")
    model_dory = copy.deepcopy(teacher)
    phys_14 = [copy.deepcopy(orig_layers[i]) for i in KEEP_14]
    # Create Pass 2 recurrent layers [5..9] that SHARE 100% of self_attn & mlp weights with Pass 1,
    # while having independent input_layernorm & post_attention_layernorm (1.7 KB/layer) for Pass 2 scale adaptation!
    pass2_recurrent = []
    for i in range(5, 10):
        layer_p2 = copy.deepcopy(phys_14[i])
        # Tie attention & MLP weight tensors directly to Pass 1 physical layer!
        layer_p2.self_attn.q_proj = phys_14[i].self_attn.q_proj
        layer_p2.self_attn.k_proj = phys_14[i].self_attn.k_proj
        layer_p2.self_attn.v_proj = phys_14[i].self_attn.v_proj
        layer_p2.self_attn.o_proj = phys_14[i].self_attn.o_proj
        layer_p2.mlp = phys_14[i].mlp
        # Attenuate Pass 2 residual output slightly at init via post_attention_layernorm / input_layernorm
        with torch.no_grad():
            layer_p2.input_layernorm.weight.mul_(0.7)
            layer_p2.post_attention_layernorm.weight.mul_(0.7)
        pass2_recurrent.append(layer_p2)

    dory_layers = phys_14[0:5] + phys_14[5:10] + pass2_recurrent + phys_14[10:14]
    for idx, layer in enumerate(dory_layers):
        layer.self_attn.layer_idx = idx
    model_dory.model.layers = nn.ModuleList(dory_layers)
    model_dory.config.num_hidden_layers = 19

    unique_p = sum(p.numel() for p in set(model_dory.parameters()))
    print(f"    Unique Physical Parameters in Dory 19L: {unique_p:,} (vs {sum(p.numel() for p in set(model_14l.parameters())):,} in Linear 14L)")

    params_dory = []
    for n, p in model_dory.model.named_parameters():
        if any(k in n for k in ["norm", "o_proj", "down_proj"]):
            p.requires_grad = True
            if all(p is not ex for ex in params_dory):
                params_dory.append(p)
        else:
            p.requires_grad = False

    train_distill(model_dory, params_dory, teacher_batches, epochs=10)
    post_dory_acc, post_dory_kl = eval_metrics(model_dory, teacher_batches)
    print(f"    Dory 14L->19L: Post-Heal = {post_dory_acc:.2f}% (KL={post_dory_kl:.2f})")
    save_hf_checkpoint(model_dory, TEACHER_DIR, OUT_DORY19L_DIR, 19)
    print(f"    Saved to {OUT_DORY19L_DIR} (Total time: {time.time() - t0:.1f}s)")

if __name__ == "__main__":
    main()
