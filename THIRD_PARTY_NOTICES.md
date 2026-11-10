# 第三方声明 / Third-Party Notices

本仓库是 AgentFlow 的**可运行核心**，整体按 [Apache License 2.0](LICENSE) 提供。
**仓库内不包含任何第三方技能内容**：`skills/` 只保留一个空目录、本仓库自写的说明文件与 `.gitkeep`，用作运行时挂载点。

## 为什么不随附技能

开发过程中曾使用过一批社区技能，但它们的许可状态并不一致，无法作为一个整体按 Apache-2.0 再分发。整理时逐个核查了 26 个技能目录（依据各目录内 `LICENSE` / `LICENSE.txt` 的前几行）：

| 许可状态 | 数量 | 目录 |
|:--|:--:|:--|
| Apache-2.0 | 9 | `algorithmic-art`、`brand-guidelines`、`canvas-design`、`frontend-design`、`internal-comms`、`mcp-builder`、`skill-creator`、`webapp-testing`、`web-artifacts-builder` |
| MIT | 4 | `academic-search`、`frontend-slides-main`、`html-ppt-skill-main`、`ppt-master` |
| **All rights reserved** | 1 | `pdf` |
| **无许可声明** | 12 | `brainstorming`、`chart-visualization`、`clinical-case-report`、`doc-coauthoring`、`excel`、`lit-review-notes`、`meeting-minutes`、`ppt-generation`、`statistical-analyst`、`systematic-debugging`、`test-driven-development`、`writing-plans` |

## 处理原则

- **Apache-2.0 / MIT**：允许再分发，前提是保留原始 `LICENSE` 与版权声明。本项目出于体积与维护成本考虑，选择不随仓库分发，改由使用者按需安装。
- **`pdf`（All rights reserved）**：许可明确保留所有权利，**不得**并入本仓库或任何再分发产物。
- **无许可声明的 12 个目录**：缺省即「保留所有权利」，同样不得再分发。若上游后续补充了明确的开源许可，可重新评估。
- **`assets/` 中的截图、GIF 与录屏**：本项目自行采集的演示素材，随本仓库按 Apache-2.0 提供。
- **Python / Node 依赖**：`backend/requirements*.txt` 与 `frontend/package.json` 声明的第三方包由包管理器在安装时获取，其源码不在本仓库内复制，各自遵循上游许可。

## 按需安装技能

1. 从技能的上游仓库获取副本，**保留其原始 LICENSE**；
2. 放进 `skills/<技能名>/`（目录内含 `SKILL.md`）；
3. 重启服务或在管理后台刷新，技能即出现在广场。

`public/.gitignore` 中的 `skills/*/` 会阻止把第三方技能误提交进本仓库。自制技能不受此限制，但若要随仓库分发，请一并说明其许可。

可选的 HTML-PPT 链路还会读取 `skills/html-ppt-skill-main/assets`、`skills/html-ppt-skill-main/templates/full-decks` 与 `skills/frontend-slides-main/viewport-base.css`；未安装时调用对应功能会报文件缺失，属预期行为。

> 本文件是对仓库内容的如实说明，不构成法律意见。再分发第三方内容前，请自行核实其当期许可条款。
