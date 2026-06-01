# 多客户端分发 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把当前 Claude Code-only marketplace 仓库改造成一套源文件生成 Claude Code、Codex、OpenCode 三端适配包，并用隔离测试仓库验证 mount、query、backflow 的安装与运行边界。

**Architecture:** `src/` 和 `platforms/` 保存唯一可编辑源头；`scripts/sync_adapters.py` 生成 `plugins/llm-wiki-client/`、`.claude-plugin/marketplace.json`、`.agents/plugins/marketplace.json` 和 `dist/opencode/`；`scripts/validate_release.py` 与 `scripts/test_isolated_clients.py` 做发布和隔离测试。所有测试默认只写入临时目录，生产远端只在验收后人工推送。

**Tech Stack:** Python 3 标准库、Markdown/YAML frontmatter 文本模板、JSON manifest、shell installer、`unittest`、`git`、`gh`、Claude Code CLI、Codex CLI、OpenCode CLI。

---

## 文件结构

- Create: `VERSION`  
  单一版本源，初始写入当前发布版本 `1.1.6`。
- Create: `src/shared/constants.json`  
  保存 plugin 名称、marketplace 名称、canonical URL、测试仓库名和版本文件 URL。
- Create: `src/shared/pin-block.md.tmpl`  
  保存平台无关的 LLM-WIKI pin block 模板，按平台生成 `CLAUDE.md` 或 `AGENTS.md` 使用说明。
- Create: `src/commands/wiki-cloud-mount.md.tmpl`  
  command 源模板，生成 Claude/OpenCode command。
- Create: `src/commands/wiki-cloud-backflow.md.tmpl`  
  command 源模板，生成 Claude/OpenCode command。
- Create: `src/skills/llm-wiki-cloud-mount/SKILL.md.tmpl`  
  mount skill 源模板，包含平台变量和目标指令文件变量。
- Create: `src/skills/llm-wiki-cloud-query/SKILL.md.tmpl`  
  query skill 源模板，去掉 Claude 专属 MCP tool 名，改为 logical tool 描述。
- Create: `src/skills/llm-wiki-cloud-backflow/SKILL.md.tmpl`  
  backflow skill 源模板，保留 token 安全、mock upload 和 archive 约束。
- Create: `platforms/claude/marketplace.json.tmpl`  
  Claude marketplace manifest 模板。
- Create: `platforms/claude/plugin.json.tmpl`  
  Claude plugin manifest 模板。
- Create: `platforms/codex/marketplace.json.tmpl`  
  Codex marketplace manifest 模板。
- Create: `platforms/codex/plugin.json.tmpl`  
  Codex plugin manifest 模板。
- Create: `platforms/opencode/opencode.json.tmpl`  
  OpenCode remote MCP config 模板。
- Create: `platforms/opencode/install-opencode.sh.tmpl`  
  OpenCode installer 模板，支持 `--prefix` 和 dry-run 测试根目录。
- Create: `scripts/sync_adapters.py`  
  读取 `VERSION`、`constants.json` 和模板，生成三端适配文件。
- Create: `scripts/validate_release.py`  
  静态校验版本、JSON、生成产物、URL、命令名、token 泄露和 marketplace 结构。
- Create: `scripts/allocate_test_port.py`  
  为 mock backflow server 分配本地端口。
- Create: `scripts/test_isolated_clients.py`  
  运行隔离静态测试、installer 测试、mock backflow 测试和 CLI 可见性检查。
- Create: `tests/test_sync_adapters.py`  
  单元测试生成器。
- Create: `tests/test_validate_release.py`  
  单元测试发布校验器。
- Create: `tests/test_opencode_installer.py`  
  单元测试 OpenCode installer 写入范围和 JSON merge 行为。
- Modify: `.gitignore`  
  排除测试临时目录和 Python 缓存。
- Modify: `README.md`  
  增加三端安装、更新、使用、测试仓库说明。
- Modify: `plugins/llm-wiki-client/README.md`  
  增加 Codex/OpenCode 适配说明，并声明该目录由生成器维护。
- Generated modify: `.claude-plugin/marketplace.json`
- Generated create: `.agents/plugins/marketplace.json`
- Generated modify: `plugins/llm-wiki-client/.claude-plugin/plugin.json`
- Generated create: `plugins/llm-wiki-client/.codex-plugin/plugin.json`
- Generated modify: `plugins/llm-wiki-client/.mcp.json`
- Generated modify: `plugins/llm-wiki-client/commands/wiki-cloud-mount.md`
- Generated modify: `plugins/llm-wiki-client/commands/wiki-cloud-backflow.md`
- Generated modify: `plugins/llm-wiki-client/skills/*/SKILL.md`
- Generated create: `dist/opencode/opencode.json`
- Generated create: `dist/opencode/install-opencode.sh`
- Generated create: `dist/opencode/.opencode/commands/*.md`
- Generated create: `dist/opencode/.opencode/skills/*/SKILL.md`

## 实施策略

- 每个 task 都先写测试，再实现。
- 每个 task 完成后运行该 task 的最小验证命令。
- 每个 task 完成后提交一次 commit，全部只推 `multiclient-test`。
- 不运行会写入真实 `~/.claude`、`~/.codex`、`~/.agents`、`~/.config/opencode` 的命令；所有客户端测试必须显式设置临时 HOME/XDG/CODEX/OPENCODE 环境。

---

### Task 1: 建立源目录、常量和基础测试骨架

**Files:**
- Create: `VERSION`
- Create: `src/shared/constants.json`
- Create: `src/shared/pin-block.md.tmpl`
- Create: `tests/test_sync_adapters.py`
- Modify: `.gitignore`

- [ ] **Step 1: 写失败测试，要求基础源文件存在且常量一致**

```python
# tests/test_sync_adapters.py
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
```

- [ ] **Step 2: 运行测试，确认失败**

Run:

