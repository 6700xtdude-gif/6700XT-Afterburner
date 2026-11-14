#!/usr/bin/env python3
"""
heal_draft_model.py - Optimal 18-Layer Surgery + Knowledge Distillation Healing
1. Applies the optimal 18-layer architecture discovered by ShortGPT BI + Greedy Search:
   Kept:    [0, 1, 2, 3, 4, 5, 6, 7, 8, 14, 15, 16, 17, 19, 20, 21, 22, 23]
   Dropped: [9, 10, 11, 12, 13, 18] (-25% transformer depth)
2. Runs a PyTorch Knowledge Distillation healing pass (KL-divergence on logits +
   cosine hidden-state alignment) on the seam layers to heal residual jumps.
3. Exports the healed checkpoint via safetensors for GGUF conversion & Vulkan benchmarking.
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
HEALED_OUT_DIR = str(ROOT_DIR / "Models" / "Qwen2.5-Coder-0.5B-L18-Healed")

# Optimal 18-layer subset discovered via ShortGPT BI + Greedy KL search
OPTIMAL_KEEP_18 = [0, 1, 2, 3, 4, 5, 6, 7, 8, 14, 15, 16, 17, 19, 20, 21, 22, 23]

CALIBRATION_TEXTS = [
    "<|im_start|>system\nYou are Qwen, created by Alibaba Cloud. You are a helpful assistant.<|im_end|>\n<|im_start|>user\nWrite a clean, optimized quicksort implementation in Python with comments.<|im_end|>\n<|im_start|>assistant\nCertainly! Below is a clean, optimized implementation of the Quicksort algorithm in Python, complete with comments explaining each part:\n\n```python\ndef quicksort(arr):\n    # Base case: if the array has 0 or 1 elements, it is already sorted\n    if len(arr) <= 1:\n        return arr\n    \n    # Choose the middle element as the pivot\n    pivot = arr[len(arr) // 2]\n    \n    # Partition the array into three sub-arrays\n    left = [x for x in arr if x < pivot]\n    middle = [x for x in arr if x == pivot]\n    right = [x for x in arr if x > pivot]\n    \n    # Recursively sort left and right, then combine\n    return quicksort(left) + middle + quicksort(right)\n```",
    "<|im_start|>system\nYou are Qwen, created by Alibaba Cloud. You are a helpful assistant.<|im_end|>\n<|im_start|>user\nOutput a valid JSON schema representing a user profile with id, username, email, roles, and settings.<|im_end|>\n<|im_start|>assistant\nCertainly! Below is a valid JSON schema representing a user profile:\n\n```json\n{\n  \"$schema\": \"http://json-schema.org/draft-07/schema#\",\n  \"title\": \"UserProfile\",\n  \"type\": \"object\",\n  \"properties\": {\n    \"id\": {\n      \"type\": \"integer\",\n      \"description\": \"Unique identifier for the user\"\n    },\n    \"username\": {\n      \"type\": \"string\"\n    },\n    \"email\": {\n      \"type\": \"string\",\n      \"format\": \"email\"\n    },\n    \"roles\": {\n      \"type\": \"array\",\n      \"items\": {\n        \"type\": \"string\"\n      }\n    },\n    \"settings\": {\n      \"type\": \"object\"\n    }\n  },\n  \"required\": [\"id\", \"username\", \"email\"]\n}\n```",
    "<|im_start|>system\nYou are Qwen, created by Alibaba Cloud. You are a helpful assistant.<|im_end|>\n<|im_start|>user\nExplain the architectural trade-offs between memory bandwidth and cache latency during autoregressive LLM decoding on modern GPUs.<|im_end|>\n<|im_start|>assistant\nDuring autoregressive LLM decoding, token generation is primarily memory-bandwidth bound because each forward pass requires loading all model weights from VRAM into compute units to generate a single token. High-speed SRAM caches like AMD Infinity Cache reduce latency and amplify effective bandwidth when active weights fit inside the cache.",
    "<|im_start|>system\nYou are Qwen, created by Alibaba Cloud. You are a helpful assistant.<|im_end|>\n<|im_start|>user\nWrite a Python function to implement binary search and merge sort.<|im_end|>\n<|im_start|>assistant\nCertainly! Here is an implementation of binary search in Python:\n\n```python\ndef binary_search(arr, target):\n    low, high = 0, len(arr) - 1\n    while low <= high:\n        mid = (low + high) // 2\n        if arr[mid] == target:\n            return mid\n        elif arr[mid] < target:\n            low = mid + 1\n        else:\n            high = mid - 1\n    return -1\n```"
]

def evaluate_agreement(model, teacher_batches):
    matches = 0
    total = 0
    kl_sum = 0.0
    with torch.no_grad():
        for input_ids, t_logits, t_top1 in teacher_batches:
            s_logits = model(input_ids=input_ids).logits
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

def save_healed_checkpoint(model, source_dir, output_dir, num_layers):
    os.makedirs(output_dir, exist_ok=True)
    model_bf16 = model.to(torch.bfloat16)
    state_dict = {}
    for k, v in model_bf16.state_dict().items():
        # Skip lm_head.weight if tie_word_embeddings is True (same as original safetensors)
        if k == "lm_head.weight":
            continue
        state_dict[k] = v.contiguous()

    out_safetensors = os.path.join(output_dir, "model.safetensors")
    save_file(state_dict, out_safetensors)

    with open(os.path.join(source_dir, "config.json"), "r", encoding="utf-8") as f:
        config = json.load(f)
    config["num_hidden_layers"] = num_layers
    if "layer_types" in config and isinstance(config["layer_types"], list):
        config["layer_types"] = config["layer_types"][:num_layers]
    if "max_window_layers" in config:
        config["max_window_layers"] = min(config["max_window_layers"], num_layers)

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
    print("=" * 76)
    print("6700XT-AFTERBURNER: OPTIMAL 18L SURGERY + KNOWLEDGE DISTILLATION HEALER")
    print("=" * 76)

    tokenizer = AutoTokenizer.from_pretrained(TEACHER_DIR)
    model = AutoModelForCausalLM.from_pretrained(TEACHER_DIR, dtype=torch.float32, device_map="cpu")
    model.eval()

    print("\n[Step 1] Caching 24-Layer Teacher Logits & Hidden States...")
    teacher_batches = []
    teacher_hidden = []
    with torch.no_grad():
        for text in CALIBRATION_TEXTS:
            inp = tokenizer(text, return_tensors="pt")["input_ids"]
            out = model(input_ids=inp, output_hidden_states=True)
            logits = out.logits.detach()
            top1 = logits.argmax(dim=-1).detach()
            teacher_batches.append((inp, logits, top1))
            teacher_hidden.append(out.hidden_states[-1].detach())

    orig_layers = list(model.model.layers)

    # Slice to Optimal 18-Layer Architecture
    model.model.layers = nn.ModuleList([copy.deepcopy(orig_layers[i]) for i in OPTIMAL_KEEP_18])
    pre_acc, pre_kl = evaluate_agreement(model, teacher_batches)
    print(f"\n[Step 2] Optimal 18-Layer Architecture (Dropped [9, 10, 11, 12, 13, 18]):")
    print(f"  Pre-Healing Top-1 Agreement: {pre_acc:.2f}% | KL Divergence: {pre_kl:.4f}")

    # Step 3: Knowledge Distillation Seam Healing
    # Only tune the seam layers around the cuts (layers 8, 9, 10, 13, 14 in new indexing + final norm)
    # to prevent overfitting while restoring exact residual alignment!
    print("\n[Step 3] Running Seam Knowledge Distillation Healing Pass (8 Epochs)...")
    seam_layers = {"layers.8.", "layers.9.", "layers.10.", "layers.13.", "layers.14.", "layers.17.", "model.norm"}
    trainable_params = []
    for name, param in model.model.named_parameters():
        if any(s in name for s in seam_layers) and any(k in name for k in ["norm", "o_proj", "down_proj"]):
            param.requires_grad = True
            trainable_params.append(param)
        else:
            param.requires_grad = False

    optimizer = torch.optim.AdamW(trainable_params, lr=5e-5, weight_decay=0.01)
    num_epochs = 8

    model.train()
    for epoch in range(1, num_epochs + 1):
        epoch_loss = 0.0
        for idx, (input_ids, t_logits, _) in enumerate(teacher_batches):
            optimizer.zero_grad()
            out = model(input_ids=input_ids, output_hidden_states=True)
            s_logits = out.logits
            s_hidden = out.hidden_states[-1]
            t_hid = teacher_hidden[idx]

            T = 1.5
            top_v, top_idx = torch.topk(t_logits, k=128, dim=-1)
            s_top_v = torch.gather(s_logits, -1, top_idx)
            t_prob = F.softmax(top_v / T, dim=-1)
            s_log_prob = F.log_softmax(s_top_v / T, dim=-1)
            kl_loss = F.kl_div(s_log_prob, t_prob, reduction="batchmean") * (T * T)

            cos_loss = (1.0 - F.cosine_similarity(s_hidden, t_hid, dim=-1)).mean()
            mse_loss = F.mse_loss(s_hidden, t_hid)

            loss = kl_loss + 2.0 * cos_loss + 0.05 * mse_loss
            loss.backward()
            torch.nn.utils.clip_grad_norm_(trainable_params, 1.0)
            optimizer.step()
            epoch_loss += loss.item()

        if epoch % 2 == 0 or epoch == 1:
            model.eval()
            cur_acc, cur_kl = evaluate_agreement(model, teacher_batches)
            print(f"  Epoch {epoch:2d}/{num_epochs} | Loss: {epoch_loss/len(teacher_batches):.4f} | Top-1 Agreement: {cur_acc:6.2f}% | KL: {cur_kl:.4f}")
            model.train()

    model.eval()
    post_acc, post_kl = evaluate_agreement(model, teacher_batches)
    print("\n" + "=" * 76)
    print(f"HEALING COMPLETE in {time.time() - t0:.1f}s!")
    print(f"  Greedy 18L Pre-Heal Agreement:  {pre_acc:6.2f}% (KL: {pre_kl:.4f})")
    print(f"  Healed 18L Post-Heal Agreement: {post_acc:6.2f}% (KL: {post_kl:.4f})")
    print("=" * 76)

    print(f"\n[Step 4] Exporting Healed 18L Safetensors to {HEALED_OUT_DIR}...")
    save_healed_checkpoint(model, TEACHER_DIR, HEALED_OUT_DIR, len(OPTIMAL_KEEP_18))
    print("Saved successfully!")

if __name__ == "__main__":
    main()
