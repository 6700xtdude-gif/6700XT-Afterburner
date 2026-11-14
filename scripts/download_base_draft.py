#!/usr/bin/env python3
r"""
download_base_draft.py - Downloads Qwen2.5-Coder-0.5B-Instruct for 6700XT-Afterburner.
Target: Models/Qwen2.5-Coder-0.5B-Instruct
"""
import os
from pathlib import Path
from huggingface_hub import snapshot_download

ROOT_DIR = Path(__file__).resolve().parent.parent
REPO_ID = "Qwen/Qwen2.5-Coder-0.5B-Instruct"
LOCAL_DIR = str(ROOT_DIR / "Models" / "Qwen2.5-Coder-0.5B-Instruct")

def main():
    print(f"Downloading {REPO_ID} to {LOCAL_DIR}...")
    os.makedirs(LOCAL_DIR, exist_ok=True)
    snapshot_download(
        repo_id=REPO_ID,
        local_dir=LOCAL_DIR,
        local_dir_use_symlinks=False,
        ignore_patterns=["*.msgpack", "*.h5", "*.ot"]
    )
    print("Download completed successfully!")

if __name__ == "__main__":
    main()
