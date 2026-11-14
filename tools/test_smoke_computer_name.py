#!/usr/bin/env python3
import json
import subprocess
import urllib.request

ENDPOINT = "http://127.0.0.1:8080/v1/chat/completions"

# Turn 1: Ask the question with tool declaration
payload1 = {
    "model": "qwen3.8-27b",
    "messages": [
        {"role": "system", "content": "You are a local assistant on this Windows machine with access to powershell tools to inspect system information."},
        {"role": "user", "content": "What is the name of this computer?"}
    ],
    "tools": [{
        "type": "function",
        "function": {
            "name": "run_powershell",
            "description": "Execute a PowerShell command to inspect the system",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"]
            }
        }
    }],
    "temperature": 0.0
}

req1 = urllib.request.Request(ENDPOINT, data=json.dumps(payload1).encode("utf-8"), headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req1) as resp:
    res1 = json.loads(resp.read().decode("utf-8"))

msg1 = res1["choices"][0]["message"]
tool_call = msg1["tool_calls"][0]
tool_args = json.loads(tool_call["function"]["arguments"])
cmd = tool_args["command"]
call_id = tool_call["id"]

# Execute tool
proc = subprocess.run(["powershell.exe", "-NoProfile", "-Command", cmd], capture_output=True, text=True)
tool_output = proc.stdout.strip()

# Turn 2: Feed back tool result
messages2 = list(payload1["messages"])
messages2.append(msg1)
messages2.append({
    "role": "tool",
    "tool_call_id": call_id,
    "content": tool_output
})

payload2 = {
    "model": "qwen3.8-27b",
    "messages": messages2,
    "temperature": 0.0
}

req2 = urllib.request.Request(ENDPOINT, data=json.dumps(payload2).encode("utf-8"), headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req2) as resp:
    res2 = json.loads(resp.read().decode("utf-8"))

msg2 = res2["choices"][0]["message"]
print(json.dumps({
    "turn1_reasoning": msg1.get("reasoning_content"),
    "tool_executed": f"{tool_call['function']['name']}(command={cmd!r})",
    "tool_output": tool_output,
    "turn2_reasoning": msg2.get("reasoning_content"),
    "final_content": msg2.get("content")
}, indent=2))
