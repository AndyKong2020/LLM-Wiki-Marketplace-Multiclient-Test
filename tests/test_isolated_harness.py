from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "scripts/test_isolated_clients.py"


def load_harness():
    spec = importlib.util.spec_from_file_location("isolated_clients_harness", HARNESS)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class IsolatedHarnessTests(unittest.TestCase):
    def test_tree_digest_handles_missing_files_directories_and_symlinks(self):
        harness = load_harness()
        with tempfile.TemporaryDirectory(prefix="isolated-harness-test-") as temp_dir:
            root = Path(temp_dir)
            missing = root / "missing"
            self.assertEqual(harness.tree_digest(missing), "missing")

            file_path = root / "config.json"
            file_path.write_text("one\n", encoding="utf-8")
            first_file_digest = harness.tree_digest(file_path)
            file_path.write_text("two\n", encoding="utf-8")
            self.assertNotEqual(first_file_digest, harness.tree_digest(file_path))

            outside = root / "outside.txt"
            outside.write_text("outside-one\n", encoding="utf-8")
            tree = root / "tree"
            tree.mkdir()
            (tree / "inside.txt").write_text("inside\n", encoding="utf-8")
            (tree / "outside-link").symlink_to(outside)
            first_tree_digest = harness.tree_digest(tree)
            outside.write_text("outside-two\n", encoding="utf-8")

            self.assertEqual(first_tree_digest, harness.tree_digest(tree))

    def test_snapshot_global_configs_covers_codex_sessions(self):
        harness = load_harness()
        with tempfile.TemporaryDirectory(prefix="isolated-harness-test-") as temp_dir:
            root = Path(temp_dir)
            codex_home = root / ".codex"
            sessions = codex_home / "sessions"
            sessions.mkdir(parents=True)
            harness.GLOBAL_PATHS = [codex_home]

            before = harness.snapshot_global_configs()
            before_digest = harness.tree_digest(codex_home)
            (sessions / "x").write_text("session\n", encoding="utf-8")

            self.assertNotEqual(before, harness.snapshot_global_configs())
            self.assertNotEqual(before_digest, harness.tree_digest(codex_home))

    def test_unmarked_codex_plugins_change_is_unexpected(self):
        harness = load_harness()
        with tempfile.TemporaryDirectory(prefix="isolated-harness-test-") as temp_dir:
            root = Path(temp_dir)
            codex_home = root / ".codex"
            codex_home.mkdir()
            harness.GLOBAL_PATHS = [codex_home]

            before = harness.snapshot_global_configs()
            plugins = codex_home / "plugins"
            plugins.mkdir()
            (plugins / "probe").write_text("global pollution\n", encoding="utf-8")
            after = harness.snapshot_global_configs()

            unexpected = harness.unexpected_global_config_changes(
                before,
                after,
                {str(codex_home): {"sessions"}},
            )
            self.assertIn(str(codex_home), unexpected)
            self.assertIn("plugins/probe", unexpected[str(codex_home)])

    def test_volatile_codex_sessions_change_is_allowed(self):
        harness = load_harness()
        with tempfile.TemporaryDirectory(prefix="isolated-harness-test-") as temp_dir:
            root = Path(temp_dir)
            codex_home = root / ".codex"
            sessions = codex_home / "sessions"
            sessions.mkdir(parents=True)
            harness.GLOBAL_PATHS = [codex_home]

            probe_before = harness.snapshot_global_configs()
            (sessions / "during-probe").write_text("external\n", encoding="utf-8")
            probe_after = harness.snapshot_global_configs()
            volatile = harness.detect_volatile_top_levels(probe_before, probe_after)

            before = harness.snapshot_global_configs()
            (sessions / "after-probe").write_text("external later\n", encoding="utf-8")
            after = harness.snapshot_global_configs()

            self.assertEqual({str(codex_home): {"sessions"}}, volatile)
            self.assertEqual({}, harness.unexpected_global_config_changes(before, after, volatile))

    def test_strict_global_digest_reports_volatile_changes(self):
        harness = load_harness()
        with tempfile.TemporaryDirectory(prefix="isolated-harness-test-") as temp_dir:
            root = Path(temp_dir)
            codex_home = root / ".codex"
            sessions = codex_home / "sessions"
            sessions.mkdir(parents=True)
            harness.GLOBAL_PATHS = [codex_home]

            before = harness.snapshot_global_configs()
            (sessions / "x").write_text("session\n", encoding="utf-8")
            after = harness.snapshot_global_configs()

            unexpected = harness.unexpected_global_config_changes(
                before,
                after,
                {str(codex_home): {"sessions"}},
                strict_global_digest=True,
            )
            self.assertIn(str(codex_home), unexpected)
            self.assertIn("sessions/x", unexpected[str(codex_home)])

    def test_isolated_env_redirects_all_client_config_paths(self):
        harness = load_harness()
        with tempfile.TemporaryDirectory(prefix="isolated-harness-test-") as temp_dir:
            root = Path(temp_dir)
            env = harness.isolated_env(root, "http://127.0.0.1:12345/upload/backflow")

            path_keys = [
                "HOME",
                "XDG_CONFIG_HOME",
                "XDG_DATA_HOME",
                "CODEX_HOME",
                "OPENCODE_CONFIG",
                "OPENCODE_CONFIG_DIR",
                "CLAUDE_CONFIG_DIR",
            ]
            for key in path_keys:
                self.assertTrue(Path(env[key]).is_relative_to(root), key)

            self.assertEqual(env["LLM_WIKI_UPLOAD_URL"], "http://127.0.0.1:12345/upload/backflow")
            self.assertEqual(env["LLM_WIKI_UPLOAD_TOKEN"], "llmw_test_token")

    def test_mock_backflow_server_accepts_local_uploads(self):
        harness = load_harness()
        server, upload_url = harness.start_mock_server()
        try:
            self.assertTrue(upload_url.startswith("http://127.0.0.1:"))
            request = urllib.request.Request(
                upload_url,
                data=b'{"hello":"world"}',
                headers={"content-type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=5) as response:
                body = json.loads(response.read().decode("utf-8"))

            self.assertEqual(response.status, 200)
            self.assertEqual(body["status"], "ok")
            self.assertEqual(body["id"], "test-backflow-id")
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
