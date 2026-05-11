---
name: llm-wiki-backflow
description: 任务结束后使用。无参数触发，由 agent 判断 task slug 和 workspace，先归档真实任务轨迹，再在用户确认后上传到 LLM-Wiki PR。
allowed-tools: Bash Read Write
version: 0.1.0
---

# LLM-Wiki Backflow

本 skill 只做两件事：**轨迹归档** 和 **轨迹上传**。

```text
/wiki-backflow
    |
    +--> 1. 轨迹归档：把本次任务整理成本地 sources/<task-slug>/
    |
    +--> 2. 轨迹上传：用户确认后，把 sources/<task-slug>/ 提交到 wiki 仓 PR
```

客户端 backflow 不生成 patch proposal，不修改 `experience/`、`wiki/`、`schema/`、`agents/`、`templates/`，不更新 `experience/q_table.json`。后续 patch proposal 由服务端根据任务归档、`wiki_usage.md`、任务轨迹和当前 wiki 仓生成。

## 1. 轨迹归档

轨迹归档在本地完成，不要求用户提供参数。agent 根据当前任务上下文判断 `task-slug` 和 workspace。

### 1.1 判断 Task Slug 和 Workspace

不要要求 `/wiki-backflow` 传入参数。流程核心是确定 `task-slug`，不是确定 task name。

`task-slug` 固定为：

```text
<YYYY-MM-DD>-<short-ascii-description>
```

判断顺序：

- 如果当前任务已有明确 slug，直接使用。
- 否则从当前 `progress.md` 标题、当前 git branch、最近用户任务描述、workspace 目录名中推断一个短 slug。
- slug 必须使用小写 ASCII、数字和短横线；非字母数字统一转成 `-`。
- slug 是目录名、source id 和 PR 分支名的基础，长度要短，避免整句描述。
- 如果多个 slug 都合理但会影响后续 PR 路径或可读性，先问用户确认。
- 只是不够漂亮时不要问用户；选择一个稳定、可读的 slug。
- 如果本地已存在同名 `.claude/llm-wiki/backflow/<task-slug>/`，不要覆盖。优先复用已有归档继续上传；如果这次是新任务，给 slug 追加短后缀，例如 `-r2`。

workspace 判断：

- workspace 优先选择当前 Claude Code 项目目录。
- 如果当前任务明显在某个子目录完成，则选择该子目录。
- 如果存在多个同样可信的 workspace，且选错会导致归档范围明显不同，先问用户确认。

source entry 的 `title` 只是展示字段。可以从 slug 反推成可读标题，也可以使用 `progress.md` 标题；它不驱动目录、PR 或 ingest 流程。

### 1.2 判断应归档的材料

归档目标是保留后续服务端生成 proposal 所需的证据，而不是镜像整个机器。

优先纳入：

- `progress.md` 或等价任务记录
- `wiki_usage.md`
- 任务相关源码、配置、小型脚本、README、命令记录
- 任务侧 patch、diff、git status，作为普通 workspace 材料保存
- 小型 benchmark 摘要、profiling 摘要、结论截图或文本报告

默认排除：

- profiler raw data、benchmark dump、模型权重、数据集
- 构建产物、依赖目录、缓存目录、虚拟环境
- 大体积二进制文件
- credentials、tokens、keys、`.env*`
- `.git/`、`.idea/`、`.vscode/`、`.claude/llm-wiki/backflow/`、`.claude/llm-wiki/pr-workspaces/`

如果被排除的材料有证据价值，在 source entry 的 `Notes` 中写清原路径、原因、摘要和可访问位置；不要把大文件硬塞进仓库。

### 1.3 创建本地归档

本地工作目录固定为：

```text
.claude/llm-wiki/backflow/<task-slug>/
```

如果该目录已经存在，先判断它是否属于同一次任务：

- 同一次任务：复用目录，增量补齐缺失材料。
- 不是同一次任务：不要删除旧目录，重新选择带后缀的 `task-slug`。

其中真正要上传到 wiki 仓的是：

```text
.claude/llm-wiki/backflow/<task-slug>/sources/<task-slug>/
```

这个目录结构是故意和目标仓库对齐的。上传时可以把本地的 `sources/<task-slug>/` 原样放到 wiki 仓根目录。

归档目录至少包含：

```text
sources/<task-slug>/
├── <task-slug>.md
└── workspace/
```

执行方式由 agent 自行判断。可以使用 `mkdir`、`cp`、`rsync`、`find`、`git status`、`git diff` 等小命令，但不要把整个流程包装成一段大脚本。

建议做法：

- 先创建 `sources/<task-slug>/workspace/`。
- 把判断为相关的任务材料复制到 `workspace/`。
- 如果 workspace 是 git 仓库，可以把 `git status --short` 或 `git diff --no-ext-diff -- .` 保存为普通 workspace 文件。
- 不固定创建 `patches/` 目录；是否保存 diff、保存到哪里，由 agent 根据当前任务判断。
- 如果 diff 太大，不要归档原文，只在 `Notes` 说明。

### 1.4 编写 Source Entry

在 `sources/<task-slug>/<task-slug>.md` 写 source entry。frontmatter 遵循 source schema；PR 创建前还没有 fork、分支和稳定 URL，因此 `url`、`repo`、`ref` 先留空，轨迹上传阶段再回写。

注意：空 `url`、`repo`、`ref` 只允许存在于本地归档阶段。提交 PR 或给出人工提交说明前，必须把三者补齐。

推荐结构：

