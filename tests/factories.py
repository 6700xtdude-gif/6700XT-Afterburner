"""Test factories and mock response builders for Strata test suite.

Allows hermetic testing of benchmark runners, bridges, and correctness verifiers
without needing live GPU inference servers or heavy PyTorch/CUDA dependencies.
"""

import json


def create_mock_completion_response(
    content="Hello from mock model!",
    reasoning_content="",
    predicted_tokens=100,
    prompt_tokens=25,
    predicted_per_second=22.5,
    prompt_per_second=80.0,
    prompt_ms=125.0,
    draft_n=80,
    draft_n_accepted=60,
    finish_reason="stop"
):
    """Builds an OpenAI-compatible completion response matching llama-server's schema."""
    return {
        "id": "chatcmpl-mock-12345",
        "object": "chat.completion",
        "created": 1700000000,
        "model": "qwen38-27b-mock",
        "choices": [
            {
                "index": 0,
                "finish_reason": finish_reason,
                "message": {
                    "role": "assistant",
                    "content": content,
                    "reasoning_content": reasoning_content
                }
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": predicted_tokens,
            "total_tokens": prompt_tokens + predicted_tokens
        },
        "timings": {
            "prompt_n": prompt_tokens,
            "prompt_ms": prompt_ms,
            "prompt_per_second": prompt_per_second,
            "predicted_n": predicted_tokens,
            "predicted_ms": (predicted_tokens / predicted_per_second * 1000.0) if predicted_per_second > 0 else 0.0,
            "predicted_per_second": predicted_per_second,
            "draft_n": draft_n,
            "draft_n_accepted": draft_n_accepted
        }
    }


class MockHTTPResponse:
    """Mock context manager for urllib.request.urlopen."""
    def __init__(self, data_dict, status=200):
        self.data_bytes = json.dumps(data_dict).encode("utf-8")
        self.status = status

    def read(self):
        return self.data_bytes

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
