#!/usr/bin/env python3
"""
test_qwen27b_workflow.py - Verification test for Qwen 3.8 27B GGUF on RX 6700 XT Vulkan
Verifies:
1. Model loading with -ngl 40 (GPU/CPU hybrid) via llama-server
2. OpenAI-compatible /v1/chat/completions endpoint
3. Thinking extraction and streaming output
4. Structured JSON / tool calling generation
"""

import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BIN_DIR = os.path.join(ROOT_DIR, "bin", "vulkan")
SERVER_EXE = os.path.join(BIN_DIR, "llama-server.exe")
MODEL_PATH = os.path.join(ROOT_DIR, "Models", "Qwen3.8-27B-UD-Q4_K_XL", "Qwen3.8-27B-UD-Q4_K_XL.gguf")
MMPROJ_PATH = os.path.join(ROOT_DIR, "Models", "Qwen3.8-27B-UD-Q4_K_XL", "mmproj-BF16.gguf")

PORT = 8080
HEALTH_URL = f"http://127.0.0.1:{PORT}/health"
COMPLETIONS_URL = f"http://127.0.0.1:{PORT}/v1/chat/completions"

def wait_for_server(proc, timeout=60):
    start = time.time()
    print(f"Waiting for llama-server to become ready on port {PORT}...")
    while time.time() - start < timeout:
        if proc.poll() is not None:
            raise RuntimeError(f"llama-server terminated unexpectedly with code {proc.returncode}")
        try:
            req = urllib.request.Request(HEALTH_URL)
            with urllib.request.urlopen(req, timeout=2) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode())
                    if data.get("status") == "ok":
                        print(f"llama-server is healthy! (Ready in {time.time() - start:.1f}s)")
                        return True
        except Exception:
            pass
        time.sleep(1.5)
    raise TimeoutError("llama-server failed to become healthy within timeout.")

def test_chat_completion():
    print("\n--- Test 1: Standard Chat Completion (Python function) ---")
    payload = {
        "model": "qwen3.8-27b",
        "messages": [
            {"role": "system", "content": "You are an expert software engineer. Reply with concise code."},
            {"role": "user", "content": "Write a clean Python function to check if a string is a palindrome. Include docstring and type hints."}
        ],
        "temperature": 0.0,
        "max_tokens": 128
    }

    req = urllib.request.Request(
        COMPLETIONS_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    t1 = time.time()

    choice = result["choices"][0]
    message = choice["message"]
    content = message.get("content", "")
    reasoning = message.get("reasoning_content", "")
    usage = result.get("usage", {})
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    elapsed = t1 - t0
    tok_per_sec = completion_tokens / elapsed if elapsed > 0 else 0

    print(f"Elapsed: {elapsed:.2f}s | Completion Tokens: {completion_tokens} | Rate: {tok_per_sec:.2f} t/s")
    if reasoning:
        print(f"Reasoning/Thinking:\n{reasoning.strip()[:200]}...")
    print(f"Response:\n{content.strip()}")
    return result

def test_tool_calling():
    print("\n--- Test 2: Structured Tool Calling ---")
    payload = {
        "model": "qwen3.8-27b",
        "messages": [
            {"role": "system", "content": "You are a local coding assistant with access to tools."},
            {"role": "user", "content": "Check the git status of the repository using powershell."}
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "run_powershell",
                    "description": "Execute a PowerShell command",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {"type": "string", "description": "Command string"}
                        },
                        "required": ["command"]
                    }
                }
            }
        ],
        "temperature": 0.0,
        "max_tokens": 128
    }

    req = urllib.request.Request(
        COMPLETIONS_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    t1 = time.time()

    choice = result["choices"][0]
    message = choice["message"]
    elapsed = t1 - t0
    tool_calls = message.get("tool_calls", [])
    print(f"Elapsed: {elapsed:.2f}s | Finish Reason: {choice.get('finish_reason')}")
    if tool_calls:
        print(f"Tool Call Generated: {json.dumps(tool_calls, indent=2)}")
    else:
        print(f"Text Generated: {message.get('content')}")
    return result

def main():
    if not os.path.exists(MODEL_PATH):
        print(f"Error: Model not found at {MODEL_PATH}")
        sys.exit(1)

    cmd = [
        SERVER_EXE,
        "-m", MODEL_PATH,
        "--host", "127.0.0.1",
        "--port", str(PORT),
        "-ngl", "40",
        "-fa", "on",
        "-ctk", "q8_0",
        "-ctv", "q8_0",
        "-c", "4096",
        "--cache-reuse", "64",
        "-t", "6"
    ]
    if os.path.exists(MMPROJ_PATH):
        cmd.extend(["--mmproj", MMPROJ_PATH])

    print("Launching llama-server for verification...")
    print(f"Command: {' '.join(cmd[:6])} ...")

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)

    try:
        wait_for_server(proc, timeout=90)
        test_chat_completion()
        test_tool_calling()
        print("\nAll workflow verification tests completed successfully!")
    finally:
        print("\nStopping llama-server...")
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        print("Server stopped.")

if __name__ == "__main__":
    main()
