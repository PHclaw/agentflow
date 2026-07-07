# AgentFlow - AI Agent 部署平台

> 让中小企业也能轻松部署 AI Agent，无需写代码

## 项目概述

### 定位
面向中小企业和非技术用户的 AI Agent 部署平台，通过拖拽式界面 + 预置模板，让业务人员也能快速构建智能体。

### 差异化
| 维度 | Dify/Coze | AgentFlow |
|------|-----------|-----------|
| 目标用户 | 开发者 | 业务人员 |
| 使用方式 | 需要技术背景 | 零代码拖拽 |
| 模板 | 通用模板 | 行业深度模板 |
| 集成 | API 接入 | 内置连接器 |

### 核心价值
- **零代码**：拖拽式 Agent 构建，业务人员 10 分钟上手
- **行业模板**：客服、销售、HR、财务等开箱即用
- **一键集成**：微信、钉钉、企业微信、飞书等
- **成本可控**：按使用量计费，中小企业也能用

---

## 市场分析

### 市场规模
- 2025 年企业级 AI Agent 市场：**232 亿元**
- 2027 年预计：**5,442 亿元**
- 年均复合增长率：**77%**

### 目标用户
| 用户类型 | 痛点 | 付费意愿 |
|---------|------|---------|
| 中小企业主 | 没技术团队，想用 AI | 中 ($99-299/月) |
| 业务部门负责人 | 想自动化但 IT 排期慢 | 高 ($199-499/月) |
| 自由职业者 | 个人效率工具 | 中 ($29-99/月) |
| 代理商/服务商 | 给客户部署 AI | 很高 ($499+/月) |

### 竞争策略
1. **差异化**：专注"业务人员"而非"开发者"
2. **垂直化**：深耕 3-5 个行业场景（客服、销售、HR）
3. **本土化**：中文优化、国内系统集成

---

## 核心功能

### MVP（v1.0，3 个月）

#### 模块 A：Agent 构建器
| 功能 | 描述 | 优先级 |
|------|------|--------|
| 拖拽式工作流 | 可视化拖拽构建 Agent 流程 | P0 |
| 预置模板库 | 客服机器人、销售助手等 | P0 |
| 知识库管理 | 上传文档，RAG 检索 | P0 |
| 模型配置 | OpenAI/Claude/DeepSeek 切换 | P0 |

#### 模块 B：Agent 运行时
| 功能 | 描述 | 优先级 |
|------|------|--------|
| 多轮对话 | 上下文记忆、对话管理 | P0 |
| 工具调用 | 搜索、计算、API 调用 | P0 |
| 人工介入 | 关键节点人工确认 | P1 |
| 日志追踪 | 运行日志、调试 | P1 |

#### 模块 C：集成与发布
| 功能 | 描述 | 优先级 |
|------|------|--------|
| Web 对话组件 | 嵌入网站的小部件 | P0 |
| API 接口 | REST API 供外部调用 | P0 |
| 微信/企微 | 微信生态集成 | P1 |

### 进阶功能（v2.0，6 个月）

| 功能 | 描述 |
|------|------|
| 多 Agent 协作 | Agent 之间协作完成任务 |
| 数据分析面板 | 对话数据统计、用户画像 |
| A/B 测试 | 不同 Agent 版本对比 |
| 私有化部署 | 企业本地部署版本 |

---

## 技术架构

### 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                      前端层                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │  构建器 UI  │  │  模板市场   │  │  管理后台   │        │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘        │
└─────────┼────────────────┼────────────────┼────────────────┘
          │                │                │
          └────────────────┴────────────────┘
                           │
                    ┌──────┴──────┐
                    │   API 网关   │
                    └──────┬──────┘
                           │
┌──────────────────────────┼──────────────────────────────────┐
│                      服务层                                  │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐       │
│  │工作流引擎│  │ Agent运行│  │ 知识库  │  │ 集成服务 │       │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘       │
└───────┼────────────┼────────────┼────────────┼─────────────┘
        │            │            │            │
┌───────┴────────────┴────────────┴────────────┴─────────────┐
│                      数据层                                  │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐       │
│  │PostgreSQL│  │  Redis  │  │ 向量库  │  │ 对象存储 │       │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘       │
└─────────────────────────────────────────────────────────────┘
```

### 技术选型

| 层级 | 技术栈 | 选型理由 |
|------|--------|---------|
| **前端** | React + TypeScript + Tailwind + ReactFlow | ReactFlow 用于拖拽工作流 |
| **后端** | Python FastAPI | AI 生态好、异步性能高 |
| **工作流引擎** | LangGraph | 灵活、LangChain 生态 |
| **数据库** | PostgreSQL + pgvector | 向量检索一体化 |
| **缓存** | Redis | 会话管理、限流 |
| **消息队列** | Celery + Redis | 异步任务处理 |
| **对象存储** | MinIO | 文档、日志存储 |

### 核心模块设计

#### 工作流引擎

```python
# workflow_engine.py

from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated

class AgentState(TypedDict):
    """Agent 状态"""
    messages: list
    current_node: str
    context: dict
    tools: list

