#!/usr/bin/env python3
"""
llm_bridge_mcp.py - MCP (Model Context Protocol) Bridge for Antigravity
Exposes OpenRouter API and Local Vulkan LLM (llama-server) as native tools in Antigravity.
Zero external dependencies (uses standard Python library).
"""

import sys
import os
import json
import urllib.request
import urllib.error
from pathlib import Path

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_OPENROUTER_MODEL = "openrouter/auto"
DEFAULT_LOCAL_URL = os.environ.get("LOCAL_LLM_URL", "http://127.0.0.1:8080/v1")
LOCAL_TOKEN_LOG = os.environ.get(
    "LOCAL_TOKEN_LOG",
    str(Path.home() / ".gemini" / "antigravity" / "scratch" / "endo" / "MEMORY" / "local_token_log.jsonl"),
)


def log_usage(caller, usage):
    """Append local token usage to the savings audit log."""
    try:
        import datetime
        entry = {
            "ts": datetime.datetime.now().isoformat(),
            "model": "granite-4.0-h-tiny-q6_k (local)",
            "caller": caller,
            "prompt_tokens": int((usage or {}).get("prompt_tokens", 0) or 0),
            "completion_tokens": int((usage or {}).get("completion_tokens", 0) or 0),
            "total_tokens": int((usage or {}).get("total_tokens", 0) or 0),
        }
        os.makedirs(os.path.dirname(LOCAL_TOKEN_LOG), exist_ok=True)
        with open(LOCAL_TOKEN_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass

def log(msg):
    sys.stderr.write(f"[llm-bridge] {msg}\n")
    sys.stderr.flush()

def call_openrouter(prompt: str, model: str = None, system_prompt: str = None, temperature: float = 0.7) -> str:
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        return "Error: OPENROUTER_API_KEY environment variable is not configured. Please set your OpenRouter API key."
    
    target_model = model.strip() if model else DEFAULT_OPENROUTER_MODEL
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": target_model,
        "messages": messages,
        "temperature": temperature
    }

    req = urllib.request.Request(
        OPENROUTER_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://antigravity.google",
            "X-Title": "Antigravity LLM Bridge"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        return f"OpenRouter HTTP {e.code} Error: {err_body}"
    except Exception as e:
        return f"OpenRouter Error: {str(e)}"

def call_local_llm(prompt: str, system_prompt: str = None, temperature: float = 0.7) -> str:
    endpoint = f"{DEFAULT_LOCAL_URL.rstrip('/')}/chat/completions"
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "messages": messages,
        "temperature": temperature
    }

    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            msg = data["choices"][0]["message"]
            content = msg.get("content") or ""
            reasoning = msg.get("reasoning_content") or ""
            log_usage("llm_bridge_mcp (Antigravity)", data.get("usage", {}))
            if reasoning and content:
                return f"<think>\n{reasoning.strip()}\n</think>\n\n{content.strip()}"
            elif reasoning and not content:
                return f"<think>\n{reasoning.strip()}\n</think>"
            return content
    except urllib.error.URLError:
        return (
            f"Cannot connect to local LLM server at {endpoint}. "
            "Please ensure llama-server or LM Studio is running on http://127.0.0.1:8080."
        )
    except Exception as e:
        return f"Local LLM Error: {str(e)}"

def check_local_status() -> str:
    endpoint = f"{DEFAULT_LOCAL_URL.rstrip('/')}/models"
    req = urllib.request.Request(endpoint, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = [m.get("id", "unknown") for m in data.get("data", [])]
            return f"Local LLM Server Online at {DEFAULT_LOCAL_URL}. Loaded models: {', '.join(models) if models else 'default'}"
    except Exception as e:
        return f"Local LLM Server Offline ({endpoint}): {str(e)}"


def call_live_memory(query: str, k: int = 6, use_embeddings: bool = False) -> str:
    """Run live_memory.py and return its output (retrieval + grounded answer)."""
    import subprocess
    script = os.environ.get(
        "LIVE_MEMORY_SCRIPT",
        str(Path.home() / ".gemini" / "antigravity" / "scratch" / "endo" / "SCRIPTS" / "live_memory.py"),
    )
    cmd = [sys.executable, script, query, "--k", str(k)]
    if use_embeddings:
        cmd.append("--embed")
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=180, encoding="utf-8", errors="replace")
        out = (res.stdout or "").strip()
        err = (res.stderr or "").strip()
        if res.returncode != 0:
            return f"live_memory error (exit {res.returncode}): {err or out}"
        return out if out else (err or "(no output)")
    except Exception as e:
        return f"live_memory error: {str(e)}"

