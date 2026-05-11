# LLM-Wiki Marketplace

本仓库是 LLM-Wiki 的 Claude Code 插件市场，只维护用户端插件和安装入口。LLM-Wiki 知识库内容继续由 `git@gitcode.com:AndyKong2020/LLM-Wiki.git` 维护，插件发布与 wiki 内容更新彼此解耦。

## 安装

添加 marketplace：

```bash
claude plugin marketplace add AndyKong2020/LLM-Wiki-Marketplace --scope user
```

安装客户端插件：

```bash
claude plugin install llm-wiki-client@llm-wiki --scope user
```

安装后，在需要使用 LLM-Wiki 的项目中执行：

```text
/wiki-mount
```

`/wiki-mount` 会把固定 wiki 仓库拉到本机 cache，并在当前项目的 `CLAUDE.md` 写入 wiki 使用说明。后续真实任务结束后，可以使用 `/wiki-backflow` 归档任务轨迹并回流到 wiki 主仓。

## 仓库边界

- `LLM-Wiki-Marketplace` 只维护 Claude Code 插件、commands、skills 和 marketplace manifest。
- `LLM-Wiki` 只维护知识库内容、schema、agents、experience、sources 和 wiki 页面。
- 插件通常很少更新；wiki 内容通过 `/wiki-mount` 自己拉取最新主仓，不依赖插件发版。

## 本地开发

本地调试 marketplace：

```bash
cd /path/to/LLM-Wiki-Marketplace
claude plugin marketplace add "$(pwd)" --scope user
claude plugin install llm-wiki-client@llm-wiki --scope user
```

修改插件后执行校验：

```bash
claude plugin validate .
claude plugin validate plugins/llm-wiki-client
```

发布新版本时，需要同步更新：

- `.claude-plugin/marketplace.json`
- `plugins/llm-wiki-client/.claude-plugin/plugin.json`
