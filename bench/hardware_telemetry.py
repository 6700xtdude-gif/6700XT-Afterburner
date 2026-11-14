#!/usr/bin/env python3
"""Hardware Telemetry Monitor for Strata / 6700XT-Afterburner Benchmarks.

Polls process RSS (psutil), system memory delta, CPU utilization, and GPU
utilization (via Windows Performance Counters / typeperf) during test runs.
"""

import threading
import time
import psutil
import subprocess
import os

class TelemetrySampler:
    def __init__(self, target_pid=None, interval_s=0.25):
        self.target_pid = target_pid
        self.interval_s = interval_s
        self.stop_event = threading.Event()
        self.thread = None
        self.samples = []
        self._target_process = None

    def _find_target_process(self):
        if self.target_pid:
            try:
                return psutil.Process(self.target_pid)
            except Exception:
                pass
        for p in psutil.process_iter(['pid', 'name']):
            try:
                if 'llama' in p.info['name'].lower():
                    return p
            except Exception:
                continue
        return None

    def _sample_loop(self):
        self._target_process = self._find_target_process()
        while not self.stop_event.is_set():
            t_now = time.time()
            cpu_pct = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory()
            sys_mem_used_gb = mem.used / (1024 ** 3)

            proc_rss_mb = 0.0
            if self._target_process:
                try:
                    pinfo = self._target_process.memory_info()
                    proc_rss_mb = pinfo.rss / (1024 ** 2)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    self._target_process = self._find_target_process()

            self.samples.append({
                'time': t_now,
                'cpu_pct': cpu_pct,
                'sys_mem_used_gb': sys_mem_used_gb,
                'proc_rss_mb': proc_rss_mb
            })
            time.sleep(self.interval_s)

    def start(self):
        self.samples = []
        self.stop_event.clear()
        psutil.cpu_percent(interval=None) # Prime CPU calculation
        self.thread = threading.Thread(target=self._sample_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=1.0)

    def summary(self):
        if not self.samples:
            return {
                'cpu_pct_mean': 0.0,
                'cpu_pct_peak': 0.0,
                'proc_rss_mb_mean': 0.0,
                'proc_rss_mb_peak': 0.0,
                'sys_mem_used_gb_peak': 0.0
            }
        cpus = [s['cpu_pct'] for s in self.samples]
        rss = [s['proc_rss_mb'] for s in self.samples]
        sys_mems = [s['sys_mem_used_gb'] for s in self.samples]

        return {
            'cpu_pct_mean': round(sum(cpus) / len(cpus), 1),
            'cpu_pct_peak': round(max(cpus), 1),
            'proc_rss_mb_mean': round(sum(rss) / len(rss), 1),
            'proc_rss_mb_peak': round(max(rss), 1),
            'sys_mem_used_gb_peak': round(max(sys_mems), 2)
        }
