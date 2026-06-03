# LLM-Wiki Marketplace Test

本仓库是 **CANN-Infer-Wiki** 云服务的多客户端插件市场测试仓库，面向 Claude Code、Codex
和 OpenCode 分发同一套云端 wiki 读写入口。这里用于隔离验证，不要把测试分支推到生产
marketplace 仓库。

GitHub 测试仓库：`AndyKong2020/LLM-Wiki-Marketplace-Multiclient-Test`
测试 ref：`codex/multiclient-distribution-spec`
Marketplace 名称：`llm-wiki-cloud-test`
插件：`llm-wiki-client@llm-wiki-cloud-test`

## 模拟用户使用流程

下面每段都使用临时配置目录，按真实用户路径测试安装、更新和使用，不写入生产
marketplace，也不依赖一键 smoke 脚本。

### Claude Code

启动隔离 Claude Code 会话：

```bash
tmpdir="$(mktemp -d)"
(
  export HOME="$tmpdir/home"
  export CLAUDE_CONFIG_DIR="$tmpdir/claude-config"
  export CLAUDE_HOME="$tmpdir/claude-home"
  mkdir -p "$HOME" "$CLAUDE_CONFIG_DIR" "$CLAUDE_HOME"
  claude
)
```

在 Claude Code 里粘贴安装：

```text
/plugin marketplace add AndyKong2020/LLM-Wiki-Marketplace-Multiclient-Test@codex/multiclient-distribution-spec
/plugin install llm-wiki-client@llm-wiki-cloud-test
/reload-plugins
```

在 Claude Code 里粘贴更新：

```text
/plugin marketplace update llm-wiki-cloud-test
/plugin update llm-wiki-client@llm-wiki-cloud-test
/reload-plugins
```

在 Claude Code 里模拟使用：

```text
/llm-wiki-client:wiki-cloud-mount
请用 CANN-Infer-Wiki 查询 AscendC tiling 优化的注意事项，回答 3 条要点。
/llm-wiki-client:wiki-cloud-backflow
```

在需要挂载知识库的项目中运行 `/llm-wiki-client:wiki-cloud-mount`。它会探活远程
MCP，并向 `CLAUDE.md` 写入 wiki 使用提示。正常使用 Claude Code；任务进入
LLM/NPU 推理优化相关阶段时，`llm-wiki-cloud-query` skill 通过 MCP tools 查询
wiki。任务结束后可运行 `/llm-wiki-client:wiki-cloud-backflow` 创建本地任务归档；
若用户确认且配置了 `LLM_WIKI_UPLOAD_TOKEN`，插件会通过私有 HTTP backflow 入口上传归档。

### Codex

启动隔离 shell 并安装：

```bash
tmpdir="$(mktemp -d)"
export HOME="$tmpdir/home"
export XDG_CONFIG_HOME="$tmpdir/xdg-config"
export XDG_DATA_HOME="$tmpdir/xdg-data"
export XDG_CACHE_HOME="$tmpdir/xdg-cache"
export CODEX_HOME="$tmpdir/codex-home"
export AGENTS_HOME="$tmpdir/agents-home"
mkdir -p "$HOME" "$XDG_CONFIG_HOME" "$XDG_DATA_HOME" "$XDG_CACHE_HOME" "$CODEX_HOME" "$AGENTS_HOME"
codex plugin marketplace add AndyKong2020/LLM-Wiki-Marketplace-Multiclient-Test --ref codex/multiclient-distribution-spec
codex plugin add llm-wiki-client@llm-wiki-cloud-test
```

更新：

```bash
codex plugin marketplace upgrade llm-wiki-cloud-test
codex plugin remove llm-wiki-client@llm-wiki-cloud-test
codex plugin add llm-wiki-client@llm-wiki-cloud-test
```

启动 Codex 后模拟使用：

```bash
codex
```

在 Codex 里输入：

```text
先执行 llm-wiki-cloud-mount，挂载当前项目的 CANN-Infer-Wiki。
请使用 llm-wiki-cloud-query 查询 AscendC tiling 优化的注意事项，回答 3 条要点。
执行 llm-wiki-cloud-backflow，为这次测试创建本地任务归档，不上传。
```

