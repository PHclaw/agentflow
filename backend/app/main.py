"""
AgentFlow - AI Agent 部署平台
生产级架构，支持 WebSocket、缓存、监控、日志
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import time

from app.core.config import settings
from app.core.database import init_db
from app.core.logging import setup_logging, logger
from app.core.monitoring import metrics_middleware, router as monitoring_router
from app.core.websocket import router as websocket_router
from app.api import auth, users, agents, templates, chat, billing
from app.api.knowledge import router as knowledge_api_router
from app.api.workflow import router as workflow_router
from app.api.agent_routes import router as agent_routes_router

# 导入模型以便创建表
from app.models import user, agent, subscription, document

# 初始化日志
setup_logging(level=settings.LOG_LEVEL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    logger.info("AgentFlow starting...")
    
    # 启动时初始化数据库
    await init_db()
    logger.info("Database initialized")
    
    yield
    
    # 关闭时清理资源
    logger.info("AgentFlow shutting down...")


app = FastAPI(
    title="AgentFlow API",
    description="🚀 AI Agent 部署平台 | 可视化工作流 | RAG 知识库 | 多模型集成",
    version="2.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 请求日志中间件
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """记录所有请求"""
    start_time = time.time()
    
    # 处理请求
    response = await call_next(request)
    
    # 计算耗时
    duration_ms = (time.time() - start_time) * 1000
    
    # 记录日志
    logger.info(
        f"{request.method} {request.url.path} - {response.status_code} - {duration_ms:.2f}ms"
    )
    
    # 添加响应头
    response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"
    response.headers["X-Service"] = "AgentFlow"
    
    return response


# 注册路由
app.include_router(auth.router, prefix="/api/v1/auth", tags=["认证"])
app.include_router(users.router, prefix="/api/v1/users", tags=["用户"])
app.include_router(agent_routes_router, prefix="/api/v1/agents", tags=["Agent-增强"])
app.include_router(agents.router, prefix="/api/v1/agents", tags=["Agent"])
app.include_router(templates.router, prefix="/api/v1/templates", tags=["模板"])
app.include_router(knowledge_api_router, tags=["知识库"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["对话"])
app.include_router(billing.router, tags=["支付"])
app.include_router(workflow_router, tags=["工作流"])

# WebSocket 路由
app.include_router(websocket_router, prefix="/ws", tags=["WebSocket"])

# 监控路由
app.include_router(monitoring_router, prefix="/api/v1/monitoring", tags=["监控"])


@app.get("/")
async def root():
    """根路径"""
    return {
        "name": "AgentFlow API",
        "version": "2.1.0",
        "docs": "/docs",
        "health": "/api/v1/monitoring/health",
        "features": [
            "AI Agent 可视化编排",
            "RAG 知识库检索",
            "多模型集成 (OpenAI/Claude/DeepSeek)",
            "实时 WebSocket 通信",
            "工作流版本控制",
        ]
    }


@app.get("/health")
async def health():
    """健康检查"""
    return {
        "status": "healthy",
        "service": "AgentFlow",
        "version": "2.1.0",
        "timestamp": time.time()
    }


# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理"""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": str(exc) if settings.DEBUG else "An error occurred",
            "path": request.url.path
        }
    )


# 404 处理
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return JSONResponse(
        status_code=404,
        content={
            "error": "Not Found",
            "message": f"Route {request.url.path} not found",
            "path": request.url.path
        }
    )
