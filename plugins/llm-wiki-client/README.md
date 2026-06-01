# LLM-Wiki Client

CANN-Infer-Wiki 云端服务的多客户端 adapter。`plugins/llm-wiki-client/` 同时承载
Claude Code 和 Codex adapter；OpenCode adapter 由同一套源模板生成到 repository root
的 `dist/opencode/`。

## Commands And Skills

Claude Code slash commands：

- `/llm-wiki-client:wiki-cloud-mount`：探活远程 MCP，并在当前项目 `CLAUDE.md` 写入 LLM-WIKI pin block。
- `/llm-wiki-client:wiki-cloud-backflow`：创建 `.claude/llm-wiki/backflow/<task-slug>/`；归档汇报后，
  如果用户确认且配置了 `LLM_WIKI_UPLOAD_TOKEN`，上传一份 `tar.gz` 副本。

`llm-wiki-cloud-query` 没有 slash command。它由 pin block 在需要 CANN-Infer-Wiki
知识的任务阶段自动触发。Codex 使用同名 skills，但从 `codex/skills` 读取，避免混用
Claude Code 专属 tool 名。

## Adapter Layout

`plugins/llm-wiki-client/` 内的 adapter 文件包括：

- `.claude-plugin/plugin.json`：Claude Code plugin manifest。
- `.codex-plugin/plugin.json`：Codex plugin manifest，skill root 指向 `./codex/skills/`。
- `.mcp.json`：Claude Code / Codex 共享的远程 MCP 配置。
- `commands/`：Claude Code slash command。
- `skills/`：Claude Code skills。
- `codex/skills/`：Codex skills。

OpenCode adapter 不放在本目录内，而是生成到 root `dist/opencode/`：

- `dist/opencode/install-opencode.sh`
- `dist/opencode/opencode.json`
- `dist/opencode/.opencode/commands/`
- `dist/opencode/.opencode/skills/`

## Generated Adapter Maintenance

本 README 是维护文档；其他 adapter 产物不要手工编辑 generated adapter。维护者应修改
`src/` 和 `platforms/` 下的源模板，然后重新生成并校验：

```bash
python3 scripts/sync_adapters.py
python3 scripts/validate_release.py
```

修改三端行为时，优先调整 `src/commands/`、`src/skills/` 和对应 `platforms/`
模板；`scripts/sync_adapters.py` 会同步生成 Claude Code、Codex 和 OpenCode adapter。
如果需要更新本 README 的维护说明，也应和 root README 及相关 tests 一起提交。

## Endpoints

```text
MCP read:         https://wiki.andykong.top/mcp
Backflow upload: https://wiki.andykong.top/upload/backflow
Assets:          https://wiki.andykong.top/assets/...
```

MCP 读取匿名可用；backflow 写入走独立的 token-gated HTTPS 请求。

## Backflow Upload

只在本地环境中设置上传 token：

```bash
export LLM_WIKI_UPLOAD_TOKEN="llmw_<token-from-operator>"
```

可选 staging 覆盖：

```bash
export LLM_WIKI_UPLOAD_URL="https://example.test/upload/backflow"
```

上传包约束：

- 源目录：`.claude/llm-wiki/backflow/<task-slug>/`
- 格式：`tar.gz`
- 压缩后大小：不超过 50 MiB
- 顶层：有且只有一个 `.md` 文件
- macOS 打包使用 `COPYFILE_DISABLE=1`，避免带入 `._*` 元数据文件

Server 响应：

| `status` | 含义 |
|---|---|
| `ok` | 上传已接受；汇报 `id`、`path`、`entrypoint`。 |
| `duplicate` | Server 已有相同包；汇报已有 `id` 和 `path`。 |
| `error` | 上传失败；汇报 `error` 和 `message`，保留本地归档。 |

上传成功或 duplicate 后，内容进入服务端 `sources/sessions/uploaded/` 队列。
ingest 异步执行；slash command 不等待 accepted/to_review 处理。

## Image Handling

当 wiki 页面包含 asset URL，且 agent 需要理解图片内容时，先下载到：

```text
/tmp/llm-wiki-assets/<page-id>/<filename>
```

然后用本地图片读取工具检查文件。不要只凭 URL、文件名、alt 文本或上下文推断图片内容。

## Install And Maintenance

安装、更新和仓库维护说明见 repository root `README.md`。
