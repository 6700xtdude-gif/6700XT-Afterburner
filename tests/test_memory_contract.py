"""Conformance tests for the durable-memory contract.

These do not test the model or the GPU. They test whether the thing that is
supposed to survive a reimage actually exists on disk: the AGENTS.md hierarchy,
the MEMORY/ and NOTEBOOK/ ledgers, the vendored-patch export, and the absence of
committed credentials.

Run before any reimage, and again after, to prove the memory system came back.

    python -m unittest tests.test_memory_contract -v
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILE = os.path.expanduser("~")

SECRET_PATTERNS = [
    re.compile(r"ghp_[A-Za-z0-9]{36}"),
    re.compile(r"gho_[A-Za-z0-9]{36}"),
    re.compile(r"sk-or-v1-[a-f0-9]{64}"),
    re.compile(r"sk-ant-[A-Za-z0-9\-_]{32,}"),
]

SKIP_DIRS = {".git", "Models", "packs", "bin", "__pycache__", ".venv", "venv",
             os.path.join("tools", "llama.cpp"), "tools/llama.cpp"}
MAX_SCAN_BYTES = 2 * 1024 * 1024


def read(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


class TestAgentsHierarchy(unittest.TestCase):
    """Three scopes must exist: machine, documents, project."""

    def test_machine_agents_md_exists(self):
        path = os.path.join(PROFILE, "AGENTS.md")
        self.assertTrue(os.path.isfile(path), f"missing machine-scope file: {path}")
        body = read(path)
        self.assertIn("8080", body, "machine rules must guard the llama-server port")
        self.assertIn("PowerShell", body, "machine rules must state the shell")

    def test_documents_agents_md_exists(self):
        path = os.path.join(PROFILE, "Documents", "AGENTS.md")
        self.assertTrue(os.path.isfile(path), f"missing documents-scope file: {path}")
        self.assertIn("MEMORY", read(path))

    def test_project_agents_md_exists(self):
        path = os.path.join(REPO_ROOT, "AGENTS.md")
        self.assertTrue(os.path.isfile(path), f"missing project file: {path}")
        body = read(path)
        self.assertIn("Hardware", body)
        self.assertIn("Zero Spill", body)


class TestMemoryLedger(unittest.TestCase):
    """The git-backed ledger is the only memory that survives a reimage."""

    def test_digest_exists_and_is_current_state(self):
        path = os.path.join(REPO_ROOT, "MEMORY", "DIGEST.md")
        self.assertTrue(os.path.isfile(path), f"missing {path}")
        body = read(path)
        self.assertIn("Active Context", body)
        self.assertIn("GitHub Repository", body)

    def test_experiment_log_exists(self):
        self.assertTrue(os.path.isfile(os.path.join(REPO_ROOT, "MEMORY", "EXPERIMENT_LOG.md")))

    def test_lessons_exist(self):
        self.assertTrue(os.path.isfile(os.path.join(REPO_ROOT, "MEMORY", "LESSONS.md")))

    def test_notebook_baseline_exists(self):
        self.assertTrue(os.path.isfile(os.path.join(REPO_ROOT, "NOTEBOOK", "SYSTEM_BASELINE.md")))

    def test_ram_baseline_is_captured(self):
        ram_dir = os.path.join(REPO_ROOT, "MEMORY")
        found = [f for f in os.listdir(ram_dir) if f.startswith("RAM_") and f.endswith(".json")]
        self.assertTrue(found, "no RAM_*.json baseline captured; run bench/ram_topology.py")


class TestVendoredTreeSafety(unittest.TestCase):
    """Local edits inside the gitignored llama.cpp clone must be exported."""

    def test_gitignore_covers_models_and_vendored_tree(self):
        body = read(os.path.join(REPO_ROOT, ".gitignore"))
        self.assertIn("Models/", body)
        self.assertIn("tools/llama.cpp/", body)

    def test_at_least_one_exported_patch(self):
        patch_dir = os.path.join(REPO_ROOT, "patches")
        self.assertTrue(os.path.isdir(patch_dir), "missing patches/ directory")
        patches = [f for f in os.listdir(patch_dir) if f.endswith(".patch")]
        self.assertTrue(patches, "vendored llama.cpp edits must be exported to patches/")

    def test_vendored_tree_is_documented(self):
        path = os.path.join(REPO_ROOT, "docs", "VENDORED_TREES.md")
        self.assertTrue(os.path.isfile(path))
        body = read(path)
        self.assertIn("AGENTS.md", body)
        self.assertIn("upstream rules are not project rules", body.lower())


class TestNoCommittedSecrets(unittest.TestCase):
    """A credential in the repo is a credential in every clone and every backup."""

    def test_no_secret_patterns_in_tracked_tree(self):
        hits = []
        for root, dirs, files in os.walk(REPO_ROOT):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            if "tools" in root.split(os.sep) and "llama.cpp" in root.split(os.sep):
                continue
            for name in files:
                path = os.path.join(root, name)
                try:
                    if os.path.getsize(path) > MAX_SCAN_BYTES:
                        continue
                    body = read(path)
                except OSError:
                    continue
                for pat in SECRET_PATTERNS:
                    if pat.search(body):
                        hits.append(f"{os.path.relpath(path, REPO_ROOT)} matches {pat.pattern}")
        self.assertEqual(hits, [], "secret material found: " + "; ".join(hits))


class TestTooling(unittest.TestCase):
    """The backup and topology tools must be present and invocable."""

    def test_backup_script_exists(self):
        path = os.path.join(REPO_ROOT, "scripts", "backup_memory.ps1")
        self.assertTrue(os.path.isfile(path))
        body = read(path)
        self.assertIn("bundle", body)
        self.assertIn("opencode.db", body)

    def test_ram_topology_tool_exists(self):
        path = os.path.join(REPO_ROOT, "bench", "ram_topology.py")
        self.assertTrue(os.path.isfile(path))
        self.assertIn("speedActualMHz", read(path))


if __name__ == "__main__":
    unittest.main()
