---
description: 创建本地 LLM-Wiki backflow archive，并准备 PR 交接材料
allowed-tools: Bash
---

使用 `llm-wiki-backflow` skill 为当前任务创建本地 backflow archive。

本 command 不直接运行脚本。`llm-wiki-backflow` skill 按两个步骤执行：先做轨迹归档，再在用户确认后做轨迹上传。

不要解析命令参数。`task-slug` 和 workspace 由 `llm-wiki-backflow` skill 根据当前任务上下文判断。
