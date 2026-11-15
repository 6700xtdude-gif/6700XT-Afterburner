"""Hermetic unit tests for AfterBurner Control Center (dashboard/server.py)."""

import json
import os
import sys
import unittest
import urllib.error
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import dashboard.server as srv
from tests.factories import MockHTTPResponse


class TestDashboardServer(unittest.TestCase):
    def test_parse_telemetry_counters_selects_primary_vram_adapter(self):
        samples = [
            {
                "path": r"\\host\gpu adapter memory(luid_0x00000000_0x0000fab2_phys_0)\dedicated usage",
                "inst": "luid_0x00000000_0x0000fab2_phys_0",
                "val": 0,
            },
            {
                "path": r"\\host\gpu adapter memory(luid_0x00000000_0x0000dcba_phys_0)\dedicated usage",
                "inst": "luid_0x00000000_0x0000dcba_phys_0",
                "val": 10737418240,  # 10240 MB
            },
            {
                "path": r"\\host\gpu adapter memory(luid_0x00000000_0x0000dcba_phys_0)\shared usage",
                "inst": "luid_0x00000000_0x0000dcba_phys_0",
                "val": 536870912,  # 512 MB
            },
            {
                "path": r"\\host\gpu engine(pid_6768_luid_0x00000000_0x0000dcba_phys_0_eng_2_engtype_compute 0)\utilization percentage",
                "inst": "pid_6768_luid_0x00000000_0x0000dcba_phys_0_eng_2_engtype_compute 0",
                "val": 97.4,
            },
            {
                "path": r"\\host\processor(_total)\% processor time",
                "inst": "_total",
                "val": 14.6,
            },
        ]
        parsed = srv.parse_telemetry_counters(samples)
        self.assertEqual(parsed["vramUsedMb"], 10240.0)
        self.assertEqual(parsed["vramTotalMb"], 12288)
        self.assertEqual(parsed["sharedGpuUsedMb"], 512.0)
        self.assertEqual(parsed["gpuComputePercent"], 97.4)
        self.assertEqual(parsed["cpuPercent"], 14.6)

    def test_parse_telemetry_counters_empty_samples_safe(self):
        parsed = srv.parse_telemetry_counters([])
        self.assertEqual(parsed["vramUsedMb"], 0.0)
        self.assertEqual(parsed["sharedGpuUsedMb"], 0.0)
        self.assertEqual(parsed["gpuComputePercent"], 0.0)
        self.assertIsNone(parsed["cpuPercent"])

    @patch("dashboard.server.urllib.request.urlopen")
    def test_fetch_llama_status_online_generating(self, mock_urlopen):
        mock_urlopen.side_effect = [
            MockHTTPResponse({"status": "ok"}),
            MockHTTPResponse({"model_path": r"C:\Models\Qwen3.8-27B-IQ2_M.gguf"}),
            MockHTTPResponse([{"id": 0, "n_ctx": 65536, "is_processing": True, "speculative": True}]),
        ]
        st = srv.fetch_llama_status("http://127.0.0.1:8080")
        self.assertTrue(st["online"])
        self.assertEqual(st["health"], "ok")
        self.assertEqual(st["model"], "Qwen3.8-27B-IQ2_M.gguf")
        self.assertEqual(st["nCtx"], 65536)
        self.assertTrue(st["isProcessing"])
        self.assertEqual(st["slotState"], "generating")

    @patch("dashboard.server.urllib.request.urlopen")
    def test_fetch_llama_status_offline(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
        st = srv.fetch_llama_status("http://127.0.0.1:8080")
        self.assertFalse(st["online"])
        self.assertEqual(st["health"], "offline")
        self.assertEqual(st["slotState"], "offline")

    @patch("dashboard.server.urllib.request.urlopen")
    def test_optimize_prompt_local_payload(self, mock_urlopen):
        mock_urlopen.return_value = MockHTTPResponse(
            {"choices": [{"message": {"content": "Run pytest on tests/ and fix errors."}}]}
        )
        res = srv.optimize_prompt("fix test pls", engine="local")
        self.assertTrue(res["ok"])
        self.assertEqual(res["optimizedPrompt"], "Run pytest on tests/ and fix errors.")
        req = mock_urlopen.call_args[0][0]
        sent = json.loads(req.data.decode("utf-8"))
        self.assertEqual(sent["max_tokens"], 300)
        self.assertEqual(sent["reasoning_format"], "none")
        self.assertEqual(sent["chat_template_kwargs"], {"enable_thinking": False})

    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "", "GEMINI_API_KEY": ""}, clear=False)
    def test_optimize_prompt_cloud_missing_keys(self):
        with self.assertRaises(ValueError):
            srv.optimize_prompt("hello", engine="cloud", provider="openrouter", api_key="")
        with self.assertRaises(ValueError):
            srv.optimize_prompt("hello", engine="cloud", provider="gemini", api_key="")

    @patch("dashboard.server.urllib.request.urlopen")
    def test_optimize_prompt_gemini_success(self, mock_urlopen):
        mock_urlopen.return_value = MockHTTPResponse(
            {"candidates": [{"content": {"parts": [{"text": "Inspect logs and fix bug."}]}}]}
        )
        res = srv.optimize_prompt("check logs", engine="cloud", provider="gemini", api_key="test-key")
        self.assertEqual(res["optimizedPrompt"], "Inspect logs and fix bug.")
        self.assertEqual(res["provider"], "gemini")

    def test_build_pi_env_prepends_paths(self):
        env = srv.build_pi_env({"LOCALAPPDATA": r"C:\Users\X\AppData\Local", "USERPROFILE": r"C:\Users\X", "PATH": r"C:\Windows"})
        self.assertTrue(env["PATH"].startswith(r"C:\Users\X\AppData\Local\pi-node\current;C:\Users\X\.pi\agent\bin;"))

    def test_start_llama_server_validation(self):
        with self.assertRaises(ValueError):
            srv.start_llama_server(mode="invalid_mode", reasoning_budget=256)
        with self.assertRaises(ValueError):
            srv.start_llama_server(mode="qwen27b_vram", reasoning_budget=123)

    def test_get_lan_ip_returns_valid_string(self):
        ip = srv.get_lan_ip()
        self.assertIsInstance(ip, str)
        self.assertGreaterEqual(len(ip.split(".")), 4)


if __name__ == "__main__":
    unittest.main()