````md
---
url: ""
title: "<display title>"
repo: ""
ref: ""
created_at: <YYYY-MM-DD>
updated_at: <YYYY-MM-DD>
---

# <display title>

## Summary


## Task Trace

给出 `progress.md` 的路径链接

## Wiki Usage History

给出 `wiki_usage.md` 的路径链接

## Archive Layout

展示该条source的目录结构。

## Notes

- 未归档的大文件、raw profiler、数据集、模型权重等在这里说明原路径、排除原因和可访问位置。
- 如果没有 `progress.md` 或任务轨迹不完整，在这里说明。

````

如果没有找到 `progress.md` 或等价任务记录，必须在 `Summary` 或 `Notes` 中说明证据链不完整。

### 1.5 汇报并等待确认

轨迹归档完成后，向用户汇报：

- 本地 archive 路径
- 将上传的 `sources/<task-slug>/` 路径
- 纳入了哪些关键文件
- 排除了哪些重要文件以及原因

在用户确认前，不进入轨迹上传。

## 2. 轨迹上传

轨迹上传只在用户确认后执行。上传对象固定为：

```text
sources/<task-slug>/
```

不要上传 `experience/`、`wiki/`、`schema/`、`agents/`、`templates/` 或其他控制面文件。

### 2.1 检查 GitCode 发布能力

先检查本机是否可用 GitCode 自动发布能力：

```bash
claude plugin list
```

如果 `gitcode-api@awesome-claude-infra` 已安装并启用，使用 `gitcode-api` skill 创建或复用 fork，并在本地 PR workspace 完成文件提交后创建 PR。

如果插件不存在，帮助用户安装：

```bash
claude plugin install gitcode-api@awesome-claude-infra --scope user
```

如果插件已安装但未启用，帮助用户启用：

```bash
claude plugin enable gitcode-api@awesome-claude-infra
```

安装或启用后，按 Claude Code 的提示让用户 reload；如果必须重启，告诉用户重启后 resume 当前会话继续。插件不可用时，不中止 backflow；保留本地 archive，并给出人工提交步骤。

### 2.2 创建 PR

使用固定 upstream：

```text
git@gitcode.com:AndyKong2020/LLM-Wiki.git
main
```

上传必须在独立 PR workspace 中操作，不要在当前业务 workspace 或 mounted wiki cache 中直接提交。

上传采用一种固定模型：**本地 git workspace 提交文件，GitCode API 只用于确认或创建 fork、创建 PR**。不要同时使用 GitCode API 文件写入和本地 git 提交两套方式。

目录约定：

```text
<project>/.claude/llm-wiki/backflow/<task-slug>/sources/<task-slug>/   # 已生成的本地归档，只读输入
<project>/.claude/llm-wiki/pr-workspaces/<task-slug>/                  # 本次上传使用的 wiki fork 工作区
```

其中 `<project>` 是当前 Claude Code 项目目录。`pr-workspaces/<task-slug>/` 可以删除重建；`backflow/<task-slug>/` 不要在上传阶段删除。

上传顺序：

1. 在 `<project>/.claude/llm-wiki/pr-workspaces/` 下创建或清理本次 `<task-slug>/` 工作区。
2. 使用 `gitcode-api` skill 确认或创建用户 fork，取得 fork 的 clone URL 和 `owner/repo`。
3. 在 PR workspace 中 clone 用户 fork，remote `origin` 指向用户 fork。
4. 在 PR workspace 中添加或确认 remote `upstream` 指向 `git@gitcode.com:AndyKong2020/LLM-Wiki.git`。
5. fetch `upstream main`，从 `upstream/main` 创建任务分支，分支名使用 `backflow/<task-slug>`。
6. 只从本地归档复制 `backflow/<task-slug>/sources/<task-slug>/` 到 PR workspace 的 `sources/<task-slug>/`。
7. 在 PR workspace 中回写 `sources/<task-slug>/<task-slug>.md` 的 `url`、`repo`、`ref`：
   - `url` 指向 fork 任务分支上的 `sources/<task-slug>/`
   - `repo` 使用 fork 的 `owner/repo`
   - `ref` 使用任务分支名；PR 创建后如果能取得 commit SHA，可以更新为 commit SHA
8. 在 PR workspace 中检查 `git status --short`，确认实际改动只包含 `sources/<task-slug>/`。
9. commit 并 push `backflow/<task-slug>` 到用户 fork。
10. 使用 `gitcode-api` skill 创建从用户 fork 任务分支到 upstream `main` 的 PR。
11. 返回 PR URL。

如果第 8 步发现 `experience/`、`wiki/`、`schema/`、`agents/`、`templates/` 或其他路径变更，停止上传并修正 PR workspace。不要把这些路径提交出去。

如果 `backflow/<task-slug>` 分支在 fork 中已存在，先判断是否是同一次任务：

- 同一次任务：允许 force-with-lease 更新该任务分支。
- 不是同一次任务：不要覆盖旧分支，回到轨迹归档阶段重新选择带后缀的 `task-slug`。

PR 描述至少包含：

- 任务摘要
- 上传的 `sources/<task-slug>/`
- `wiki_usage.md` 是否存在
- `progress.md` 是否存在
- 主要排除项
- 后续处理：服务端生成 patch proposal，再进入 patch-merge 和 Ingest Apply

GitCode 插件不可用时，输出本地 `sources/<task-slug>/` 路径和人工提交说明，不要伪造 PR URL。人工提交说明必须提醒用户：提交前先回写 `<task-slug>.md` 的 `url`、`repo`、`ref`，并且 PR 只能包含 `sources/<task-slug>/`。
