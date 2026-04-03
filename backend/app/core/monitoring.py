"""
监控和日志
"""
import logging
from datetime import datetime
from typing import Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import time

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("agentflow")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """请求日志中间件"""
    
    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.time()
        
        # 记录请求
        logger.info(f"Request: {request.method} {request.url.path}")
        
        response = await call_next(request)
        
        # 记录响应
        duration = time.time() - start_time
        logger.info(
            f"Response: {request.method} {request.url.path} "
            f"- Status: {response.status_code} - Duration: {duration:.3f}s"
        )
        
        return response


class MetricsCollector:
    """指标收集器"""
    
    def __init__(self):
        self.requests = 0
        self.errors = 0
        self.total_duration = 0.0
        self.start_time = datetime.utcnow()
    
    def record_request(self, duration: float, success: bool = True):
        self.requests += 1
        self.total_duration += duration
        if not success:
            self.errors += 1
    
    def get_stats(self) -> dict:
        avg_duration = (
            self.total_duration / self.requests if self.requests > 0 else 0
        )
        error_rate = self.errors / self.requests if self.requests > 0 else 0
        
        return {
            "total_requests": self.requests,
            "total_errors": self.errors,
            "error_rate": error_rate,
            "avg_duration_ms": avg_duration * 1000,
            "uptime_seconds": (datetime.utcnow() - self.start_time).total_seconds(),
        }


# 全局指标收集器
metrics = MetricsCollector()
