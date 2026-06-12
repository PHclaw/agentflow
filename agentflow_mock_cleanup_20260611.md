# AgentFlow Mock 数据清理 + 数据库化

## 目标
移除 agentflow 项目中散落在各处的 mock/硬编码/内存存储数据，统一接入 SQLAlchemy 数据库。

## 变更摘要

### 后端 (4 个文件)
| 文件 | 改动 |
|------|------|
| `backend/app/api/agents.py` | **内存 dict → 数据库 CRUD**。create_agent 同时修复了重复 key bug (id/name 返回两次)。所有操作通过 AsyncSession + Agent ORM 模型完成 |
| `backend/app/api/agent_routes.py` | **全部 mock 端点接入 DB**。stats/versions/duplicate/export/import/health/validate/performance/templates 共 12 个端点。新增 GET /stats/summary dashboard 接口 |
| `frontend/src/pages/DashboardPage.tsx` | 移除 50+ 行硬编码 mock 数据，改为调用 /agents/stats/summary |
| `frontend/src/pages/AgentListPage.tsx` | 移除 mock 数据 fallback (3 个假 Agent)，修复 response.data 用法 |
| `frontend/src/pages/ChatPage.tsx` | 移除 mock 数据 fallback，修复 response.data 用法 |

### 修复的 Bug
1. `agents.py` create_agent 返回字典中存在重复的 `id` 和 `name` key（Python dict 后覆盖前者）
2. `agents.py` 完全使用内存字典，服务重启后所有 Agent 丢失
3. 前端多处使用 `response.data` 而非直接使用响应体（与 api.ts 返回格式不匹配）
4. 前端静默回退到 mock 数据，掩盖了 API 错误

### 影响
- Agent 数据持久化到 SQLite/PostgreSQL
- 所有增强路由（统计、模板、版本）不再是假数据
- Dashboard 显示真实数据
- 减少约 300 行无用代码

### 下一步建议
- 添加 Alembic 迁移
- WorkflowPage 和 KnowledgePage 的 mock 数据清理
- Auth 系统数据库化
