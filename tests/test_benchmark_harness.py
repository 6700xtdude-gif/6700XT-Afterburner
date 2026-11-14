"""Unit tests for the Strata Benchmark Harness."""

import unittest
from unittest.mock import patch
import sys
import os

# Ensure bench and tests are in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from bench.hardware_telemetry import TelemetrySampler
from bench.bench_head_to_head import execute_request
from tests.factories import create_mock_completion_response, MockHTTPResponse


class TestBenchmarkHarness(unittest.TestCase):
    def test_telemetry_sampler_lifecycle(self):
        sampler = TelemetrySampler(interval_s=0.05)
        sampler.start()
        sampler.stop()
        summary = sampler.summary()
        self.assertIn("cpu_pct_mean", summary)
        self.assertIn("proc_rss_mb_peak", summary)
        self.assertIn("sys_mem_used_gb_peak", summary)

    @patch("urllib.request.urlopen")
    def test_execute_request_metrics_parsing(self, mock_urlopen):
        mock_data = create_mock_completion_response(
            content="test output",
            predicted_tokens=150,
            prompt_tokens=30,
            predicted_per_second=24.5,
            prompt_per_second=85.0,
            prompt_ms=120.0,
            draft_n=100,
            draft_n_accepted=75
        )
        mock_urlopen.return_value = MockHTTPResponse(mock_data)

        metrics = execute_request("http://mock:8080/v1", "test prompt", max_tokens=150, temperature=0.0)

        self.assertEqual(metrics["pred_tok_s"], 24.5)
        self.assertEqual(metrics["prompt_tok_s"], 85.0)
        self.assertEqual(metrics["ttft_ms"], 120.0)
        self.assertEqual(metrics["pred_tokens"], 150)
        self.assertEqual(metrics["draft_tokens"], 100)
        self.assertEqual(metrics["draft_accepted"], 75)
        self.assertEqual(metrics["accept_rate_pct"], 75.0)

    @patch("urllib.request.urlopen")
    def test_execute_request_fallback_when_timings_missing(self, mock_urlopen):
        # Server without detailed timings block
        raw_data = {
            "choices": [{"message": {"role": "assistant", "content": "hello"}}],
            "usage": {"completion_tokens": 50, "prompt_tokens": 10}
        }
        mock_urlopen.return_value = MockHTTPResponse(raw_data)

        metrics = execute_request("http://mock:8080/v1", "hello", max_tokens=50, temperature=0.0)
        self.assertEqual(metrics["pred_tokens"], 50)
        self.assertGreater(metrics["pred_tok_s"], 0.0)


if __name__ == "__main__":
    unittest.main()
