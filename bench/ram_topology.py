#!/usr/bin/env python3
"""Capture the RAM/host topology and pair it with a benchmark run.

Why this exists: the RX 6700 XT rig is about to move from 64 GB (2x32, DDR4-3200)
to 96 GB (4 DIMMs). On Ryzen 5000, four dual-rank DIMMs force the memory
controller down a clock step, so the capacity gain costs memory bandwidth. That
cost has to be measured, not guessed, and the measurement is only comparable if
the topology is recorded alongside the throughput.

Usage:
    python bench/ram_topology.py --label 64gb-2dimm
    python bench/ram_topology.py --label 96gb-4dimm --bench
    python bench/ram_topology.py --compare MEMORY/RAM_64gb-2dimm.json MEMORY/RAM_96gb-4dimm.json

Output goes to MEMORY/RAM_<label>.json so it is committed with the project and
survives a reimage.
"""

import argparse
import datetime
import json
import os
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEMORY_DIR = os.path.join(REPO_ROOT, "MEMORY")

PS_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$out = @{}
$out.collectedAt = (Get-Date).ToString('o')

try {
  $dimms = Get-CimInstance -ClassName Win32_PhysicalMemory | ForEach-Object {
    [ordered]@{
      slot            = $_.DeviceLocator
      bank            = $_.BankLabel
      capacityGB      = [math]::Round($_.Capacity / 1GB, 1)
      speedRatedMHz   = $_.Speed
      speedActualMHz  = $_.ConfiguredClockSpeed
      manufacturer    = "$($_.Manufacturer)".Trim()
      partNumber      = "$($_.PartNumber)".Trim()
      memoryType      = $_.SMBIOSMemoryType
      dataWidth       = $_.DataWidth
      totalWidth      = $_.TotalWidth
    }
  }
  $out.dimms = @($dimms)
} catch { $out.dimms = @() }

try {
  $cpu = Get-CimInstance -ClassName Win32_Processor | Select-Object -First 1
  $out.cpu = [ordered]@{
    name   = "$($cpu.Name)".Trim()
    cores  = $cpu.NumberOfCores
    threads= $cpu.NumberOfLogicalProcessors
    maxMHz = $cpu.MaxClockSpeed
  }
} catch { $out.cpu = $null }

try {
  $bb = Get-CimInstance -ClassName Win32_BaseBoard | Select-Object -First 1
  $out.board = [ordered]@{ manufacturer = "$($bb.Manufacturer)".Trim(); model = "$($bb.Product)".Trim() }
} catch { $out.board = $null }

try {
  $bios = Get-CimInstance -ClassName Win32_BIOS | Select-Object -First 1
  $out.bios = [ordered]@{ version = "$($bios.SMBIOSBIOSVersion)".Trim(); date = "$($bios.ReleaseDate)" }
} catch { $out.bios = $null }

try {
  $os = Get-CimInstance -ClassName Win32_OperatingSystem | Select-Object -First 1
  $out.os = [ordered]@{
    caption = "$($os.Caption)".Trim()
    version = "$($os.Version)"
    build   = "$($os.BuildNumber)"
    totalGB = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1)
  }
} catch { $out.os = $null }

