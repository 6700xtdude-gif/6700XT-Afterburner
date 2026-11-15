#!/usr/bin/env python3
"""Practical 3-Question Windows Admin Smoke Test & Session Grader.

Measures real agent results rather than raw tokens/sec:
- Result Accuracy Score (0-100% against ground-truth verification groups)
- Wall-Clock Time-to-Result (seconds)
- Tool Call Efficiency (tool calls + error-free execution rate)
- Peak Context Tokens
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import glob
import json
import os
import subprocess
import time
from typing import Any

ROOT_DIR = r"C:\Users\6700XT\Documents\Strata"
DEFAULT_SESSIONS_DIR = os.path.join(
    os.path.expanduser("~"),
    ".pi",
    "agent",
    "sessions",
    "--C--Users-6700XT-Documents-Strata--",
)
RESULTS_PATH = os.path.join(ROOT_DIR, "MEMORY", "PRACTICAL_SMOKE_RESULTS.json")


@dataclass(frozen=True)
class SmokeQuestion:
    qid: int
    name: str
    prompt: str
    prompt_match_substrings: tuple[str, ...]
    expected_groups: tuple[tuple[str, ...], ...]


SMOKE_QUESTIONS: dict[int, SmokeQuestion] = {
    1: SmokeQuestion(
        qid=1,
        name="Q1: System Identity & Hardware",
        prompt=(
            "Using PowerShell, check and report this computer's exact hostname, "
            "Windows build number, GPU model, and total installed RAM in GB."
        ),
        prompt_match_substrings=("hostname", "name of this computer"),
        expected_groups=(
            ("sandbox",),
            ("26300", "26100"),
            ("6700 xt", "6700xt"),
            ("64", "63.9", "63.8"),
        ),
    ),
    2: SmokeQuestion(
        qid=2,
        name="Q2: Stopped Automatic Services & Top RAM",
        prompt=(
            "Using PowerShell, list any Automatic-start Windows services that are "
            "currently Stopped, plus the top 3 processes by RAM usage. Do not modify anything."
        ),
        prompt_match_substrings=("automatic-start", "stopped"),
        expected_groups=(
            ("mapsbroker", "downloaded maps"),
            ("stopped",),
            ("llama-server", "mb", "gb"),
        ),
    ),
    3: SmokeQuestion(
        qid=3,
        name="Q3: Event Log 3-Error Root Cause Triage",
        prompt=(
            "list the last three unique error messages in windows 'administer events', "
            "conduct root cause analysis, investigate error and web research each error, "
            "return to me your recommendations for remediation, don't fix anything yet, "
            "just tell what is broke and how I can fix it."
        ),
        prompt_match_substrings=("unique error messages", "administer events"),
        expected_groups=(
            ("mapsbroker", "downloaded maps", "7023"),
            ("2042", "firewall"),
            ("10010", "dcom", "9ba05972"),
            ("benign", "harmless", "ignore", "noise", "not broken", "nothing is actually broken"),
            ("disabled", "disable"),
        ),
    ),
}


def score_answer(text: str, expected_groups: tuple[tuple[str, ...], ...]) -> dict[str, Any]:
    """Score final answer text against expected ground-truth keyword groups."""
    lower = (text or "").lower()
    matched = []
    missed = []
    for group in expected_groups:
        hit = next((kw for kw in group if kw.lower() in lower), None)
        if hit:
            matched.append(hit)
        else:
            missed.append(" / ".join(group))
    total = len(expected_groups)
    pct = round((len(matched) / total) * 100.0, 1) if total else 0.0
    return {
        "scorePct": pct,
        "matchedCount": len(matched),
        "totalGroups": total,
        "matched": matched,
        "missed": missed,
    }


def _extract_user_text(msg: dict[str, Any]) -> str:
    content = msg.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(str(part.get("text", "")) for part in content if isinstance(part, dict))
    return ""


def _extract_assistant_text(msg: dict[str, Any]) -> str:
    content = msg.get("content", [])
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            str(part.get("text", ""))
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        )
    return ""


def _parse_iso_ms(ts: str | None) -> float | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp() * 1000.0
    except ValueError:
        return None


def analyze_session(jsonl_path: str, question_id: int = 3) -> dict[str, Any]:
    """Parse a Pi .jsonl session file and extract practical result & efficiency metrics."""
    q = SMOKE_QUESTIONS[question_id]
    records: list[dict[str, Any]] = []
    with open(jsonl_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    msg_records = [r for r in records if r.get("type") == "message"]

    # Find the slice starting at the user prompt matching this question (or first user prompt)
    start_idx = 0
    for idx, rec in enumerate(msg_records):
        msg = rec.get("message", {})
        if msg.get("role") == "user":
            utext = _extract_user_text(msg).lower()
            if any(sub in utext for sub in q.prompt_match_substrings):
                start_idx = idx
                break

    # Stop at the next user prompt after start_idx, if another prompt followed
    end_idx = len(msg_records)
    for idx in range(start_idx + 1, len(msg_records)):
        if msg_records[idx].get("message", {}).get("role") == "user":
            end_idx = idx
            break

    slice_msgs = msg_records[start_idx:end_idx]

    assistant_turns = 0
    total_output_tokens = 0
    total_assistant_ms = 0.0
    peak_context_tokens = 0
    tool_calls = 0
    tool_errors = 0
    final_text = ""

    start_ts_ms = _parse_iso_ms(slice_msgs[0].get("timestamp")) if slice_msgs else None
    end_ts_ms = start_ts_ms

    for rec in slice_msgs:
        msg = rec.get("message", {})
        role = msg.get("role")
        ts_ms = _parse_iso_ms(rec.get("timestamp"))
        if ts_ms is not None:
            end_ts_ms = ts_ms

        if role == "assistant":
            assistant_turns += 1
            usage = msg.get("usage") or {}
            total_output_tokens += int(usage.get("output") or 0)
            peak_context_tokens = max(peak_context_tokens, int(usage.get("totalTokens") or 0))
            total_assistant_ms += float(msg.get("durationMs") or 0.0)
            for part in msg.get("content", []):
                if isinstance(part, dict) and part.get("type") == "toolCall":
                    tool_calls += 1
            txt = _extract_assistant_text(msg)
            if txt.strip():
                final_text = txt
        elif role == "toolResult":
            if msg.get("isError"):
                tool_errors += 1

    wall_sec = (
        round((end_ts_ms - start_ts_ms) / 1000.0, 1)
        if start_ts_ms is not None and end_ts_ms is not None
        else round(total_assistant_ms / 1000.0, 1)
    )
    tool_success_pct = (
        round(((tool_calls - tool_errors) / tool_calls) * 100.0, 1)
        if tool_calls > 0
        else 100.0
    )
    grading = score_answer(final_text, q.expected_groups)

    return {
        "sessionFile": os.path.basename(jsonl_path),
        "questionId": question_id,
        "questionName": q.name,
        "wallClockSec": wall_sec,
        "assistantTurns": assistant_turns,
        "totalOutputTokens": total_output_tokens,
        "peakContextTokens": peak_context_tokens,
        "toolCalls": tool_calls,
        "toolErrors": tool_errors,
        "toolSuccessPct": tool_success_pct,
        "resultScorePct": grading["scorePct"],
        "matchedKeywords": grading["matched"],
        "missedKeywords": grading["missed"],
    }


def _pi_env() -> dict[str, str]:
    env = os.environ.copy()
    local_app = env.get("LOCALAPPDATA", "")
    user_prof = env.get("USERPROFILE", os.path.expanduser("~"))
    extra = [p for p in (os.path.join(local_app, "pi-node", "current"), os.path.join(user_prof, ".pi", "agent", "bin")) if p]
    env["PATH"] = os.pathsep.join(extra + [env.get("PATH", "")])
    return env


def run_live_question(question_id: int, sessions_dir: str) -> dict[str, Any]:
    """Run a single smoke-test prompt through Pi CLI (--print) and grade the created session."""
    q = SMOKE_QUESTIONS[question_id]
    before = set(glob.glob(os.path.join(sessions_dir, "*.jsonl")))
    t0 = time.perf_counter()
    proc = subprocess.run(
        ["pi.cmd", "--provider", "afterburner", "--model", "default", "--print", q.prompt],
        cwd=ROOT_DIR,
        env=_pi_env(),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=900,
    )
    elapsed = round(time.perf_counter() - t0, 1)
    after = set(glob.glob(os.path.join(sessions_dir, "*.jsonl")))
    created = sorted(after - before, key=os.path.getmtime)
    if created:
        report = analyze_session(created[-1], question_id=question_id)
        report["wallClockSec"] = elapsed
    else:
        grading = score_answer(proc.stdout, q.expected_groups)
        report = {
            "sessionFile": "(stdout only)",
            "questionId": question_id,
            "questionName": q.name,
            "wallClockSec": elapsed,
            "assistantTurns": 1,
            "totalOutputTokens": 0,
            "peakContextTokens": 0,
            "toolCalls": 0,
            "toolErrors": 0,
            "toolSuccessPct": 100.0,
            "resultScorePct": grading["scorePct"],
            "matchedKeywords": grading["matched"],
            "missedKeywords": grading["missed"],
        }
    report["returncode"] = proc.returncode
    return report


def find_q3_history_sessions(sessions_dir: str) -> list[str]:
    """Return session .jsonl files in chronological order that contain the Q3 Event Log prompt."""
    matches = []
    for path in sorted(glob.glob(os.path.join(sessions_dir, "*.jsonl"))):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                content = fh.read().lower()
            if "administer events" in content or "unique error messages" in content:
                matches.append(path)
        except OSError:
            continue
    return matches


def print_table(results: list[dict[str, Any]]) -> None:
    header = (
        f"{'Session / Test':<38} | {'Score':>6} | {'Time(s)':>8} | "
        f"{'Turns':>5} | {'Tools(Err)':>10} | {'OutTok':>7} | {'PeakCtx':>7}"
    )
    print(header)
    print("-" * len(header))
    for r in results:
        label = f"{r['questionName'][:18]} [{r['sessionFile'][:16]}]"
        tools_str = f"{r['toolCalls']}({r['toolErrors']})"
        print(
            f"{label:<38} | {r['resultScorePct']:>5.1f}% | {r['wallClockSec']:>8.1f} | "
            f"{r['assistantTurns']:>5} | {tools_str:>10} | {r['totalOutputTokens']:>7} | "
            f"{r['peakContextTokens']:>7}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Practical 3-Question Windows Admin Smoke Benchmark")
    parser.add_argument("--sessions-dir", default=DEFAULT_SESSIONS_DIR, help="Path to Pi sessions directory")
    parser.add_argument("--analyze-session", help="Analyze a specific Pi .jsonl session file")
    parser.add_argument("--analyze-history", action="store_true", help="Score historical Q3 Event Log sessions")
    parser.add_argument("--run", action="store_true", help="Run live Pi CLI smoke test")
    parser.add_argument("--question", default="all", choices=["1", "2", "3", "all"], help="Which question to run/analyze")
    args = parser.parse_args()

    results: list[dict[str, Any]] = []
    if args.analyze_session:
        qid = 3 if args.question == "all" else int(args.question)
        results.append(analyze_session(args.analyze_session, question_id=qid))
    elif args.analyze_history:
        for path in find_q3_history_sessions(args.sessions_dir):
            results.append(analyze_session(path, question_id=3))
    elif args.run:
        qids = [1, 2, 3] if args.question == "all" else [int(args.question)]
        for qid in qids:
            results.append(run_live_question(qid, args.sessions_dir))
    else:
        parser.print_help()
        return

    print_table(results)
    os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)
    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "questions": {k: asdict(v) for k, v in SMOKE_QUESTIONS.items()},
        "results": results,
    }
    with open(RESULTS_PATH, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    print(f"\nSaved benchmark results to: {RESULTS_PATH}")


if __name__ == "__main__":
    main()
