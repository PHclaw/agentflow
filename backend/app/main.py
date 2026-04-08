"""
AgentFlow - AI Agent 部署平台
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.database import init_db
from app.api import auth, users, agents, templates, knowledge, chat, billing

# 导入模型以便创建表
from app.models import user, agent, subscription, document


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    # 启动时初始化数据库
    await init_db()
    yield
    # 关闭时清理资源


app = FastAPI(
    title="AgentFlow API",
    description="AI Agent 部署平台 API",
    version="1.2.0",
    lifespan=lifespan,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router, prefix="/api/v1/auth", tags=["认证"])
app.include_router(users.router, prefix="/api/v1/users", tags=["用户"])
app.include_router(agents.router, prefix="/api/v1/agents", tags=["Agent"])
app.include_router(templates.router, prefix="/api/v1/templates", tags=["模板"])
app.include_router(knowledge.router, tags=["知识库"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["对话"])
app.include_router(billing.router, tags=["支付"])


@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "ok", "service": "AgentFlow", "version": "1.2.0"}


@app.get("/")
async def root():
    """根路径"""
    return {"message": "AgentFlow API", "docs": "/docs", "version": "1.2.0"}
