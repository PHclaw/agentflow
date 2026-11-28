# 贡献指南 / Contributing

欢迎 Issue、文档修正和代码贡献。仓库包含完整应用代码、界面截图与演示素材，以及 `skills/` 下的 28 个技能目录；不含任何用户数据。第三方技能的许可与归属见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

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

`skills/` 下自带 28 个技能目录，服务启动时扫描加载，删除某个目录即等于下线该技能（广场随之不再显示）。

这些技能来自不同社区，**许可证各不相同**（Apache-2.0 / MIT / 无声明 / 保留所有权利），不能整体按本仓库协议再分发。归属与许可见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)；格式说明见 [skills/README.md](skills/README.md)。

新增技能不需要改代码：建一个目录，放入 `SKILL.md`（含 frontmatter 与正文说明），重启后端即可在广场看到。

## 第一次贡献从哪里开始

不确定能做什么时，按这个顺序找：

1. 带 [`good first issue`](https://github.com/PHclaw/agentflow/labels/good%20first%20issue) 标签的 issue —— 都是「不需要读完整代码库、改几行或加一个目录」就能完成的
2. 带 `documentation` 标签的 —— 文档错别字、命令跑不通、截图过期
3. 自己想加的技能（[#19](https://github.com/PHclaw/agentflow/issues/19) 就是一个模板）

领了 issue 之后在下面留一句话说明你在做，避免和别人撞车。卡住了直接问，不要憋着。

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
