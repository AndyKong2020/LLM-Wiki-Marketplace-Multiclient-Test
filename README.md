# LLM-Wiki Marketplace

本仓库是 **CANN-Infer-Wiki** 的 Claude Code 云端客户端插件市场。这里
只维护客户端插件、commands、skills、marketplace manifest 和插件自带的
`.mcp.json`；wiki 内容、MCP server、ingest、上传 token 和部署运维都在云端
服务仓维护。

Marketplace 名称：`llm-wiki-cloud`
插件安装目标：`llm-wiki-client@llm-wiki-cloud`

Cloud 版和旧本地版 `llm-wiki-client@llm-wiki` 使用不同 marketplace 名称，
可以在迁移期并存。

## 安装

日常 user-scope 安装：

```bash
claude plugin marketplace add AndyKong2020/LLM-Wiki-Marketplace-Cloud --scope user
claude plugin install llm-wiki-client@llm-wiki-cloud --scope user
```

隔离 project-scope 测试：

```bash
claude plugin marketplace add AndyKong2020/LLM-Wiki-Marketplace-Cloud --scope project
claude plugin install llm-wiki-client@llm-wiki-cloud --scope project
```

如果旧本地插件仍处于 enabled，建议禁用，避免 agent 同时看到两套 wiki 入口：

```bash
claude plugin disable llm-wiki-client@llm-wiki --scope user
```

当前 Claude Code 会话已启动时，安装或更新后运行：

```text
/reload-plugins
```

更新：

```bash
claude plugin update llm-wiki-client@llm-wiki-cloud --scope user
```

project-scope 安装把 `--scope user` 换成 `--scope project`。

## 用户流程

1. 在项目中运行 `/wiki-cloud-mount`。它会探活远程 MCP，并向 `CLAUDE.md`
   写入 LLM-WIKI pin block。
2. 正常工作。任务进入 LLM/NPU 推理优化相关阶段时，`llm-wiki-cloud-query`
   skill 通过 MCP tools 查询 wiki。
3. 任务结束后运行 `/wiki-cloud-backflow` 创建本地任务归档。若用户确认且配置了
   `LLM_WIKI_UPLOAD_TOKEN`，插件会通过私有 HTTP backflow 入口上传归档。

固定入口：

```text
MCP read:        https://wiki.andykong.top/mcp
Backflow upload: https://wiki.andykong.top/upload/backflow
Assets:          https://wiki.andykong.top/assets/...
```

Backflow 上传是可选的 token-gated 能力：

```bash
export LLM_WIKI_UPLOAD_TOKEN="llmw_<token-from-operator>"
```

Token 由 operator 通过仓库外渠道分发。不要提交 token，不要把 token 写入归档，
也不要粘贴到日志里。

需要理解 wiki 图片内容时，query skill 会把
`https://wiki.andykong.top/assets/...` 下载到
`/tmp/llm-wiki-assets/<page-id>/<filename>`，再用 Claude Code 的 Read 工具读取；
不要只凭 URL、文件名、alt 文本或上下文推断图片内容。

## 仓库边界

- **本仓库**：Claude Code marketplace manifest、plugin manifest、`.mcp.json`、
  slash commands 和 skills。
- **CANN-Infer-Wiki 云服务仓**：wiki 内容、MCP server、assets、ingest、
  上传 token store、部署脚本和运维文档。
- **普通用户**：只安装插件；不 clone wiki 仓、不启动本机 server、不需要
  GitCode/SSH 权限。

## 目录结构

```text
.claude-plugin/marketplace.json
plugins/llm-wiki-client/
  .claude-plugin/plugin.json
  .mcp.json
  README.md
  commands/
    wiki-cloud-mount.md
    wiki-cloud-backflow.md
  skills/
    llm-wiki-cloud-mount/SKILL.md
    llm-wiki-cloud-query/SKILL.md
    llm-wiki-cloud-backflow/SKILL.md
```

## 维护

提交前校验：

```bash
claude plugin validate .
claude plugin validate plugins/llm-wiki-client
```

修改插件行为或发布用户可见版本时，同步更新：

- `.claude-plugin/marketplace.json`
- `plugins/llm-wiki-client/.claude-plugin/plugin.json`
- `plugins/llm-wiki-client/skills/*/SKILL.md` 的 frontmatter version

如果改了 `.mcp.json`，已运行的 Claude Code 会话需要 `/reload-plugins` 才会加载
新的 MCP 配置。

## Smoke Test

安装后预期：

```text
/wiki-cloud-mount
mcp_probe=rpc_ok
```

MCP tools 应包含：

```text
wiki_search
wiki_get_page
wiki_get_index
```

页面图片应使用 HTTPS asset URL：

```text
https://wiki.andykong.top/assets/...
```

当前已验证路径：全新 project-scope 安装可以访问 `https://wiki.andykong.top/mcp`，
获取 HTTPS asset URL，下载图片到本地，并用 Claude Code Read 工具读图。
