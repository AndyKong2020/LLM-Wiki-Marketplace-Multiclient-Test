#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_MCP_URL = "https://wiki.andykong.top/mcp"
SEMVER_RE = re.compile(r"\d+\.\d+\.\d+")
OPENCODE_SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
TOKEN_RE = re.compile(r"\bllmw_(?!<token-from-operator>)(?!token-from-operator\b)[A-Za-z0-9_=-]{12,}\b")

JSON_FILES = [
    ".claude-plugin/marketplace.json",
    ".agents/plugins/marketplace.json",
    "plugins/llm-wiki-client/.claude-plugin/plugin.json",
    "plugins/llm-wiki-client/.codex-plugin/plugin.json",
    "plugins/llm-wiki-client/.mcp.json",
    "dist/opencode/opencode.json",
]
GENERATED_SCAN_ROOTS = [
    ".claude-plugin",
    ".agents",
    "plugins/llm-wiki-client",
    "dist/opencode",
]
GENERATED_DIFF_PATHS = [
    ".claude-plugin",
    ".agents",
    "plugins/llm-wiki-client",
    "dist/opencode",
]
SKILL_ROOTS = [
    "plugins/llm-wiki-client/skills",
    "plugins/llm-wiki-client/codex/skills",
    "dist/opencode/.opencode/skills",
]
MOUNT_SKILLS = [
    "plugins/llm-wiki-client/skills/llm-wiki-cloud-mount/SKILL.md",
    "plugins/llm-wiki-client/codex/skills/llm-wiki-cloud-mount/SKILL.md",
    "dist/opencode/.opencode/skills/llm-wiki-cloud-mount/SKILL.md",
]
COMMAND_DIRS = [
    "plugins/llm-wiki-client/commands",
    "dist/opencode/.opencode/commands",
]
EXPECTED_COMMANDS = {"wiki-cloud-mount.md", "wiki-cloud-backflow.md"}
SKIP_TOKEN_PARTS = {".git", ".idea"}
SKIP_TOKEN_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".bmp", ".tiff"}


class ValidationError(Exception):
    pass


def fail(message: str) -> None:
    raise ValidationError(message)


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_text(relative_path: str) -> str:
    path = ROOT / relative_path
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        fail(f"missing file: {relative_path}")
    except UnicodeDecodeError as exc:
        fail(f"invalid UTF-8 in {relative_path}: {exc}")
    raise AssertionError("unreachable")


def read_version() -> str:
    version = read_text("VERSION").strip()
    if not SEMVER_RE.fullmatch(version):
        fail(f"invalid VERSION semver: {version}")
    return version


def load_json(relative_path: str) -> Any:
    try:
        return json.loads(read_text(relative_path))
    except json.JSONDecodeError as exc:
        fail(f"invalid JSON in {relative_path}: {exc.msg}")


def load_json_files() -> dict[str, Any]:
    return {relative_path: load_json(relative_path) for relative_path in JSON_FILES}


