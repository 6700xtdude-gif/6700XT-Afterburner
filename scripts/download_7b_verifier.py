#!/usr/bin/env python3
r"""
download_7b_verifier.py - Download Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf
Target: Models/Qwen2.5-Coder-7B-Instruct-GGUF
"""
import os
from pathlib import Path
from huggingface_hub import hf_hub_download

ROOT_DIR = Path(__file__).resolve().parent.parent
REPO_ID = "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF"
FILENAME = "qwen2.5-coder-7b-instruct-q4_k_m.gguf"
LOCAL_DIR = str(ROOT_DIR / "Models" / "Qwen2.5-Coder-7B-Instruct-GGUF")

def main():
    print(f"Downloading {FILENAME} from {REPO_ID} to {LOCAL_DIR}...")
    os.makedirs(LOCAL_DIR, exist_ok=True)
    file_path = hf_hub_download(
        repo_id=REPO_ID,
        filename=FILENAME,
        local_dir=LOCAL_DIR
    )
    print(f"Downloaded successfully to: {file_path}")

if __name__ == "__main__":
    main()
