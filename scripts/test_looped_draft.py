#!/usr/bin/env python3
"""
test_looped_draft.py - Dory-Style Latent-Recurrent Layer Looping for the 96 MB Infinity Cache Model
Tests whether looping a middle recurrent block (like NVIDIA Dory1.0-4B) on our 14-layer
96 MB Infinity Cache architecture (14 physical layers -> 19 effective layers via 2x middle loop
with gated residual/input re-injection + Seam/Loop Knowledge Distillation) beats a standard
linear 14-layer model with the exact same 86 MB weight footprint!
"""
import copy
from pathlib import Path
import torch
import torch.nn as nn
import torch.nn.functional as F
from transformers import AutoModelForCausalLM, AutoTokenizer

ROOT_DIR = Path(__file__).resolve().parent.parent
TEACHER_DIR = str(ROOT_DIR / "Models" / "Qwen2.5-Coder-0.5B-Instruct")

# 14 optimal physical layers (fits in <90 MB at Q2_0 inside 96 MB Infinity Cache)
KEEP_14 = [0, 1, 2, 3, 4, 5, 6, 7, 15, 16, 17, 20, 22, 23]

CALIBRATION_TEXTS = [
    "<|im_start|>system\nYou are Qwen, created by Alibaba Cloud. You are a helpful assistant.<|im_end|>\n<|im_start|>user\nWrite a clean, optimized quicksort implementation in Python with comments.<|im_end|>\n<|im_start|>assistant\nCertainly! Below is a clean, optimized implementation of the Quicksort algorithm in Python, complete with comments explaining each part:\n\n```python\ndef quicksort(arr):\n    # Base case: if the array has 0 or 1 elements, it is already sorted\n    if len(arr) <= 1:\n        return arr\n    \n    # Choose the middle element as the pivot\n    pivot = arr[len(arr) // 2]\n    \n    # Partition the array into three sub-arrays\n    left = [x for x in arr if x < pivot]\n    middle = [x for x in arr if x == pivot]\n    right = [x for x in arr if x > pivot]\n    \n    # Recursively sort left and right, then combine\n    return quicksort(left) + middle + quicksort(right)\n```",
    "<|im_start|>system\nYou are Qwen, created by Alibaba Cloud. You are a helpful assistant.<|im_end|>\n<|im_start|>user\nOutput a valid JSON schema representing a user profile with id, username, email, roles, and settings.<|im_end|>\n<|im_start|>assistant\nCertainly! Below is a valid JSON schema representing a user profile:\n\n```json\n{\n  \"$schema\": \"http://json-schema.org/draft-07/schema#\",\n  \"title\": \"UserProfile\",\n  \"type\": \"object\",\n  \"properties\": {\n    \"id\": {\n      \"type\": \"integer\",\n      \"description\": \"Unique identifier for the user\"\n    },\n    \"username\": {\n      \"type\": \"string\"\n    },\n    \"email\": {\n      \"type\": \"string\",\n      \"format\": \"email\"\n    },\n    \"roles\": {\n      \"type\": \"array\",\n      \"items\": {\n        \"type\": \"string\"\n      }\n    },\n    \"settings\": {\n      \"type\": \"object\"\n    }\n  },\n  \"required\": [\"id\", \"username\", \"email\"]\n}\n```",
    "<|im_start|>system\nYou are Qwen, created by Alibaba Cloud. You are a helpful assistant.<|im_end|>\n<|im_start|>user\nWrite a Python function to implement binary search and merge sort.<|im_end|>\n<|im_start|>assistant\nCertainly! Here is an implementation of binary search in Python:\n\n```python\ndef binary_search(arr, target):\n    low, high = 0, len(arr) - 1\n    while low <= high:\n        mid = (low + high) // 2\n        if arr[mid] == target:\n            return mid\n        elif arr[mid] < target:\n            low = mid + 1\n        else:\n            high = mid - 1\n    return -1\n```"
]

class AnchorCaptureLayer(nn.Module):
    """Wraps the first layer of Pass 1 to capture the input anchor state (like NVIDIA Dory)."""
    def __init__(self, shared_layer, state_holder):
        super().__init__()
        self.shared_layer = shared_layer
        self.state_holder = state_holder
        if hasattr(shared_layer, "attention_type"):
            self.attention_type = shared_layer.attention_type

    def forward(self, hidden_states, *args, **kwargs):
        self.state_holder["anchor"] = hidden_states
        return self.shared_layer(hidden_states, *args, **kwargs)

