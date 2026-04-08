# AgentFlow - AI Agent 部署平台

<div align="center">

![AgentFlow](https://img.shields.io/badge/AgentFlow-AI%20Agent%20Platform-6366F1?style=for-the-badge&logo=robot&logoColor=white)
[![Python](https://img.shields.io/badge/Python-3.11+-00.svg?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688.svg?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-222.svg?style=flat-square&logo=react&logoColor=61DAFB)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0-3178C6.svg?style=flat-square&logo=typescript&logoColor=white)](https://typescriptlang.org)
[![License](https://img.shields.io/badge/License-MIT-FF6B6B.svg?style=flat-square)](LICENSE)
[![Stars](https://img.shields.io/github/stars/PHclaw/agentflow?style=flat-square)](https://github.com/PHclaw/agentflow/stargazers)

**🚀 让每个企业都能拥有专属 AI Agent — 低代码/零代码构建，开箱即用的行业模板**

[English](./README.md) · [功能介绍](#✨-特性) · [快速开始](#-快速开始) · [架构设计](#-系统架构) · [部署指南](#-部署指南) · [贡献指南](#-贡献)

</div>

---

## ✨ 特性

<p align="center">
  <img src="https://via.placeholder.com/800x400/6366F1/FFFFFF?text=AgentFlow+Dashboard" alt="Dashboard" width="800"/>
</p>

### 🎯 核心能力

| 功能 | 描述 | 状态 |
|:-----|:-----|:-----|
| **拖拽式工作流构建** | 可视化节点编辑器，无需编码即可构建复杂 AI 工作流 | ✅ |
| **多模型支持** | OpenAI GPT-4 / Anthropic Claude / DeepSeek 一键切换 | ✅ |
| **知识库 RAG** | 上传文档自动分块、嵌入向量，精准检索增强生成 | ✅ |
| **工具调用** | 内置搜索/计算/天气等工具，支持自定义 API 扩展 | ✅ |
| **🌐 浏览器自动化** | 内置 Browser-Use 引擎，让 Agent 控制浏览器执行复杂任务 | ✅ |
| **多渠道接入** | 一键部署到网站/微信/钉钉/企业微信/API | 🚧 |
| **实时数据分析** | 对话统计、意图分析、用户反馈追踪 | ✅ |

### 📦 开箱即用的行业模板

| 模板 | 场景 | 核心功能 |
|:-----|:-----|:---------|
| 💬 **智能客服** | 客服中心 | FAQ 自动回答 · 多轮对话 · 工单创建 · 满意度调查 |
| 💰 **销售助手** | 销售团队 | 客户跟进 · 报价生成 · 会议安排 · CRM 集成 |
| 👥 **HR 助手** | 人力资源 | 政策查询 · 假期申请 · 薪资咨询 · 培训推荐 |
| 📊 **财务助手** | 财务部门 | 报销审批 · 发票查询 · 预算咨询 · 报表生成 |
| 📚 **知识库问答** | 企业知识库 | 文档导入 · 智能检索 · 多格式支持 · 权限管理 |
| 📅 **预约助手** | 服务行业 | 在线预约 · 日程管理 · 提醒通知 · 数据统计 |

---

## 🏗️ 技术架构

### 系统架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              AgentFlow 架构                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐                   │
│   │   Web       │     │   Mobile    │     │   API       │                   │
│   │   (React)   │     │   (H5)      │     │   Clients   │                   │
│   └──────┬──────┘     └──────┬──────┘     └──────┬──────┘                   │
│          │                   │                   │                          │
│          └───────────────────┼───────────────────┘                          │
│                              ▼                                               │
│                    ┌───────────────────┐                                    │
│                    │    Nginx Gateway   │                                    │
│                    │  (Reverse Proxy)   │                                    │
│                    └─────────┬─────────┘                                    │
│                              │                                               │
│          ┌───────────────────┼───────────────────┐                         │
│          ▼                   ▼                   ▼                           │
│   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐                   │
│   │  Frontend   │     │   Backend   │     │   Celery    │                   │
│   │   (Vite)    │     │  (FastAPI)  │     │   Worker    │                   │
│   │   Port:3000│     │   Port:8000 │     │             │                   │
│   └─────────────┘     └──────┬──────┘     └──────┬──────┘                   │
│                              │                   │                           │
│                              ▼                   ▼                           │
│                    ┌─────────────────────────────────────┐                  │
│                    │              Redis                   │                  │
│                    │        (Cache + Message Queue)       │                  │
│                    └──────────────────┬────────────────────┘                  │
│                                       │                                      │
│                    ┌──────────────────┼──────────────────┐                  │
│                    ▼                  ▼                  ▼                  │
│             ┌────────────┐    ┌────────────┐    ┌────────────┐             │
│             │ PostgreSQL  │    │   LLM      │    │  Embedding │             │
│             │ + pgvector  │    │  Providers │    │   Models   │             │
│             │  (Vectors)  │    │            │    │            │             │
│             └────────────┘    └────────────┘    └────────────┘             │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 技术栈详情

#### 后端技术
| 技术 | 版本 | 用途 |
|:-----|:-----|:-----|
| **Python** | 3.11+ | 核心开发语言 |
| **FastAPI** | 0.109 | 高性能异步 Web 框架 |
| **SQLAlchemy** | 2.0 | 异步 ORM，支持 PostgreSQL |
| **pgvector** | 0.2.3 | 向量数据库，支持相似度搜索 |
| **LangGraph** | 0.0.20 | Agent 工作流状态机编排 |
| **Celery** | 5.3 | 异步任务队列 |
| **Redis** | 7+ | 缓存、Session、消息队列 |

#### 前端技术
| 技术 | 版本 | 用途 |
|:-----|:-----|:-----|
| **React** | 18+ | UI 框架 |
| **TypeScript** | 5.0 | 类型安全 |
| **Vite** | 5.0 | 构建工具 |
| **ReactFlow** | 11+ | 拖拽式工作流编辑器 |
| **Tailwind CSS** | 3.4 | 原子化 CSS 框架 |
| **React Router** | 6+ | 客户端路由 |

#### 🌐 浏览器自动化 (Browser-Use)

AgentFlow 内置 Browser-Use 引擎，Agent 可以像人一样操作浏览器：

```
用户: "帮我去 GitHub 找一个 AI Agent 相关的热门项目"
     ↓
AgentFlow 触发 Browser Tool
     ↓
Browser-Use 控制浏览器 → 打开 GitHub → 搜索 → 分析 → 截图
     ↓
返回结果 + 截图给用户
```

**支持操作**：打开网页、点击元素、输入文字、滚动页面、截图、数据采集、表单填写、多标签页管理

#### AI/LLM 集成
| 模型 | 提供商 | 支持功能 |
|:-----|:-------|:---------|
| GPT-4 / GPT-4o / GPT-3.5 | OpenAI | 对话、嵌入、函数调用 |
| Claude 3 / Claude 2 | Anthropic | 长上下文、安全对话 |
| DeepSeek Chat | DeepSeek | 高性价比对话 |
| 本地模型 | Ollama | 私有化部署 |

---

## 🚀 快速开始

### 环境要求

| 依赖 | 最低版本 | 推荐版本 |
|:-----|:---------|:---------|
| Python | 3.11 | 3.12 |
| Node.js | 18 | 20 LTS |
| PostgreSQL | 14 | 16+ |
| Redis | 6 | 7+ |
| Docker | 24 | 25+ |

### 方法一：Docker 部署（推荐）

```bash
# 1. 克隆项目
git clone https://github.com/PHclaw/agentflow.git
cd agentflow

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入你的 API Keys

# 3. 启动所有服务
docker-compose up -d

# 4. 访问应用
open http://localhost:3000
```

### 方法二：本地开发

#### 后端启动

```bash
cd agentflow/backend

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Linux / macOS
source venv/bin/activate

# Windows PowerShell
.\venv\Scripts\Activate.ps1

# Windows CMD
.\venv\Scripts\activate.bat

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入以下必要配置：
# DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/agentflow
# REDIS_URL=redis://localhost:6379/0
# OPENAI_API_KEY=sk-xxx

# 初始化数据库（需要先启动 PostgreSQL）
alembic upgrade head

# 启动开发服务器
uvicorn app.main:app --reload --port 8000
```

#### 前端启动

```bash
cd agentflow/frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 访问 http://localhost:5173
```

### 方法三：混合部署

```bash
# 后端使用 Docker
docker-compose up -d backend postgres redis

# 前端本地开发
cd frontend && npm install && npm run dev
```

---

## 📁 项目结构

```
agentflow/
├── backend/                          # 🚀 后端服务
│   ├── app/
│   │   ├── api/                      # API 路由层
│   │   │   ├── agents.py            # Agent 管理接口
│   │   │   ├── auth.py               # 认证接口
│   │   │   ├── chat.py               # 对话接口
│   │   │   ├── knowledge.py          # 知识库接口
│   │   │   ├── templates.py          # 模板接口
│   │   │   ├── upload.py             # 文件上传接口
│   │   │   └── users.py              # 用户接口
│   │   ├── core/                     # 核心模块
│   │   │   ├── config.py             # 配置管理
│   │   │   ├── database.py           # 数据库连接
│   │   │   ├── migrations.py         # 数据库迁移
│   │   │   └── monitoring.py         # 监控日志
│   │   ├── models/                   # 数据模型
│   │   │   ├── agent.py              # Agent 模型
│   │   │   └── user.py               # 用户模型
│   │   ├── services/                 # 业务逻辑层
│   │   │   ├── llm.py               # LLM 服务
│   │   │   ├── knowledge.py          # 知识库服务
│   │   │   ├── tools.py              # 工具服务（含浏览器自动化）
│   │   │   ├── browser.py            # Browser-Use 浏览器控制
│   │   │   ├── runtime.py            # Agent 运行时
│   │   │   └── templates.py          # 模板服务
│   │   ├── workflows/                # 工作流引擎
│   │   │   └── engine.py             # LangGraph 工作流
│   │   └── main.py                   # FastAPI 入口
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/                         # 🎨 前端应用
│   ├── src/
│   │   ├── components/               # React 组件
│   │   │   ├── WorkflowBuilder.tsx  # 工作流构建器
│   │   │   ├── ChatWidget.tsx       # 对话组件
│   │   │   ├── AgentList.tsx        # Agent 列表
│   │   │   └── KnowledgeBase.tsx    # 知识库管理
│   │   ├── pages/                   # 页面组件
│   │   │   ├── Dashboard.tsx        # 控制台
│   │   │   ├── Login.tsx            # 登录页
│   │   │   ├── Register.tsx          # 注册页
│   │   │   ├── ChatPage.tsx         # 对话页
│   │   │   └── TemplateMarket.tsx   # 模板市场
│   │   ├── services/                # API 服务
│   │   │   └── api.ts               # API 客户端
│   │   ├── App.tsx                  # 主应用
│   │   ├── Router.tsx               # 路由配置
│   │   └── main.tsx                 # 入口文件
│   ├── public/
│   ├── Dockerfile
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── tailwind.config.js
│
├── docker-compose.yml                # Docker 编排配置
├── .env.example                      # 环境变量示例
├── README.md                        # 项目文档
└── LICENSE                          # MIT 许可证
```

---

## 🎨 工作流节点类型

```
┌────────────────────────────────────────────────────────────────────────────┐
│                           可视化工作流编辑器                                  │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│    ┌──────────┐                           ┌──────────┐                     │
│    │  START   │                           │   END    │                     │
│    └────┬─────┘                           └────┬─────┘                     │
│         │                                      ▲                           │
│         ▼                                      │                           │
│    ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐       │
│    │   LLM    │────▶│CONDITION │────▶│  TOOL    │────▶│  OUTPUT   │       │
│    │  节点    │     │  节点    │     │   节点   │     │   节点    │       │
│    └──────────┘     └────┬─────┘     └──────────┘     └──────────┘       │
│                          │                                                    │
│                          ▼                                                    │
│                    ┌──────────┐                                               │
│                    │KNOWLEDGE │                                               │
│                    │   节点   │                                               │
│                    └──────────┘                                               │
│                                                                             │
└────────────────────────────────────────────────────────────────────────────┘
```

| 节点类型 | 图标 | 功能描述 |
|:---------|:-----|:---------|
| **LLM** | 🤖 | 调用 LLM 生成回复，支持系统提示词、上下文注入 |
| **Condition** | 🔀 | 条件分支，根据变量值路由到不同分支 |
| **Tool** | 🔧 | 调用外部工具（搜索/计算/API/浏览器） |
| **Browser** | 🌐 | Browser-Use 自动化，AI 控制浏览器操作网页 |
| **Knowledge** | 📚 | 知识库检索，增强 LLM 回答准确性 |
| **Start/End** | 🚩 | 工作流入口/出口节点 |

---

## ⚙️ 配置说明

### 环境变量 (.env)

```env
# =============================================================================
# 数据库配置
# =============================================================================
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/agentflow

# =============================================================================
# Redis 配置
# =============================================================================
REDIS_URL=redis://localhost:6379/0

# =============================================================================
# JWT 认证配置
# =============================================================================
JWT_SECRET_KEY=your-super-secret-key-change-in-production
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# =============================================================================
# LLM API Keys（至少配置一个）
# =============================================================================
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxxxxx
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx

# =============================================================================
# Embedding 模型
# =============================================================================
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

# =============================================================================
# 应用配置
# =============================================================================
APP_NAME=AgentFlow
APP_DEBUG=true
APP_URL=http://localhost:8000

# =============================================================================
# CORS 配置
# =============================================================================
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

---

## 📖 API 文档

启动服务后访问交互式 API 文档：

| 文档类型 | 地址 | 说明 |
|:---------|:-----|:-----|
| **Swagger UI** | http://localhost:8000/docs | ⭐ 推荐，支持在线调试 |
| **ReDoc** | http://localhost:8000/redoc | 离线友好的文档 |
| **OpenAPI JSON** | http://localhost:8000/openapi.json | 可导入 Postman |

### 主要 API 接口

#### 认证接口

```
POST /api/v1/auth/register     - 用户注册
POST /api/v1/auth/login        - 用户登录
POST /api/v1/auth/refresh      - 刷新 Token
GET  /api/v1/auth/me           - 获取当前用户
```

#### Agent 管理

```
GET    /api/v1/agents           - 获取 Agent 列表
POST   /api/v1/agents           - 创建 Agent
GET    /api/v1/agents/{id}     - 获取 Agent 详情
PUT    /api/v1/agents/{id}     - 更新 Agent
DELETE /api/v1/agents/{id}     - 删除 Agent
POST   /api/v1/agents/{id}/publish  - 发布 Agent
```

#### 对话接口

```
POST /api/v1/chat/{agent_id}   - 发送消息
GET  /api/v1/chat/{agent_id}/history  - 获取对话历史
DELETE /api/v1/chat/{session_id}     - 清空对话历史
```

#### 知识库接口

```
GET    /api/v1/knowledge           - 获取知识库列表
POST   /api/v1/knowledge           - 创建知识库
POST   /api/v1/knowledge/{id}/upload  - 上传文档
POST   /api/v1/knowledge/{id}/search  - 搜索知识库
DELETE /api/v1/knowledge/{id}     - 删除知识库
```

#### 模板接口

```
GET /api/v1/templates            - 获取所有模板
GET /api/v1/templates/{category} # 按分类获取模板
POST /api/v1/templates/{id}/use  # 使用模板创建 Agent
```

---

## 🔧 开发指南

### 运行测试

```bash
# 后端测试
cd backend
pytest tests/ -v

# 前端测试
cd frontend
npm test

# E2E 测试
npx playwright test
```

### 代码规范

```bash
# 后端 - Python
cd backend
black .                    # 代码格式化
isort .                    # 导入排序
mypy .                     # 类型检查
flake8                     # 代码风格检查

# 前端 - TypeScript
cd frontend
npm run lint              # ESLint 检查
npm run format            # Prettier 格式化
```

### 数据库迁移

```bash
cd backend

# 创建迁移
alembic revision --autogenerate -m "add new table"

# 应用迁移
alembic upgrade head

# 回滚迁移
alembic downgrade -1
```

---

## 🌐 部署指南

### 生产环境部署

#### 1. 服务器准备

```bash
# 安装 Docker
curl -fsSL https://get.docker.com | sh

# 安装 Docker Compose
sudo apt-get install docker-compose

# 配置 PostgreSQL + pgvector
docker pull pgvector/pgvector:pg16
```

#### 2. 构建生产镜像

```bash
# 构建前端
cd frontend
npm run build

# 构建后端
cd ../backend
docker build -t agentflow-backend:latest .

# 构建前端（已构建）
docker build -t agentflow-frontend:latest -f ../frontend/Dockerfile ../frontend
```

#### 3. 配置 Nginx

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # 前端静态文件
    location / {
        root /usr/share/nginx/html;
        try_files $uri $uri/ /index.html;
    }

    # API 代理
    location /api {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

#### 4. SSL 证书

```bash
# 使用 Let's Encrypt
certbot --nginx -d your-domain.com
```

---

## 🤝 贡献指南

我们欢迎所有形式的贡献！

### 如何贡献

1. **Fork** 本仓库
2. **Clone** 你的 Fork：`git clone https://github.com/YOUR_USERNAME/agentflow.git`
3. **创建分支**：`git checkout -b feature/amazing-feature`
4. **提交改动**：`git commit -m 'Add amazing feature'`
5. **推送分支**：`git push origin feature/amazing-feature`
6. **创建 Pull Request**

### 开发流程

```
Issue → Fork → Branch → Develop → Test → PR → Review → Merge → Deploy
```

---

## 📊 项目路线图

```
版本规划 (Roadmap)
═══════════════════════════════════════════════════════════════════════════════

[v1.0.0] MVP 发布 ✅
├── 用户注册/登录
├── Agent 创建和配置
├── 工作流编辑器
├── 实时对话
└── 基础模板

[v1.1.0] 知识库增强 🚧
├── 文档上传和处理
├── RAG 向量检索
├── 知识库管理
└── 文档分类

[v1.2.0] 渠道扩展 📋
├── 微信接入
├── 钉钉接入
├── 企业微信
└── API 开放平台

[v1.3.0] 企业功能 📋
├── 多租户支持
├── 权限管理
├── 审计日志
└── SSO 单点登录

[v2.0.0] 高级特性 📋
├── 多 Agent 协作
├── Agent 市场
├── 插件系统
└── 自定义模型
```

---

## 📬 联系方式

| 渠道 | 链接 |
|:-----|:-----|
| **GitHub Issues** | [报告 Bug / 请求功能](https://github.com/PHclaw/agentflow/issues) |
| **Discussions** | [讨论区](https://github.com/PHclaw/agentflow/discussions) |
| **邮箱** | support@agentflow.dev |

---

## 📄 许可证

本项目基于 [MIT License](LICENSE) 开源。

```
MIT License

Copyright (c) 2025 AgentFlow

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
```

---

<div align="center">

**如果这个项目对你有帮助，请给我们一个 ⭐**

[![Star](https://img.shields.io/github/stars/PHclaw/agentflow?style=social)](https://github.com/PHclaw/agentflow)
[![Fork](https://img.shields.io/github/forks/PHclaw/agentflow?style=social)](https://github.com/PHclaw/agentflow)
[![Watch](https://img.shields.io/github/watchers/PHclaw/agentflow?style=social)](https://github.com/PHclaw/agentflow)

</div>
