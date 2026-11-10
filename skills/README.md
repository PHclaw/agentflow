# 技能目录

这个目录是 AgentFlow 的**运行时技能挂载点**。本仓库刻意保持为空。

## 为什么是空的

社区技能的许可状态不一致：整理时核查的 26 个技能中，9 个为 Apache-2.0、4 个为 MIT、1 个标注「All rights reserved」、12 个没有任何许可声明。后面两类不能按本仓库的 Apache-2.0 再分发，因此**第三方技能不随本仓库提供**。完整核查结果见 [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)。

服务启动不依赖技能：`app/services/skill/store.py` 会在需要时自动创建目录，空目录只是让技能广场返回空列表，其余功能（工作流、对话、知识库、模板市场）均不受影响。

> 请勿删除本目录。`app/core/paths.py` 用它的存在来推断仓库根目录，`backend/Dockerfile` 也会 `COPY skills/`；目录消失会导致本地路径判断和镜像构建出错。

## 按需安装

1. 从技能的上游仓库获取副本，**保留其原始 `LICENSE`**；
2. 放到 `skills/<技能名>/`，目录内含一个 `SKILL.md`（技能元数据与说明）以及技能自带脚本；
3. 重启服务或在管理后台刷新，技能即出现在广场。

`.gitignore` 中的 `skills/*/` 会阻止第三方技能被误提交；这是有意的保护，请勿绕过。

## 自制技能

自写技能不受上述限制：新建一个带 `SKILL.md` 的目录即可，格式参考 `backend/app/services/skill/store.py` 中的解析逻辑。若希望随本仓库分发，请在 PR 中说明其来源与许可。

## 已知的可选依赖

`backend/app/services/skill/ppt_html.py` 的 HTML-PPT 链路会读取下列路径，均由对应的社区技能提供：

- `skills/html-ppt-skill-main/assets`
- `skills/html-ppt-skill-main/templates/full-decks`
- `skills/frontend-slides-main/viewport-base.css`

未安装这些技能时调用相关功能会抛 `FileNotFoundError`，属预期行为，不是核心代码缺陷。