### OpenCode

从测试分支远程安装到隔离目录：

```bash
tmpdir="$(mktemp -d)"
git clone --depth 1 --branch codex/multiclient-distribution-spec \
  git@github.com:AndyKong2020/LLM-Wiki-Marketplace-Multiclient-Test.git "$tmpdir/marketplace"
bash "$tmpdir/marketplace/dist/opencode/install-opencode.sh" --prefix "$tmpdir/opencode"
```

更新：

```bash
git -C "$tmpdir/marketplace" pull --ff-only
bash "$tmpdir/marketplace/dist/opencode/install-opencode.sh" --prefix "$tmpdir/opencode"
```

启动隔离 OpenCode 会话：

```bash
export HOME="$tmpdir/home"
export XDG_CONFIG_HOME="$tmpdir/xdg-config"
export XDG_DATA_HOME="$tmpdir/xdg-data"
export XDG_CACHE_HOME="$tmpdir/xdg-cache"
export OPENCODE_CONFIG="$tmpdir/opencode/opencode.json"
export OPENCODE_CONFIG_DIR="$tmpdir/opencode"
mkdir -p "$HOME" "$XDG_CONFIG_HOME" "$XDG_DATA_HOME" "$XDG_CACHE_HOME" "$OPENCODE_CONFIG_DIR"
opencode
```

在 OpenCode 里模拟使用：

```text
/wiki-cloud-mount
请用 CANN-Infer-Wiki 查询 AscendC tiling 优化的注意事项，回答 3 条要点。
/wiki-cloud-backflow
```

OpenCode installer 会把 command、skill 和 MCP config 写入 `--prefix` 指定目录；省略
`--prefix` 才会写入默认 `~/.config/opencode`。重新运行 `install-opencode.sh` 即可覆盖为当前测试版本。

### 隔离测试仓库

多客户端开发先推测试仓库 remote `multiclient-test`，不要推 `origin` 或 `cloud`：

```bash
git push multiclient-test codex/multiclient-distribution-spec
```

确认三端 smoke 测试和人工验收完成后，再由维护者决定是否发布到正式 remote。

## 固定入口和 Token

```text
MCP read:         https://wiki.andykong.top/mcp
Backflow upload: https://wiki.andykong.top/upload/backflow
Assets:          https://wiki.andykong.top/assets/...
```

Backflow 上传是可选的，需配置 api-token：

```bash
export LLM_WIKI_UPLOAD_TOKEN="llmw_<token-from-operator>"
```

Token 由 operator 通过仓库外渠道分发。不要提交 token，不要把 token 写入归档，
也不要粘贴到日志里。

## Generated Adapter 维护

`src/` 和 `platforms/` 是可编辑源头。`scripts/sync_adapters.py` 会生成 Claude Code、
Codex 和 OpenCode adapter，包括 `plugins/llm-wiki-client/`、`.claude-plugin/marketplace.json`、
`.agents/plugins/marketplace.json` 和 `dist/opencode/`。维护生成产物时不要直接手改带有
generated marker 的文件；应修改源模板后运行：

```bash
python3 scripts/sync_adapters.py
python3 scripts/validate_release.py
```

`validate_release.py` 会在临时副本中重新运行 sync，并确认当前 generated outputs 与模板
生成结果一致；因此同步后的 generated 产物即使尚未提交也可以通过，手工改动或漏生成仍会失败。

## 目录结构

```text
.claude-plugin/marketplace.json
.agents/plugins/marketplace.json
plugins/llm-wiki-client/
  .claude-plugin/plugin.json
  .codex-plugin/plugin.json
  .mcp.json
  README.md
  commands/
    wiki-cloud-mount.md
    wiki-cloud-backflow.md
  skills/
    llm-wiki-cloud-mount/SKILL.md
    llm-wiki-cloud-query/SKILL.md
    llm-wiki-cloud-backflow/SKILL.md
  codex/skills/
    llm-wiki-cloud-mount/SKILL.md
    llm-wiki-cloud-query/SKILL.md
    llm-wiki-cloud-backflow/SKILL.md
dist/opencode/
  install-opencode.sh
  opencode.json
  .opencode/
    commands/
    skills/
```
