# 多客户端分发设计

## 背景

当前仓库把 `llm-wiki-client@llm-wiki-cloud` 作为 Claude Code marketplace 插件发布，用于连接云端 CANN-Infer-Wiki 服务。插件已经提供：

- 远程只读 MCP server：`https://wiki.andykong.top/mcp`
- mount 流程：探活 MCP，并写入项目级使用说明
- query 流程：通过 wiki search/page 工具检索知识，并记录使用情况
- backflow 流程：创建本地任务归档，并在用户确认后通过 token-gated HTTP 入口上传

下一轮迭代需要让同一个仓库同时支持 Claude Code、Codex 和 OpenCode，且不能让维护者手工维护三份会逐渐漂移的内容。

## 目标

- skill 行为、command prompt、endpoint 常量和发布版本只有一份源头。
- 为 Claude Code、Codex 和 OpenCode 生成平台专属适配文件。
- 三个工具的安装路径都尽量低摩擦。
- 三个客户端都要覆盖 mount、query 和 backflow 的完整功能测试。
- 所有测试必须隔离于生产远端和用户真实全局配置。

## 非目标

- 不替换生产用的 `cloud` 或 `origin` 远端。
- 不把测试 backflow archive 上传到生产 backflow endpoint。
- 不要求用户安装本地 MCP server。
- 不引入动态 OpenCode JS/TS plugin，除非静态 config、commands 和 skills 无法满足需求。

## 仓库策略

采用“一份可编辑源文件 + 自动生成平台适配层”的结构。

```text
VERSION
src/
  shared/
    constants.json
    pin-block.md.tmpl
  skills/
    llm-wiki-cloud-mount/SKILL.md.tmpl
    llm-wiki-cloud-query/SKILL.md.tmpl
    llm-wiki-cloud-backflow/SKILL.md.tmpl
  commands/
    wiki-cloud-mount.md.tmpl
    wiki-cloud-backflow.md.tmpl

platforms/
  claude/
    marketplace.json.tmpl
    plugin.json.tmpl
  codex/
    marketplace.json.tmpl
    plugin.json.tmpl
  opencode/
    opencode.json.tmpl
    install-opencode.sh.tmpl

plugins/llm-wiki-client/
  .claude-plugin/plugin.json
  .codex-plugin/plugin.json
  .mcp.json
  README.md
  commands/
  skills/

dist/opencode/
  opencode.json
  install-opencode.sh
  .opencode/
    commands/
    skills/

scripts/
  sync_adapters.py
  validate_release.py
  test_isolated_clients.py
```

维护者只手工修改 `VERSION`、`src/`、`platforms/`、顶层文档和脚本。`plugins/llm-wiki-client/` 与 `dist/opencode/` 是生成产物，但仍提交到 git，方便 marketplace 安装和用户直接复制安装。任何这些目录下的变更都必须由 `scripts/sync_adapters.py` 生成。

只要目标格式支持注释，生成文件都要带一行简短标记，说明文件由脚本生成，不应手工编辑。

## 平台适配层

### Claude Code

Claude Code 保留当前 marketplace 形态：

```text
.claude-plugin/marketplace.json
plugins/llm-wiki-client/.claude-plugin/plugin.json
plugins/llm-wiki-client/.mcp.json
plugins/llm-wiki-client/commands/*.md
plugins/llm-wiki-client/skills/*/SKILL.md
```

安装方式保持不变：

```text
/plugin marketplace add AndyKong2020/LLM-Wiki-Marketplace-Cloud
/plugin install llm-wiki-client@llm-wiki-cloud
/reload-plugins
```

mount 写入或更新 `CLAUDE.md`，因为这是 Claude Code 原生项目指令文件。

### Codex

Codex 复用同一个 plugin root，但额外增加 Codex manifest 和 marketplace：

```text
.agents/plugins/marketplace.json
plugins/llm-wiki-client/.codex-plugin/plugin.json
plugins/llm-wiki-client/.mcp.json
plugins/llm-wiki-client/skills/*/SKILL.md
```

Codex 适配层中的 skill 正文不能依赖 Claude 专属工具名。skill 应描述 MCP server 和逻辑工具名：

```text
cann-infer-wiki-cloud wiki_search
cann-infer-wiki-cloud wiki_get_page
```

mount 写入或更新 `AGENTS.md`。

### OpenCode

OpenCode 使用生成出来的静态适配包：

```text
dist/opencode/opencode.json
dist/opencode/install-opencode.sh
dist/opencode/.opencode/commands/*.md
dist/opencode/.opencode/skills/*/SKILL.md
```

