#!/usr/bin/env python3
"""
test_local_tool_calling.py - Agentic Tool Call Loop Verification for Local LLM on RX 6700 XT
Tests whether Qwen 35B-A3B running on llama-server can:
1. Receive tool declarations (run_powershell, read_file).
2. Autonomous decide to invoke a tool.
3. Process tool execution output.
4. Formulate the final answer.
"""

import json
import subprocess
import urllib.request
import urllib.error

ENDPOINT = "http://127.0.0.1:8080/v1/chat/completions"

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_powershell",
            "description": "Execute a Windows PowerShell command and return standard output and error.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The exact PowerShell command line to execute."
                    }
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the text content of a file on the local filesystem.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path to the file."
                    }
                },
                "required": ["path"]
            }
        }
    }
]

def execute_tool(name, args):
    print(f"\n[HARNESS EXECUTING TOOL] {name} with args: {args}")
    if name == "run_powershell":
        cmd = args.get("command", "")
        proc = subprocess.run(["powershell.exe", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=30)
        out = (proc.stdout + "\n" + proc.stderr).strip()
        print(f"[HARNESS TOOL OUTPUT]\n{out[:500]}...")
        return out
    elif name == "read_file":
        path = args.get("path", "")
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(2000)
                print(f"[HARNESS TOOL OUTPUT]\n{content[:300]}...")
                return content
        except Exception as e:
            return f"Error reading file: {e}"
    return f"Unknown tool: {name}"

def send_chat(messages, tools=None, temperature=0.7, top_p=0.95, min_p=0.05, seed=42):
    payload = {
        "messages": messages,
        "temperature": temperature,
        "top_p": top_p,
        "min_p": min_p,
        "seed": seed
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read().decode("utf-8"))

def main():
    print("=" * 60)
    print("Starting Agentic Tool Call Test with Local Model on RX 6700 XT")
    print("Endpoint:", ENDPOINT)
    print("=" * 60)

    from pathlib import Path
    root_dir = str(Path(__file__).resolve().parent.parent)
    prompt = (
        "You are an AI assistant running locally on Windows with full tool execution access. "
        f"Use your run_powershell tool to check the contents of {root_dir}, "
        "and tell me what directories exist there."
    )

    messages = [
        {"role": "system", "content": "You are a helpful coding and system administration agent with access to PowerShell tools."},
        {"role": "user", "content": prompt}
    ]

    print("\n[Step 1] Sending prompt to local model...")
    res = send_chat(messages, tools=TOOLS)
    choice = res["choices"][0]
    msg = choice["message"]

    print("\n[Step 2] Model Response:")
    print("Content:", msg.get("content"))
    tool_calls = msg.get("tool_calls", [])
    
    # Parse XML-style tool calls if raw tool_calls array is empty
    if not tool_calls and msg.get("content"):
        import re
        content = msg["content"]
        
        # Pattern 1: <function name="..."><arguments><command>...</command></arguments></function>
        fn_match = re.search(r'<function name="([^"]+)">\s*<arguments>(.*?)</arguments>\s*</function>', content, re.DOTALL)
        if fn_match:
            fname = fn_match.group(1).strip()
            arg_str = fn_match.group(2).strip()
            # Extract child tags as dict
            args = {}
            for tag_match in re.finditer(r'<([^>]+)>(.*?)</\1>', arg_str, re.DOTALL):
                args[tag_match.group(1)] = tag_match.group(2).strip()
            tool_calls = [{"id": "call_xml_0", "function": {"name": fname, "arguments": args}}]
        
        # Pattern 2: <tool_call>\n{"name": ..., "arguments": ...}\n</tool_call>
        tc_match = re.search(r'<tool_call>\s*(\{.*?\})\s*</tool_call>', content, re.DOTALL)
        if tc_match:
            try:
                tc_data = json.loads(tc_match.group(1))
                tool_calls = [{"id": "call_xml_1", "function": tc_data}]
            except Exception:
                pass

    print("Tool Calls Detected:", len(tool_calls))

    if not tool_calls:
        print("Warning: Model did not emit tool_calls structure. Raw message:")
        print(json.dumps(msg, indent=2))
        return

    messages.append(msg)

    # Process each tool call
    for tc in tool_calls:
        func = tc["function"]
        fname = func["name"]
        fargs = json.loads(func["arguments"]) if isinstance(func["arguments"], str) else func["arguments"]
        tool_res = execute_tool(fname, fargs)

        messages.append({
            "role": "tool",
            "tool_call_id": tc["id"],
            "name": fname,
            "content": tool_res
        })

    print("\n[Step 3] Sending tool execution results back to local model for final synthesis...")
    final_res = send_chat(messages, tools=TOOLS)
    final_msg = final_res["choices"][0]["message"]

    print("\n" + "=" * 60)
    print("FINAL MODEL SYNTHESIS:")
    print("=" * 60)
    print(final_msg.get("content"))

if __name__ == "__main__":
    main()
