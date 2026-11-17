# 常见问题

> 本页由 README 拆分而来，内容与代码同步维护。返回 [README](../README.md)。

#### AgentFlow 是免费的吗？

是的，AgentFlow 以 **Apache-2.0** 开源，允许包括商业用途在内的使用、修改与再分发。你需要自行承担服务器与 LLM API 调用费用。

注意 `skills/` 下的技能来自不同社区，各自许可不同（Apache-2.0 / MIT / 无声明 / 保留所有权利），不能整体按本仓库协议再分发，详见 [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)。

#### 不会写代码能用 AgentFlow 吗？

可以。AgentFlow 的核心就是零代码拖拽式工作流编辑器，通过可视化画布连接节点即可构建 AI Agent。6 个行业模板开箱即用，5 分钟即可上线。

#### 支持哪些大模型？

目前支持 OpenAI（GPT-4o / GPT-4.1 / o3 / o4-mini）、Anthropic（Claude Sonnet 4 / Claude 3.5 Haiku）、DeepSeek（V3 / R1）和 Ollama 本地模型。通过 `GET /api/v1/templates/models/list` 可获取完整模型列表。

#### 知识库 RAG 是怎么工作的？

三步流程：1）上传文档 → 自动分块；2）调用 **独立配置的 embedding 端点**生成向量，默认存入 chromadb（换 PostgreSQL + pgvector 是可选路径）；3）提问时检索相关片段，注入上下文生成回答。支持 PDF、TXT、Markdown 等格式。

> Docker 部署必须填 `EMBEDDING_BASE_URL`：官方镜像没装本地 embedding 模型（2GB+），留空会静默失败——表现为知识库能建但检索不出内容。

#### 可以自托管吗？数据安全吗？

可以完全自托管，Docker 一键部署。数据（用户、Agent、对话、知识库记录）默认存在你自己的 **SQLite 文件**（`./data/agentflow.db`），也可以切到 PostgreSQL；模型调用走你配置的端点，可以指向本地 Ollama，连外网都不出。

#### AgentFlow 和 Dify 有什么区别？

Dify 功能更全（插件市场、观测、多租户都更成熟），本项目更小更轻，差异主要在部署与交付形态：

1. **部署成本**：本项目默认 SQLite + 两个容器（backend + nginx）；Dify 起步需要 PostgreSQL + Redis + worker，四五个容器。
2. **产物交付**：本项目生成的文件作为附件回传，图片类直接内联在对话里；Dify 部分支持。
3. **扩展方式**：本项目是「加一个带 `SKILL.md` 的目录」，也能直接改源码（Apache-2.0）；Dify 走插件市场。

反过来说清楚的短板：本项目**没有**异步任务队列、没有细粒度权限、没有插件生态，并发能力也远不如 Dify。选它是因为「一台小机器 + 数据不出内网」，不是因为功能更多。完整对照见 [COMPARISON.md](COMPARISON.md)。

#### 如何贡献代码？

标准流程：Issue → Fork → Branch → Develop → Test → PR → Review → Merge。详细开发指南见项目 `CONTRIBUTING.md`。
