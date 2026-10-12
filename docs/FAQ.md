# 常见问题

> 本页由 README 拆分而来，内容与代码同步维护。返回 [README](../README.md)。

#### AgentFlow 是免费的吗？

是的，AgentFlow 完全开源（MIT 协议），可免费用于个人和商业项目。你需要自行承担服务器和 LLM API 调用费用。

#### 不会写代码能用 AgentFlow 吗？

可以。AgentFlow 的核心就是零代码拖拽式工作流编辑器，通过可视化画布连接节点即可构建 AI Agent。6 个行业模板开箱即用，5 分钟即可上线。

#### 支持哪些大模型？

目前支持 OpenAI（GPT-4o / GPT-4.1 / o3 / o4-mini）、Anthropic（Claude Sonnet 4 / Claude 3.5 Haiku）、DeepSeek（V3 / R1）和 Ollama 本地模型。通过 `GET /api/v1/templates/models/list` 可获取完整模型列表。

#### 知识库 RAG 是怎么工作的？

三步流程：1）上传文档 → 自动分块；2）通过 embedding 模型生成向量并存入 pgvector；3）用户提问时检索相关片段，注入 LLM 上下文生成回答。支持 PDF、TXT、Markdown 等格式。

#### 可以自托管吗？数据安全吗？

可以完全自托管，Docker 一键部署。所有数据（用户信息、对话记录、知识库文档）存储在你自己的 PostgreSQL 中，不经过任何第三方服务器。

#### AgentFlow 和 Dify 有什么区别？

核心区别三点：1）AgentFlow 内置浏览器自动化（Browser-Use），Dify 没有；2）AgentFlow 深度整合 9 个 agent-* 生态库，从提示词模板到可观测性全链路覆盖；3）两者都开源，但 AgentFlow 更轻量，适合快速部署和二次开发。

#### 如何贡献代码？

标准流程：Issue → Fork → Branch → Develop → Test → PR → Review → Merge。详细开发指南见项目 `CONTRIBUTING.md`。
