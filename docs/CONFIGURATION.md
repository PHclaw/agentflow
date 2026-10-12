# 配置说明

> 本页由 README 拆分而来，内容与代码同步维护。返回 [README](../README.md)。

## 环境变量

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

## 大模型 API 配置（支持热切换）

在 **设置 → 模型配置** 里可以自行填写 API Key 与端点，**不用改 .env、也不用重启服务**。

| 能力 | 说明 |
|:-----|:-----|
| 增删改查 | 别名、服务商、Base URL、模型、温度、最大 tokens、备注 |
| 别名与默认项 | 别名唯一（重复会明确提示）；「设为默认」即刻生效 |
| 启用/停用 | 可临时停用某套配置；默认项不允许停用，避免出现无可用配置 |
| 连接测试 | 保存前可先测；先探测 `/models`（不消耗 token），不可用时退回一次最小对话请求 |
| 错误提示 | 认证失败 / 域名解析失败 / 连接被拒绝 / 路径需要 `/v1` / 模型不存在 / 超时，分别给出可操作提示 |
| 密钥安全 | Fernet 加密落库，接口只返回脱敏值（如 `sk-l******7890`），明文不出后端 |
| 热切换 | 写操作立即让运行时快照失效，**下一条请求**就用新配置 |

**热切换是怎么做到的**

全项目的模型凭证只有一个出口：`app/services/model_runtime.py` 的 `resolve_credentials()`。
它优先读内存中的「生效配置快照」，快照由 `app/services/llm_config.py` 维护：

- 启动时预加载一次（`main.py` 的 lifespan）
- 任何增删改都会 `invalidate()`，立刻刷新快照并清空底层 SDK 客户端缓存
- 请求级中间件只在快照过期时查库，因此多 worker 部署下最迟
  `LLM_CONFIG_CACHE_TTL_SECONDS`（默认 5 秒）对所有进程一致

**回退行为**：一套配置都没有时，继续使用 `.env` 里的凭证，原有部署不受影响；
界面会标注「当前来自 .env 回退」。

**接口**

| 方法 | 路径 | 说明 |
|:-----|:-----|:-----|
| GET | `/api/v1/llm-configs` | 列表（脱敏）+ 当前生效项 |
| POST | `/api/v1/llm-configs` | 新增 |
| PUT | `/api/v1/llm-configs/{id}` | 更新（不传 `api_key` 表示保留原密钥）|
| DELETE | `/api/v1/llm-configs/{id}` | 删除（删掉默认项会自动补一个）|
| POST | `/api/v1/llm-configs/{id}/default` | 设为默认并立即生效 |
| POST | `/api/v1/llm-configs/{id}/active` | 启用 / 停用 |
| POST | `/api/v1/llm-configs/{id}/test` | 测试已保存配置并记录结果 |
| POST | `/api/v1/llm-configs/test` | 测试未保存的草稿 |
| GET | `/api/v1/llm-configs/active` | 当前真正生效的配置 |
| GET | `/api/v1/llm-configs/providers` | 可选服务商预设与建议模型 |

> 仅支持 **OpenAI 兼容协议** 的端点（OpenAI / DeepSeek / Ollama / 百炼 / vLLM / OneAPI 等）。
> 原生 Anthropic 协议需要额外的适配器，暂不在本系统范围内。

---

## SQLite 轻量模式

只想把后端跑起来、不想装数据库和一堆重型依赖时，用一键脚本：

```powershell
.\scripts\dev-backend.ps1                # 启动在 http://127.0.0.1:8001
.\scripts\dev-backend.ps1 -Port 8002     # 指定端口
.\scripts\dev-backend.ps1 -SkipServe     # 只准备环境，不启动服务
.\scripts\dev-backend.ps1 -Reinstall     # 强制重装依赖
```

脚本会自动完成：探测 Python 3.11+ → 创建 `backend/.venv` → 安装 `backend/requirements-lite.txt` → 生成 `.env`（默认 `DATABASE_URL` 为 SQLite）→ 启动 uvicorn。

