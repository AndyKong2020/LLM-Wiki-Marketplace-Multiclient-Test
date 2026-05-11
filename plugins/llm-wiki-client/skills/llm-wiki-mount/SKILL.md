---
name: llm-wiki-mount
description: 挂载或刷新固定的 LLM-Wiki 仓库。用于 /wiki-mount、刷新 wiki cache、校验 mounted commit、修复项目 CLAUDE.md pin。
allowed-tools: Bash Read Edit Write
version: 0.1.0
---

# LLM-Wiki Mount

## 1. 概述

`llm-wiki-mount` 把固定的 LLM-Wiki 仓库挂载到当前 Claude Code 项目。mount 不把 wiki 复制进项目，只维护全局 cache 和 `CLAUDE.md` 中的 pin block。

固定输入：

```text
repo: git@gitcode.com:AndyKong2020/LLM-Wiki.git
ref: main
cache: ~/.claude/llm-wiki/repos/llm-wiki/
project: ${CLAUDE_PROJECT_DIR:-$PWD}
```

整体流程：

```text
/wiki-mount
    |
    v
llm-wiki-mount skill
    |
    +--> 拉取最新 wiki
    |       |
    |       +--> 检查 cache 路径
    |       |       |
    |       |       +--> missing -------------> clone main
    |       |       +--> ready git repo -------> fast-forward update
    |       |       +--> invalid -------------> ask user
    |
    +--> 注入 CLAUDE.md
            |
            +--> 检查 LLM-WIKI pin block
            +--> 写入 cache_path
            +--> 汇报 mount 结果
```

## 2. 重要原则

不要向用户询问 repo URL 或 ref。`/wiki-mount` 不接收参数，仓库和分支由本 skill 固定。

不要调用外部脚本。mount 的 git 和 filesystem 操作直接按本 skill 的步骤执行。

mount 必须幂等。cache 已经是最新时不重复 clone；`CLAUDE.md` pin block 内容一致时不重写。

mount 只允许修改两个位置：`~/.claude/llm-wiki/repos/` 下的 wiki cache 目录，以及当前项目 `CLAUDE.md` 中的 LLM-WIKI pin block。不要创建独立的 mount 配置文件。

cache 路径只归并为三种状态：`missing`、`ready`、`invalid`。不要把 `not git`、`remote mismatch`、`dirty`、`ahead`、`diverged` 暴露成独立流程分支。

`invalid` 表示 cache 路径存在但不能安全复用，包括非 git 目录、remote 不匹配、本地未提交改动、本地已提交但未进入 `origin/main`、或与 `origin/main` 分叉。

遇到 `invalid` 时必须暂停并询问用户。给两个选择：暂停 mount，让用户手动处理；或备份当前 cache 并重新 clone 最新 wiki。不要在用户确认前自动覆盖。

不要预加载 wiki 页面，不要复制 wiki 仓库到用户项目，不要修改 mounted wiki cache 中的业务内容。

## 3. 操作步骤

### 3.1 拉取最新 wiki

这一阶段先判断 cache 路径处于哪种状态，再进入对应分支。不要跳过路径探测直接 clone 或 fetch。状态只允许是 `missing`、`ready`、`invalid`。

#### 3.1.1 检查 cache 路径

不要用一整段脚本完成 cache 检查。按顺序执行下面几条短命令，由 agent 根据输出归并状态。能直接根据文件存在性、remote、status 判断的事情，不要再包装成脚本判断器。

先设置固定路径：

```bash
REPO_URL="git@gitcode.com:AndyKong2020/LLM-Wiki.git"
CACHE_PATH="${HOME}/.claude/llm-wiki/repos/llm-wiki"
```

判断路径是否存在：

```bash
CACHE_PATH="${HOME}/.claude/llm-wiki/repos/llm-wiki"
test -e "$CACHE_PATH" && printf 'exists\n' || printf 'missing\n'
```

如果输出 `missing`，状态就是 `missing`，直接进入 `3.1.2`。

如果路径存在，确认它是不是 git repo：