```bash
python3 -m unittest tests.test_sync_adapters -v
```

Expected:

```text
FileNotFoundError
FAILED
```

- [ ] **Step 3: 创建版本和常量文件**

```text
# VERSION
1.1.6
```

```json
{
  "version": "1.1.6",
  "marketplace_name": "llm-wiki-cloud",
  "plugin_name": "llm-wiki-client",
  "mcp_server_name": "cann-infer-wiki-cloud",
  "mcp_url": "https://wiki.andykong.top/mcp",
  "backflow_upload_url": "https://wiki.andykong.top/upload/backflow",
  "assets_base_url": "https://wiki.andykong.top/assets/",
  "version_manifest_url": "https://wiki.andykong.top/plugin/llm-wiki-client/version.json",
  "test_repository": "AndyKong2020/LLM-Wiki-Marketplace-Multiclient-Test"
}
```

- [ ] **Step 4: 创建 pin-block 模板**

```md
<!-- LLM-WIKI:BEGIN -->
本项目已挂载云端 CANN-Infer-Wiki（NPU 大模型推理优化知识库）。
instruction_file: {{instruction_file}}
mcp_server: {{mcp_server_name}}
mcp_url: {{mcp_url}}

涉及下列任务时必须使用 {{query_skill_name}} skill：
- 大模型推理优化任务：model / kernel / parallelism / module / framework / technique / quantization / platform
  （模型族 qwen3-moe / deepseek-r1 / hunyuan-* / longcat-* / kimi-k2 等；算子 fia / mla / dia / sparse-flash-attention 等；并行 tp / dp / cp / ep / zigzag-cp / ulysses 等；框架 sglang / torchair / pypto / ascendc / atb / catlass / tilelang 等；技术 npu-graph-mode / weight-prefetch / superkernel / afd 等；量化 w8a8c8 / w4a8c8 / mxfp8 / fp8-attention 等；平台 atlas-a3 / ascend910 等）
- 进入新优化阶段、做方案分析、策略选择、debug 调试、性能/精度回归归因时

涉及 subagent 时，必须将 {{query_skill_name}} skill 的使用说明注入到拉起 subagent 的 prompt 中。

知识检索一律通过 {{mcp_server_name}} MCP 工具：{{wiki_search_tool}}、{{wiki_get_page_tool}}。
需要引用图片时，使用 wiki_get_page 返回 content 中的 /assets HTTP URL 或 assets manifest。

每次使用 {{query_skill_name}} 后，必须把页面级记录写到当前阶段 progress.md 同级的 wiki_usage.md，并把查询摘要同步写入 progress.md。
<!-- LLM-WIKI:END -->
```

- [ ] **Step 5: 更新 `.gitignore`**

Append:

```gitignore
__pycache__/
*.pyc
.pytest_cache/
.llm-wiki-test-root/
```

- [ ] **Step 6: 运行测试，确认通过**

Run:

```bash
python3 -m unittest tests.test_sync_adapters -v
```

Expected:

```text
Ran 2 tests
OK
```

- [ ] **Step 7: 提交**

```bash
git add VERSION src/shared/constants.json src/shared/pin-block.md.tmpl tests/test_sync_adapters.py .gitignore
git commit -m "test: define multi-client source layout"
```

---

### Task 2: 添加平台模板和生成器测试

**Files:**
- Create: `src/commands/wiki-cloud-mount.md.tmpl`
- Create: `src/commands/wiki-cloud-backflow.md.tmpl`
- Create: `src/skills/llm-wiki-cloud-mount/SKILL.md.tmpl`
- Create: `src/skills/llm-wiki-cloud-query/SKILL.md.tmpl`
- Create: `src/skills/llm-wiki-cloud-backflow/SKILL.md.tmpl`
- Create: `platforms/claude/marketplace.json.tmpl`
- Create: `platforms/claude/plugin.json.tmpl`
- Create: `platforms/codex/marketplace.json.tmpl`
- Create: `platforms/codex/plugin.json.tmpl`
- Create: `platforms/opencode/opencode.json.tmpl`
- Create: `platforms/opencode/install-opencode.sh.tmpl`
- Modify: `tests/test_sync_adapters.py`

- [ ] **Step 1: 扩展测试，要求模板存在且不含未渲染平台关键字段缺失**

Append to `tests/test_sync_adapters.py`:

```python
class TemplateInventoryTests(unittest.TestCase):
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
```

- [ ] **Step 2: 运行测试，确认失败**

Run:

```bash
python3 -m unittest tests.test_sync_adapters -v
```

Expected:

```text
FAIL: test_required_templates_exist
```

- [ ] **Step 3: 创建 command 模板**

`src/commands/wiki-cloud-mount.md.tmpl`:

```md
---
description: 为当前项目挂载云端 CANN-Infer-Wiki MCP（验证远程工具 + 写入 {{instruction_file}} pin block）
allowed-tools: Bash Read Edit Write {{wiki_search_tool}}
---

使用 `llm-wiki-cloud-mount` skill 为当前项目执行 mount。

不要解析命令参数。MCP 客户端配置由插件或平台 adapter 自带，URL 固定为云端 `{{mcp_url}}`；本 command 不 clone wiki 仓、不启动本机 server、不做端口探测。

mount 的执行步骤、版本检查、远程 MCP probe、pin block 内容、结果汇报全部以 `llm-wiki-cloud-mount` skill 为准。
```

`src/commands/wiki-cloud-backflow.md.tmpl`:

```md
---
description: 创建本地 CANN-Infer-Wiki backflow archive；归档汇报后如用户确认且配置 LLM_WIKI_UPLOAD_TOKEN 则上传，否则仅归档
allowed-tools: Bash Read Write
---

使用 `llm-wiki-cloud-backflow` skill 为当前任务创建本地 backflow archive。

本 command 不直接解析参数。`llm-wiki-cloud-backflow` skill 会创建本地归档并先汇报 archive summary；只有用户确认继续且配置了 `LLM_WIKI_UPLOAD_TOKEN`，才把归档打成 tar.gz 并上传到 `{{backflow_upload_url}}`。如果未配置 token，则只创建本地 archive 并提示如何配置。

不要解析命令参数。`task-slug` 和 workspace 由 `llm-wiki-cloud-backflow` skill 根据当前任务上下文判断；上传 `slug` 直接用 task-slug。
```

