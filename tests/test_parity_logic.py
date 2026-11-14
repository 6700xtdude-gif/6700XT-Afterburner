"""Unit tests for the Parity & Correctness evaluation logic."""

import unittest
import ast
import json
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class TestParityLogic(unittest.TestCase):
    def test_json_validation_clean_string(self):
        raw = '{"system": "llm", "status": "ok", "tokens_per_second": 22.5, "speculative": true}'
        data = json.loads(raw)
        required = {"system", "status", "tokens_per_second", "speculative"}
        self.assertTrue(required.issubset(data.keys()))

    def test_json_validation_markdown_fence(self):
        raw = '```json\n{"system": "llm", "status": "ok", "tokens_per_second": 22.5, "speculative": true}\n```'
        cleaned = raw.split("```json")[1].split("```")[0].strip()
        data = json.loads(cleaned)
        required = {"system", "status", "tokens_per_second", "speculative"}
        self.assertTrue(required.issubset(data.keys()))

    def test_python_ast_validity(self):
        code = """
def fast_dot_product(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))
"""
        parsed = ast.parse(code)
        self.assertIsInstance(parsed, ast.Module)

    def test_python_ast_syntax_error(self):
        invalid_code = "def bad_func(:"
        with self.assertRaises(SyntaxError):
            ast.parse(invalid_code)


if __name__ == "__main__":
    unittest.main()
