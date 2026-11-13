## 这个 PR 做了什么

<!-- 一句话概括；如果是修 Bug，写明修的是哪个 issue -->

Closes #

## 改动类型

- [ ] 修复 Bug
- [ ] 新功能
- [ ] 文档
- [ ] 重构（不改变行为）
- [ ] 依赖 / 构建调整

## 怎么验证的

<!-- 写清楚复现路径，reviewer 才不用猜 -->

1.
2.

## 自检

- [ ] 后端：`cd backend && ruff check app/ && python -m pytest tests/ -v`
- [ ] 前端：`cd frontend && npx tsc --noEmit && npm run build`
- [ ] 涉及界面改动时，附了截图或录屏
- [ ] 涉及配置项时，同步更新了 `.env.example` 与 `docs/CONFIGURATION.md`

## 有 breaking change 吗

<!-- 有的话说明影响范围与迁移方式 -->
