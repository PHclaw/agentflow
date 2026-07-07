# AgentFlow API 文档

## 概述

AgentFlow 是一个零代码 AI Agent 部署平台，支持：
- 多种 LLM 后端（OpenAI、Anthropic、本地模型）
- RAG 知识库
- 工具调用
- 多 Agent 协作
- 完整的可观测性

## 基础 URL

```
http://localhost:8000/api/v1
```

## 认证

所有 API 需要在 Header 中携带 JWT Token：

```
Authorization: Bearer <token>
```

---

## API 端点

### 认证

#### POST /auth/register

注册新用户

**Request:**
```json
{
  "email": "user@example.com",
  "username": "username",
  "password": "password123"
}
```

**Response:**
```json
{
  "id": "user-uuid",
  "email": "user@example.com",
  "username": "username",
  "access_token": "jwt-token"
}
```

#### POST /auth/login

登录

**Request:**
```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

**Response:**
```json
{
  "access_token": "jwt-token",
  "token_type": "bearer"
}
```

---

### Agent 管理

#### GET /agents

获取用户的 Agent 列表

**Response:**
```json
{
  "agents": [
    {
      "id": "agent-uuid",
      "name": "My Agent",
      "description": "Description",
      "model_config": {
        "provider": "openai",
        "model": "gpt-4o-mini"
      },
      "message_count": 100,
      "created_at": "2026-05-07T00:00:00Z"
    }
  ]
}
```

#### POST /agents

创建 Agent

**Request:**
```json
{
  "name": "My Agent",
  "description": "A helpful assistant",
  "model_config": {
    "provider": "openai",
    "model": "gpt-4o-mini"
  },
  "temperature": 0.7,
  "template": "qa",
  "knowledge_base_id": "kb-uuid"
}
```

#### GET /agents/{agent_id}

获取 Agent 详情

#### PUT /agents/{agent_id}

更新 Agent

#### DELETE /agents/{agent_id}

删除 Agent

---

### 对话

#### POST /chat/{agent_id}

与 Agent 对话（整合版）

**Request:**
```json
{
  "message": "Hello, how can you help me?",
  "session_id": "session-uuid",
  "stream": false
}
```

**Response:**
```json
{
  "response": "Hello! I'm here to help you...",
  "session_id": "session-uuid",
  "stats": {
    "agent_id": "agent-uuid",
    "message_count": 101,
    "tracing": {
      "total_spans": 5,
      "total_duration_ms": 1234
    }
  }
}
```

**特性：**
- 自动追踪对话（agent-observability）
- 使用提示词模板（agent-prompt-templates）
- 解析输出（agent-output-parser）
- 管理记忆（agent-memory-store）

#### POST /chat/{agent_id}/with-tools

带工具调用的对话

**Request:**
```json
{
  "message": "Search for the latest news about AI",
  "session_id": "session-uuid"
}
```

**Response:**
```json
{
  "response": "Here are the latest AI news...",
  "session_id": "session-uuid",
  "stats": {...}
}
```

#### POST /chat/multi-agent

多 Agent 协作

**Request:**
```json
{
  "message": "Analyze this data and create a report",
  "agent_ids": ["agent-1", "agent-2", "agent-3"],
  "session_id": "session-uuid"
}
```

**Response:**
```json
{
  "results": {
    "result": "Final output from multi-agent collaboration"
  },
  "session_id": "session-uuid"
}
```

#### GET /chat/{agent_id}/stats

获取 Agent 统计信息

---

### 知识库

#### GET /knowledge

获取知识库列表

#### POST /knowledge

创建知识库

**Request:**
```json
{
  "name": "My Knowledge Base",
  "description": "Company documents",
  "embedding_model": "text-embedding-3-small"
}
```

#### POST /knowledge/{kb_id}/documents

上传文档

**Request:** `multipart/form-data`
- `file`: 文档文件（PDF、TXT、MD、DOCX）

#### POST /knowledge/{kb_id}/search

搜索知识库

**Request:**
```json
{
  "query": "What is the company policy?",
  "top_k": 5
}
```

**Response:**
```json
{
  "results": [
    {
      "content": "The company policy states...",
      "score": 0.85,
      "metadata": {
        "source": "policy.pdf",
        "page": 1
      }
    }
  ]
}
```

---

### 模板

#### GET /templates

获取提示词模板列表

**Response:**
```json
{
  "templates": [
    {
      "name": "qa",
      "description": "Question answering template",
      "variables": ["context", "question"]
    },
    {
      "name": "cot",
      "description": "Chain of thought template",
      "variables": ["context", "question"]
    }
  ]
}
```

---

### 计费

#### GET /billing/subscription

获取订阅信息

#### POST /billing/checkout

创建 Stripe Checkout Session

**Request:**
```json
{
  "price_id": "price-uuid"
}
```

**Response:**
```json
{
  "checkout_url": "https://checkout.stripe.com/..."
}
```

---

## 整合的 Agent-* 库

AgentFlow 整合了以下 agent-* 库：

| 库 | 功能 | 整合位置 |
|---|---|---|
| agent-config-loader | 多环境配置 | integrations/__init__.py |
| agent-observability | 追踪/可观测性 | integrations/__init__.py |
| agent-prompt-templates | 提示词模板 | integrations/prompts_outputs.py |
| agent-output-parser | 输出解析 | integrations/prompts_outputs.py |
| agent-tool-registry | 工具管理 | integrations/tools_memory.py |
| agent-memory-store | 记忆管理 | integrations/tools_memory.py |
| agent-orchestrator | 多 Agent 编排 | services/integrated_runtime.py |

---

## 错误处理

所有错误响应格式：

```json
{
  "detail": "Error message"
}
```

常见错误码：
- `400` - 请求参数错误
- `401` - 未认证
- `403` - 无权限
- `404` - 资源不存在
- `500` - 服务器错误

---

## WebSocket

实时对话支持：

```
ws://localhost:8000/api/v1/ws/chat/{agent_id}
```

**Message:**
```json
{
  "type": "message",
  "content": "Hello"
}
```

**Response (stream):**
```json
{
  "type": "token",
  "content": "Hello"
}
{
  "type": "token",
  "content": "!"
}
{
  "type": "done",
  "content": "Hello! How can I help you?"
}
```

---

## 开发

### 安装

```bash
cd backend
pip install -r requirements.txt
```

### 运行测试

```bash
pytest --cov=app
```

### 启动开发服务器

```bash
uvicorn app.main:app --reload
```

### 环境变量

创建 `.env` 文件：

```env
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/agentflow
REDIS_URL=redis://localhost:6379
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
STRIPE_SECRET_KEY=sk_...
```
