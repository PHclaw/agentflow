# 部署指南

两种方式：**Docker Compose（推荐）** 和 **裸机直跑**。先读「部署前必须改的配置」。

> 本文的命令都在 Docker Desktop 29.x / Compose v5 上实际跑通过：两个镜像构建成功、
> 容器起来后走过一遍完整用户流程（注册 → 收码 → 登录 → 技能广场 → 导入 54MB
> 技能包），并验证过**容器彻底重建后数据仍在**。

---

## 0. 部署前必须改的配置

```bash
cp .env.example .env
```

⚠️ **文件必须放在项目根目录**，不是 `backend/.env`。两个原因：

- `docker compose` 只从项目根目录读 `.env`（用于 `${VAR}` 插值和 `env_file`）；
- 放错位置的话容器拿不到任何配置，`JWT_SECRET_KEY` 会退回内置的
  `change-me-in-production` —— 而**它不会报错**，看起来一切正常，实际上
  任何人都能伪造登录态。

至少改掉这几项：

| 项 | 为什么必须改 |
|:--|:--|
| `JWT_SECRET_KEY` | 默认值是公开的，不改＝任何人可伪造登录态。用 `python -c "import secrets;print(secrets.token_urlsafe(48))"` 生成 |
| `ADMIN_EMAILS` | 谁是管理员。留空则**没有人**能进管理后台 |
| `MAIL_*` | 不配则注册验证码发不出去（`REQUIRE_EMAIL_CODE=true` 时流程走不通） |
| `CORS_ORIGINS` | 换成你的实际域名。Docker 部署下前端 nginx 同源反代，通常可以不管 |
| `PUBLIC_BASE_URL` | 对外域名（协议 + 域名，不带路径）。邮件里的品牌标识只能靠绝对地址引用 |

**不要把 `.env` 提交进版本库**，也不要放进镜像 —— 根目录的 `.dockerignore` 已经把
`.env` / `*.key` / `*.db` 全部排除，但真正的责任在部署者。

**不要把 `DATABASE_URL` 留成空值**：空串会被当成一个真的连接串，SQLAlchemy 直接抛
`Could not parse SQLAlchemy URL` 让进程起不来。不需要改就把整行注释掉。

---

## 1. Docker Compose（推荐）

前置：Docker + Docker Compose v2。

```bash
# 1) 进项目根目录
cd agentflow

# 2) 准备环境变量（放根目录！）
cp .env.example .env
vi .env

# 3) 构建 + 启动（首次 5~15 分钟，主要是装 168 个 Python 包）
docker compose up -d --build

# 4) 看启动过程（迁移会自动执行，见下）
docker compose logs -f backend
```

访问入口：**前端 `http://服务器IP:3000`**。后端 8001 端口只为本地调试保留，
生产建议在 compose 里把 `ports:` 那段注释掉，只经前端 nginx 访问。

### 数据库迁移是自动的，不需要手工执行

容器入口脚本会先 `alembic upgrade head`、成功后再起 uvicorn，日志长这样：

```
[entrypoint] 数据库迁移完成，启动：uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers ...
Using SQLite database: /data/agentflow.db
Database initialized: File-based (persistent) -> /data/agentflow.db
Templates seeded
LLM config loaded: alias=.env source=env
Uvicorn running on http://0.0.0.0:8000
```

顺序不能反：应用启动时的 `init_db()` 用的是 `create_all`，它**只新建缺失的表、
不改已有表的列，而且不写 `alembic_version`**。新库若先被 `create_all` 建出来，
版本基线就是空的，之后 `alembic upgrade` 会因为「表已存在」失败，升级链再也接不上。

### 涉及哪些服务

| 服务 | 端口 | 说明 |
|:--|:--|:--|
| `frontend` | 3000 | nginx 托管静态产物，`/api` `/static` `/ws` 反代到后端 |
| `backend` | 8001→8000 | FastAPI（含迁移入口脚本） |
| `postgres` | 可选 | 只有 `--profile postgres` 才启动，见下 |
| `redis` | 可选 | 只有 `--profile redis` 才启动 |

