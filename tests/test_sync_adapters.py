from pathlib import Path
import json
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SourceLayoutTests(unittest.TestCase):
    def test_version_and_constants_exist(self):
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        constants = json.loads((ROOT / "src/shared/constants.json").read_text(encoding="utf-8"))
        self.assertRegex(version, r"^\d+\.\d+\.\d+$")
        self.assertEqual(constants["version"], version)
        self.assertEqual(constants["plugin_name"], "llm-wiki-client")
        self.assertEqual(constants["marketplace_name"], "llm-wiki-cloud")
        self.assertEqual(constants["mcp_url"], "https://wiki.andykong.top/mcp")
        self.assertEqual(constants["backflow_upload_url"], "https://wiki.andykong.top/upload/backflow")
        self.assertEqual(constants["version_manifest_url"], "https://wiki.andykong.top/plugin/llm-wiki-client/version.json")

    def test_pin_block_template_has_platform_slots(self):
        text = (ROOT / "src/shared/pin-block.md.tmpl").read_text(encoding="utf-8")
        self.assertIn("{{instruction_file}}", text)
        self.assertIn("{{mcp_url}}", text)
        self.assertIn("{{query_skill_name}}", text)
        self.assertIn("{{wiki_search_tool}}", text)
        self.assertIn("{{wiki_get_page_tool}}", text)


if __name__ == "__main__":
    unittest.main()
