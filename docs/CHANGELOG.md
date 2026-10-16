# 更新日志与路线图

> 本页由 README 拆分而来，内容与代码同步维护。返回 [README](../README.md)。

## v2.0.1

**Skill 广场整合** — 将 Model Lab 预置 Skill 接入 AgentFlow，开箱即用专业场景助手。

#### 新增能力

| 模块 | 说明 |
|:-----|:-----|
| **Skill 广场 API** | `GET /api/v1/skills/plaza` 浏览预置 Skill；`POST /api/v1/skills/{id}/call` 调用 |
| **文件系统 Skill** | `skills/<slug>/SKILL.md` 扫盘加载，改配置即生效 |
| **编排运行时** | 规划 → 工具执行 → 模型回复（Excel / PDF / PPT 等带工具 Skill） |
| **静态产出** | 生成的 xlsx / png / pdf 等通过 `/static/generated/` 下载 |

#### 内置 Skill（8 个）

| Skill | 场景 |
|:------|:-----|
| `excel` | 表格分析、汇总、导出、出图 |
| `pdf` | 合并拆分、转 Word、抽表 |
| `ppt-generation` | 问卷与 PPT 生成 |
| `meeting-minutes` | 会议纪要整理 |
| `statistical-analyst` | 假设检验、置信区间等 |
| `academic-search` | 学术文献检索 |
| `lit-review-notes` | 文献速读笔记 |
| `clinical-case-report` | 临床病例报告 |

#### 配置补充

Skill 运行时支持 OpenAI 兼容网关，可在 `.env` 中配置 `CHATZOC_*` / `DASHSCOPE_API_KEY` / `MODEL_BASE_URL`（见 `.env.example`）。

---

## 版本路线图

| 版本 | 状态 | 内容 |
|:-----|:-----|:-----|
| **v1.0** | ✅ 已发布 | MVP：用户系统 + Agent 管理 + 工作流编辑器 + 对话 |
| **v1.1** | ✅ 已发布 | 知识库 RAG + 文档处理 + 向量检索 |
| **v1.2** | ✅ 已发布 | Stripe 订阅 + 定价方案 + 配额管理 |
| **v2.0** | ✅ 已发布 | 全新 UI + agent-* 生态整合 + 9 个核心库集成 |
| **v2.0.1** | ✅ 已发布 | Model Lab Skill 广场整合：8 个预置 Skill + 编排运行时 + REST API |
| **v2.1** | 🚧 开发中 | 多 Agent 协作 + 插件市场 |
| **v3.0** | 📋 规划中 | 多租户企业版 + SSO + 审计日志 |