`opencode.json` 配置远程 MCP：

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "cann-infer-wiki-cloud": {
      "type": "remote",
      "url": "https://wiki.andykong.top/mcp",
      "enabled": true
    }
  }
}
```

OpenCode commands 是 `.opencode/commands/` 下的 Markdown 文件。OpenCode skills 是 `.opencode/skills/<name>/SKILL.md` 文件。mount 写入或更新 `AGENTS.md`；OpenCode 可以 fallback 到 `CLAUDE.md`，但原生规则文件是 `AGENTS.md`。

## Command 和 Skill 行为

### Mount

mount 必须：

- 从生成后的 skill metadata 中读取本地 adapter 版本
- 拉取 `https://wiki.andykong.top/plugin/llm-wiki-client/version.json`
- 如果本地版本落后于远端版本，则停止执行
- 调用 `wiki_search(query="mount probe", limit=1)` 探活
- 写入最新版 LLM-WIKI pin block
- 汇报版本、MCP 模式、probe 结果、pin 状态和目标指令文件路径

项目指令文件目标：

| 平台 | 目标文件 |
|---|---|
| Claude Code | `CLAUDE.md` |
| Codex | `AGENTS.md` |
| OpenCode | `AGENTS.md` |

### Query

query 必须：

- 根据当前模型、算子、框架、优化阶段构造具体 wiki query
- 调用 `wiki_search`
- 对相关候选调用 `wiki_get_page`
- 在理解图片内容前先下载 assets
- 将每个读取过的页面记录到 `wiki_usage.md`
- 如果任务存在 `progress.md`，则追加查询摘要
- 把 wiki 内容视作经验建议，而不是绝对真相

### Backflow

backflow 必须：

- 推断 task slug 和 workspace
- 创建 `.claude/llm-wiki/backflow/<task-slug>/`
- 顶层必须且只能有一个 Markdown entrypoint
- 纳入任务轨迹、wiki usage、小型相关文件、git status/diff，以及存在时相关的 agent summary
- 排除 credentials、tokens、`.env*`、`.git/`、IDE 状态、raw profiler dump、模型权重、数据集、缓存和大体积二进制
- 在任何上传前先汇报 archive summary
- 只在用户确认且 `LLM_WIKI_UPLOAD_TOKEN` 已配置时上传
- 支持用 `LLM_WIKI_UPLOAD_URL` 指向 staging 或 mock upload endpoint
- 永远不要打印或归档 token

## 版本和发布流程

发布版本只写在 `VERSION`。

发布步骤：

```bash
python3 scripts/sync_adapters.py
python3 scripts/validate_release.py
git diff --exit-code
git tag "v${VERSION}"
```

`sync_adapters.py` 必须把版本同步到：

- root Claude marketplace
- Claude plugin manifest
- Codex plugin manifest
- Codex marketplace
- 所有生成后的 skill frontmatter
- plugin README
- 生成后的 OpenCode install package

`validate_release.py` 必须检查：

- JSON 合法性
- 所有版本与 `VERSION` 一致
- 所有生成文件都是最新
- 所有 MCP URL 与 canonical URL 一致
- OpenCode skill name 匹配 `^[a-z0-9]+(-[a-z0-9]+)*$`
- 只存在预期 command 名称
- 已提交文件中没有疑似 token 的字符串
- README 安装命令与生成后的 adapter 名称一致

## 隔离测试仓库

多客户端测试使用独立 private GitHub 仓库：

```text
AndyKong2020/LLM-Wiki-Marketplace-Multiclient-Test
```

本地 remote 名：

```text
multiclient-test
```

规则：

- 永远不要把测试分支 push 到 `origin` 或 `cloud`。
- 永远不要修改 `origin` 或 `cloud` 的 URL。
- 测试 push 必须显式指定 remote：

```bash
git push multiclient-test "$BRANCH"
```

- 测试仓库可以接收生成后的 adapters、测试分支、GitHub Actions workflow 和 release dry-run。
- 生产 marketplace 仓库在测试验收通过前保持不变。

## 隔离本地测试 Harness

所有自动化客户端测试都必须运行在临时测试根目录下。

```bash
LLM_WIKI_TEST_ROOT="$(mktemp -d)"
export HOME="$LLM_WIKI_TEST_ROOT/home"
export XDG_CONFIG_HOME="$LLM_WIKI_TEST_ROOT/xdg-config"
export XDG_DATA_HOME="$LLM_WIKI_TEST_ROOT/xdg-data"
export CODEX_HOME="$LLM_WIKI_TEST_ROOT/codex-home"
export OPENCODE_CONFIG="$LLM_WIKI_TEST_ROOT/opencode/opencode.json"
export OPENCODE_CONFIG_DIR="$LLM_WIKI_TEST_ROOT/opencode"
export LLM_WIKI_UPLOAD_TOKEN="llmw_test_token"
export LLM_WIKI_MOCK_PORT="$(python3 scripts/allocate_test_port.py)"
export LLM_WIKI_UPLOAD_URL="http://127.0.0.1:${LLM_WIKI_MOCK_PORT}/upload/backflow"
```

