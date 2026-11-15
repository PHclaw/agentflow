# 贡献指南 / Contributing

欢迎Issue、文档修正和代码贡献。本仓库只含**可运行核心**，不含演示录屏、内部规划文档、用户数据或第三方技能。

## 环境要求

- Python 3.11+（已在 3.13 验证）
- Node.js 18+（已在 25 验证）
- 可选：Docker + Docker Compose

## 本地启动

```bash
# 后端（SQLite 轻量模式，无需 PostgreSQL / Redis / torch）
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements-lite.txt   # Windows
# .venv/bin/pip install -r requirements-lite.txt     # macOS / Linux
cp .env.example .env                                # 至少改 JWT_SECRET_KEY
.venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8001

# 前端（另开一个终端）
cd frontend
npm install
npm run dev                                          # http://localhost:5173
```

`vite.config.ts` 把 `/api` 与 `/static` 代理到 `127.0.0.1:8001`，因此后端端口需保持 8001。
全新空数据库可以正常启动：`init_db()` 会自动建表并写入模板种子数据，无需导入任何 `.db` 文件。

也可以直接 `cp .env.example .env && docker compose up -d --build`，前端在 `http://localhost:3000`。

## 关于 skills/

克隆下来后 `skills/` 是空的，这是**预期行为**，不是缺文件：服务启动不依赖任何技能，空目录时技能广场返回空列表，其余功能不受影响。第三方技能不随本仓库分发，原因见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)；安装方法见 [skills/README.md](skills/README.md)。

## 提交前检查

```bash
cd backend  && ruff check app/ && python -m pytest tests/ -v
cd frontend && npx tsc --noEmit && npm run build
```

新增/修改 API 时，请同步更新 `docs/API.md`；行为变更请在 `docs/CHANGELOG.md` 留一条记录。

## PR 流程

Issue → Fork → 分支 → 开发 → 测试 → PR → Review → Merge

- 分支名建议 `feat/xxx`、`fix/xxx`、`docs/xxx`
- 一个 PR 只做一件事，附上验证方式与截图（涉及 UI 时）
- 不要提交 `.env`、`*.db`、`*.log`、`uploads/`、`static/generated/`、`recordings/` 或任何真实密钥与用户数据
- 不要把第三方技能目录提交进仓库（`.gitignore` 已忽略 `skills/*/`）

## 行为准则

就事论事、友善沟通；不欢迎人身攻击、骚扰或任何形式的歧视。

安全问题请**不要**开公开 Issue，按 [SECURITY.md](SECURITY.md) 私下报告。
