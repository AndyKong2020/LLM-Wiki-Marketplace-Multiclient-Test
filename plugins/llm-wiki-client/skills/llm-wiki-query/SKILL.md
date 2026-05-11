---
name: llm-wiki-query
description: 查询和运行时消费 mounted LLM-Wiki。进入新的 LLM/NPU 优化阶段、方案分析、策略选择、debug 调试、性能回归分析、model/kernel/case/gene/capsule/source 问题时使用。
allowed-tools: Read Grep Bash Write Edit
version: 0.1.0
---

# LLM-Wiki Query

## 1. 要查 Wiki 的场景

本节定义的是“哪些任务阶段必须查 wiki”，不是让 agent 临时判断是否要调用。`/wiki-mount` 写入的 `CLAUDE.md` pin block 会持续要求相关任务使用 `llm-wiki-query`。

遇到下面任一情况时，必须查 LLM-Wiki：

- 进入新的优化阶段，例如 bringup、profiling、kernel tuning、并行策略调整、显存优化、回归定位
- 做方案分析、策略选择或实现路线判断
- debug 调试、性能异常排查、错误模式归因
- 需要查询 model、kernel、case、gene、capsule、source 相关知识
- 需要判断当前任务是否已有 wiki 经验可复用

本 skill 是真实任务运行时的 wiki 入口。使用一次就必须记录一次页面使用记录，并把本次 wiki 查询摘要同步写入当前阶段的 `progress.md`。

## 2. 定位 Wiki

从当前项目 `CLAUDE.md` 的 LLM-WIKI pin block 读取 wiki cache：

```text
<!-- LLM-WIKI:BEGIN -->
...
cache_path: <absolute cache path>
...
<!-- LLM-WIKI:END -->
```

把 `cache_path` 记为 `$WIKI_ROOT`。如果 `CLAUDE.md` 不存在，或没有完整 LLM-WIKI pin block，要求用户先运行 `/wiki-mount`，不要猜测路径。

## 3. Wiki 目录

LLM-Wiki 是面向 LLM/NPU 推理优化的结构化 Markdown wiki。它不把“有哪些模型、算子、经验”写死在 skill 里；这些事实都要在运行时从 wiki 文件现读。

### 内容分层

```text
$WIKI_ROOT/
├── wiki/                 # 知识平面
│   ├── index/            #   顶层索引 + 各类型子索引
│   ├── cases/            #   优化、排障、回归案例
│   ├── models/           #   模型画像页
│   ├── kernels/          #   算子 / 执行单元页
│   ├── parallelism/      #   并行策略页
│   ├── platform/         #   硬件平台页
│   ├── quantization/     #   量化方法页
│   ├── modules/          #   模型组件页
│   ├── framework/        #   推理框架页
│   └── technique/        #   优化技术页
├── experience/           # 经验平面
│   ├── index.md          #   经验层入口
│   ├── genes/            #   策略模板（Gene）
│   ├── capsules/         #   场景实例（Capsule）
│   └── q_table.json      #   预留的效用快照
├── sources/              # 来源层：外部证据入口
├── schema/               # 活规范
├── agents/               # Agent 角色定义
├── templates/            # 页面模板
└── log/                  # 变更日志
```

### 三层信息架构

| 层 | 目录 | 作用 | 典型内容 |
|---|---|---|---|
| 来源层 | `sources/` | 记录外部资料、任务归档和关键路径 | Git 仓库、progress、报告、profiling 摘要 |
| 知识层 | `wiki/` | 整理后的稳定知识，结论应能回链 evidence/source | 模型画像、算子行为、优化案例、策略对比 |
| 经验层 | `experience/` | 运行时可复用的策略和实例 | gene、capsule |

信息流向通常是：`sources/` 提供证据，`wiki/` 整理稳定知识，`experience/` 抽取可复用策略和场景实例。

### 知识页类型

wiki 通常包含这些类型：

| 类型 | 目录 | 覆盖范围 |
|---|---|---|
| Case | `wiki/cases/` | 业务案例、排障过程、优化任务 |
| Model | `wiki/models/` | 模型结构、部署参数、已知热点 |
| Kernel | `wiki/kernels/` | 算子角色、性能信号、优化要点 |
| Parallelism | `wiki/parallelism/` | TP / EP / CP / DP / 多流并行 |
| Platform | `wiki/platform/` | NPU 代际、算力规格、互联拓扑 |
| Quantization | `wiki/quantization/` | W8A8 / W4A16 / FP8 等 |
| Module | `wiki/modules/` | Attention / MoE / Embedding 等组件 |
| Framework | `wiki/framework/` | vLLM / SGLang / AscendC 等 |
| Technique | `wiki/technique/` | Paged Attention / Offload / 多流调度等 |

上表只作结构参考。实际可用类型、页面数量和入口必须从 `$WIKI_ROOT/wiki/index/index.md` 现读。

### Gene 与 Capsule

- **Gene**：可跨任务复用的策略模板，回答“什么情况下用什么方法”。
- **Capsule**：某个 gene 在真实环境中的执行实例，回答“这个方法在什么条件下怎么生效”。

