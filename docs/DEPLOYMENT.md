# AgentFlow 部署指南

## 快速部署

### Railway（推荐）

Railway 支持全栈部署，包含数据库和 Redis。

1. **Fork 仓库**
   ```bash
   git clone https://github.com/your-username/agentflow.git
   cd agentflow
   ```

2. **创建 Railway 项目**
   - 访问 https://railway.app
   - 点击 "New Project" → "Deploy from GitHub repo"
   - 选择你的 AgentFlow 仓库

3. **添加服务**
   - PostgreSQL 数据库
   - Redis
   - 后端服务（从 backend/Dockerfile）
   - 前端服务（从 frontend/Dockerfile）

4. **配置环境变量**
   ```
   DATABASE_URL=${{Postgres.DATABASE_URL}}
   REDIS_URL=${{Redis.REDIS_URL}}
   OPENAI_API_KEY=sk-xxx
   JWT_SECRET_KEY=your-secret-key
   STRIPE_SECRET_KEY=sk_test_xxx
   STRIPE_WEBHOOK_SECRET=whsec_xxx
   ```

5. **部署**
   ```bash
   railway up
   ```

### Vercel（仅前端）

前端可单独部署到 Vercel：

```bash
cd frontend
vercel
```

环境变量配置：
```
VITE_API_URL=https://your-backend-url.com
```

## Docker Compose（自建）

```bash
# 克隆仓库
git clone https://github.com/PHclaw/agentflow.git
cd agentflow

# 配置环境变量
cp backend/.env.example backend/.env
# 编辑 .env 文件

# 启动服务
docker-compose up -d

# 访问
open http://localhost:8080
```

## 环境变量

### 必需

| 变量 | 说明 | 示例 |
|-----|-----|-----|
| DATABASE_URL | PostgreSQL 连接 | postgresql://user:pass@host:5432/db |
| JWT_SECRET_KEY | JWT 密钥 | 随机32字符字符串 |
| OPENAI_API_KEY | OpenAI API | sk-xxx |

### 可选

| 变量 | 说明 | 默认值 |
|-----|-----|-------|
| REDIS_URL | Redis 连接 | redis://localhost:6379/0 |
| STRIPE_SECRET_KEY | Stripe 支付 | - |
| STRIPE_WEBHOOK_SECRET | Stripe Webhook | - |
| CORS_ORIGINS | 允许的源 | http://localhost:3000 |

## Stripe 配置

1. **创建 Stripe 账号**
   - 访问 https://dashboard.stripe.com

2. **创建产品和价格**
   ```
   Products → Add Product
   - Pro: ¥29/月
   - Team: ¥99/月
   ```

3. **获取 API 密钥**
   ```
   Developers → API Keys
   - Publishable key (前端)
   - Secret key (后端)
   ```

4. **配置 Webhook**
   ```
   Developers → Webhooks → Add endpoint
   - URL: https://your-domain.com/api/billing/webhook
   - Events: checkout.session.completed, customer.subscription.*
   ```

## 数据库迁移

```bash
# 生成迁移
alembic revision --autogenerate -m "initial"

# 执行迁移
alembic upgrade head
```

## 监控

内置 Prometheus metrics：

```
GET /metrics
```

推荐监控方案：
- **Uptime**: UptimeRobot / Pingdom
- **Logs**: Logflare / Papertrail
- **Errors**: Sentry
- **Analytics**: Plausible / Umami

## 常见问题

**Q: 部署后前端无法连接后端？**
A: 检查 CORS_ORIGINS 配置，确保包含前端域名。

**Q: Stripe webhook 验证失败？**
A: 检查 STRIPE_WEBHOOK_SECRET 是否正确配置。

**Q: 数据库连接失败？**
A: 检查 DATABASE_URL 格式，确保数据库已启动。
