---
description: 为当前项目挂载固定的 LLM-Wiki 仓库
---

使用 `llm-wiki-mount` skill 为当前项目执行 mount。

不要解析命令参数，不要在 command 中展开流程，不要直接执行脚本。mount 的执行步骤、幂等规则和结果汇报都以 `llm-wiki-mount` skill 为准。