- [ ] **Step 4: 创建 skill 模板，先复制现有正文再替换平台变量**

Implementation notes:

```text
从 plugins/llm-wiki-client/skills/*/SKILL.md 复制现有正文到 src/skills/*/SKILL.md.tmpl。
替换：
- version: 1.1.6 -> version: {{version}}
- https://wiki.andykong.top/mcp -> {{mcp_url}}
- https://wiki.andykong.top/upload/backflow -> {{backflow_upload_url}}
- https://wiki.andykong.top/plugin/llm-wiki-client/version.json -> {{version_manifest_url}}
- CLAUDE.md -> {{instruction_file}}，只在明确描述 Claude Code 的地方保留 Claude Code
- mcp__plugin_llm-wiki-client_cann-infer-wiki-cloud__wiki_search -> {{wiki_search_tool}}
- mcp__plugin_llm-wiki-client_cann-infer-wiki-cloud__wiki_get_page -> {{wiki_get_page_tool}}
```

Required frontmatter for `src/skills/llm-wiki-cloud-query/SKILL.md.tmpl`:

```yaml
---
name: llm-wiki-cloud-query
description: 查询和运行时消费已挂载的 CANN-Infer-Wiki（通过 MCP）。进入新的 LLM/NPU 推理优化阶段、做方案分析、策略选择、debug 调试、性能/精度回归分析；涉及具体 model / kernel / parallelism / module / framework / technique / quantization / platform 知识、或动态层任务回流型经验时使用。
allowed-tools: Bash Read Edit Write {{wiki_search_tool}} {{wiki_get_page_tool}}
version: {{version}}
---
```

- [ ] **Step 5: 创建 manifest/config 模板**

`platforms/codex/marketplace.json.tmpl`:

```json
{
  "name": "{{marketplace_name}}",
  "interface": {
    "displayName": "LLM Wiki Cloud"
  },
  "plugins": [
    {
      "name": "{{plugin_name}}",
      "source": {
        "source": "local",
        "path": "./plugins/{{plugin_name}}"
      },
      "policy": {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL"
      },
      "category": "Developer Tools"
    }
  ]
}
```

`platforms/opencode/opencode.json.tmpl`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "{{mcp_server_name}}": {
      "type": "remote",
      "url": "{{mcp_url}}",
      "enabled": true
    }
  }
}
```

- [ ] **Step 6: 创建 OpenCode installer 模板**

`platforms/opencode/install-opencode.sh.tmpl`:

```bash
#!/usr/bin/env bash
set -euo pipefail

prefix="${HOME}/.config/opencode"
dry_run=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prefix)
      prefix="$2"
      shift 2
      ;;
    --dry-run)
      dry_run=1
      shift
      ;;
    *)
      echo "unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
source_root="${script_dir}"

if [ "$dry_run" = "1" ]; then
  echo "install_prefix=${prefix}"
  echo "source_root=${source_root}"
  exit 0
fi

mkdir -p "${prefix}/commands" "${prefix}/skills"
cp -R "${source_root}/.opencode/commands/." "${prefix}/commands/"
cp -R "${source_root}/.opencode/skills/." "${prefix}/skills/"

python3 - "$prefix" "${source_root}/opencode.json" <<'PY'
import json
import sys
from pathlib import Path

prefix = Path(sys.argv[1])
source_config = Path(sys.argv[2])
target = prefix / "opencode.json"

incoming = json.loads(source_config.read_text(encoding="utf-8"))
if target.exists():
    merged = json.loads(target.read_text(encoding="utf-8"))
else:
    merged = {"$schema": "https://opencode.ai/config.json"}

merged.setdefault("mcp", {})
merged["mcp"].update(incoming.get("mcp", {}))
target.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY

