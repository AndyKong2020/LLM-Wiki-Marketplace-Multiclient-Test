from pathlib import Path
import json
import os
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "plugins/llm-wiki-client-opencode/install-opencode.sh"
UNINSTALLER = ROOT / "plugins/llm-wiki-client-opencode/uninstall.sh"
MCP_SERVER_NAME = "cann-infer-wiki-cloud"
MCP_URL = "https://wiki.andykong.top/mcp"


class OpenCodeInstallerTests(unittest.TestCase):
    def run_installer(
        self,
        temp_root: Path,
        prefix: Path,
    ) -> tuple[Path, Path, Path, Path]:
        home = temp_root / "home"
        xdg_config = temp_root / "xdg-config"
        opencode_config = temp_root / "env-opencode-config" / "opencode.json"
        opencode_config_dir = temp_root / "env-opencode-config-dir"
        home.mkdir()
        xdg_config.mkdir()

        env = os.environ.copy()
        env["HOME"] = str(home)
        env["XDG_CONFIG_HOME"] = str(xdg_config)
        env["OPENCODE_CONFIG"] = str(opencode_config)
        env["OPENCODE_CONFIG_DIR"] = str(opencode_config_dir)

        result = subprocess.run(
            ["bash", str(INSTALLER), "--prefix", str(prefix)],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return home, xdg_config, opencode_config, opencode_config_dir

    def assert_env_config_paths_untouched(
        self,
        home: Path,
        xdg_config: Path,
        opencode_config: Path,
        opencode_config_dir: Path,
    ) -> None:
        self.assertFalse((home / ".config/opencode").exists())
        self.assertFalse((xdg_config / "opencode").exists())
        self.assertFalse(opencode_config.exists())
        self.assertFalse(opencode_config.parent.exists())
        self.assertFalse(opencode_config_dir.exists())

    def test_prefix_install_writes_only_requested_opencode_tree(self):
        with tempfile.TemporaryDirectory(prefix="opencode-installer-") as temp_dir:
            temp_root = Path(temp_dir)
            prefix = temp_root / "prefix"

            home, xdg_config, opencode_config, opencode_config_dir = self.run_installer(
                temp_root,
                prefix,
            )

            self.assertEqual(
                {child.name for child in prefix.iterdir()},
                {"skills", "opencode.json"},
            )
            self.assertTrue((prefix / "skills/llm-wiki-cloud-query/SKILL.md").is_file())
            self.assertTrue((prefix / "opencode.json").is_file())
            self.assert_env_config_paths_untouched(
                home,
                xdg_config,
                opencode_config,
                opencode_config_dir,
            )

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

            home, xdg_config, opencode_config, opencode_config_dir = self.run_installer(
                temp_root,
                prefix,
            )

            merged = json.loads((prefix / "opencode.json").read_text(encoding="utf-8"))
            self.assertEqual(merged["$schema"], existing_config["$schema"])
            self.assertEqual(merged["theme"], "legacy-dark")
            self.assertEqual(
                merged["mcp"]["existing-server"],
                existing_config["mcp"]["existing-server"],
            )
            self.assertIn(MCP_SERVER_NAME, merged["mcp"])
            self.assertEqual(
                merged["mcp"][MCP_SERVER_NAME],
                {"type": "remote", "url": MCP_URL, "enabled": True},
            )
            self.assert_env_config_paths_untouched(
                home,
                xdg_config,
                opencode_config,
                opencode_config_dir,
            )

    def test_uninstall_removes_only_llm_wiki_files_and_mcp_entry(self):
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
            self.run_installer(temp_root, prefix)

            result = subprocess.run(
                ["bash", str(UNINSTALLER), "--prefix", str(prefix)],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            self.assertFalse((prefix / "skills/llm-wiki-cloud-mount").exists())
            self.assertFalse((prefix / "skills/llm-wiki-cloud-query").exists())
            self.assertFalse((prefix / "skills/llm-wiki-cloud-backflow").exists())

            config = json.loads((prefix / "opencode.json").read_text(encoding="utf-8"))
            self.assertEqual(config["theme"], "legacy-dark")
            self.assertEqual(config["mcp"]["existing-server"], existing_config["mcp"]["existing-server"])
            self.assertNotIn(MCP_SERVER_NAME, config["mcp"])


if __name__ == "__main__":
    unittest.main()