harness 必须在 `LLM_WIKI_TEST_ROOT` 内创建临时项目 workspace，不能使用真实用户项目。

每次测试运行前后，harness 必须检查这些真实全局路径没有变化：

```text
~/.claude
~/.codex
~/.agents
~/.config/opencode
```

如果某个客户端忽略临时环境变量并写入真实全局路径，测试必须立刻失败。

## 完整测试覆盖

### 静态校验

- 从模板生成 adapters。
- 校验所有 JSON 文件。
- 校验 skill frontmatter。
- 校验 command 名称和描述。
- 校验版本一致性。
- 校验没有生产 upload token。

### Claude Code Smoke Test

只在临时 home/config 下运行。

- 从测试仓库或本地 checkout 安装或加载生成后的 Claude plugin。
- 确认远程 MCP config 可见。
- 在临时项目中运行 mount。
- 验证 `CLAUDE.md` 恰好包含一个 LLM-WIKI block。
- 连续运行两次 mount，验证幂等性。
- 触发一次 query 任务，验证 `wiki_usage.md` 和 `progress.md` 被写入。
- 运行 backflow archive 创建流程，验证 archive layout。
- 上传到本地 mock backflow server，不触达生产。

### Codex Smoke Test

在临时 `CODEX_HOME`、`HOME` 和 `XDG_*` 下运行。

- 从测试仓库或本地 checkout 安装或加载生成后的 Codex plugin。
- 确认 `.codex-plugin/plugin.json`、`.mcp.json` 和 skills 被发现。
- 在临时项目中运行 mount。
- 验证 `AGENTS.md` 恰好包含一个 LLM-WIKI block。
- 连续运行两次 mount，验证幂等性。
- 触发一次 query 任务，验证 `wiki_usage.md` 和 `progress.md` 被写入。
- 运行 backflow archive 创建流程，验证 archive layout。
- 上传到本地 mock backflow server。

### OpenCode Smoke Test

在临时 `HOME`、`XDG_*`、`OPENCODE_CONFIG` 和 `OPENCODE_CONFIG_DIR` 下运行。

- 运行 `dist/opencode/install-opencode.sh --prefix "$LLM_WIKI_TEST_ROOT/opencode-install"` 或等价 dry-run 模式。
- 验证 commands、skills 和 `opencode.json` 只安装到测试根目录下。
- 验证 MCP config 包含启用状态的 remote server `cann-infer-wiki-cloud`。
- 在临时项目中运行 mount。
- 验证 `AGENTS.md` 恰好包含一个 LLM-WIKI block。
- 连续运行两次 mount，验证幂等性。
- 触发一次 query 任务，验证 `wiki_usage.md` 和 `progress.md` 被写入。
- 运行 backflow archive 创建流程，验证 archive layout。
- 上传到本地 mock backflow server。

### Mock Backflow Server

测试 harness 必须提供本地 HTTP server，接收 multipart upload，并返回：

```json
{
  "status": "ok",
  "id": "test-backflow-id",
  "path": "sources/sessions/uploaded/test",
  "entrypoint": "test.md"
}
```

额外测试用例：

- `duplicate` 响应按成功处理。
- `error` 响应必须被汇报，且不能删除本地 archive。
- 超过 50 MiB 的 package 必须在 upload 前被拒绝。
- 缺少或存在多个顶层 Markdown 文件时，必须在 upload 前被拒绝。
- token 不能出现在 stdout、stderr、archive 文件或 git diff 中。

## 验收标准

- 维护者只需更新一次内容，运行 `sync_adapters.py` 后即可得到三个客户端 adapter。
- Claude Code、Codex 和 OpenCode 都能从同一个测试仓库或生成包安装。
- Claude Code、Codex 和 OpenCode 的 mount、query、backflow 都经过测试。
- 测试不会修改生产 remote。
- 测试不会修改真实全局客户端配置。
- 测试 upload 永远不会触达 `https://wiki.andykong.top/upload/backflow`。
- 只有 `validate_release.py` 和隔离客户端测试都通过后，才允许生产发布。

## 实施顺序

1. 添加 `VERSION`、源模板、平台模板和生成脚本。
2. 生成 Claude/Codex 共用 plugin root。
3. 生成 OpenCode adapter package 和 installer。
4. 添加 release validator。
5. 添加带 mock backflow server 的隔离测试 harness。
6. 只把 feature branch push 到 `multiclient-test`。
7. 从 private 测试仓库运行完整客户端 smoke tests。
8. 验收后，再单独决定是否以及何时提升到生产 remote。