```bash
CACHE_PATH="${HOME}/.claude/llm-wiki/repos/llm-wiki"
test -d "$CACHE_PATH/.git" && printf 'git_repo\n' || printf 'invalid\n'
```

如果输出 `invalid`，状态就是 `invalid`，进入 `3.1.4`。

如果是 git repo，检查 remote：

```bash
CACHE_PATH="${HOME}/.claude/llm-wiki/repos/llm-wiki"
git -C "$CACHE_PATH" config --get remote.origin.url
```

输出必须等于 `git@gitcode.com:AndyKong2020/LLM-Wiki.git`。否则状态是 `invalid`，进入 `3.1.4`。

remote 正确后，检查是否有未提交改动：

```bash
CACHE_PATH="${HOME}/.claude/llm-wiki/repos/llm-wiki"
git -C "$CACHE_PATH" status --porcelain
```

输出为空时，状态暂定为 `ready`。输出非空时，状态是 `invalid`，进入 `3.1.4`。

最后确认本地 `HEAD` 是否能安全对齐远端：

```bash
CACHE_PATH="${HOME}/.claude/llm-wiki/repos/llm-wiki"
git -C "$CACHE_PATH" fetch origin main --prune
git -C "$CACHE_PATH" rev-parse HEAD
git -C "$CACHE_PATH" rev-parse origin/main
git -C "$CACHE_PATH" merge-base --is-ancestor HEAD origin/main && printf 'safe_to_update\n' || printf 'invalid\n'
```

如果本地 `HEAD` 等于 `origin/main`，状态是 `ready`，进入 `3.1.3` 后会得到 `already_latest`。如果输出 `safe_to_update`，状态是 `ready`，进入 `3.1.3` 后会 fast-forward。否则状态是 `invalid`，进入 `3.1.4`。

根据 `cache_state` 选择下一步：

- `missing`：执行 `3.1.2`。
- `ready`：执行 `3.1.3`。
- `invalid`：执行 `3.1.4`。

#### 3.1.2 cache 不存在时 clone

仅当 `cache_state=missing` 时执行：

```bash
set -euo pipefail

REPO_URL="git@gitcode.com:AndyKong2020/LLM-Wiki.git"
REF="main"
CACHE_ROOT="${HOME}/.claude/llm-wiki/repos"
CACHE_PATH="${CACHE_ROOT}/llm-wiki"

mkdir -p "$CACHE_ROOT"

remote_commit="$(git ls-remote "$REPO_URL" "refs/heads/$REF" | awk '{print $1}')"
if [ -z "$remote_commit" ]; then
  printf 'ok=false\n'
  printf 'error_code=remote_ref_not_found\n'
  printf 'message=找不到远端 ref：%s\n' "$REF"
  exit 1
fi

git clone --branch "$REF" --single-branch "$REPO_URL" "$CACHE_PATH" >/dev/null

printf 'ok=true\n'
printf 'cache_status=cloned\n'
printf 'cache_path=%s\n' "$CACHE_PATH"
```

#### 3.1.3 cache 已存在时更新

仅当 `cache_state=ready` 时执行：

```bash
set -euo pipefail

REF="main"
CACHE_PATH="${HOME}/.claude/llm-wiki/repos/llm-wiki"

current_branch="$(git -C "$CACHE_PATH" rev-parse --abbrev-ref HEAD)"
if [ "$current_branch" != "$REF" ]; then
  git -C "$CACHE_PATH" checkout "$REF" >/dev/null
fi

local_before="$(git -C "$CACHE_PATH" rev-parse HEAD)"
remote_commit="$(git -C "$CACHE_PATH" rev-parse "origin/$REF")"

if [ "$local_before" = "$remote_commit" ]; then
  cache_status="already_latest"
else
  git -C "$CACHE_PATH" merge --ff-only "origin/$REF" >/dev/null
  cache_status="updated"
fi

printf 'ok=true\n'
printf 'cache_status=%s\n' "$cache_status"
printf 'cache_path=%s\n' "$CACHE_PATH"
```