def require_dict(data: Any, relative_path: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        fail(f"expected JSON object in {relative_path}")
    return data


def get_plugin_version_from_claude_marketplace(data: Any) -> str:
    marketplace = require_dict(data, ".claude-plugin/marketplace.json")
    plugins = marketplace.get("plugins")
    if not isinstance(plugins, list) or not plugins:
        fail("Claude marketplace has no plugins")
    plugin = plugins[0]
    if not isinstance(plugin, dict):
        fail("Claude marketplace plugin entry is not an object")
    version = plugin.get("version")
    if not isinstance(version, str):
        fail("Claude marketplace plugin version missing")
    return version


def get_manifest_version(data: Any, relative_path: str) -> str:
    manifest = require_dict(data, relative_path)
    version = manifest.get("version")
    if not isinstance(version, str):
        fail(f"version missing in {relative_path}")
    return version


def parse_frontmatter(relative_path: str) -> dict[str, str]:
    text = read_text(relative_path)
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        fail(f"frontmatter missing in {relative_path}")

    fields: dict[str, str] = {}
    for line in lines[1:]:
        if line == "---":
            return fields
        if ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()

    fail(f"frontmatter terminator missing in {relative_path}")


def iter_skill_files(skill_root: str) -> list[str]:
    root = ROOT / skill_root
    if not root.is_dir():
        fail(f"missing skill root: {skill_root}")
    skill_files = sorted(path for path in root.glob("*/SKILL.md") if path.is_file())
    if not skill_files:
        fail(f"no generated skills in {skill_root}")
    return [rel(path) for path in skill_files]


def check_versions(version: str, json_data: dict[str, Any]) -> None:
    version_checks = {
        ".claude-plugin/marketplace.json": get_plugin_version_from_claude_marketplace(
            json_data[".claude-plugin/marketplace.json"]
        ),
        "plugins/llm-wiki-client/.claude-plugin/plugin.json": get_manifest_version(
            json_data["plugins/llm-wiki-client/.claude-plugin/plugin.json"],
            "plugins/llm-wiki-client/.claude-plugin/plugin.json",
        ),
        "plugins/llm-wiki-client/.codex-plugin/plugin.json": get_manifest_version(
            json_data["plugins/llm-wiki-client/.codex-plugin/plugin.json"],
            "plugins/llm-wiki-client/.codex-plugin/plugin.json",
        ),
    }
    for relative_path, actual in version_checks.items():
        if actual != version:
            fail(f"version mismatch in {relative_path}: {actual} != {version}")

    for skill_root in SKILL_ROOTS:
        for skill_file in iter_skill_files(skill_root):
            skill_version = parse_frontmatter(skill_file).get("version")
            if skill_version != version:
                fail(f"skill version mismatch in {skill_file}: {skill_version} != {version}")


def check_codex_manifest_skill_root(json_data: dict[str, Any]) -> None:
    relative_path = "plugins/llm-wiki-client/.codex-plugin/plugin.json"
    manifest = require_dict(json_data[relative_path], relative_path)
    actual = manifest.get("skills")
    expected = "./codex/skills/"
    if actual != expected:
        fail(f"Codex manifest skill root mismatch in {relative_path}: {actual} != {expected}")


def check_canonical_mcp_url(json_data: dict[str, Any]) -> None:
    mcp_config = json.dumps(json_data["plugins/llm-wiki-client/.mcp.json"], ensure_ascii=False)
    if CANONICAL_MCP_URL not in mcp_config:
        fail("canonical mcp url missing in plugins/llm-wiki-client/.mcp.json")

    opencode_config = json.dumps(json_data["dist/opencode/opencode.json"], ensure_ascii=False)
    if CANONICAL_MCP_URL not in opencode_config:
        fail("canonical mcp url missing in dist/opencode/opencode.json")

    for mount_skill in MOUNT_SKILLS:
        if CANONICAL_MCP_URL not in read_text(mount_skill):
            fail(f"canonical mcp url missing in {mount_skill}")


def check_opencode_skill_names() -> None:
    root = ROOT / "dist/opencode/.opencode/skills"
    if not root.is_dir():
        fail("missing OpenCode skill root: dist/opencode/.opencode/skills")
    for skill_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        if not OPENCODE_SKILL_NAME_RE.fullmatch(skill_dir.name):
            fail(f"invalid OpenCode skill directory name: {skill_dir.name}")
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.is_file():
            fail(f"missing OpenCode skill file: {rel(skill_file)}")
        name = parse_frontmatter(rel(skill_file)).get("name")
        if name != skill_dir.name:
            fail(f"OpenCode skill name mismatch in {rel(skill_file)}: {name} != {skill_dir.name}")
        if not OPENCODE_SKILL_NAME_RE.fullmatch(name):
            fail(f"invalid OpenCode skill name: {name}")


def check_command_directories() -> None:
    for command_dir in COMMAND_DIRS:
        root = ROOT / command_dir
        if not root.is_dir():
            fail(f"missing command directory: {command_dir}")
        actual = {path.name for path in root.iterdir()}
        if actual != EXPECTED_COMMANDS:
            fail(f"unexpected commands in {command_dir}: {sorted(actual)}")


def check_no_unrendered_templates() -> None:
    for scan_root in GENERATED_SCAN_ROOTS:
        root = ROOT / scan_root
        if not root.exists():
            fail(f"missing generated root: {scan_root}")
        for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "{{" in text or "}}" in text:
                fail(f"unrendered template marker in {rel(path)}")


def should_skip_token_scan(path: Path) -> bool:
    if not path.is_file():
        return True
    if any(part in SKIP_TOKEN_PARTS for part in path.parts):
        return True
    return path.suffix.lower() in SKIP_TOKEN_SUFFIXES


def check_no_token_like_strings() -> None:
    for path in sorted(ROOT.rglob("*")):
        if should_skip_token_scan(path):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if TOKEN_RE.search(text):
            fail(f"token-like string in {rel(path)}")


def git_diff_quiet() -> int:
    result = subprocess.run(["git", "diff", "--quiet", "--", *GENERATED_DIFF_PATHS], cwd=ROOT)
    return result.returncode


def check_git_diff_result(returncode: int, stage: str) -> bool:
    if returncode == 0:
        return False
    if returncode == 1:
        return True
    fail(f"git diff failed during {stage} generated check with exit code {returncode}")


def run_sync_adapters() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/sync_adapters.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        if detail:
            fail(f"sync_adapters.py failed: {detail}")
        fail(f"sync_adapters.py failed with exit code {result.returncode}")


def check_generated_files_current() -> None:
    stale_before_sync = check_git_diff_result(git_diff_quiet(), "pre-sync")
    run_sync_adapters()
    stale_after_sync = check_git_diff_result(git_diff_quiet(), "post-sync")
    if stale_before_sync or stale_after_sync:
        fail("generated files are stale")


def validate() -> None:
    version = read_version()
    json_data = load_json_files()
    check_versions(version, json_data)
    check_codex_manifest_skill_root(json_data)
    check_canonical_mcp_url(json_data)
    check_opencode_skill_names()
    check_command_directories()
    check_no_unrendered_templates()
    check_no_token_like_strings()
    check_generated_files_current()


def main() -> int:
    try:
        validate()
    except ValidationError as exc:
        print(f"validate_release=failed reason={exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"validate_release=failed reason=unexpected {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print("validate_release=ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
