# 开发指南

> 本页由 README 拆分而来，内容与代码同步维护。返回 [README](../README.md)。

```bash
# 示例：用代码生成一份《人工智能介绍》PPT（依赖 python-pptx）
python examples/generate_ai_ppt.py -o 人工智能介绍.pptx

# 后端测试 + 覆盖率
cd backend && pytest tests/ -v --cov=app

# 前端类型检查
cd frontend && npm run typecheck

# 对话页 UI 冒烟测试（Edge headless，零依赖；需前后端已在运行）
node scripts/ui-smoke.mjs <agent_id> ["可选的消息内容"]

# 前端全路由诊断：逐页收集控制台错误 / 异常 / 失败请求 / 异常跳转，并截图
node scripts/ui-diagnose.mjs
node scripts/ui-diagnose.mjs --only=settings,knowledge   # 只看指定页面

# 前端交互诊断：逐个点击按钮/标签，找出报错与「点了没反应」的无效按钮
node scripts/ui-interact.mjs --only=settings --max=8

# 数据库迁移（backend 目录下执行，连接串取自 .env）
alembic upgrade head                     # 新库建表
alembic revision --autogenerate -m "desc"  # 改完模型后生成迁移
alembic stamp head                       # 已有库标记为基线
alembic current                          # 查看当前版本
```

> **迁移与 `create_all` 的关系**：应用启动时仍会用 `create_all` 建缺失的表，
> 这只适合本地开发和测试。**对已存在的库做结构变更必须走 Alembic 迁移**，
> 因为 `create_all` 不会修改已有表的列或约束。

> **UI 诊断脚本不用装 Playwright/Puppeteer**：直接驱动系统自带 Edge 的 headless
> 模式（CDP），零第三方依赖。`ui-diagnose` 逐页收集控制台错误、未捕获异常、
> 失败请求与异常跳转；`ui-interact` 进一步逐个点击按钮，能发现「点了没反应」的
> 死按钮。截图与报告输出到 `%TEMP%/af-diag-shots`（交互诊断在 `af-interact-shots`）。