#### 3.1.4 invalid 处理

`invalid` 状态下先暂停，向用户说明 cache 路径和 invalid 原因，然后让用户选择：

- 暂停 mount，让用户手动处理 cache。
- 备份当前 cache，并重新 clone 最新 wiki 覆盖标准 cache 路径。

用户选择暂停时，停止 mount，不改 `CLAUDE.md`。

用户选择重新 clone 时，先把旧 cache 移到同一 cache root 下的备份目录，再重新 clone 最新 wiki 到标准 cache 路径。执行：

```bash
set -euo pipefail

REPO_URL="git@gitcode.com:AndyKong2020/LLM-Wiki.git"
REF="main"
CACHE_ROOT="${HOME}/.claude/llm-wiki/repos"
CACHE_PATH="${CACHE_ROOT}/llm-wiki"
BACKUP_PATH="${CACHE_PATH}.backup.$(date '+%Y%m%d%H%M%S')"

if [ -e "$CACHE_PATH" ]; then
  mv "$CACHE_PATH" "$BACKUP_PATH"
fi

mkdir -p "$CACHE_ROOT"
git clone --branch "$REF" --single-branch "$REPO_URL" "$CACHE_PATH" >/dev/null

printf 'ok=true\n'
printf 'cache_status=recloned\n'
printf 'cache_path=%s\n' "$CACHE_PATH"
printf 'backup_path=%s\n' "$BACKUP_PATH"
```

重新 clone 成功后进入 `3.2`。

### 3.2 注入 CLAUDE.md

这一阶段只处理当前项目的 `CLAUDE.md`。它不会读取 wiki 内容，也不会改动 pin block 之外的文本。

#### 3.2.1 定位文件

`CLAUDE.md` 位于当前项目根目录。项目目录优先使用 `CLAUDE_PROJECT_DIR`，否则使用当前工作目录。

不要用脚本修改 `CLAUDE.md`。直接读取文件内容，按下面规则用文件编辑能力完成更新。

#### 3.2.2 使用的 pin block

标准 block 使用下面的格式。`cache_path` 使用前面步骤输出的 cache path。

```md
<!-- LLM-WIKI:BEGIN -->
本项目已挂载 LLM-Wiki。
cache_path: <absolute cache path>
涉及 LLM/NPU optimization、model、kernel、framework、quantization、parallelism、case、gene、capsule、source、新优化阶段、方案分析、策略选择或 debug 调试时，必须使用 llm-wiki-query skill。
涉及 subagent 拉起，需让 subagent 使用 llm-wiki-query skill。
使用 llm-wiki-query 后，必须把页面级记录写到当前阶段 progress.md 同级的 wiki_usage.md，并把查询摘要同步写入 progress.md。
按需从 mounted cache 读取 wiki 内容，不要预加载整个 wiki。
<!-- LLM-WIKI:END -->
```

#### 3.2.3 编辑规则

如果 `CLAUDE.md` 不存在，创建文件，内容就是填入实际 `cache_path` 后的标准 block，并记 `claude_md_status=created`。

如果 `CLAUDE.md` 同时存在 `<!-- LLM-WIKI:BEGIN -->` 和 `<!-- LLM-WIKI:END -->`，只比较并替换这两个标记之间的完整 block。内容一致时不编辑，记 `claude_md_status=already_current`；内容不一致时只替换 block 内文本，记 `claude_md_status=updated`。

如果 `CLAUDE.md` 不包含任何 LLM-WIKI 标记，把标准 block 追加到文件末尾。追加前保留原文，原文末尾补一个空行，记 `claude_md_status=created`。

如果 `CLAUDE.md` 只存在开始标记或只存在结束标记，停止 mount。汇报 `error_code=claude_pin_broken`，要求用户先手动修复该文件。

### 3.3 汇报结果

两个一级步骤都成功后，只汇报这些字段：`cache_status`、`cache_path`、`claude_md_status`。

不要转述完整命令输出，不要展开 cache 内部文件列表。
