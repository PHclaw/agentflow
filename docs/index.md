---
title: AgentFlow 文档
---

# AgentFlow 文档

零代码 AI Agent 平台：拖拽式工作流 + 多模型热切换 + 知识库 RAG + Skill 广场 + 一键部署。
默认 SQLite 单机可跑，数据完全留在自己的机器上。

- 仓库：<https://github.com/PHclaw/agentflow>
- 在线演示：<http://159.75.21.251:3000>
- Wiki（入门与常见问题）：<https://github.com/PHclaw/agentflow/wiki>

## 开始使用

| 文档 | 内容 |
|:--|:--|
| [配置说明](CONFIGURATION.md) | 环境变量全表 · 模型配置热切换 · SQLite 轻量模式 |
| [部署指南](DEPLOYMENT.md) | Docker Compose · Nginx 反向代理 · 数据库备份 |
| [常见问题](FAQ.md) | 模型 · RAG · 自托管 · 计费 |

## 深入了解

| 文档 | 内容 |
|:--|:--|
| [架构说明](ARCHITECTURE.md) | 系统架构 · 工作流节点类型 · 项目结构 |
| [API 文档](API.md) | REST 端点 · 认证 · 错误处理 |
| [开发指南](DEVELOPMENT.md) | 测试 · 数据库迁移 · UI 诊断脚本 |
| [与同类产品对比](COMPARISON.md) | 与 Dify / Coze 等方案的差异 |
| [更新日志](CHANGELOG.md) | 版本变更记录与路线图 |

## 快速开始

```bash
git clone https://github.com/PHclaw/agentflow.git
cd agentflow
cp .env.example .env      # 至少填 JWT_SECRET_KEY
docker compose up -d --build
```

打开 <http://localhost:3000>，注册后进「设置 → 模型配置」填上模型端点即可对话。