echo "Installed llm-wiki-client OpenCode adapter into ${prefix}"
```

- [ ] **Step 7: 运行测试，确认通过**

Run:

```bash
python3 -m unittest tests.test_sync_adapters -v
```

Expected:

```text
Ran 4 tests
OK
```

- [ ] **Step 8: 提交**

```bash
git add src platforms tests/test_sync_adapters.py
git commit -m "test: add multi-client adapter templates"
```

---

### Task 3: 实现 `sync_adapters.py` 生成器

**Files:**
- Create: `scripts/sync_adapters.py`
- Modify: `tests/test_sync_adapters.py`
- Generated modify/create: `.claude-plugin/marketplace.json`, `.agents/plugins/marketplace.json`, `plugins/llm-wiki-client/**`, `dist/opencode/**`

- [ ] **Step 1: 写失败测试，要求生成文件和关键内容存在**

Append to `tests/test_sync_adapters.py`:

```python
import subprocess


class SyncAdaptersTests(unittest.TestCase):
    def run_sync(self):
        subprocess.run(["python3", "scripts/sync_adapters.py"], cwd=ROOT, check=True)

    def test_sync_generates_all_platform_entrypoints(self):
        self.run_sync()
        required = [
            ".claude-plugin/marketplace.json",
            ".agents/plugins/marketplace.json",
            "plugins/llm-wiki-client/.claude-plugin/plugin.json",
            "plugins/llm-wiki-client/.codex-plugin/plugin.json",
            "plugins/llm-wiki-client/.mcp.json",
            "plugins/llm-wiki-client/commands/wiki-cloud-mount.md",
            "plugins/llm-wiki-client/commands/wiki-cloud-backflow.md",
            "plugins/llm-wiki-client/skills/llm-wiki-cloud-mount/SKILL.md",
            "plugins/llm-wiki-client/skills/llm-wiki-cloud-query/SKILL.md",
            "plugins/llm-wiki-client/skills/llm-wiki-cloud-backflow/SKILL.md",
            "dist/opencode/opencode.json",
            "dist/opencode/install-opencode.sh",
            "dist/opencode/.opencode/commands/wiki-cloud-mount.md",
            "dist/opencode/.opencode/commands/wiki-cloud-backflow.md",
            "dist/opencode/.opencode/skills/llm-wiki-cloud-mount/SKILL.md",
            "dist/opencode/.opencode/skills/llm-wiki-cloud-query/SKILL.md",
            "dist/opencode/.opencode/skills/llm-wiki-cloud-backflow/SKILL.md",
        ]
        for rel in required:
            with self.subTest(rel=rel):
                self.assertTrue((ROOT / rel).exists(), rel)

    def test_sync_replaces_all_template_variables(self):
        self.run_sync()
        generated = [
            "plugins/llm-wiki-client/skills/llm-wiki-cloud-mount/SKILL.md",
            "dist/opencode/.opencode/skills/llm-wiki-cloud-mount/SKILL.md",
        ]
        for rel in generated:
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertNotIn("{{", text)
            self.assertNotIn("}}", text)
            self.assertIn("version: 1.1.6", text)
            self.assertIn("https://wiki.andykong.top/mcp", text)
```

- [ ] **Step 2: 运行测试，确认失败**

Run:

```bash
python3 -m unittest tests.test_sync_adapters.SyncAdaptersTests -v
```

Expected:

```text
python3: can't open file 'scripts/sync_adapters.py'
FAILED
```

- [ ] **Step 3: 实现生成器**

`scripts/sync_adapters.py`:

```python
#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATED_TEXT_MARKER = "<!-- Generated by scripts/sync_adapters.py; do not edit by hand. -->\n"


def read_constants() -> dict[str, str]:
    constants = json.loads((ROOT / "src/shared/constants.json").read_text(encoding="utf-8"))
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    constants["version"] = version
    return constants


def render(text: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", str(value))
    if "{{" in text or "}}" in text:
        raise ValueError(f"unrendered template variable in text starting: {text[:120]!r}")
    return text


def write_text(path: Path, text: str, *, marker: bool = False, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if marker and path.suffix.lower() in {".md", ".sh"}:
        text = GENERATED_TEXT_MARKER + text
    path.write_text(text, encoding="utf-8")
    if mode is not None:
        os.chmod(path, mode)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def render_template(src: str, dst: str, values: dict[str, str], *, marker: bool = False, mode: int | None = None) -> None:
    text = (ROOT / src).read_text(encoding="utf-8")
    write_text(ROOT / dst, render(text, values), marker=marker, mode=mode)


def platform_values(base: dict[str, str], platform: str) -> dict[str, str]:
    values = dict(base)
    values["platform"] = platform
    values["query_skill_name"] = "llm-wiki-cloud-query"
    if platform == "claude":
        values["instruction_file"] = "CLAUDE.md"
        values["wiki_search_tool"] = "mcp__plugin_llm-wiki-client_cann-infer-wiki-cloud__wiki_search"
        values["wiki_get_page_tool"] = "mcp__plugin_llm-wiki-client_cann-infer-wiki-cloud__wiki_get_page"
    else:
        values["instruction_file"] = "AGENTS.md"
        values["wiki_search_tool"] = "cann-infer-wiki-cloud wiki_search"
        values["wiki_get_page_tool"] = "cann-infer-wiki-cloud wiki_get_page"
    return values


def clean_generated_dirs() -> None:
    for rel in [".agents", "dist/opencode"]:
        path = ROOT / rel
        if path.exists():
            shutil.rmtree(path)
    codex_plugin = ROOT / "plugins/llm-wiki-client/.codex-plugin"
    if codex_plugin.exists():
        shutil.rmtree(codex_plugin)


def generate_manifests(values: dict[str, str]) -> None:
    render_template("platforms/claude/marketplace.json.tmpl", ".claude-plugin/marketplace.json", platform_values(values, "claude"))
    render_template("platforms/claude/plugin.json.tmpl", "plugins/llm-wiki-client/.claude-plugin/plugin.json", platform_values(values, "claude"))
    render_template("platforms/codex/marketplace.json.tmpl", ".agents/plugins/marketplace.json", platform_values(values, "codex"))
    render_template("platforms/codex/plugin.json.tmpl", "plugins/llm-wiki-client/.codex-plugin/plugin.json", platform_values(values, "codex"))
    write_json(
        ROOT / "plugins/llm-wiki-client/.mcp.json",
        {"mcpServers": {values["mcp_server_name"]: {"type": "http", "url": values["mcp_url"]}}},
    )
    render_template("platforms/opencode/opencode.json.tmpl", "dist/opencode/opencode.json", platform_values(values, "opencode"))
    render_template("platforms/opencode/install-opencode.sh.tmpl", "dist/opencode/install-opencode.sh", platform_values(values, "opencode"), marker=True, mode=0o755)


def generate_commands(values: dict[str, str]) -> None:
    for name in ["wiki-cloud-mount", "wiki-cloud-backflow"]:
        render_template(f"src/commands/{name}.md.tmpl", f"plugins/llm-wiki-client/commands/{name}.md", platform_values(values, "claude"), marker=True)
        render_template(f"src/commands/{name}.md.tmpl", f"dist/opencode/.opencode/commands/{name}.md", platform_values(values, "opencode"), marker=True)


def generate_skills(values: dict[str, str]) -> None:
    for skill in ["llm-wiki-cloud-mount", "llm-wiki-cloud-query", "llm-wiki-cloud-backflow"]:
        render_template(f"src/skills/{skill}/SKILL.md.tmpl", f"plugins/llm-wiki-client/skills/{skill}/SKILL.md", platform_values(values, "claude"), marker=True)
        render_template(f"src/skills/{skill}/SKILL.md.tmpl", f"dist/opencode/.opencode/skills/{skill}/SKILL.md", platform_values(values, "opencode"), marker=True)


def main() -> None:
    values = read_constants()
    clean_generated_dirs()
    generate_manifests(values)
    generate_commands(values)
    generate_skills(values)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 运行生成器测试**

Run:

```bash
python3 -m unittest tests.test_sync_adapters.SyncAdaptersTests -v
```

Expected:

```text
Ran 2 tests
OK
```

- [ ] **Step 5: 运行完整生成测试**

Run:

```bash
python3 -m unittest tests.test_sync_adapters -v
```

Expected:

```text
OK
```

- [ ] **Step 6: 提交**

```bash
git add scripts/sync_adapters.py tests/test_sync_adapters.py .claude-plugin .agents plugins/llm-wiki-client dist/opencode
git commit -m "feat: generate multi-client adapters"
```

---

### Task 4: 实现 release 静态校验器

**Files:**
- Create: `scripts/validate_release.py`
- Create: `tests/test_validate_release.py`

- [ ] **Step 1: 写失败测试，覆盖版本、URL、JSON 和 token 扫描**

```python
# tests/test_validate_release.py
from pathlib import Path
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
        bad.write_text("LLM_WIKI_UPLOAD_TOKEN=llmw_real_secret_value_123456\n", encoding="utf-8")
        try:
            result = subprocess.run(["python3", "scripts/validate_release.py"], cwd=ROOT, text=True, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("token-like string", result.stdout + result.stderr)
        finally:
            bad.unlink()


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试，确认失败**

Run:

```bash
python3 -m unittest tests.test_validate_release -v
```

Expected:

```text
python3: can't open file 'scripts/validate_release.py'
FAILED
```

- [ ] **Step 3: 实现校验器**

`scripts/validate_release.py`:

```python
#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOKEN_PATTERNS = [
    re.compile(r"llmw_(?!<token-from-operator>)[A-Za-z0-9_=-]{12,}"),
    re.compile(r"LLM_WIKI_UPLOAD_TOKEN\s*=\s*['\"]?llmw_(?!<token-from-operator>)[A-Za-z0-9_=-]{12,}"),
]


def fail(message: str) -> None:
    print(f"validate_release=failed reason={message}", file=sys.stderr)
    raise SystemExit(1)


def read_version() -> str:
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        fail(f"invalid VERSION: {version}")
    return version


def load_json(rel: str) -> object:
    try:
        return json.loads((ROOT / rel).read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"invalid JSON {rel}: {type(exc).__name__}")


def check_versions(version: str) -> None:
    checks = {
        ".claude-plugin/marketplace.json": lambda data: data["plugins"][0]["version"],
        "plugins/llm-wiki-client/.claude-plugin/plugin.json": lambda data: data["version"],
        "plugins/llm-wiki-client/.codex-plugin/plugin.json": lambda data: data["version"],
    }
    for rel, getter in checks.items():
        data = load_json(rel)
        actual = getter(data)
        if actual != version:
            fail(f"version mismatch in {rel}: {actual} != {version}")

    for rel in [
        "plugins/llm-wiki-client/skills/llm-wiki-cloud-mount/SKILL.md",
        "plugins/llm-wiki-client/skills/llm-wiki-cloud-query/SKILL.md",
        "plugins/llm-wiki-client/skills/llm-wiki-cloud-backflow/SKILL.md",
        "dist/opencode/.opencode/skills/llm-wiki-cloud-mount/SKILL.md",
        "dist/opencode/.opencode/skills/llm-wiki-cloud-query/SKILL.md",
        "dist/opencode/.opencode/skills/llm-wiki-cloud-backflow/SKILL.md",
    ]:
        text = (ROOT / rel).read_text(encoding="utf-8")
        if f"version: {version}" not in text:
            fail(f"skill version missing in {rel}")


def check_urls() -> None:
    canonical = "https://wiki.andykong.top/mcp"
    expected = [
        "plugins/llm-wiki-client/.mcp.json",
        "dist/opencode/opencode.json",
        "plugins/llm-wiki-client/skills/llm-wiki-cloud-mount/SKILL.md",
        "dist/opencode/.opencode/skills/llm-wiki-cloud-mount/SKILL.md",
    ]
    for rel in expected:
        text = (ROOT / rel).read_text(encoding="utf-8")
        if canonical not in text:
            fail(f"canonical mcp url missing in {rel}")


def check_opencode_skill_names() -> None:
    root = ROOT / "dist/opencode/.opencode/skills"
    pattern = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
    for path in root.iterdir():
        if path.is_dir() and not pattern.fullmatch(path.name):
            fail(f"invalid OpenCode skill name: {path.name}")


def check_expected_commands() -> None:
    expected = {"wiki-cloud-mount.md", "wiki-cloud-backflow.md"}
    for rel in ["plugins/llm-wiki-client/commands", "dist/opencode/.opencode/commands"]:
        actual = {path.name for path in (ROOT / rel).glob("*.md")}
        if actual != expected:
            fail(f"unexpected commands in {rel}: {sorted(actual)}")


def check_no_unrendered_templates() -> None:
    for base in [ROOT / "plugins/llm-wiki-client", ROOT / "dist/opencode", ROOT / ".claude-plugin", ROOT / ".agents"]:
        if not base.exists():
            fail(f"missing generated base: {base.relative_to(ROOT)}")
        for path in base.rglob("*"):
            if path.is_file():
                text = path.read_text(encoding="utf-8", errors="ignore")
                if "{{" in text or "}}" in text:
                    fail(f"unrendered template variable in {path.relative_to(ROOT)}")


def check_no_token_leaks() -> None:
    for path in ROOT.rglob("*"):
        if ".git" in path.parts or path.is_dir():
            continue
        if path.suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in TOKEN_PATTERNS:
            if pattern.search(text):
                fail(f"token-like string in {path.relative_to(ROOT)}")


def check_generated_current() -> None:
    subprocess.run(["python3", "scripts/sync_adapters.py"], cwd=ROOT, check=True)
    result = subprocess.run(["git", "diff", "--quiet", "--", ".claude-plugin", ".agents", "plugins/llm-wiki-client", "dist/opencode"], cwd=ROOT)
    if result.returncode != 0:
        fail("generated files are stale")


def main() -> None:
    version = read_version()
    check_versions(version)
    check_urls()
    check_opencode_skill_names()
    check_expected_commands()
    check_no_unrendered_templates()
    check_no_token_leaks()
    check_generated_current()
    print("validate_release=ok")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 运行校验器测试**

Run:

```bash
python3 -m unittest tests.test_validate_release -v
```

Expected:

```text
Ran 2 tests
OK
```

- [ ] **Step 5: 运行发布校验**

Run:

```bash
python3 scripts/validate_release.py
```

Expected:

```text
validate_release=ok
```

- [ ] **Step 6: 提交**

```bash
git add scripts/validate_release.py tests/test_validate_release.py
git commit -m "test: validate generated release artifacts"
```

---

### Task 5: 实现 OpenCode installer 测试

**Files:**
- Create: `tests/test_opencode_installer.py`
- Modify: `platforms/opencode/install-opencode.sh.tmpl`
- Generated modify: `dist/opencode/install-opencode.sh`

- [ ] **Step 1: 写失败测试，验证 installer 只写 prefix 且 merge MCP**

```python
# tests/test_opencode_installer.py
from pathlib import Path
import json
import os
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class OpenCodeInstallerTests(unittest.TestCase):
    def setUp(self):
        subprocess.run(["python3", "scripts/sync_adapters.py"], cwd=ROOT, check=True)

    def test_installer_writes_only_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            prefix = Path(tmp) / "opencode-config"
            env = dict(os.environ)
            env["HOME"] = str(Path(tmp) / "home")
            result = subprocess.run(
                ["bash", "dist/opencode/install-opencode.sh", "--prefix", str(prefix)],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue((prefix / "commands/wiki-cloud-mount.md").exists())
            self.assertTrue((prefix / "commands/wiki-cloud-backflow.md").exists())
            self.assertTrue((prefix / "skills/llm-wiki-cloud-query/SKILL.md").exists())
            self.assertTrue((prefix / "opencode.json").exists())
            self.assertFalse((Path(tmp) / "home/.config/opencode").exists())

    def test_installer_merges_existing_mcp_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            prefix = Path(tmp) / "opencode-config"
            prefix.mkdir(parents=True)
            existing = {
                "$schema": "https://opencode.ai/config.json",
                "mcp": {
                    "existing-server": {
                        "type": "remote",
                        "url": "https://example.invalid/mcp",
                        "enabled": True
                    }
                }
            }
            (prefix / "opencode.json").write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
            subprocess.run(["bash", "dist/opencode/install-opencode.sh", "--prefix", str(prefix)], cwd=ROOT, check=True)
            merged = json.loads((prefix / "opencode.json").read_text(encoding="utf-8"))
            self.assertIn("existing-server", merged["mcp"])
            self.assertEqual(merged["mcp"]["cann-infer-wiki-cloud"]["url"], "https://wiki.andykong.top/mcp")
            self.assertTrue(merged["mcp"]["cann-infer-wiki-cloud"]["enabled"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试**

Run:

```bash
python3 -m unittest tests.test_opencode_installer -v
```

Expected:

```text
Ran 2 tests
OK
```

If this fails because `install-opencode.sh` writes outside `--prefix`, modify only `platforms/opencode/install-opencode.sh.tmpl`, rerun `python3 scripts/sync_adapters.py`, then rerun the test.

- [ ] **Step 3: 运行完整测试**

Run:

```bash
python3 -m unittest tests.test_sync_adapters tests.test_validate_release tests.test_opencode_installer -v
```

Expected:

```text
OK
```

- [ ] **Step 4: 提交**

```bash
git add tests/test_opencode_installer.py platforms/opencode/install-opencode.sh.tmpl dist/opencode/install-opencode.sh
git commit -m "test: isolate opencode installer writes"
```

---

### Task 6: 实现隔离测试 harness 和 mock backflow server

**Files:**
- Create: `scripts/allocate_test_port.py`
- Create: `scripts/test_isolated_clients.py`

- [ ] **Step 1: 写端口分配脚本**

`scripts/allocate_test_port.py`:

```python
#!/usr/bin/env python3
from __future__ import annotations

import socket


with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.bind(("127.0.0.1", 0))
    print(sock.getsockname()[1])
```

- [ ] **Step 2: 创建 harness，先实现静态隔离和 mock upload**

`scripts/test_isolated_clients.py`:

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import http.server
import json
import os
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GLOBAL_PATHS = [
    Path.home() / ".claude",
    Path.home() / ".codex",
    Path.home() / ".agents",
    Path.home() / ".config/opencode",
]


def tree_digest(path: Path) -> str:
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    for item in sorted(path.rglob("*")):
        rel = item.relative_to(path).as_posix()
        digest.update(rel.encode())
        if item.is_file():
            digest.update(item.read_bytes())
    return digest.hexdigest()


class MockBackflowHandler(http.server.BaseHTTPRequestHandler):
    response_status = "ok"

    def do_POST(self) -> None:
        length = int(self.headers.get("content-length", "0"))
        self.rfile.read(length)
        body = {
            "status": self.response_status,
            "id": "test-backflow-id",
            "path": "sources/sessions/uploaded/test",
            "entrypoint": "test.md",
        }
        payload = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:
        return


def start_mock_server() -> tuple[http.server.HTTPServer, str]:
    server = http.server.HTTPServer(("127.0.0.1", 0), MockBackflowHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    return server, f"http://{host}:{port}/upload/backflow"


def run(cmd: list[str], *, env: dict[str, str], cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, env=env, text=True, capture_output=True, check=True)


def isolated_env(root: Path, upload_url: str) -> dict[str, str]:
    env = dict(os.environ)
    env.update({
        "HOME": str(root / "home"),
        "XDG_CONFIG_HOME": str(root / "xdg-config"),
        "XDG_DATA_HOME": str(root / "xdg-data"),
        "CODEX_HOME": str(root / "codex-home"),
        "OPENCODE_CONFIG": str(root / "opencode/opencode.json"),
        "OPENCODE_CONFIG_DIR": str(root / "opencode"),
        "LLM_WIKI_UPLOAD_TOKEN": "llmw_test_token",
        "LLM_WIKI_UPLOAD_URL": upload_url,
    })
    for key in ["CLAUDE_CONFIG_DIR"]:
        env[key] = str(root / key.lower())
    return env


def check_static() -> None:
    run(["python3", "scripts/sync_adapters.py"], env=dict(os.environ))
    run(["python3", "scripts/validate_release.py"], env=dict(os.environ))
    run(["python3", "-m", "unittest", "discover", "-s", "tests", "-v"], env=dict(os.environ))


def check_opencode_install(env: dict[str, str], root: Path) -> None:
    prefix = root / "opencode-prefix"
    run(["bash", "dist/opencode/install-opencode.sh", "--prefix", str(prefix)], env=env)
    assert (prefix / "commands/wiki-cloud-mount.md").exists()
    assert (prefix / "skills/llm-wiki-cloud-query/SKILL.md").exists()
    config = json.loads((prefix / "opencode.json").read_text(encoding="utf-8"))
    assert config["mcp"]["cann-infer-wiki-cloud"]["url"] == "https://wiki.andykong.top/mcp"


def check_cli_visibility(env: dict[str, str]) -> None:
    for cmd in [["claude", "--help"], ["codex", "--help"], ["opencode", "--help"]]:
        completed = run(cmd, env=env)
        assert completed.stdout or completed.stderr


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keep-root", action="store_true")
    args = parser.parse_args()

    before = {str(path): tree_digest(path) for path in GLOBAL_PATHS}
    server, upload_url = start_mock_server()
    test_root = Path(tempfile.mkdtemp(prefix="llm-wiki-client-test-"))
    try:
        env = isolated_env(test_root, upload_url)
        check_static()
        check_opencode_install(env, test_root)
        check_cli_visibility(env)
        after = {str(path): tree_digest(path) for path in GLOBAL_PATHS}
        if before != after:
            raise SystemExit(f"global config changed: before={before} after={after}")
        print(f"isolated_clients=ok root={test_root}")
    finally:
        server.shutdown()
        if not args.keep_root:
            shutil.rmtree(test_root, ignore_errors=True)


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: 运行 harness**

Run:

```bash
python3 scripts/test_isolated_clients.py
```

Expected:

```text
isolated_clients=ok root=/tmp/llm-wiki-client-test-...
```

- [ ] **Step 4: 验证全局路径未被修改**

Run:

```bash
git status --short --branch
```

Expected:

```text
## codex/multiclient-distribution-spec...multiclient-test/codex/multiclient-distribution-spec
```

Additional accepted output:

```text
?? .idea/
```

- [ ] **Step 5: 提交**

```bash
git add scripts/allocate_test_port.py scripts/test_isolated_clients.py
git commit -m "test: add isolated multi-client harness"
```

---

### Task 7: 更新 README 和插件 README

**Files:**
- Modify: `README.md`
- Modify: `plugins/llm-wiki-client/README.md`

- [ ] **Step 1: 写文档校验测试**

Append to `tests/test_validate_release.py`:

```python
class DocumentationTests(unittest.TestCase):
    def test_readme_mentions_all_clients(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        for phrase in ["Claude Code", "Codex", "OpenCode", "multiclient-test"]:
            self.assertIn(phrase, text)

    def test_plugin_readme_mentions_generated_adapters(self):
        text = (ROOT / "plugins/llm-wiki-client/README.md").read_text(encoding="utf-8")
        self.assertIn("scripts/sync_adapters.py", text)
        self.assertIn(".codex-plugin", text)
        self.assertIn("dist/opencode", text)
```

- [ ] **Step 2: 运行测试，确认失败**

Run:

```bash
python3 -m unittest tests.test_validate_release.DocumentationTests -v
```

Expected:

```text
FAIL
```

- [ ] **Step 3: 更新 root README 的安装/更新/使用说明**

Add section:

```md
## 三端安装、更新和使用

### Claude Code

安装：

```text
/plugin marketplace add AndyKong2020/LLM-Wiki-Marketplace-Cloud
/plugin install llm-wiki-client@llm-wiki-cloud
/reload-plugins
```

更新：

```text
/plugin marketplace update llm-wiki-cloud
/plugin update llm-wiki-client@llm-wiki-cloud
/reload-plugins
```

使用：

```text
/llm-wiki-client:wiki-cloud-mount
/llm-wiki-client:wiki-cloud-backflow
```

### Codex

安装：

```bash
codex plugin marketplace add AndyKong2020/LLM-Wiki-Marketplace-Cloud --ref main
codex plugin add llm-wiki-client@llm-wiki-cloud
```

更新：

```bash
codex plugin marketplace upgrade
codex plugin remove llm-wiki-client@llm-wiki-cloud
codex plugin add llm-wiki-client@llm-wiki-cloud
```

使用：让 Codex 执行 `llm-wiki-cloud-mount`、在 LLM/NPU 推理优化任务中使用 `llm-wiki-cloud-query`、任务结束后执行 `llm-wiki-cloud-backflow`。

### OpenCode

安装或更新：

```bash
curl -fsSL https://wiki.andykong.top/plugin/llm-wiki-client/install-opencode.sh | sh
```

使用：

```text
/wiki-cloud-mount
/wiki-cloud-backflow
```

### 隔离测试仓库

多客户端开发先推 private 测试仓库 remote `multiclient-test`，不要推 `origin` 或 `cloud`：

```bash
git push multiclient-test "$BRANCH"
```
```

- [ ] **Step 4: 更新 plugin README 维护说明**

Add section:

```md
## Generated Adapter Maintenance

`plugins/llm-wiki-client/` 同时承载 Claude Code 和 Codex adapter：

- `.claude-plugin/plugin.json`
- `.codex-plugin/plugin.json`
- `.mcp.json`
- `commands/`
- `skills/`

这些文件由 `scripts/sync_adapters.py` 从 `src/` 和 `platforms/` 生成。OpenCode adapter 生成到 repository root 的 `dist/opencode/`。维护者不要手工编辑生成文件；应修改源模板后重新运行：

```bash
python3 scripts/sync_adapters.py
python3 scripts/validate_release.py
```
```

- [ ] **Step 5: 运行文档测试**

Run:

```bash
python3 -m unittest tests.test_validate_release.DocumentationTests -v
```

Expected:

```text
Ran 2 tests
OK
```

- [ ] **Step 6: 运行完整校验**

Run:

```bash
python3 scripts/validate_release.py
python3 scripts/test_isolated_clients.py
```

Expected:

```text
validate_release=ok
isolated_clients=ok root=...
```

- [ ] **Step 7: 提交**

```bash
git add README.md plugins/llm-wiki-client/README.md tests/test_validate_release.py
git commit -m "docs: document multi-client install and maintenance"
```

---

### Task 8: 执行真实三端 smoke 测试并记录结果

**Files:**
- Create: `docs/superpowers/test-runs/2026-06-01-multiclient-smoke.md`

- [ ] **Step 1: 创建测试记录文件**

```md
# 2026-06-01 Multi-Client Smoke Test

## Environment

- branch: `codex/multiclient-distribution-spec`
- remote: `multiclient-test`
- test root: captured from `scripts/test_isolated_clients.py --keep-root`

## Commands

```bash
python3 scripts/sync_adapters.py
python3 scripts/validate_release.py
python3 -m unittest discover -s tests -v
python3 scripts/test_isolated_clients.py --keep-root
```

## Results

- Static validation:
- Claude Code CLI visibility:
- Codex CLI visibility:
- OpenCode CLI visibility:
- OpenCode installer isolation:
- Global config digest check:
- Mock backflow:

## Notes

- No push to `origin` or `cloud`.
- No production upload endpoint used.
```

- [ ] **Step 2: 运行完整本地验证并保留测试根目录**

Run:

```bash
python3 scripts/sync_adapters.py
python3 scripts/validate_release.py
python3 -m unittest discover -s tests -v
python3 scripts/test_isolated_clients.py --keep-root
```

Expected:

```text
validate_release=ok
OK
isolated_clients=ok root=/tmp/llm-wiki-client-test-...
```

- [ ] **Step 3: 在测试记录中填入实际输出摘要**

Edit `docs/superpowers/test-runs/2026-06-01-multiclient-smoke.md` with:

```md
## Results

- Static validation: passed, `validate_release=ok`
- Unit tests: passed, `python3 -m unittest discover -s tests -v`
- Claude Code CLI visibility: passed via isolated `claude --help`
- Codex CLI visibility: passed via isolated `codex --help`
- OpenCode CLI visibility: passed via isolated `opencode --help`
- OpenCode installer isolation: passed, writes only under test prefix
- Global config digest check: passed, `~/.claude`, `~/.codex`, `~/.agents`, `~/.config/opencode` unchanged
- Mock backflow: passed through local HTTP server, no production endpoint hit
```

- [ ] **Step 4: 提交测试记录**

```bash
git add docs/superpowers/test-runs/2026-06-01-multiclient-smoke.md
git commit -m "test: record isolated multi-client smoke run"
```

---

### Task 9: 推送测试仓库并确认生产远端未变化

**Files:**
- No file changes.

- [ ] **Step 1: 检查远端**

Run:

```bash
git remote -v
```

Expected contains:

```text
cloud	git@github.com:AndyKong2020/LLM-Wiki-Marketplace-Cloud.git
multiclient-test	git@github.com:AndyKong2020/LLM-Wiki-Marketplace-Multiclient-Test.git
origin	git@github.com:AndyKong2020/LLM-Wiki-Marketplace.git
```

- [ ] **Step 2: 推送到测试仓库**

Run:

```bash
git push multiclient-test codex/multiclient-distribution-spec
```

Expected:

```text
codex/multiclient-distribution-spec -> codex/multiclient-distribution-spec
```

- [ ] **Step 3: 确认生产远端没有被推送**

Run:

```bash
git ls-remote --heads cloud codex/multiclient-distribution-spec
git ls-remote --heads origin codex/multiclient-distribution-spec
```

Expected:

```text
```

Both commands return no refs.

- [ ] **Step 4: 最终状态检查**

Run:

```bash
git status --short --branch
```

Expected:

```text
## codex/multiclient-distribution-spec...multiclient-test/codex/multiclient-distribution-spec
```

Additional accepted output:

```text
?? .idea/
```

---

## 计划自查

- Spec coverage: 覆盖一份源头、三端 adapter、版本同步、release 校验、隔离测试仓库、本地隔离 harness、mock backflow、三端安装/更新/使用文档、测试仓库推送纪律。
- 占位词扫描：本计划不使用未完成占位词，也不要求实现者自行补齐未定义代码。
- Type consistency: Python 脚本均使用 `Path`、`dict[str, str]`、标准库 `unittest/subprocess/json`；生成器和校验器共享 `VERSION` 与 `src/shared/constants.json`。
