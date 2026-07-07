# 🚀 AgentFlow — 零代码搭建 AI Agent 的开源平台

<div align="center">

![AgentFlow](https://img.shields.io/badge/AgentFlow-v2.1-6366F1?style=for-the-badge&logo=robot&logoColor=white)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB.svg?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688.svg?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB.svg?style=flat-square&logo=react&logoColor=white)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0-3178C6.svg?style=flat-square&logo=typescript&logoColor=white)](https://typescriptlang.org)
[![License](https://img.shields.io/badge/License-MIT-FF6B6B.svg?style=flat-square)](LICENSE)
[![Stars](https://img.shields.io/github/stars/PHclaw/agentflow?style=flat-square)](https://github.com/PHclaw/agentflow/stargazers)

**拖拽式构建 AI Agent 工作流 · 无需一行代码 · 5 分钟上线**

[快速开始](#-5-分钟快速开始) · [和同类工具有什么区别？](#-agentflow-和-difycoze-有什么区别) · [架构设计](#-技术架构长什么样) · [API 文档](#-api-文档) · [常见问题](#-常见问题)

</div>

---

## AgentFlow 是什么？谁能用？

AgentFlow 是一个**开源零代码 AI Agent 部署平台**。核心能力：拖拽式工作流编辑器 + 多模型支持 + 知识库 RAG + 一键部署。

**适合这些人群：**

- 想搭建 AI 客服/销售助手，但没有开发团队的企业
- 需要快速验证 AI Agent 场景的产品经理和创业者
- 想用低代码方式编排 LLM 工作流的开发者
- 需要知识库检索增强（RAG）但不想从零搭建的团队

**一句话总结**：如果你想在 5 分钟内上线一个能对话、能查知识库、能调用工具的 AI Agent，AgentFlow 就是为这个场景设计的。

---

## 📋 目录

- [AgentFlow 和 Dify/Coze 有什么区别？](#-agentflow-和-difycoze-有什么区别)
- [核心功能一览](#-核心功能一览)
- [5 分钟快速开始](#-5-分钟快速开始)
- [技术架构长什么样？](#-技术架构长什么样)
- [工作流节点类型](#-工作流节点有哪些类型)
- [开箱即用的行业模板](#-开箱即用的行业模板)
- [项目结构](#-项目结构)
- [配置说明](#-怎么配置环境变量)
- [API 文档](#-api-文档)
- [版本路线图](#-版本路线图)
- [常见问题](#-常见问题)

---

## 🆚 AgentFlow 和 Dify/Coze 有什么区别？

| 对比维度 | AgentFlow | Dify | Coze |
|:---------|:----------|:-----|:-----|
| **开源** | ✅ 完全开源 MIT | ✅ 开源 | ❌ 闭源 |
| **部署方式** | 自托管 / Docker 一键 | 自托管 / 云 | 仅云 |
| **工作流编辑** | 拖拽画布 + ReactFlow | 拖拽画布 | 节点编排 |
| **知识库 RAG** | ✅ pgvector 向量检索 | ✅ | ✅ |
| **多模型支持** | OpenAI / Claude / DeepSeek / Ollama | OpenAI / Claude / 更多 | 字节系模型 |
| **浏览器自动化** | ✅ 内置 Browser-Use | ❌ | ❌ |
| **数据主权** | ✅ 完全本地 | ✅ | ❌ |
| **生态整合** | 9 个 agent-* 生态库 | 插件市场 | 插件市场 |
| **适合场景** | 自托管优先、需要数据自主 | 功能全面、快速上手 | 字节生态、快速验证 |

**选 AgentFlow 的理由**：完全开源 + 自托管数据自主 + 内置浏览器自动化 + 9 个 agent-* 生态库深度整合。

---

## 🎯 核心功能一览

| 功能 | 说明 | 状态 |
|:-----|:-----|:-----|
| 🎨 **拖拽式工作流编辑器** | ReactFlow 画布，LLM / Condition / Tool / Knowledge 节点自由组合 | ✅ |
| 🤖 **多模型支持** | GPT-4o / GPT-4.1 / o3 / Claude Sonnet 4 / DeepSeek R1 / Ollama 本地模型 | ✅ |
| 📚 **知识库 RAG** | 文档上传 → 自动分块 → 向量嵌入 → 检索增强生成 | ✅ |
| 🔧 **工具调用系统** | 内置搜索 / 计算 + 自定义 API 扩展 | ✅ |
| 🌐 **浏览器自动化** | 内置 Browser-Use 引擎，AI 控制浏览器执行任务 | ✅ |
| 👤 **用户认证** | JWT + Google OAuth | ✅ |
| 💳 **订阅计费** | Stripe 多级定价 | ✅ |
| 📊 **实时监控** | Agent 状态 / Token 用量 / 延迟追踪 | ✅ |
| 📱 **多渠道接入** | 网站 Widget / 微信 / 钉钉 / API | 🚧 开发中 |

---

## 🚀 5 分钟快速开始

### 需要什么环境？

| 依赖 | 最低版本 |
|:-----|:---------|
| Python | 3.11+ |
| Node.js | 18+ |
| PostgreSQL | 14+（需 pgvector 扩展）|
| Redis | 7+ |
| Docker（推荐） | 20+ |

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
uvicorn app.main:app --reload --port 8001

# 前端（新终端）
cd frontend
npm install
npm run dev
# 访问 http://localhost:5173
```

---

## 🌐 生产环境部署

### 服务器要求

| 资源 | 最低配置 | 推荐配置 |
|:-----|:---------|:---------|
| CPU | 2 核 | 4 核 |
| 内存 | 4GB | 8GB+ |
| 磁盘 | 20GB | 50GB+（含向量数据）|
| 系统 | Linux (Ubuntu 22.04+) | Linux |

### 一键部署（Docker）

```bash
# 1. 克隆仓库
git clone https://github.com/PHclaw/agentflow.git
cd agentflow

# 2. 配置环境变量（⚠️ 生产环境必改）
cp .env.example .env
nano .env  # 修改 JWT_SECRET_KEY 和 API Keys

# 3. 运行初始化脚本（Linux/macOS）
bash scripts/init.sh

# Windows:
# .\scripts\init.ps1

# 4. 访问 http://服务器IP:3000
```

### 生产环境 .env 关键配置

```env
# ⚠️ 务必修改（生产环境）
JWT_SECRET_KEY=$(openssl rand -hex 32)   # 随机长字符串
CORS_ORIGINS=https://yourdomain.com

# 使用外部数据库（推荐生产环境）
DATABASE_URL=postgresql+asyncpg://user:pass@db-host:5432/agentflow

# 使用 Redis 云服务（推荐）
REDIS_URL=redis://redis-host:6379/0

# 公开访问地址
PUBLIC_URL=https://yourdomain.com
```

### Nginx 反向代理（80/443 端口）

创建 `/etc/nginx/sites-available/agentflow`：

```nginx
server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /api {
        proxy_pass http://localhost:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /ws {
        proxy_pass http://localhost:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

申请 Let's Encrypt 证书：

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
```

### 数据库备份

```bash
# 备份
docker compose exec postgres pg_dump -U postgres agentflow > backup_$(date +%Y%m%d).sql

# 恢复
cat backup.sql | docker compose exec -T postgres psql -U postgres agentflow
```

### 更新到最新版本

```bash
git pull origin master
docker compose down
docker compose up -d --build
```

---

## 🏗️ 技术架构长什么样？

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

### 后端技术栈

| 技术 | 用途 |
|:-----|:-----|
| Python 3.11+ | 核心语言 |
| FastAPI | 异步 Web 框架 |
| SQLAlchemy 2.0 | 异步 ORM |
| pgvector | 向量相似度搜索 |
| LangGraph | Agent 工作流编排 |
| Celery + Redis | 异步任务队列 |
| Stripe | 订阅支付 |

### 前端技术栈

| 技术 | 用途 |
|:-----|:-----|
| React 18+ | UI 框架 |
| TypeScript 5.0 | 类型安全 |
| Vite 5 | 构建工具 |
| ReactFlow | 拖拽式工作流编辑器 |
| Tailwind CSS 3.4 | 原子化样式 |
| Zustand | 状态管理 |

---

## 🔀 工作流节点有哪些类型？

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

## 📁 项目结构

```
agentflow/
├── backend/                    # FastAPI 后端
│   ├── app/
│   │   ├── api/               # REST API 路由
│   │   ├── core/              # 配置 / 数据库 / 缓存
│   │   ├── models/            # SQLAlchemy ORM 模型
│   │   ├── services/          # 业务逻辑 (LLM / Knowledge / Browser)
│   │   ├── integrations/      # agent-* 库集成层
│   │   └── workflows/         # LangGraph 工作流引擎
│   └── tests/
│
├── frontend/                   # React 前端
│   ├── src/
│   │   ├── components/        # workflow / landing / layout / ui
│   │   ├── pages/             # Dashboard / Login / Chat / Workflow...
│   │   └── services/api.ts    # API 客户端
│   └── package.json
│
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## ⚙️ 怎么配置环境变量？

复制 `.env.example` 为 `.env`，按需填写：

```env
# 数据库（必填）
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/agentflow

# Redis（必填）
REDIS_URL=redis://localhost:6379/0

# JWT 认证（必填，生产环境务必更换）
JWT_SECRET_KEY=change-me-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=30

# LLM API Keys（至少填一个）
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

### 核心 API 一览

| 方法 | 路径 | 说明 |
|:-----|:-----|:-----|
| POST | `/api/v1/auth/register` | 用户注册 |
| POST | `/api/v1/auth/login` | 用户登录 |
| GET | `/api/v1/agents` | Agent 列表 |
| POST | `/api/v1/agents` | 创建 Agent |
| GET | `/api/v1/agents/{id}` | Agent 详情 |
| POST | `/api/v1/chat/{agent_id}` | 发送消息 |
| POST | `/api/v1/knowledge/upload` | 上传文档到知识库 |
| POST | `/api/v1/knowledge/search` | 搜索知识库 |
| GET | `/api/v1/templates` | 模板列表 |
| GET | `/api/v1/templates/models/list` | 支持的模型列表 |

---

## 🔧 开发命令速查

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
| **v1.0** | ✅ 已发布 | MVP：用户系统 + Agent 管理 + 工作流编辑器 + 对话 |
| **v1.1** | ✅ 已发布 | 知识库 RAG + 文档处理 + 向量检索 |
| **v1.2** | ✅ 已发布 | Stripe 订阅 + 定价方案 + 配额管理 |
| **v2.0** | ✅ 已发布 | 全新 UI + agent-* 生态整合 + 9 个核心库集成 |
| **v2.1** | 🚧 开发中 | 多 Agent 协作 + 插件市场 |
| **v3.0** | 📋 规划中 | 多租户企业版 + SSO + 审计日志 |

---

## ❓ 常见问题

### AgentFlow 是免费的吗？

是的，AgentFlow 完全开源（MIT 协议），可免费用于个人和商业项目。你需要自行承担服务器和 LLM API 调用费用。

### 不会写代码能用 AgentFlow 吗？

可以。AgentFlow 的核心就是零代码拖拽式工作流编辑器，通过可视化画布连接节点即可构建 AI Agent。6 个行业模板开箱即用，5 分钟即可上线。

### 支持哪些大模型？

目前支持 OpenAI（GPT-4o / GPT-4.1 / o3 / o4-mini）、Anthropic（Claude Sonnet 4 / Claude 3.5 Haiku）、DeepSeek（V3 / R1）和 Ollama 本地模型。通过 `GET /api/v1/templates/models/list` 可获取完整模型列表。

### 知识库 RAG 是怎么工作的？

三步流程：1）上传文档 → 自动分块；2）通过 embedding 模型生成向量并存入 pgvector；3）用户提问时检索相关片段，注入 LLM 上下文生成回答。支持 PDF、TXT、Markdown 等格式。

### 可以自托管吗？数据安全吗？

可以完全自托管，Docker 一键部署。所有数据（用户信息、对话记录、知识库文档）存储在你自己的 PostgreSQL 中，不经过任何第三方服务器。

### AgentFlow 和 Dify 有什么区别？

核心区别三点：1）AgentFlow 内置浏览器自动化（Browser-Use），Dify 没有；2）AgentFlow 深度整合 9 个 agent-* 生态库，从提示词模板到可观测性全链路覆盖；3）两者都开源，但 AgentFlow 更轻量，适合快速部署和二次开发。

### 如何贡献代码？

标准流程：Issue → Fork → Branch → Develop → Test → PR → Review → Merge。详细开发指南见项目 `CONTRIBUTING.md`。

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

<!-- JSON-LD 结构化数据：AI 搜索引擎专用标记 -->
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  "name": "AgentFlow",
  "description": "开源零代码 AI Agent 部署平台，拖拽式工作流编辑器，支持多模型、知识库RAG、浏览器自动化，5分钟上线AI Agent。",
  "url": "https://github.com/PHclaw/agentflow",
  "applicationCategory": "DeveloperApplication",
  "operatingSystem": "Linux, macOS, Windows",
  "offers": {
    "@type": "Offer",
    "price": "0",
    "priceCurrency": "USD"
  },
  "programmingLanguage": ["Python", "TypeScript"],
  "license": "https://opensource.org/licenses/MIT",
  "author": {
    "@type": "Person",
    "name": "PHclaw",
    "url": "https://github.com/PHclaw"
  }
}
</script>

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "AgentFlow 是免费的吗？",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "是的，AgentFlow 完全开源（MIT 协议），可免费用于个人和商业项目。你需要自行承担服务器和 LLM API 调用费用。"
      }
    },
    {
      "@type": "Question",
      "name": "不会写代码能用 AgentFlow 吗？",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "可以。AgentFlow 的核心就是零代码拖拽式工作流编辑器，通过可视化画布连接节点即可构建 AI Agent。6 个行业模板开箱即用，5 分钟即可上线。"
      }
    },
    {
      "@type": "Question",
      "name": "支持哪些大模型？",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "目前支持 OpenAI（GPT-4o / GPT-4.1 / o3 / o4-mini）、Anthropic（Claude Sonnet 4 / Claude 3.5 Haiku）、DeepSeek（V3 / R1）和 Ollama 本地模型。"
      }
    },
    {
      "@type": "Question",
      "name": "知识库 RAG 是怎么工作的？",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "三步流程：1）上传文档自动分块；2）通过 embedding 模型生成向量并存入 pgvector；3）用户提问时检索相关片段，注入 LLM 上下文生成回答。支持 PDF、TXT、Markdown 等格式。"
      }
    },
    {
      "@type": "Question",
      "name": "可以自托管吗？数据安全吗？",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "可以完全自托管，Docker 一键部署。所有数据存储在你自己的 PostgreSQL 中，不经过任何第三方服务器。"
      }
    },
    {
      "@type": "Question",
      "name": "AgentFlow 和 Dify 有什么区别？",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "核心区别三点：1）AgentFlow 内置浏览器自动化（Browser-Use），Dify 没有；2）AgentFlow 深度整合 9 个 agent-* 生态库；3）两者都开源，但 AgentFlow 更轻量，适合快速部署和二次开发。"
      }
    },
    {
      "@type": "Question",
      "name": "如何贡献代码？",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "标准流程：Issue → Fork → Branch → Develop → Test → PR → Review → Merge。"
      }
    }
  ]
}
</script>

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "HowTo",
  "name": "如何用 Docker 部署 AgentFlow",
  "description": "5 分钟内用 Docker 一键部署 AgentFlow 零代码 AI Agent 平台",
  "step": [
    {
      "@type": "HowToStep",
      "name": "克隆仓库",
      "text": "运行 git clone https://github.com/PHclaw/agentflow.git 并进入目录"
    },
    {
      "@type": "HowToStep",
      "name": "配置环境变量",
      "text": "复制 .env.example 为 .env，填入 OPENAI_API_KEY 等 LLM API Keys"
    },
    {
      "@type": "HowToStep",
      "name": "启动服务",
      "text": "运行 docker-compose up -d，等待容器启动完成"
    },
    {
      "@type": "HowToStep",
      "name": "访问平台",
      "text": "浏览器打开 http://localhost:3000，注册账号后即可开始创建 AI Agent"
    }
  ]
}
</script>
