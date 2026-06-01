from pathlib import Path
import json
import os
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "dist/opencode/install-opencode.sh"
MCP_SERVER_NAME = "cann-infer-wiki-cloud"
MCP_URL = "https://wiki.andykong.top/mcp"


class OpenCodeInstallerTests(unittest.TestCase):
    def run_installer(self, temp_root: Path, prefix: Path) -> tuple[Path, Path]:
        home = temp_root / "home"
        xdg_config = temp_root / "xdg-config"
        home.mkdir()
        xdg_config.mkdir()

        env = os.environ.copy()
        env["HOME"] = str(home)
        env["XDG_CONFIG_HOME"] = str(xdg_config)

        result = subprocess.run(
            ["bash", str(INSTALLER), "--prefix", str(prefix)],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return home, xdg_config

    def test_prefix_install_writes_only_requested_opencode_tree(self):
        with tempfile.TemporaryDirectory(prefix="opencode-installer-") as temp_dir:
            temp_root = Path(temp_dir)
            prefix = temp_root / "prefix"

            home, xdg_config = self.run_installer(temp_root, prefix)

            self.assertEqual(
                {child.name for child in prefix.iterdir()},
                {"commands", "skills", "opencode.json"},
            )
            self.assertTrue((prefix / "commands/wiki-cloud-mount.md").is_file())
            self.assertTrue((prefix / "commands/wiki-cloud-backflow.md").is_file())
            self.assertTrue((prefix / "skills/llm-wiki-cloud-query/SKILL.md").is_file())
            self.assertTrue((prefix / "opencode.json").is_file())
            self.assertFalse((home / ".config/opencode").exists())
            self.assertFalse((xdg_config / "opencode").exists())

    def test_existing_opencode_mcp_config_is_preserved_and_merged(self):
        with tempfile.TemporaryDirectory(prefix="opencode-installer-") as temp_dir:
            temp_root = Path(temp_dir)
            prefix = temp_root / "prefix"
            prefix.mkdir()
            existing_config = {
                "$schema": "https://opencode.ai/config.json",
                "theme": "legacy-dark",
                "mcp": {
                    "existing-server": {
                        "type": "stdio",
                        "command": ["run-existing-server"],
                        "enabled": False,
                    }
                },
            }
            (prefix / "opencode.json").write_text(
                json.dumps(existing_config, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            home, xdg_config = self.run_installer(temp_root, prefix)

            merged = json.loads((prefix / "opencode.json").read_text(encoding="utf-8"))
            self.assertEqual(merged["theme"], "legacy-dark")
            self.assertEqual(
                merged["mcp"]["existing-server"],
                existing_config["mcp"]["existing-server"],
            )
            self.assertIn(MCP_SERVER_NAME, merged["mcp"])
            self.assertEqual(merged["mcp"][MCP_SERVER_NAME]["url"], MCP_URL)
            self.assertIs(merged["mcp"][MCP_SERVER_NAME]["enabled"], True)
            self.assertFalse((home / ".config/opencode").exists())
            self.assertFalse((xdg_config / "opencode").exists())


if __name__ == "__main__":
    unittest.main()