**轻量依赖集 vs 完整依赖集**

`requirements-lite.txt` 刻意排除了以下包，以缩短安装时间并避免版本冲突：

| 排除的包 | 影响 |
|:---------|:-----|
| `sentence-transformers` | 会拖入 torch（约 2GB）。本地嵌入不可用，知识库改用 OpenAI embeddings 不受影响 |
| `faiss-cpu` | Python 3.13 常无预编译 wheel。基于 faiss 的本地向量检索不可用 |
| `playwright` / `browser-use` | 浏览器自动化节点不可用，需另行安装并下载浏览器内核 |
| `asyncpg` / `pgvector` | 仅 PostgreSQL 需要，SQLite 模式用不到 |

需要完整功能时，改用 `pip install -r requirements.txt`（注意 `langgraph==0.0.20` + `langchain==0.1.4` 的锁定组合较旧，Python 3.13 下可能需要放宽松版本）。

## PiAgent 引擎（可选）

除了内置的「直连大模型」链路，AgentFlow 还可以把外部 agent CLI（`pi`）作为
Agent 的**可选推理引擎**。两条链路完全独立、互不影响，用环境变量切换。

**1. 安装 CLI**

```bash
npm install -g @earendil-works/pi-coding-agent
pi --version
```

**2. 启用（`backend/.env`）**

```env
PIAGENT_ENABLED=true
PIAGENT_EXE=pi                 # 留空或 pi 即自动在 PATH 中查找
PIAGENT_TIMEOUT=180
# pi 默认 provider 是 google；如需与项目模型保持一致可显式指定
# PIAGENT_PROVIDER=openai
# PIAGENT_MODEL=gpt-4o-mini
# PIAGENT_WORKSPACE_ROOT=      # 默认 uploads/pi_workspace/<agent_id>
# PIAGENT_SKILLS_DIR=          # 默认仓库根的 skills/
```

**3. 配置 pi 的凭据**

pi 自己管理凭据（`pi auth`），也可以直接给它设置 provider 环境变量。放在
`backend/.env` 里的 `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` 等会被自动透传给
pi 子进程，无需重复配置。

**接口**

| 方法 | 路径 | 说明 |
|:-----|:-----|:-----|
| GET | `/api/v1/pi/status` | 就绪状态、解析到的 exe、可用技能列表 |
| POST | `/api/v1/pi/{agent_id}/stream` | 流式对话（SSE） |
| POST | `/api/v1/pi/{agent_id}/run` | 非流式对话（脚本/调试用） |
| GET | `/api/v1/pi/{agent_id}/workspace` | 列出该 Agent 工作区产物 |
| GET | `/api/v1/pi/{agent_id}/files/{path}` | 下载产物（限制在工作区内） |

**SSE 事件协议**

```json
{"type": "log",       "content": "AI 正在思考…"}
{"type": "thinking",  "content": "…"}
{"type": "tool_call", "content": "正在调用工具：write_file"}
{"type": "text",      "content": "增量正文"}
{"type": "done",      "content": "最终答案", "files": [...], "session_id": null}
{"type": "error",     "content": "错误说明"}
```

**设计要点**

- 每个 Agent 一个独立工作区（`uploads/pi_workspace/<agent_id>`），互不干扰
- 提示词经一次性临时文件传递，避免命令行长度限制与多行截断，用完即删
- 系统提示词取自 Agent 配置（`model_config.system_prompt` / `settings.system_prompt`），
  未配置时按 Agent 名称与描述自动生成
- 技能通过 `--skill` 注入 AgentFlow 已有的 `skills/<slug>/SKILL.md`
- 工作区新旧文件对比，新增文件自动作为可下载附件回传
- 过滤「我将读取文件…」这类过程性叙述，避免向用户暴露内部机制
- Windows 下自动改用 `node + cli.js` 绕过 `.cmd`，避免 subprocess 兼容问题