没有 `celery-worker`：`app/celery_app.py` 在全项目里没有任何地方引用
（`.delay(` / `apply_async` / `shared_task` 都是 0 命中），原编排里的 worker 只是空转。

### 数据持久化

| 宿主目录 | 容器内 | 内容 |
|:--|:--|:--|
| `./data` | `/data` | **SQLite 数据库**（用户、Agent、对话、知识库记录） |
| `./skills` | `/repo/skills` | 技能（管理员在后台增删会直接写这里） |
| `./uploads` | `/repo/uploads` | 知识库原始文件、PiAgent 工作区 |
| `./static` | `/repo/static` | 头像、技能产物（Excel/PDF/PPT 下载） |
| `./config` | `/repo/config`（只读） | 静态模型目录 `models.json` |

**备份就是打包这五个目录**（`data/` 最关键）。

⚠️ compose 里的 `DATABASE_URL` 刻意**不用** `${DATABASE_URL}` 插值，而是读
`AGENTFLOW_DOCKER_DATABASE_URL`。因为 `.env` 是本地开发和 Docker 共用的一份，
而本地那份通常写着相对路径（`sqlite+aiosqlite:///./agentflow.db`）—— 插值会把
它原样带进容器，数据库落进容器可写层，接口全正常，直到 `docker compose down`
之后所有数据一起消失。

### 改了代码之后

```bash
docker compose up -d --build          # 有新迁移会自动执行，不用手工跑
docker compose logs --tail=50 backend
```

### 用 PostgreSQL（可选，未验证）

```bash
# 1) 放开 backend/requirements-docker.txt 末尾的 asyncpg / pgvector 注释
# 2) 在 .env 里加：
#    AGENTFLOW_DOCKER_DATABASE_URL=postgresql+asyncpg://agentflow:改密码@postgres:5432/agentflow
#    POSTGRES_PASSWORD=改密码
# 3) 启动时带上 profile
docker compose --profile postgres up -d --build
```

这条路径**没有经过验证**（默认的 SQLite 组合才是跑通的）。Redis 同理：
`docker compose --profile redis up -d`，并在 `.env` 里设
`AGENTFLOW_DOCKER_REDIS_URL=redis://redis:6379/0`。
单实例部署可以完全不启 Redis —— 验证码会退回进程内存，功能正常（启动日志会
显式警告，属于预期）。

### 构建时网络不通

Docker Hub 与 PyPI / npm 在国内都可能有连不上的情况，三个参数都可以覆盖。

`docker compose build` 的 `--build-arg` 会同时作用于两个镜像（求之不得：两者
都需要 `BASE_REGISTRY`）：

```bash
docker compose build --build-arg BASE_REGISTRY=docker.m.daocloud.io
docker compose up -d
```

pip 源和 npm 源是两个镜像各自用的参数，分别构建时才能分别指定：

```bash
docker build \
  --build-arg BASE_REGISTRY=docker.m.daocloud.io \
  --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
  -f backend/Dockerfile -t agentflow-backend:2.0.2 .

docker build \
  --build-arg BASE_REGISTRY=docker.m.daocloud.io \
  --build-arg NPM_REGISTRY=https://registry.npmmirror.com \
  -t agentflow-frontend:2.0.2 ./frontend
```

---

## 2. 裸机直跑（不用 Docker）

前置：Python 3.13（与 `requirements-docker.txt` 对齐）、Node 20+、
（可选）PostgreSQL + pgvector、Redis。

```bash
# ---- 后端 ----
cd backend
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements-docker.txt

cp ../.env.example .env && vi .env   # 裸机跑时 .env 放在 backend/ 下

alembic upgrade head                 # 建表 / 升级
uvicorn app.main:app --host 0.0.0.0 --port 8001 --workers 2

# ---- 前端 ----
cd ../frontend
npm ci
npm run build                        # 产物在 dist/
# 用 nginx 托管 dist/，并把 /api /static /ws 反代到 8001 —— 参考 frontend/nginx.conf
```

**裸机部署的两个坑**：

