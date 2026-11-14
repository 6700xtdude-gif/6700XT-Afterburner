"""Hermetic unit tests for the LLM Bridge MCP server (tools/llm_bridge_mcp.py).

Verifies OpenRouter routing, local Vulkan LLM calls, thinking/reasoning parsing,
and connection error handling without live network or GPU inference.
"""

import unittest
from unittest.mock import patch
import sys
import os
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import tools.llm_bridge_mcp as bridge
from tests.factories import MockHTTPResponse


class TestLLMBridgeMCP(unittest.TestCase):
    @patch.dict(os.environ, {"OPENROUTER_API_KEY": ""}, clear=True)
    def test_openrouter_missing_api_key(self):
        res = bridge.call_openrouter("test prompt")
        self.assertIn("OPENROUTER_API_KEY environment variable is not configured", res)

    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-mock-key"})
    @patch("urllib.request.urlopen")
    def test_openrouter_success(self, mock_urlopen):
        mock_response = {
            "choices": [{"message": {"role": "assistant", "content": "Mock OpenRouter response"}}]
        }
        mock_urlopen.return_value = MockHTTPResponse(mock_response)

        res = bridge.call_openrouter("What is 2+2?")
        self.assertEqual(res, "Mock OpenRouter response")

    @patch("urllib.request.urlopen")
    def test_local_llm_with_reasoning(self, mock_urlopen):
        mock_response = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Final answer here",
                        "reasoning_content": "Step 1: thinking..."
                    }
                }
            ]
        }
        mock_urlopen.return_value = MockHTTPResponse(mock_response)

        res = bridge.call_local_llm("Solve problem")
        self.assertIn("<think>", res)
        self.assertIn("Step 1: thinking...", res)
        self.assertIn("Final answer here", res)

    @patch("urllib.request.urlopen")
    def test_local_llm_connection_failure(self, mock_urlopen):
        import urllib.error
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

        res = bridge.call_local_llm("Hello")
        self.assertIn("Cannot connect to local LLM server", res)


if __name__ == "__main__":
    unittest.main()
