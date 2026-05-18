# LLM-Wiki Client

CANN-Infer-Wiki 云端服务的 Claude Code 客户端插件。插件通过 root `.mcp.json`
自动注册远程 `cann-infer-wiki-cloud` MCP server，提供两个 slash command，
并用 skills 承载查询和任务回流流程。

## Commands

- `/wiki-cloud-mount`：探活远程 MCP，并在当前项目 `CLAUDE.md` 写入
  LLM-WIKI pin block。
- `/wiki-cloud-backflow`：创建 `.claude/llm-wiki/backflow/<task-slug>/`；
  归档汇报后，如果用户确认且配置了 `LLM_WIKI_UPLOAD_TOKEN`，上传一份 `tar.gz`
  副本。

`llm-wiki-cloud-query` 没有 slash command。它由 `CLAUDE.md` pin block 在需要
CANN-Infer-Wiki 知识的任务阶段自动触发。

## Endpoints

```text
MCP read:        https://wiki.andykong.top/mcp
Backflow upload: https://wiki.andykong.top/upload/backflow
Assets:          https://wiki.andykong.top/assets/...
```

客户端不 clone wiki 仓、不启动本机 server、不需要 GitCode/SSH 权限。MCP 读取
匿名可用；backflow 写入走独立的 token-gated HTTPS 请求。

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

然后用 Claude Code 的 Read 工具读取本地文件。不要只凭 URL、文件名、alt 文本
或上下文推断图片内容。

## Install And Maintenance

安装、更新和仓库维护说明见 repository root `README.md`。
