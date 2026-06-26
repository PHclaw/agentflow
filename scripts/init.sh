#!/usr/bin/env bash
# AgentFlow 一键初始化脚本
# 用法: bash scripts/init.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  AgentFlow 初始化脚本"
echo -e "${GREEN}========================================${NC}"
echo ""

# 检查 Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}✗ Docker 未安装，请先安装 Docker${NC}"
    echo "  安装指南: https://docs.docker.com/engine/install/"
    exit 1
fi
echo -e "${GREEN}✓${NC} Docker 已安装"

# 检查 Docker Compose
if ! docker compose version &> /dev/null; then
    echo -e "${RED}✗ Docker Compose 未安装${NC}"
    exit 1
fi
echo -e "${GREEN}✓${NC} Docker Compose 已安装"
echo ""

# 创建 .env
if [ ! -f .env ]; then
    if [ ! -f .env.example ]; then
        echo -e "${RED}✗ .env.example 不存在${NC}"
        exit 1
    fi
    cp .env.example .env
    echo -e "${GREEN}✓${NC} 已创建 .env（请编辑填入 API Keys）"
else
    echo -e "${YELLOW}•${NC} .env 已存在，跳过创建"
fi
echo ""

# 提示用户编辑 .env
echo -e "${YELLOW}请确认 .env 配置：${NC}"
echo "  必填项："
echo "    - OPENAI_API_KEY 或 ANTHROPIC_API_KEY 或 DEEPSEEK_API_KEY"
echo "    - JWT_SECRET_KEY（生产环境务必更换）"
echo "    - DATABASE_URL（如使用外部数据库）"
echo ""
read -p "按 Enter 继续，或 Ctrl+C 退出编辑 .env ..."
echo ""

# 启动 Docker 服务
echo -e "${GREEN}正在启动 Docker 服务...${NC}"
docker compose up -d
echo -e "${GREEN}✓${NC} Docker 服务已启动"
echo ""

# 等待数据库就绪
echo "等待数据库就绪..."
sleep 5

# 数据库迁移（如需要）
echo -e "${GREEN}正在初始化数据库...${NC}"
docker compose exec -T backend alembic upgrade head 2>/dev/null || echo -e "${YELLOW}•${NC} 数据库已是最新版本（或 alembic 未配置）"
echo ""

# 播种模板数据
echo -e "${GREEN}正在播种模板数据...${NC}"
docker compose exec -T backend python -c "from app.core.seed import seed_templates; import asyncio; asyncio.run(seed_templates(None))" 2>/dev/null || true
echo ""

# 完成
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  🎉 AgentFlow 初始化完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "  访问地址："
echo "    - 前端:    http://localhost:3000"
echo "    - 后端 API: http://localhost:8001"
echo "    - API 文档: http://localhost:8001/docs"
echo ""
echo "  查看日志："
echo "    docker compose logs -f [service]"
echo ""
echo "  停止服务："
echo "    docker compose down"
echo ""
echo -e "${YELLOW}提示：首次使用请注册账号，第一个注册的用户自动成为管理员${NC}"
