# 更新日志与路线图

> 本页由 README 拆分而来，内容与代码同步维护。返回 [README](../README.md)。

## 2026-11-26 — 安全修复与群聊体验

- **安全**：修复 `tools_memory._calculator_tool` 的 eval 注入（CWE-95）。
  LLM function-calling 传入的表达式此前会直达 `eval()`，提示注入可导致后端
  任意代码执行。现改用 AST 白名单求值（见 `app/core/safe_math.py`），
  同时加固 `workflow_runtime` 中的重复实现；新增 42 个回归测试。
  感谢 **Capri Security** 负责任披露。
- **群聊**：协作接力、自动补人、飞书式交互（编辑/撤回、表情、已读、搜索、
  @全体）、群成员管理、移动端布局与消息时间戳。
- **文档**：中英文 README 补齐智能体群聊章节。

## v2.1（未发布 · master）

**完整版回归与工程化收敛** —— 补齐此前从主线移除的模块，同时把 CI 与安全从「长期红」修到全绿。

#### 完整版能力

| 模块 | 说明 |
|:-----|:-----|
| **17 个页面** | 落地页 / 控制台 / Agent 配置 / 工作流画布 / 对话 / 对话记录 / 知识库 / Skill 广场 / 模板市场 / 设置 / 管理后台等 |
| **27 个技能目录** | 在原有 8 个基础上补齐 PDF、PPT、学术检索、会议纪要、统计分析等场景，新增「API 文档助手」 |
| **Android 客户端** | Capacitor 打包，随 [v2.0.2 Release](https://github.com/PHclaw/agentflow/releases/tag/v2.0.2) 提供正式签名 APK（在线版，界面由服务端下发） |

#### 依赖与构建

| 问题 | 处理 |
|:-----|:-----|
| `requirements.txt` 钉的版本互相冲突，pip 直接 `ResolutionImpossible` | 按实际运行环境重写，`pip install --dry-run` 验证 169 个包可解析 |
| 缺少 `lunar-python` / `psutil` / `pyyaml` / `lxml` 等运行时依赖 | 按 `app/` 下真实 import 逐一补齐 |
| PostCSS / Tailwind 配置用 ESM 写法，CI 的 Node 18 不识别 | 改为 CJS，Node 18 / 20 / 22 行为一致 |
| 前端 `setup-node` 找不到锁文件 | 指定 `cache-dependency-path: frontend/package-lock.json` |

#### 安全

| 项 | 说明 |
|:---|:-----|
| CodeQL 告警 471 → 0 | 查询包由 `security-and-quality` 改为 `security-extended`，排除 `skills/` 等 vendored 代码；剩余按规则逐条标注理由 |
| 异常信息不再回传客户端 | 新增 `app/core/errors.py`，异常原文只进日志，响应返回固定文案 + `trace_id` |
| 路径穿越统一返回 403 | 工作区文件解析先归一化反斜杠再校验，避免 `..\` 在 POSIX 上被当作普通文件名而返回 404 |
| 限流与缓存 key 换 `sha256` | 原用 `md5`，虽然不涉及安全存储，但换哈希成本为零 |

#### 文档

- **文档站**（GitHub Pages）：`docs/` 下 Markdown 自动渲染，补英文落地页 `en.html`
- **Wiki**：5 个页面（Home / 快速开始 / 模型配置 / 常见问题 / 架构说明）
- `.gitattributes` 统一换行（`skills/**` 标记 vendored，不计入语言统计）+ `.editorconfig`
- `.mailmap` 修正历史提交的作者归属
- `CONTRIBUTING.md` 补「第一次贡献从哪里开始」

#### 修复的真实缺陷

- `excel_engine.category_rollup_rows` 使用了未定义的 `df`，一旦调用即 `NameError`
- 合并时 `skills/` 下 11 个技能目录与 `workflow/nodes/index.ts` 被静默删除（「我方删除、对方未修改」不产生冲突）
- 邮件模板测试用整页文案计数判定页头，依赖 `MAIL_FROM_NAME` 环境变量，在 CI 上误报

---

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
| **v2.0** | ✅ 已发布 | 全新 UI + agent-* 生态整合 + 3 个适配器（`backend/app/integrations/`） |
| **v2.0.1** | ✅ 已发布 | Model Lab Skill 广场整合：8 个预置 Skill + 编排运行时 + REST API |
| **v2.0.2** | ✅ 已发布 | Android 客户端（正式签名 APK，在线版） |
| **v2.1** | 🚧 开发中 | 完整版回归（17 页面 / 27 技能）+ CI 与 CodeQL 治理；待补多 Agent 协作与插件市场 |
| **v3.0** | 📋 规划中 | 多租户企业版 + SSO + 审计日志 |