TOOLS = [
    {
        "name": "openrouter_chat",
        "description": "Send a prompt to OpenRouter to query models like claude-3.5-sonnet, deepseek-r1, llama-3.3-70b, or qwen without consuming Antigravity token quota.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "The prompt or question."},
                "model": {"type": "string", "description": "OpenRouter model identifier (e.g. 'deepseek/deepseek-chat', 'anthropic/claude-3.5-sonnet', 'meta-llama/llama-3.3-70b-instruct'). Defaults to deepseek-chat."},
                "system_prompt": {"type": "string", "description": "Optional system guidance."},
                "temperature": {"type": "number", "description": "Temperature between 0.0 and 1.0 (default 0.7)."}
            },
            "required": ["prompt"]
        }
    },
    {
        "name": "local_llm_chat",
        "description": "Send a prompt to the local LLM running on your RX 6700 XT GPU via Vulkan (llama-server on localhost:8080). Completely local and zero cloud tokens.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "The prompt or coding task for the local model."},
                "system_prompt": {"type": "string", "description": "Optional system guidance."},
                "temperature": {"type": "number", "description": "Temperature between 0.0 and 1.0 (default 0.7)."}
            },
            "required": ["prompt"]
        }
    },
    {
        "name": "local_llm_status",
        "description": "Check if the local Vulkan llama-server is running on localhost:8080 and report loaded models.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "live_memory_query",
        "description": "Query the local ENDO knowledge-base memory (1857 normalized records) and get a grounded answer from the local Granite LLM. Retrieval + generation run entirely on-prem (zero cloud tokens). Use for fast history/context lookup instead of stuffing everything into the prompt.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The question or search query."},
                "k": {"type": "integer", "description": "Number of records to retrieve (default 6)."},
                "use_embeddings": {"type": "boolean", "description": "Re-rank with RX 570 embeddings for semantic search (default false)."}
            },
            "required": ["query"]
        }
    }
]
def handle_message(msg):
    method = msg.get("method")
    req_id = msg.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "llm-bridge",
                    "version": "1.0.0"
                }
            }
        }
    elif method == "notifications/initialized":
        return None
    elif method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}
    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": TOOLS
            }
        }
    elif method == "tools/call":
        params = msg.get("params", {})
        tool_name = params.get("name")
        args = params.get("arguments", {})

        if tool_name == "openrouter_chat":
            prompt = args.get("prompt", "")
            model = args.get("model")
            sys_p = args.get("system_prompt")
            temp = float(args.get("temperature", 0.7))
            result_text = call_openrouter(prompt, model, sys_p, temp)
        elif tool_name == "local_llm_chat":
            prompt = args.get("prompt", "")
            sys_p = args.get("system_prompt")
            temp = float(args.get("temperature", 0.7))
            result_text = call_local_llm(prompt, sys_p, temp)
        elif tool_name == "local_llm_status":
            result_text = check_local_status()
        elif tool_name == "live_memory_query":
            query = args.get("query", "")
            k = int(args.get("k", 6) or 6)
            use_emb = bool(args.get("use_embeddings", False))
            result_text = call_live_memory(query, k, use_emb)
        else:
            result_text = f"Unknown tool: {tool_name}"

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": result_text
                    }
                ]
            }
        }
    else:
        if req_id is not None:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }
        return None

def main():
    log("Server started in stdio mode.")
    for line in sys.stdin:
        line = line.strip().lstrip('\ufeff')
        if not line:
            continue
        try:
            req = json.loads(line)
            res = handle_message(req)
            if res is not None:
                out = json.dumps(res) + "\n"
                sys.stdout.write(out)
                sys.stdout.flush()
        except Exception as e:
            log(f"Error processing line: {e}")

if __name__ == "__main__":
    main()