$tmp = Join-Path $env:TEMP ("ram_topology_" + [guid]::NewGuid().ToString() + ".json")
$out | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $tmp -Encoding UTF8
Write-Output $tmp
"""


def _run_ps(script):
    """Run a PowerShell script, return the single path it prints."""
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
        capture_output=True, text=True, timeout=90,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"PowerShell failed: {proc.stderr.strip()}")
    lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
    if not lines:
        raise RuntimeError("PowerShell returned no path")
    return lines[-1]


def collect():
    tmp = _run_ps(PS_SCRIPT)
    try:
        with open(tmp, "r", encoding="utf-8-sig") as fh:
            raw = json.load(fh)
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    return summarize(raw)


def summarize(raw):
    dimms = raw.get("dimms") or []
    actual = [d["speedActualMHz"] for d in dimms if d.get("speedActualMHz")]
    rated = [d["speedRatedMHz"] for d in dimms if d.get("speedRatedMHz")]
    total = sum(d.get("capacityGB", 0) for d in dimms)

    summary = {
        "collectedAt": raw.get("collectedAt"),
        "host": {
            "cpu": raw.get("cpu"),
            "board": raw.get("board"),
            "bios": raw.get("bios"),
            "os": raw.get("os"),
        },
        "memory": {
            "dimmCount": len(dimms),
            "totalGB": round(total, 1),
            "speedRatedMHz": min(rated) if rated else None,
            "speedActualMHz": min(actual) if actual else None,
            "ranBelowRating": bool(rated and actual and min(actual) < min(rated)),
            "channels": "dual (Ryzen 5000, 2 memory channels; DIMM count does not add channels)",
            "dimms": dimms,
        },
    }
    return summary


def run_bench(label):
    """Run the existing head-to-head harness and return its report path."""
    out_dir = os.path.join(REPO_ROOT, "bench", "reports")
    cmd = [sys.executable, os.path.join(REPO_ROOT, "bench", "bench_head_to_head.py"), "--out", out_dir]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    if proc.returncode != 0:
        return {"ok": False, "error": proc.stderr.strip()[-800:], "stdout": proc.stdout.strip()[-800:]}
    return {"ok": True, "stdout": proc.stdout.strip()[-800:]}


def compare(paths):
    loaded = []
    for p in paths:
        with open(p, "r", encoding="utf-8") as fh:
            loaded.append((p, json.load(fh)))
    rows = []
    for path, data in loaded:
        mem = data.get("memory", {})
        rows.append({
            "file": os.path.basename(path),
            "label": data.get("label"),
            "totalGB": mem.get("totalGB"),
            "dimmCount": mem.get("dimmCount"),
            "speedActualMHz": mem.get("speedActualMHz"),
            "ranBelowRating": mem.get("ranBelowRating"),
            "benchMedianTps": (data.get("bench") or {}).get("medianTps"),
        })
    return rows


def main():
    ap = argparse.ArgumentParser(description="Capture RAM topology and pair it with a benchmark.")
    ap.add_argument("--label", help="Config label, e.g. 64gb-2dimm or 96gb-4dimm")
    ap.add_argument("--bench", action="store_true", help="Also run bench/bench_head_to_head.py")
    ap.add_argument("--out-dir", default=MEMORY_DIR, help="Output directory (default MEMORY/)")
    ap.add_argument("--compare", nargs="+", metavar="JSON", help="Compare previously captured configs")
    args = ap.parse_args()

    if args.compare:
        rows = compare(args.compare)
        width = max(len(r["file"]) for r in rows)
        print(f"{'file':<{width}}  {'GB':>5}  {'DIMMs':>5}  {'MHz':>5}  {'below':>5}")
        for r in rows:
            print(f"{r['file']:<{width}}  {str(r['totalGB']):>5}  {str(r['dimmCount']):>5}  "
                  f"{str(r['speedActualMHz']):>5}  {str(r['ranBelowRating']):>5}")
        return 0

    if not args.label:
        ap.error("--label is required unless --compare is used")

    data = collect()
    data["label"] = args.label
    data["capturedAtLocal"] = datetime.datetime.now().isoformat(timespec="seconds")

    if args.bench:
        data["bench"] = run_bench(args.label)

    os.makedirs(args.out_dir, exist_ok=True)
    path = os.path.join(args.out_dir, f"RAM_{args.label}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")

    mem = data["memory"]
    print(f"label        {args.label}")
    print(f"total        {mem['totalGB']} GB across {mem['dimmCount']} DIMM(s)")
    print(f"rated        {mem['speedRatedMHz']} MHz")
    print(f"actual       {mem['speedActualMHz']} MHz")
    print(f"below rating {mem['ranBelowRating']}")
    print(f"written      {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
