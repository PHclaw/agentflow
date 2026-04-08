"""
AgentFlow - AI Agent 部署平台
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.database import engine, Base
from app.api import auth, users, agents, templates, knowledge, chat, billing


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # 关闭时
    await engine.dispose()


app = FastAPI(
    title="AgentFlow API",
    description="AI Agent 部署平台 API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 路由
app.include_router(auth.router, prefix="/api/v1/auth", tags=["认证"])
app.include_router(users.router, prefix="/api/v1/users", tags=["用户"])
app.include_router(agents.router, prefix="/api/v1/agents", tags=["Agent"])
app.include_router(templates.router, prefix="/api/v1/templates", tags=["模板"])
app.include_router(knowledge.router, prefix="/api/v1/knowledge", tags=["知识库"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["对话"])
app.include_router(billing.router, tags=["支付"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "AgentFlow"}


@app.get("/")
async def root():
    return {"message": "AgentFlow API", "docs": "/docs"}