1. `AGENTFLOW_REPO_ROOT` 必须指向包含 `skills/`、`config/`、`static/` 的那一层
   （默认按 `backend/` 的上级推导）。目录结构变了就要在 `.env` 里显式设置，
   否则技能广场一个技能都加载不到。
2. **多 worker 下不要用 SQLite**。`--workers 2` 配 SQLite 会锁库；要么用
   PostgreSQL，要么把 worker 数降到 1。

---

## 3. 部署后自检

```bash
# 前端能拿到页面
curl -sI http://localhost:3000 | head -1

# 后端活着（经 nginx 反代）
curl -s http://localhost:3000/api/v1/billing/plans | head -c 200

# 未鉴权接口应当被拒（401 而不是 404/502 —— 后者说明反代没配通）
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000/api/v1/skills/plaza

# 数据库落在哪（必须是 /data/agentflow.db，不是 /app/…）
docker compose logs backend | grep "Using SQLite database"
```

再走一遍**真实用户流程**：注册 → 收验证码邮件 → 登录 → 建 Agent → 发消息。

`MAIL_ENABLED=false` 时不会真发信，验证码打印在后端日志里：

```bash
docker compose logs backend | grep -A3 "MAIL_ENABLED=false"
```

---

## 4. 常见问题

**构建时 `failed to resolve source metadata for docker.io/library/...`**
Docker Hub 连不上。用 `--build-arg BASE_REGISTRY=docker.m.daocloud.io`，或在
Docker Desktop 的 `daemon.json` 里配 `registry-mirrors`。

**前端页面白屏、控制台一堆 404**
`frontend/dist` 没构建出来（构建阶段 `tsc` 失败会直接中断 build），或 nginx 的
`try_files` 没生效。确认镜像里 `/usr/share/nginx/html/index.html` 存在。

**后端容器反复重启，日志写着 `error parsing value for field "XXX"`**
`.env` 里某个键的值类型不对。典型是 `CORS_ORIGINS` 这类列表字段 —— 逗号分隔和
JSON 数组两种写法都支持，但空值不行。

**注册时报 500**
看 `docker compose logs backend`。首次部署忘了迁移已经不可能（入口脚本会自动跑），
更可能是数据库目录不可写：`./data` 的属主/权限不对。

**邮件发不出去**
`MAIL_USE_SSL=true` 配 465；587/25 要改成 `false`（STARTTLS）。
QQ 邮箱 / 163 需要的是**授权码**而不是登录密码。

**管理后台入口看不到**
`ADMIN_EMAILS` 里要有当前登录账号的邮箱，且需要**重新登录**一次才会被授予角色。

**注册/发验证码报 422，说邮箱是「保留域名」**
`ADMIN_EMAILS` 与注册用的邮箱必须落在**真实存在的公共域名**上。
`admin@xxx.local`、`xxx.test`、`xxx.invalid` 这类保留 TLD 会被 email-validator
直接拒掉（422，提示 "special-use or reserved name"）—— 内网自测时很容易顺手
写成 `.local`，然后卡在「为什么注册不了」。

**上传大文件报 413**
nginx 的 `client_max_body_size` 太小。`frontend/nginx.conf` 里现在是 `300m`
（对应后端技能包上限 256MB），反代层如果还叠了云负载均衡，那边也要一起放开。

---

## 5. 安全清单（上生产前）

- [ ] `JWT_SECRET_KEY` 已换成随机值
- [ ] `DEBUG=false`（否则接口会把内部异常原文返回给调用方）
- [ ] `REQUIRE_EMAIL_CODE=true`
- [ ] 后端 8001 端口**不对公网开放**（compose 里默认映射了，生产请注释掉）
- [ ] PostgreSQL / Redis 不对公网开放（compose 默认就不映射它们的端口）
- [ ] `CORS_ORIGINS` 只含自己的域名
- [ ] 反向代理层（nginx / 云负载均衡）配了 HTTPS
- [ ] `.env` 权限收到 `600`
- [ ] 确认 `./data` 在备份计划里 —— 丢了它等于丢了所有用户和 Agent
