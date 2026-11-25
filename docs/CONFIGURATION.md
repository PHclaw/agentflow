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

## 邮件与注册验证码

注册默认要求邮箱验证码（`REQUIRE_EMAIL_CODE=true`）。用标准库 `smtplib` 发信，
**不需要额外安装依赖**。

### 配置 SMTP

```env
MAIL_ENABLED=true
MAIL_HOST=smtp.qq.com     # 或 smtp.163.com / 企业邮箱
MAIL_PORT=465             # 465 用 SSL；587 改 MAIL_USE_SSL=false 走 STARTTLS
MAIL_USER=you@qq.com
MAIL_PASSWORD=            # 邮箱「授权码」，不是登录密码
MAIL_FROM=                # 留空则用 MAIL_USER
MAIL_FROM_NAME=AgentFlow
MAIL_USE_SSL=true
```

> **授权码怎么拿**
> QQ 邮箱：设置 → 账户 → 开启 SMTP 服务 → 生成授权码
> 163 邮箱：设置 → POP3/SMTP/IMAP → 开启 → 新增授权密码
>
> 注意：国内云主机直连 **25 端口基本被封**，请用 465/587。发信标题也别写得像营销邮件，
> 否则容易进垃圾箱。

### 本地开发不配 SMTP

`MAIL_ENABLED=false` 时邮件**不会真的发出**，验证码以 WARNING 级别打印到后端日志：

```
WARNING | app.services.mailer | [MAIL_ENABLED=false] 邮件未发送（仅记录内容）
  To: you@example.com
  Subject: 【AgentFlow】注册验证码
你的注册验证码是：123456
```

### 验证码策略

| 变量 | 默认 | 说明 |
|:--|:--|:--|
| `CODE_TTL_SECONDS` | 300 | 有效期（秒） |
| `CODE_LENGTH` | 6 | 位数 |
| `CODE_RESEND_INTERVAL` | 60 | 同一邮箱重发冷却（秒） |
| `CODE_HOURLY_LIMIT` | 5 | 同一邮箱每小时上限 |
| `CODE_MAX_ATTEMPTS` | 5 | 单个码最多试错次数，超过即作废 |
| `SEND_CODE_IP_LIMIT` | 10 | 每 IP 每窗口的发码次数 |
| `SEND_CODE_IP_WINDOW` | 3600 | IP 限流窗口（秒） |

> 公司/学校共用出口 IP 时，`SEND_CODE_IP_LIMIT` 容易误伤，可按需放宽。
> `REQUIRE_EMAIL_CODE=false` 会关闭注册校验，**仅建议用于自动化测试与内网演示**。

### 验证码存储：务必注意多 worker

验证码优先存 **Redis**，连不上时退回**进程内存**。内存模式在 `uvicorn --workers N`
（N > 1）下**必然失效**——发码落在 worker A、校验落在 B，用户永远提示「验证码已过期」。
启动时会打印告警：

```
⚠️ 验证码当前使用内存存储：uvicorn 若开启多个 worker，发码与校验可能落在不同进程，导致校验永远失败。
```

**多 worker / 多实例部署必须配好 `REDIS_URL`。**

### 接口

| 方法 | 路径 | 说明 |
|:--|:--|:--|
| POST | `/api/v1/auth/send-code` | 发送注册验证码 |
| POST | `/api/v1/auth/register` | 注册（需带 `code` 字段） |

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
