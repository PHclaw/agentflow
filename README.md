# 🚀 AgentFlow — 零代码 AI Agent 部署平台

<div align="center">

![AgentFlow](https://img.shields.io/badge/AgentFlow-v2.1-6366F1?style=for-the-badge&logo=robot&logoColor=white)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB.svg?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688.svg?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB.svg?style=flat-square&logo=react&logoColor=white)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0-3178C6.svg?style=flat-square&logo=typescript&logoColor=white)](https://typescriptlang.org)
[![License](https://img.shields.io/badge/License-MIT-FF6B6B.svg?style=flat-square)](LICENSE)
[![Stars](https://img.shields.io/github/stars/PHclaw/agentflow?style=flat-square)](https://github.com/PHclaw/agentflow/stargazers)

**拖拽式构建 AI Agent 工作流 · 无需一行代码 · 5 分钟上线**

[English](./README.md) · [功能介绍](#-特性) · [快速开始](#-快速开始) · [架构设计](#-系统架构) · [API 文档](#-api-文档)

</div>

---

## ✨ 截图预览

### 🏠 首页 — v2.0 全新发布

<p align="center">
  <img src="screenshots/homepage-v2.png" alt="AgentFlow v2.0 Homepage" width="900"/>
</p>

v2.0 带来全新的视觉体验：工作流编辑器实时预览、一键免费开始、暗色模式切换。

### 🔐 登录页面

<p align="center">
  <img src="screenshots/login-page.png" alt="AgentFlow Login Page" width="500"/>
</p>

支持邮箱密码登录 + Google OAuth，简洁的认证体验。

---

## 🎯 核心能力

| 功能 | 描述 | 状态 |
|:-----|:-----|:-----|
| **🎨 拖拽式工作流编辑器** | ReactFlow 可视化画布，LLM / Condition / Tool / Knowledge 节点自由组合 | ✅ |
| **🤖 多模型支持** | OpenAI GPT-4o / Anthropic Claude / DeepSeek / Ollama 本地模型 | ✅ |
| **📚 知识库 RAG** | 文档上传 → 自动分块 → 向量嵌入 → 检索增强生成 | ✅ |
| **🔧 工具调用系统** | 内置搜索 / 计算等工具 + 自定义 API 扩展 | ✅ |
| **🌐 浏览器自动化** | 内置 Browser-Use 引擎，AI 控制浏览器执行复杂任务 | ✅ |
| **👤 用户认证系统** | JWT 登录注册 + Google OAuth | ✅ |
| **💳 订阅计费** | Stripe 集成，多级定价方案 | ✅ |
| **📊 实时监控面板** | Agent 运行状态、Token 用量、延迟追踪 | ✅ |
| **📱 多渠道接入** | 网站 Widget / 微信 / 钉钉 / 企业微信 / API（开发中） | 🚧 |

---

## 🏗️ 技术架构

```
┌─────────────────────────────────────────────────────────────┐
│                        AgentFlow v2.0                       │
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

### 技术栈

#### 后端
| 技术 | 用途 |
|:-----|:-----|
| Python 3.11+ | 核心语言 |
| FastAPI | 异步 Web 框架 |
| SQLAlchemy 2.0 | 异步 ORM |
| pgvector | 向量相似度搜索 |
| LangGraph | Agent 工作流编排 |
| Celery + Redis | 异步任务队列 |
| Stripe | 订阅支付 |

#### 前端
| 技术 | 用途 |
|:-----|:-----|
| React 18+ | UI 框架 |
| TypeScript 5.0 | 类型安全 |
| Vite 5 | 构建工具 |
| ReactFlow | 拖拽式工作流编辑器 |
| Tailwind CSS 3.4 | 原子化样式 |
| Zustand | 状态管理 |

---

## 🎨 工作流节点类型

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

| 节点 | 功能 |
|:-----|:-----|
| **Start / End** | 工作流入口 / 出口 |
| **LLM** | 调用大模型生成回复，支持提示词模板和上下文注入 |
| **Condition** | 根据变量值路由到不同分支 |
| **Tool** | 调用外部工具（搜索、计算、API） |
| **Knowledge** | RAG 知识库检索增强 |
| **Browser** | Browser-Use 浏览器自动化 |

---

## 📦 开箱即用的行业模板

| 模板 | 场景 | 核心功能 |
|:-----|:-----|:---------|
| 💬 **智能客服** | 客服中心 | FAQ 自动回答 · 多轮对话 · 工单创建 |
| 💰 **销售助手** | 销售团队 | 客户跟进 · 报价生成 · CRM 集成 |
| 👥 **HR 助手** | 人力资源 | 政策查询 · 假期申请 · 培训推荐 |
| 📊 **财务助手** | 财务部门 | 报销审批 · 发票查询 · 报表生成 |
| 📚 **知识库问答** | 企业知识库 | 文档导入 · 智能检索 · 权限管理 |
| 📅 **预约助手** | 服务行业 | 在线预约 · 日程管理 · 提醒通知 |

---

## 🚀 快速开始

### 环境要求

| 依赖 | 版本 |
|:-----|:-----|
| Python | 3.11+ |
| Node.js | 18+ |
| PostgreSQL | 14+ (含 pgvector) |
| Redis | 7+ |

### Docker 一键部署（推荐）

```bash
git clone https://github.com/PHclaw/agentflow.git
cd agentflow
cp .env.example .env   # 编辑填入 API Keys
docker-compose up -d
open http://localhost:3000
```

### 本地开发

```bash
# 后端
cd backend
python -m venv venv && .\venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8001

# 前端（新终端）
cd frontend
npm install
npm run dev
# http://localhost:5173
```

---

## 📁 项目结构

```
agentflow/
├── backend/                    # FastAPI 后端
│   ├── app/
│   │   ├── api/               # REST API 路由
│   │   │   ├── auth.py        # 认证 (JWT + Google OAuth)
│   │   │   ├── agents.py      # Agent CRUD
│   │   │   ├── chat.py        # 对话接口
│   │   │   ├── knowledge.py   # 知识库 RAG
│   │   │   ├── workflow.py    # 工作流引擎
│   │   │   └── billing.py     # Stripe 计费
│   │   ├── core/              # 配置 / 数据库 / 缓存 / WebSocket
│   │   ├── models/            # SQLAlchemy ORM 模型
│   │   ├── services/          # 业务逻辑 (LLM / Knowledge / Browser)
│   │   ├── integrations/      # agent-* 库集成层
│   │   └── workflows/         # LangGraph 工作流引擎
│   ├── tests/
│   └── requirements.txt
│
├── frontend/                   # React 前端
│   ├── src/
│   │   ├── components/
│   │   │   ├── workflow/      # ReactFlow 工作流编辑器
│   │   │   ├── landing/       # 首页 (Hero / Features / Pricing)
│   │   │   ├── layout/        # Header / Sidebar / AppLayout
│   │   │   └── ui/            # 通用 UI 组件
│   │   ├── pages/             # Dashboard / Login / Chat / Workflow...
│   │   ├── stores/            # Zustand 状态管理
│   │   └── services/api.ts    # API 客户端
│   └── package.json
│
├── scripts/                   # 工具脚本
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## ⚙️ 配置说明

### 环境变量 (.env)

```env
# 数据库
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/agentflow

# Redis
REDIS_URL=redis://localhost:6379/0

# JWT 认证
JWT_SECRET_KEY=change-me-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=30

# LLM API Keys（至少配一个）
OPENAI_API_KEY=sk-xxx
ANTHROPIC_API_KEY=sk-ant-xxx
DEEPSEEK_API_KEY=sk-xxx

# CORS
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

---

## 📖 API 文档

| 文档 | 地址 |
|:-----|:-----|
| **Swagger UI** | http://localhost:8001/docs |
| **ReDoc** | http://localhost:8001/redoc |

### 核心 API

```
POST   /api/v1/auth/register          用户注册
POST   /api/v1/auth/login             用户登录
GET    /api/v1/agents                 Agent 列表
POST   /api/v1/agents                 创建 Agent
GET    /api/v1/agents/{id}            Agent 详情
PUT    /api/v1/agents/{id}            更新 Agent
DELETE /api/v1/agents/{id}            删除 Agent
POST   /api/v1/chat/{agent_id}        发送消息
POST   /api/v1/knowledge/upload       上传文档到知识库
POST   /api/v1/knowledge/search       搜索知识库
GET    /api/v1/templates              模板列表
```

---

## 🔧 开发指南

```bash
# 后端测试
cd backend && pytest tests/ -v

# 前端检查
cd frontend && npm run lint && npm run format

# 数据库迁移
cd backend && alembic revision --autogenerate -m "desc"
cd backend && alembic upgrade head
```

---

## 📈 版本路线图

| 版本 | 状态 | 内容 |
|:-----|:-----|:-----|
| **v1.0** | ✅ | MVP：用户系统 + Agent 管理 + 工作流编辑器 + 对话 |
| **v1.1** | ✅ | 知识库 RAG + 文档处理 + 向量检索 |
| **v1.2** | ✅ | Stripe 订阅 + 定价方案 + 配额管理 |
| **v2.0** | ✅ | 全新 UI + agent-* 生态整合 + 9 个核心库集成 |
| **v2.1** | 🚧 | 多 Agent 协作 + 插件市场 |
| **v3.0** | 📋 | 多租户企业版 + SSO + 审计日志 |

---

## 🤝 贡献

Issue → Fork → Branch → Develop → Test → PR → Review → Merge

---

## 📄 许可证

MIT © 2025 [PHclaw](https://github.com/PHclaw)

---

<div align="center">

**觉得有用？给个 ⭐ 吧！**

[⭐ Star](https://github.com/PHclaw/agentflow) · [🍴 Fork](https://github.com/PHclaw/agentflow/fork) · [🐛 Issues](https://github.com/PHclaw/agentflow/issues)

</div>