class WorkflowEngine:
    """工作流引擎"""
    
    def __init__(self, workflow_definition: dict):
        self.definition = workflow_definition
        self.graph = StateGraph(AgentState)
        self._build_graph()
    
    def _build_graph(self):
        """根据定义构建工作流图"""
        for node in self.definition["nodes"]:
            self.graph.add_node(node["id"], self._create_node_handler(node))
        
        for edge in self.definition["edges"]:
            self.graph.add_edge(edge["source"], edge["target"])
    
    async def run(self, input_data: dict) -> dict:
        """执行工作流"""
        app = self.graph.compile()
        result = await app.ainvoke(input_data)
        return result
    
    def _create_node_handler(self, node: dict):
        """创建节点处理器"""
        node_type = node["type"]
        if node_type == "llm":
            return self._llm_node(node)
        elif node_type == "tool":
            return self._tool_node(node)
        elif node_type == "condition":
            return self._condition_node(node)
        # ... 更多节点类型
```

#### Agent 运行时

```python
# agent_runtime.py

class AgentRuntime:
    """Agent 运行时"""
    
    def __init__(self, agent_id: str, db: AsyncSession):
        self.agent_id = agent_id
        self.db = db
        self.workflow = None
        self.memory = None
    
    async def initialize(self):
        """初始化 Agent"""
        # 加载 Agent 配置
        agent = await self._load_agent()
        # 构建工作流
        self.workflow = WorkflowEngine(agent.workflow_definition)
        # 初始化记忆
        self.memory = ConversationMemory(agent.memory_config)
    
    async def chat(self, message: str, session_id: str) -> str:
        """对话"""
        # 加载历史
        history = await self.memory.get_history(session_id)
        # 构建输入
        input_data = {
            "messages": history + [{"role": "user", "content": message}],
            "session_id": session_id,
        }
        # 执行工作流
        result = await self.workflow.run(input_data)
        # 保存历史
        await self.memory.save_history(session_id, result["messages"])
        
        return result["response"]
```

### 数据库设计

```sql
-- Agent 表
CREATE TABLE agents (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    name VARCHAR(100),
    description TEXT,
    workflow_definition JSONB,  -- 工作流定义
    model_config JSONB,         -- 模型配置
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 工作流模板表
CREATE TABLE workflow_templates (
    id UUID PRIMARY KEY,
    name VARCHAR(100),
    category VARCHAR(50),  -- customer_service / sales / hr / finance
    description TEXT,
    workflow_definition JSONB,
    preview_image VARCHAR(500),
    use_count INTEGER DEFAULT 0,
    is_public BOOLEAN DEFAULT TRUE
);

-- 对话会话表
CREATE TABLE chat_sessions (
    id UUID PRIMARY KEY,
    agent_id UUID REFERENCES agents(id),
    user_id UUID,
    messages JSONB,  -- 消息历史
    metadata JSONB,  -- 元数据
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 知识库表
CREATE TABLE knowledge_bases (
    id UUID PRIMARY KEY,
    agent_id UUID REFERENCES agents(id),
    name VARCHAR(100),
    documents_count INTEGER DEFAULT 0,
    embedding_model VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);

-- 文档向量表
CREATE TABLE document_embeddings (
    id UUID PRIMARY KEY,
    kb_id UUID REFERENCES knowledge_bases(id),
    document_id UUID,
    chunk_index INTEGER,
    content TEXT,
    embedding VECTOR(1536),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## 商业化路径

### 定价策略

| 版本 | 价格 | 功能 |
|------|------|------|
| **免费版** | ¥0 | 1 个 Agent、100 次/月对话、基础模板 |
| **专业版** | ¥99/月 | 5 个 Agent、5000 次对话、全部模板、API |
| **团队版** | ¥299/月 | 20 个 Agent、50000 次对话、协作、优先支持 |
| **企业版** | ¥999/月 | 无限 Agent、私有部署、定制开发 |

### 收入预测

| 时间 | 付费用户 | ARPU | MRR |
|------|---------|------|-----|
| 6 个月 | 200 | ¥150 | ¥30,000 |
| 12 个月 | 1,000 | ¥180 | ¥180,000 |
| 24 个月 | 5,000 | ¥200 | ¥1,000,000 |

---

## 开发计划

### 里程碑

```
Month 1: 基础架构
├── Week 1-2: 数据库设计、API 框架
├── Week 3-4: 工作流引擎核心
└── Week 5-6: Agent 运行时

Month 2: 前端 + 核心功能
├── Week 1-2: 拖拽式构建器 UI
├── Week 3-4: 模板系统
└── Week 5-6: 对话组件、集成

Month 3: 完善 + 上线
├── Week 1-2: 知识库、RAG
├── Week 3-4: 用户系统、订阅
└── Week 5-6: 测试、部署、运营准备
```

---

## 下一步行动

1. [ ] 初始化项目仓库
2. [ ] 搭建后端 API 框架
3. [ ] 实现工作流引擎核心
4. [ ] 创建前端项目
5. [ ] 设计预置模板

---

> 📌 **核心洞察**：中小企业 AI 落地的最大障碍不是技术本身，而是"技术门槛"。让业务人员也能用 AI，才是真正的机会。
