from pathlib import Path
import json
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ValidateReleaseTests(unittest.TestCase):
    def test_validate_release_passes_after_sync(self):
        subprocess.run(["python3", "scripts/sync_adapters.py"], cwd=ROOT, check=True)
        result = subprocess.run(["python3", "scripts/validate_release.py"], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("validate_release=ok", result.stdout)

    def test_token_scan_rejects_realistic_secret(self):
        bad = ROOT / ".llm-wiki-test-secret.txt"
        token_prefix = "llmw_"
        token_body = "real_secret_value_123456"
        bad.write_text(f"LLM_WIKI_UPLOAD_TOKEN={token_prefix}{token_body}\n", encoding="utf-8")
        try:
            result = subprocess.run(["python3", "scripts/validate_release.py"], cwd=ROOT, text=True, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("token-like string", result.stdout + result.stderr)
        finally:
            bad.unlink()

    def test_validate_release_rejects_stale_generated_files(self):
        subprocess.run(["python3", "scripts/sync_adapters.py"], cwd=ROOT, check=True)
        generated = ROOT / "plugins/llm-wiki-client/skills/llm-wiki-cloud-query/SKILL.md"
        original = generated.read_text(encoding="utf-8")
        generated.write_text(original + "\n<!-- stale generated validator probe -->\n", encoding="utf-8")
        try:
            result = subprocess.run(["python3", "scripts/validate_release.py"], cwd=ROOT, text=True, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("generated files are stale", result.stdout + result.stderr)
        finally:
            subprocess.run(["python3", "scripts/sync_adapters.py"], cwd=ROOT, check=True)

    def test_validate_release_checks_codex_manifest_skill_root(self):
        subprocess.run(["python3", "scripts/sync_adapters.py"], cwd=ROOT, check=True)
        manifest = ROOT / "plugins/llm-wiki-client/.codex-plugin/plugin.json"
        data = json.loads(manifest.read_text(encoding="utf-8"))
        data["skills"] = "./skills/"
        manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        try:
            result = subprocess.run(["python3", "scripts/validate_release.py"], cwd=ROOT, text=True, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Codex manifest skill root", result.stdout + result.stderr)
        finally:
            subprocess.run(["python3", "scripts/sync_adapters.py"], cwd=ROOT, check=True)

    def test_validate_release_rejects_readme_install_command_name_mismatch(self):
        readme = ROOT / "README.md"
        original = readme.read_text(encoding="utf-8")
        marketplace = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
        expected = f"/plugin install {marketplace['plugins'][0]['name']}@{marketplace['name']}"
        self.assertIn(expected, original)
        readme.write_text(
            original.replace(expected, f"/plugin install wrong-client@{marketplace['name']}", 1),
            encoding="utf-8",
        )
        try:
            result = subprocess.run(["python3", "scripts/validate_release.py"], cwd=ROOT, text=True, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("README install command", result.stdout + result.stderr)
        finally:
            readme.write_text(original, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
