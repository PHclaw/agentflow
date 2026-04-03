# AgentFlow - AI Agent 部署平台

<div align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.109-green.svg" alt="FastAPI">
  <img src="https://img.shields.io/badge/React-18-61DAFB.svg" alt="React">
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License">
</div>

> 让每个企业都能拥有专属 AI Agent - 低代码/零代码构建，开箱即用的行业模板

## ✨ 特性

- **🎯 拖拽式构建** - 可视化界面，拖拽节点构建工作流
- **📦 预置行业模板** - 客服、销售、HR、财务等开箱即用
- **🧠 知识库 RAG** - 上传文档，AI 自动学习企业知识
- **⚡ 工具调用** - 搜索、计算、API 调用等工具集成
- **🔗 多渠道接入** - 微信、钉钉、企业微信、网站、API
- **📊 数据分析** - 完整的数据面板，了解用户意图

## 🏗️ 技术栈

### 后端
- **FastAPI** - 高性能 Python Web 框架
- **SQLAlchemy + PostgreSQL** - 异步 ORM + pgvector 向量数据库
- **LangGraph** - Agent 工作流编排
- **Celery + Redis** - 异步任务队列
- **JWT Auth** - 安全的用户认证

### 前端
- **React 18 + TypeScript** - 现代化前端框架
- **ReactFlow** - 拖拽式工作流编辑器
- **Tailwind CSS** - 原子化 CSS
- **React Router** - 页面路由

## 🚀 快速开始

### 环境要求
- Python 3.11+
- Node.js 18+
- PostgreSQL 16+ (with pgvector)
- Redis 7+

### 1. 克隆项目
```bash
git clone https://github.com/PHclaw/agentflow.git
cd agentflow
```

### 2. 后端启动
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Linux/Mac
.\venv\Scripts\activate  # Windows
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

### 3. 前端启动
```bash
cd frontend
npm install
npm run dev
```

### 4. Docker 部署
```bash
docker-compose up -d
```

## 📁 项目结构

```
agentflow/
├── backend/
│   ├── app/
│   │   ├── api/           # API 路由
│   │   ├── core/          # 核心配置
│   │   ├── models/        # 数据模型
│   │   ├── services/      # 业务服务
│   │   └── workflows/     # 工作流引擎
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/    # React 组件
│   │   ├── pages/         # 页面
│   │   └── services/      # API 服务
│   └── package.json
├── docker-compose.yml
└── README.md
```

## 📖 API 文档

启动服务后访问: http://localhost:8000/docs

## 📄 License

MIT License