真实任务优先从 `experience/index.md` 和相关 gene 进入；capsule、wiki page、source 都是按需下钻层。

## 4. 执行查询

执行查询时按下面六步走：

1. **理解问题**：判断当前阶段是在做事实查询、策略选择、对比分析、溯源验证还是 debug 调试。
2. **读取入口**：先读 `$WIKI_ROOT/experience/index.md`，再读 `$WIKI_ROOT/wiki/index/index.md`。不要凭记忆假设有哪些类型或页面。
3. **选择页面**：从 experience 里选择相关 gene，从 wiki index 里定位相关 case、model、kernel 或其他知识页。
4. **深入阅读**：读取目标页正文。策略类问题重点看 gene 的策略、约束和已知 capsule；案例类问题重点看 case、capsule 和相关 model/kernel。
5. **按需溯源**：需要验证结论时，沿页面中的 `[[sources/...]]` 或 Evidence 读 source。source 只用于证据回溯，不当作知识页。
6. **写入记录**：每读一个页面，就写入 `wiki_usage.md`；本次查询对阶段判断有影响时，同时把摘要写入 `progress.md`。gene 页面要在阶段结束或 subagent 返回前补充分数。

不要预加载整个 wiki。只读取当前阶段需要的页面；沿 wikilink 继续下钻时，也要遵守同样规则。

## 5. 页面使用记录

每次使用本 skill 都必须写页面使用记录。页面级记录文件放在当前任务 `progress.md` 的同级目录，文件名固定为：

```text
wiki_usage.md
```

如果当前任务有多个 `progress.md`，选择正在更新的那个阶段目录。如果当前阶段还没有 `progress.md`，先在当前阶段目录创建 `wiki_usage.md`，不要写到 `.claude/` 隐藏目录。

`wiki_usage.md` 只记录页面使用记录，不写 YAML，不写总表。每个使用过的页面用一级标题记录，标题直接写 wiki 内相对 path。

````md
# experience/genes/<gene>.md

## 原因

为什么读取这个页面。

## 效果

这个页面对当前阶段的实际帮助。

## 分数

- overall: -1 | 0 | 1
- relevance: <number in [-1, 1]>
- actionability: <number in [-1, 1]>
- correctness: <number in [-1, 1]>

## 备注

保留限制、误导点、后续是否继续使用。

# wiki/<path>.md

## 原因

为什么读取这个页面。

## 效果

这个页面对当前阶段的实际帮助。

## 备注

保留限制、误导点、后续是否继续使用。
````

非 gene 页面只写原因、效果和备注。gene 页面必须写多个分数。`overall` 表征总体有用性，只能从 `-1`、`0`、`1` 中选择；`relevance`、`actionability`、`correctness` 取值范围都是 `[-1, 1]`。

同一页面被多次使用时，不要新建重复一级标题；在已有标题下追加新的原因、效果或备注。

### Progress 同步记录

每次使用 wiki 后，也要把查询摘要写入当前阶段的 `progress.md`。不要把完整页面使用记录复制进 `progress.md`；这里只写阶段进展可读的短记录。

优先追加到当前阶段小节下；如果找不到合适位置，在文件末尾创建：

```md
## Wiki 查询记录
```

每次查询追加一条 Markdown bullet：

```md
- 查阅：`experience/genes/<gene>.md`、`wiki/<path>.md`
  - 目的：本次为什么查 wiki
  - 结论：对当前阶段产生了什么影响
  - 记录：`wiki_usage.md`
```

`progress.md` 记录的是阶段进展摘要；`wiki_usage.md` 记录的是逐页面原因、效果、分数和备注。两者都要写。

## 6. Subagent 规则

subagent 使用本 skill 时，也要写入同一个 `wiki_usage.md`。如果 subagent 无法直接写文件，必须在返回给主 agent 时提供可追加的 Markdown 片段。

subagent 返回给主 agent 前，必须完成 gene 有用性评分。评分只针对本 subagent 实际读过的 gene 页面，写在该 gene 页面标题下的 `## 分数` 中；`overall` 只能取 `-1`、`0`、`1`。

subagent 的最终回复里要带上 `wiki_usage.md` 路径，以及本次新增或更新的页面标题列表。

## 7. 主 Agent 规则

主 agent 每进入一个新阶段时，如果使用了 wiki，就在该阶段 `progress.md` 同级的 `wiki_usage.md` 中记录页面使用情况。

单个阶段结束时，主 agent 要评估本阶段实际使用过的 gene 页面是否有用，并把多个分数写回对应 gene 页面标题下。`overall` 只能取 `-1`、`0`、`1`。

如果阶段中调用了 subagent，主 agent 可以整理 subagent 返回的 Markdown 片段并追加到同一个 `wiki_usage.md`，但不要改写 subagent 已经明确给出的原因、效果和分数。

## 8. 边界

不要修改 mounted wiki cache、upstream wiki、`experience/q_table.json`。

不要在 query 阶段生成或应用 patch。

需要回流时使用 `/wiki-backflow`。backflow 会把 workspace 中的 `wiki_usage.md` 一并归档到任务 source。
