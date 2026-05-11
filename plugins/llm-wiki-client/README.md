# LLM-Wiki Client

用于 Claude Code 的 LLM-Wiki 客户端插件。它负责挂载固定的 LLM-Wiki 仓库，并把真实任务轨迹打包为 backflow archive。

## Install

本插件通过 LLM-Wiki marketplace 安装：

```bash
claude plugin marketplace add AndyKong2020/LLM-Wiki-Marketplace --scope user
claude plugin install llm-wiki-client@llm-wiki --scope user
```

## Commands

- `/wiki-mount`：为当前项目挂载固定 wiki 仓库。
- `/wiki-backflow`：创建任务 source archive，供后续 PR 提交。

`/wiki-backflow` 分为两个步骤：

1. 轨迹归档：在本地生成 `.claude/llm-wiki/backflow/<task-slug>/sources/<task-slug>/`。
2. 轨迹上传：用户确认后，只把 `sources/<task-slug>/` 上传到 wiki 仓 PR。

`/wiki-backflow` 不接收参数。`task-slug` 和 workspace 由 agent 根据当前任务上下文判断。

## Fixed Wiki

```text
git@gitcode.com:AndyKong2020/LLM-Wiki.git
main
```

## Local State

全局 cache：

```text
~/.claude/llm-wiki/repos/llm-wiki/
```

项目状态：

```text
<project>/.claude/llm-wiki/
├── backflow/
└── pr-workspaces/
```

mount 状态直接写在项目 `CLAUDE.md` 的 `<!-- LLM-WIKI:BEGIN -->` block 中，不再维护独立的 mount 配置文件。

## Design

插件不启动 server。Slash commands 只作为入口，skills 承载流程规则。mount、query 和 backflow 都直接由 skill 描述执行步骤；插件不再维护独立脚本。
