---
name: Hello Plugin
description: Example of the stable nous-plugin/1 format.
trigger_keywords:
  - hello plugin
  - nous-plugin
  - 插件示例
trigger_intent: 说明如何编写并导入一个稳定的 Nous 插件
workflow:
  - step: 1
    action: 确认用户要的是插件格式说明，而不是运行外部脚本
  - step: 2
    action: 给出 plugin.json + SKILL.md 的最小结构
confidence: 0.9
---

这是一个 **nous-plugin/1** 示例。导入后会变成一条可检索 Skill。

稳定契约：

1. 根目录放 `plugin.json`（`format` 必须是 `nous-plugin/1`）。
2. 每个 Skill 一个目录，内含 `SKILL.md`。
3. 若需要可执行工具，在 Skill 下提供 `tools/*.tool.json` + Python `scripts/`（权限需 `script.python`）。
4. 不支持在插件里跑 Node / Cordis `apply()`。DeepSeek Harness 仓库可以导入为 Skill 说明，但 TypeScript 运行时不会执行。
