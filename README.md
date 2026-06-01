# LLM-Wiki Marketplace

本仓库是 **CANN-Infer-Wiki** 云服务的多客户端插件市场，面向 Claude Code、Codex
和 OpenCode 分发同一套云端 wiki 读写入口。

Marketplace 名称：`llm-wiki-cloud`
插件：`llm-wiki-client@llm-wiki-cloud`

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

在需要挂载知识库的项目中运行 `/llm-wiki-client:wiki-cloud-mount`。它会探活远程
MCP，并向 `CLAUDE.md` 写入 wiki 使用提示。正常使用 Claude Code；任务进入
LLM/NPU 推理优化相关阶段时，`llm-wiki-cloud-query` skill 通过 MCP tools 查询
wiki。任务结束后可运行 `/llm-wiki-client:wiki-cloud-backflow` 创建本地任务归档；
若用户确认且配置了 `LLM_WIKI_UPLOAD_TOKEN`，插件会通过私有 HTTP backflow 入口上传归档。

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

使用：让 Codex 执行 `llm-wiki-cloud-mount`，在 LLM/NPU 推理优化任务中使用
`llm-wiki-cloud-query`，任务结束后执行 `llm-wiki-cloud-backflow`。Codex adapter
会通过插件 manifest 指向 `plugins/llm-wiki-client/codex/skills/`。

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

OpenCode installer 会把 command、skill 和 MCP config 写入 OpenCode 配置目录；重新运行
`install-opencode.sh` 即可覆盖为当前发布版本。

### 隔离测试仓库

多客户端开发先推 private 测试仓库 remote `multiclient-test`，不要推 `origin` 或
`cloud`：

```bash
git push multiclient-test "$BRANCH"
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
