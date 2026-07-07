"""
速率限制中间件
基于 Redis 实现滑动窗口限流
"""
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Optional, Dict
import time
import hashlib


class RateLimiter:
    """速率限制器"""

    def __init__(self, redis_client=None):
        self.redis = redis_client
        self._memory_store: Dict[str, list] = {}  # 内存存储（无 Redis 时使用）

    def _get_key(self, identifier: str, path: str) -> str:
        """生成限流 key"""
        return f"rate_limit:{hashlib.md5(f'{identifier}:{path}'.encode()).hexdigest()}"

    async def is_allowed(
        self,
        identifier: str,
        path: str,
        max_requests: int = 100,
        window_seconds: int = 60
    ) -> tuple[bool, int]:
        """
        检查请求是否允许

        Returns:
            (是否允许，剩余请求数)
        """
        key = self._get_key(identifier, path)
        now = time.time()
        window_start = now - window_seconds

        if self.redis:
            # 使用 Redis
            pipe = self.redis.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zadd(key, {str(now): now})
            pipe.zcard(key)
            pipe.expire(key, window_seconds * 2)
            _, _, count, _ = pipe.execute()

            remaining = max(0, max_requests - count)
            return count <= max_requests, remaining
        else:
            # 使用内存存储
            if key not in self._memory_store:
                self._memory_store[key] = []

            # 清理过期记录
            self._memory_store[key] = [
                t for t in self._memory_store[key] if t > window_start
            ]

            # 添加当前请求
            self._memory_store[key].append(now)
            count = len(self._memory_store[key])

            remaining = max(0, max_requests - count)
            return count <= max_requests, remaining


# 全局速率限制器
_limiter: Optional[RateLimiter] = None


def get_limiter() -> RateLimiter:
    """获取速率限制器实例"""
    global _limiter
    if _limiter is None:
        _limiter = RateLimiter()
    return _limiter


class RateLimitMiddleware(BaseHTTPMiddleware):
    """速率限制中间件"""

    def __init__(
        self,
        app,
        max_requests: int = 100,
        window_seconds: int = 60,
        exclude_paths: list = None,
    ):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.exclude_paths = exclude_paths or ["/docs", "/redoc", "/openapi.json", "/health"]
        self.limiter = get_limiter()

    async def dispatch(self, request: Request, call_next):
        # 检查是否排除
        for path in self.exclude_paths:
            if request.url.path.startswith(path):
                return await call_next(request)

        # 获取客户端标识（IP 或用户 ID）
        identifier = self._get_identifier(request)

        # 检查限流
        allowed, remaining = await self.limiter.is_allowed(
            identifier,
            request.url.path,
            max_requests=self.max_requests,
            window_seconds=self.window_seconds,
        )

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "success": False,
                    "error": "Too Many Requests",
                    "message": "请求过于频繁，请稍后再试",
                    "retry_after": self.window_seconds,
                },
                headers={
                    "X-RateLimit-Limit": str(self.max_requests),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(time.time() + self.window_seconds)),
                }
            )

        # 继续处理请求
        response = await call_next(request)

        # 添加限流头
        response.headers["X-RateLimit-Limit"] = str(self.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(time.time() + self.window_seconds))

        return response

    def _get_identifier(self, request: Request) -> str:
        """获取客户端标识"""
        # 优先使用用户 ID（如果有认证）
        user_id = request.state.user_id if hasattr(request.state, 'user_id') else None
        if user_id:
            return f"user:{user_id}"

        # 使用 IP 地址
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
        else:
            ip = request.client.host if request.client else "unknown"

        return f"ip:{ip}"


def rate_limit(max_requests: int = 100, window_seconds: int = 60):
    """装饰器形式的速率限制"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # 这里需要获取 request 和 identifier
            # 实际使用中建议使用中间件形式
            return await func(*args, **kwargs)
        return wrapper
    return decorator