class DoryReinjectLayer(nn.Module):
    """Wraps the first layer of Pass 2 to blend Pass 1 output with the input anchor before re-running shared weights."""
    def __init__(self, shared_layer, state_holder, hidden_size, norm_template):
        super().__init__()
        self.shared_layer = shared_layer
        self.state_holder = state_holder
        self.loop_alpha = nn.Parameter(torch.full((1, 1, hidden_size), 0.5))
        self.loop_norm = copy.deepcopy(norm_template)
        if hasattr(shared_layer, "attention_type"):
            self.attention_type = shared_layer.attention_type

    def forward(self, hidden_states, *args, **kwargs):
        anchor = self.state_holder["anchor"]
        alpha = torch.sigmoid(self.loop_alpha)
        blended = (1.0 - alpha) * anchor + alpha * self.loop_norm(hidden_states)
        return self.shared_layer(blended, *args, **kwargs)

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

def train_distill(model, params, teacher_batches, epochs=8):
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
            loss = kl_loss + 2.0 * cos_loss
            loss.backward()
            torch.nn.utils.clip_grad_norm_(params, 1.0)
            opt.step()
    model.eval()

def main():
    print("=" * 80)
    print("6700XT-AFTERBURNER: DORY-STYLE LAYER LOOPING EXPERIMENT (96 MB L3 BUDGET)")
    print("Physical Budget: 14 Layers (~86 MB in Q2_0) | Looped Effective Depth: 19 Layers")
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

    # 1. Standard Linear 14L Model (No Looping)
    linear_14l = copy.deepcopy(teacher)
    linear_14l.model.layers = nn.ModuleList([copy.deepcopy(orig_layers[i]) for i in KEEP_14])
    pre_lin_acc, pre_lin_kl = eval_metrics(linear_14l, teacher_batches)
    print(f"[1] Linear 14L (Pre-Heal, 14 Pass):          Top-1 Acc = {pre_lin_acc:6.2f}% | KL = {pre_lin_kl:.4f}")

    lin_params = [p for n, p in linear_14l.model.named_parameters() if any(k in n for k in ["norm", "o_proj", "down_proj"])]
    for p in linear_14l.parameters():
        p.requires_grad = False
    for p in lin_params:
        p.requires_grad = True
    train_distill(linear_14l, lin_params, teacher_batches, epochs=8)
    post_lin_acc, post_lin_kl = eval_metrics(linear_14l, teacher_batches)
    print(f"[2] Linear 14L (Healed, 14 Pass):            Top-1 Acc = {post_lin_acc:6.2f}% | KL = {post_lin_kl:.4f}")

    # 2. Dory-Style Looped 14L Model (14 Physical Layers, Layers 5..9 Looped 2x = 19 Effective Layers!)
    looped_model = copy.deepcopy(teacher)
    phys_14 = [copy.deepcopy(orig_layers[i]) for i in KEEP_14]
    state_holder = {}
    # Build 19-step execution schedule using ONLY the 14 physical layer weight objects:
    # Input (0..4) + Recurrent Pass 1 (5..9) + Recurrent Pass 2 (5..9, shared weights!) + Output (10..13)
    loop_schedule = (
        phys_14[0:5]
        + [AnchorCaptureLayer(phys_14[5], state_holder)]
        + phys_14[6:10]
        + [DoryReinjectLayer(phys_14[5], state_holder, looped_model.config.hidden_size, looped_model.model.norm)]
        + phys_14[6:10]
        + phys_14[10:14]
    )
    looped_model.model.layers = nn.ModuleList(loop_schedule)
    looped_model.config.num_hidden_layers = len(loop_schedule)
    if hasattr(looped_model.config, "layer_types") and isinstance(looped_model.config.layer_types, list):
        looped_model.config.layer_types = ["full_attention"] * len(loop_schedule)

    # Verify unique parameter count is identical (+3.5 KB for loop_alpha/loop_norm)
    unique_params_linear = sum(p.numel() for p in set(linear_14l.parameters()))
    unique_params_looped = sum(p.numel() for p in set(looped_model.parameters()))
    print(f"\n    -> Unique Physical Params: Linear 14L = {unique_params_linear:,} | Dory-Looped 14L = {unique_params_looped:,}")

    for p in looped_model.parameters():
        p.requires_grad = False
    dory_params = []
    for n, p in looped_model.model.named_parameters():
        if any(k in n for k in ["loop_alpha", "loop_norm", "norm", "o_proj", "down_proj"]):
            p.requires_grad = True
            if all(p is not existing for existing in dory_params):
                dory_params.append(p)

    train_distill(looped_model, dory_params, teacher_batches, epochs=8)
    post_dory_acc, post_dory_kl = eval_metrics(looped_model, teacher_batches)
    print(f"[3] Dory-Looped 14L (Healed, 19 Eff Pass):   Top-1 Acc = {post_dory_acc:6.2f}% | KL = {post_dory_kl:.4f}")

if __name__ == "__main__":
    main()
