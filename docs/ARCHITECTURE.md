# 架构说明

> 本页由 README 拆分而来，内容与代码同步维护。返回 [README](../README.md)。

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                        AgentFlow v2.1                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   ┌───────────┐    ┌───────────┐    ┌───────────┐         │
│   │  Frontend │    │  Backend  │    │   Celery  │         │
│   │ (React)   │◄──►│ (FastAPI) │◄──►│  Worker   │         │
│   │  :3000    │    │  :8001    │    │           │         │
│   └───────────┘    └─────┬─────┘    └─────┬─────┘         │
│                         │                 │                │
│              ┌──────────▼─────────────────▼───┐            │
│              │            Redis               │            │
│              │      (Cache + Queue)           │            │
│              └──────────────┬─────────────────┘            │
│                             │                             │
│              ┌──────────────▼─────────────────┐            │
│              │        PostgreSQL + pgvector    │            │
│              │     (数据 + 向量检索)          │            │
│              └────────────────────────────────┘            │
│                                                             │
│   整合 9 个 agent-* 生态库：                                │
│   prompt-templates · output-parser · tool-registry          │
│   memory-store · mcp-client · config-loader                 │
│   observability · orchestrator                              │
└─────────────────────────────────────────────────────────────┘
```

#### 后端技术栈

| 技术 | 用途 |
|:-----|:-----|
| Python 3.11+ | 核心语言 |
| FastAPI | 异步 Web 框架 |
| SQLAlchemy 2.0 | 异步 ORM |
| pgvector | 向量相似度搜索 |
| 自研工作流引擎 | 节点编排与执行（`app/services/workflow_runtime.py`）|
| Alembic | 数据库迁移 |
| Celery + Redis | 异步任务队列 |
| Stripe | 订阅支付 |

#### 前端技术栈

| 技术 | 用途 |
|:-----|:-----|
| React 18+ | UI 框架 |
| TypeScript 5.0 | 类型安全 |
| Vite 5 | 构建工具 |
| ReactFlow | 拖拽式工作流编辑器 |
| Tailwind CSS 3.4 | 原子化样式 |
| Zustand | 状态管理 |

---

## 工作流节点类型

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  START   │────▶│   LLM    │────▶│CONDITION │────▶│  OUTPUT  │
│  入口    │     │  大模型  │     │  条件分支│     │   出口   │
└──────────┘     └──────────┘     └────┬─────┘     └──────────┘
                                      │
                                      ▼
                               ┌──────────┐
                               │KNOWLEDGE │
                               │知识库检索│
                               └──────────┘
```

| 节点 | 功能 | 典型用途 |
|:-----|:-----|:---------|
| **Start / End** | 工作流入口 / 出口 | 定义流程边界 |
| **LLM** | 调用大模型生成回复 | 问答、翻译、摘要 |
| **Condition** | 根据变量值路由分支 | 意图识别分流 |
| **Tool** | 调用外部工具 | 搜索、计算、API |
| **Knowledge** | RAG 知识库检索 | 企业文档问答 |
| **Browser** | 浏览器自动化 | 网页操作、数据采集 |

---

## 项目结构

```
agentflow/
├── backend/                    # FastAPI 后端
│   ├── app/
│   │   ├── api/               # REST API 路由
│   │   ├── core/              # 配置 / 数据库 / 缓存
│   │   ├── models/            # SQLAlchemy ORM 模型
│   │   ├── services/          # 业务逻辑 (LLM / Knowledge / Browser / 工作流运行时)
│   │   └── integrations/      # agent-* 库集成层
│   ├── migrations/            # Alembic 迁移
│   └── tests/
│
├── frontend/                   # React 前端
│   ├── src/
│   │   ├── components/        # workflow / landing / layout / ui
│   │   ├── pages/             # Dashboard / Login / Chat / Workflow...
│   │   └── services/api.ts    # API 客户端
│   └── package.json
│
├── skills/                     # Skill 定义（SKILL.md + scripts/）v2.0.1
│   ├── excel/
│   ├── pdf/
│   └── ...
├── examples/                   # 独立示例（可脱离平台单独运行）
│   └── generate_ai_ppt.py      # 用代码生成一份结构完整的 PPT
├── assets/                     # README 配图与演示素材
│   ├── banner.svg              # 顶部横幅
│   ├── screens/                # 界面截图
│   ├── gifs/                   # 功能演示动图
│   ├── videos/                 # 完整演示录屏
│   └── ppt/                    # 自动生成的 PPT 页面示例
├── config/
│   └── models.json             # Skill 可用模型清单
├── static/generated/           # Skill 工具产出文件
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## 开箱即用的行业模板

| 模板 | 场景 | 核心功能 |
|:-----|:-----|:---------|
| 💬 **智能客服** | 客服中心 | FAQ 自动回答 · 多轮对话 · 工单创建 |
| 💰 **销售助手** | 销售团队 | 客户跟进 · 报价生成 · CRM 集成 |
| 👥 **HR 助手** | 人力资源 | 政策查询 · 假期申请 · 培训推荐 |
| 📊 **财务助手** | 财务部门 | 报销审批 · 发票查询 · 报表生成 |
| 📚 **知识库问答** | 企业知识库 | 文档导入 · 智能检索 · 权限管理 |
| 📅 **预约助手** | 服务行业 | 在线预约 · 日程管理 · 提醒通知 |
