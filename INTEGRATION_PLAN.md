# AgentFlow 与 Agent-* 库生态整合方案

## 目标

让 agentflow 使用 PHclaw 下的 8 个 agent-* 库，减少重复代码，提升可维护性。

## 整合映射表

| agent-* 库 | agentflow 现有模块 | 整合方式 |
|-----------|-------------------|---------|
| agent-config-loader | core/config.py | 替换，支持多环境 |
| agent-prompt-templates | 硬编码 prompt | 注入到 services/llm.py |
| agent-output-parser | 无 | 新增，解析 LLM 输出 |
| agent-tool-registry | services/tools.py | 替换，统一工具管理 |
| agent-memory-store | ChatSession.messages | 替换，支持多种后端 |
| agent-observability | 无 | 新增，添加 tracing |
| agent-orchestrator | workflows/engine.py | 增强，支持多 Agent |
| agent-mcp-client | 无 | 新增，MCP 协议支持 |

## 实施步骤

### Phase 1: 基础整合（低风险）

1. **agent-config-loader**
   - 替换 `core/config.py`
   - 支持 .env, .env.production, .env.staging
   - 验证 schema

2. **agent-observability**
   - 在 `AgentRuntime.chat()` 添加 tracing
   - 记录 token 使用、延迟、错误

### Phase 2: 核心整合（中风险）

3. **agent-prompt-templates**
   - 在 `services/llm.py` 使用模板
   - 支持 CoT、ReAct、Few-shot

4. **agent-output-parser**
   - 解析工具调用结果
   - 验证 JSON 输出

5. **agent-tool-registry**
   - 替换 `services/tools.py`
   - 统一工具注册和调用

### Phase 3: 高级整合（高风险）

6. **agent-memory-store**
   - 替换 ChatSession.messages
   - 支持 Redis、PostgreSQL 后端

7. **agent-orchestrator**
   - 增强 WorkflowEngine
   - 支持多 Agent 协作

8. **agent-mcp-client**
   - 新增 MCP 协议支持
   - 连接外部 MCP 服务器

## 依赖更新

```txt
# Agent ecosystem
agent-config-loader>=0.1.0
agent-prompt-templates>=0.1.0
agent-output-parser>=0.1.0
agent-tool-registry>=0.1.0
agent-memory-store>=0.1.0
agent-observability>=0.1.0
agent-orchestrator>=0.1.0
agent-mcp-client>=0.1.0
```

## 兼容性保证

- 所有整合通过适配器模式
- 保留原有 API 接口
- 渐进式迁移，可回滚

## 测试策略

- 每个整合点添加单元测试
- 集成测试验证端到端流程
- 性能基准对比

## 预期收益

| 指标 | 当前 | 整合后 |
|-----|-----|-------|
| 代码行数 | ~2000 | ~1200 |
| 测试覆盖 | 0% | 80%+ |
| 配置灵活性 | 单环境 | 多环境 |
| 可观测性 | 无 | 完整 tracing |
| 工具扩展 | 硬编码 | 插件化 |
