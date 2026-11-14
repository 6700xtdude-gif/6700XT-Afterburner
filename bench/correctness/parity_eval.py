#!/usr/bin/env python3
"""Correctness, Format Adherence, and Syntax Parity Verifier for Strata.

Modeled after Robert Karl's check-batch and parity evaluation harnesses.
Verifies:
1. Syntax validity (e.g. Python code must parse via ast.parse without SyntaxError)
2. Schema / Format validity (e.g. JSON agent prompt must decode via json.loads)
3. Speculative acceptance fidelity (draft_n_accepted / draft_n)
4. Determinism at temperature 0.0
"""

import argparse
import ast
import json
import os
import sys
import time
import urllib.request


def query_server(endpoint, prompt, max_tokens, temperature=0.0):
    url = f"{endpoint.rstrip('/')}/chat/completions"
    payload = {
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.loads(resp.read().decode("utf-8"))


def evaluate_parity(endpoint="http://127.0.0.1:8080/v1"):
    print(f"=== Running Strata Correctness & Parity Suite on {endpoint} ===\n")
    results = []

    # 1. Determinism Test
    print("[Test 1/4] Checking Determinism at temp=0.0...")
    prompt_det = "Output exactly the first 10 Fibonacci numbers as a comma-separated list."
    res1 = query_server(endpoint, prompt_det, max_tokens=64, temperature=0.0)
    res2 = query_server(endpoint, prompt_det, max_tokens=64, temperature=0.0)

    txt1 = res1.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    txt2 = res2.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    
    # If reasoning model, extract content or reasoning
    if not txt1:
        txt1 = res1.get("choices", [{}])[0].get("message", {}).get("reasoning_content", "").strip()
        txt2 = res2.get("choices", [{}])[0].get("message", {}).get("reasoning_content", "").strip()

    is_deterministic = (txt1 == txt2)
    print(f"  Result: {'PASSED' if is_deterministic else 'FAILED'} (Outputs match byte-for-byte: {is_deterministic})")
    results.append({"test": "determinism", "passed": is_deterministic})

    # 2. JSON Schema Adherence Test
    print("\n[Test 2/4] Checking JSON Schema & Syntax Integrity...")
    prompt_json = "Return only a JSON object with keys 'system', 'status', 'tokens_per_second' (number), 'speculative' (boolean). No markdown fence."
    res_json = query_server(endpoint, prompt_json, max_tokens=512, temperature=0.0)
    json_txt = res_json.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    if not json_txt:
        json_txt = res_json.get("choices", [{}])[0].get("message", {}).get("reasoning_content", "").strip()

    parsed = None
    required_keys = {"system", "status", "tokens_per_second", "speculative"}
    
    # Try parsing directly or finding any valid JSON dictionary within the text
    cleaned_json = json_txt
    if "{" in json_txt and "}" in json_txt:
        # Search for valid JSON dict candidates in the string
        start = json_txt.find("{")
        while start != -1:
            end = json_txt.rfind("}")
            while end > start:
                try:
                    candidate = json.loads(json_txt[start:end+1])
                    if isinstance(candidate, dict) and required_keys.issubset(candidate.keys()):
                        parsed = candidate
                        cleaned_json = json_txt[start:end+1]
                        break
                except Exception:
                    pass
                end = json_txt.rfind("}", 0, end)
            if parsed is not None:
                break
            start = json_txt.find("{", start + 1)

    json_valid = False
    if parsed is not None:
        json_valid = True
    else:
        try:
            parsed = json.loads(cleaned_json)
            json_valid = required_keys.issubset(parsed.keys())
        except Exception as e:
            print(f"    [DEBUG JSON Parse Error] {e} | Raw text: {repr(cleaned_json[:200])}")
            json_valid = False

    print(f"  Result: {'PASSED' if json_valid else 'FAILED'} (Valid JSON with required keys: {json_valid})")
    results.append({"test": "json_schema", "passed": json_valid})

    # 3. Code Generation AST Validation
    print("\n[Test 3/4] Checking Python AST Parse Validity...")
    prompt_code = "Write a Python 3 function `fast_dot_product(a: list[float], b: list[float]) -> float` that computes the vector dot product. Return only Python code."
    res_code = query_server(endpoint, prompt_code, max_tokens=768, temperature=0.0)
    msg = res_code.get("choices", [{}])[0].get("message", {})
    code_txt = msg.get("content", "").strip()
    if not code_txt and msg.get("reasoning_content"):
        reasoning = msg.get("reasoning_content", "")
        if "```python" in reasoning:
            code_txt = reasoning.split("```python")[1].split("```")[0].strip()
        elif "```" in reasoning:
            code_txt = reasoning.split("```")[1].split("```")[0].strip()
        elif "def fast_dot_product" in reasoning:
            # Extract just the function lines
            fn_lines = []
            for line in reasoning[reasoning.find("def fast_dot_product"):].splitlines():
                if line.startswith("def ") or line.startswith("    ") or line.startswith("\t") or line.strip() == "":
                    fn_lines.append(line)
                else:
                    break
            code_txt = "\n".join(fn_lines).strip()
        else:
            code_txt = reasoning

    cleaned_code = code_txt
    if "```python" in cleaned_code:
        cleaned_code = cleaned_code.split("```python")[1].split("```")[0].strip()
    elif "```" in cleaned_code:
        cleaned_code = cleaned_code.split("```")[1].split("```")[0].strip()

    ast_valid = False
    if cleaned_code:
        try:
            ast.parse(cleaned_code)
            ast_valid = True
        except SyntaxError as e:
            print(f"    [DEBUG AST SyntaxError] {e} | Code snippet: {repr(cleaned_code[:150])}")
            ast_valid = False
    else:
        print("    [DEBUG] Model emitted empty content (all tokens consumed by reasoning)")

    print(f"  Result: {'PASSED' if ast_valid else 'FAILED'} (Python code is syntactically valid AST: {ast_valid})")
    results.append({"test": "python_ast", "passed": ast_valid})

    # 4. Speculative Draft Acceptance Quality
    print("\n[Test 4/4] Evaluating Speculative Draft Acceptance Rate...")
    timings = res_code.get("timings", {})
    draft_n = timings.get("draft_n", 0)
    draft_acc = timings.get("draft_n_accepted", 0)
    rate = (draft_acc / draft_n * 100.0) if draft_n > 0 else 0.0
    spec_active = draft_n > 0
    spec_healthy = (rate >= 50.0) if spec_active else True

    if spec_active:
        print(f"  Speculative Enabled: True | Drafted: {draft_n} | Accepted: {draft_acc} ({rate:.1f}%)")
        print(f"  Result: {'PASSED' if spec_healthy else 'WARNING'} (Acceptance rate >= 50%: {rate >= 50.0})")
    else:
        print(f"  Speculative Enabled: False (Standalone Mode)")
        print(f"  Result: PASSED (Speculative check bypassed for non-speculative model)")
    results.append({"test": "speculative_fidelity", "passed": spec_healthy, "acceptance_rate": rate})

    all_passed = all(r["passed"] for r in results)
    print(f"\n==========================================")
    print(f"Parity & Correctness Status: {'ALL PASSED' if all_passed else 'FAILURES DETECTED'}")
    print(f"==========================================")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Strata Correctness & Parity Verifier")
    parser.add_argument("--target", default="http://127.0.0.1:8080/v1")
    args = parser.parse_args()
    evaluate_parity(args.target)
