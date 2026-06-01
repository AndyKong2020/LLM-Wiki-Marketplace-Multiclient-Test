from pathlib import Path
import json
import re
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


class TemplateInventoryTests(unittest.TestCase):
    def test_skill_templates_do_not_reference_legacy_query_skill(self):
        for path in sorted((ROOT / "src/skills").glob("*/SKILL.md.tmpl")):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("llm-wiki-query", text, path.relative_to(ROOT))

    def test_mount_template_uses_shared_pin_block_contract(self):
        mount_text = (ROOT / "src/skills/llm-wiki-cloud-mount/SKILL.md.tmpl").read_text(encoding="utf-8")
        pin_block_text = (ROOT / "src/shared/pin-block.md.tmpl").read_text(encoding="utf-8")
        self.assertIn("src/shared/pin-block.md.tmpl", mount_text)
        for slot in set(re.findall(r"{{[a-zA-Z0-9_]+}}", pin_block_text)):
            with self.subTest(slot=slot):
                self.assertIn(slot, mount_text)

    def test_skill_templates_have_no_todo_markers(self):
        for path in sorted((ROOT / "src/skills").glob("*/SKILL.md.tmpl")):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("TODO", text, path.relative_to(ROOT))

    def test_required_templates_exist(self):
        required = [
            "src/commands/wiki-cloud-mount.md.tmpl",
            "src/commands/wiki-cloud-backflow.md.tmpl",
            "src/skills/llm-wiki-cloud-mount/SKILL.md.tmpl",
            "src/skills/llm-wiki-cloud-query/SKILL.md.tmpl",
            "src/skills/llm-wiki-cloud-backflow/SKILL.md.tmpl",
            "platforms/claude/marketplace.json.tmpl",
            "platforms/claude/plugin.json.tmpl",
            "platforms/codex/marketplace.json.tmpl",
            "platforms/codex/plugin.json.tmpl",
            "platforms/opencode/opencode.json.tmpl",
            "platforms/opencode/install-opencode.sh.tmpl",
        ]
        for rel in required:
            with self.subTest(rel=rel):
                path = ROOT / rel
                self.assertTrue(path.exists(), rel)
                self.assertGreater(path.stat().st_size, 80, rel)

    def test_skill_templates_have_required_frontmatter_slots(self):
        for rel in [
            "src/skills/llm-wiki-cloud-mount/SKILL.md.tmpl",
            "src/skills/llm-wiki-cloud-query/SKILL.md.tmpl",
            "src/skills/llm-wiki-cloud-backflow/SKILL.md.tmpl",
        ]:
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn("version: {{version}}", text)
            self.assertIn("name:", text)
            self.assertIn("description:", text)


if __name__ == "__main__":
    unittest.main()
