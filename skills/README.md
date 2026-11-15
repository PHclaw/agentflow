# Skills（Model Lab 整合）

本目录来自 Model Lab `skills/`，由 AgentFlow 后端 `app.services.skill` 在启动时扫盘加载。

## 结构

```text
skills/<slug>/
  SKILL.md      # JSON frontmatter + Markdown 文档
  scripts/      # 可选可执行脚本（如 statistical-analyst）
```

## 已整合 Skill

| id | 名称 |
|----|------|
| excel | Excel 表格助手 |
| pdf | PDF 处理助手 |
| ppt-generation | PPT 生成助手 |
| meeting-minutes | 会议纪要助手 |
| statistical-analyst | 统计分析助手 |
| academic-search | 学术文献检索 |
| lit-review-notes | 文献速读笔记 |
| clinical-case-report | 临床病例报告 |

## API

- `GET /api/v1/skills/plaza` — Skill 广场列表
- `GET /api/v1/skills/{id}` — Skill 详情
- `POST /api/v1/skills/{id}/call` — 调用（JSON body: `variables`）
- `POST /api/v1/skills/{id}/call-with-files` — 带文件调用
- `POST /api/v1/skills/resolve` — 按任务文本选型

工具产出文件通过 `/static/generated/` 访问。
