"""缓存层 - Redis/内存缓存"""
import json
import hashlib
from typing import Any, Optional, Callable
from datetime import datetime, timedelta
from functools import wraps
import asyncio

# 简单的内存缓存实现（生产环境应使用 Redis）
class MemoryCache:
    """内存缓存"""
    
    def __init__(self):
        self._cache: dict = {}
        self._expiry: dict = {}
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        if key in self._cache:
            # 检查过期
            if key in self._expiry and datetime.now() > self._expiry[key]:
                del self._cache[key]
                del self._expiry[key]
                return None
            return self._cache[key]
        return None
    
    def set(self, key: str, value: Any, ttl: int = 300):
        """设置缓存"""
        self._cache[key] = value
        if ttl > 0:
            self._expiry[key] = datetime.now() + timedelta(seconds=ttl)
        else:
            # 永不过期
            if key in self._expiry:
                del self._expiry[key]
    
    def delete(self, key: str):
        """删除缓存"""
        if key in self._cache:
            del self._cache[key]
        if key in self._expiry:
            del self._expiry[key]
    
    def clear(self, pattern: str = None):
        """清除缓存"""
        if pattern:
            keys_to_delete = [k for k in self._cache.keys() if pattern in k]
            for key in keys_to_delete:
                self.delete(key)
        else:
            self._cache.clear()
            self._expiry.clear()
    
    def exists(self, key: str) -> bool:
        """检查键是否存在"""
        return self.get(key) is not None


# 全局缓存实例
cache = MemoryCache()


def generate_cache_key(prefix: str, **kwargs) -> str:
    """生成缓存键"""
    # 按键名排序确保一致性
    sorted_items = sorted(kwargs.items())
    key_str = json.dumps(sorted_items, sort_keys=True)
    key_hash = hashlib.md5(key_str.encode()).hexdigest()[:12]
    return f"{prefix}:{key_hash}"


def cached(ttl: int = 300, prefix: str = "default"):
    """缓存装饰器"""
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # 生成缓存键
            cache_key = generate_cache_key(
                f"{prefix}:{func.__name__}",
                args=str(args),
                kwargs=kwargs
            )
            
            # 尝试从缓存获取
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # 执行函数
            result = await func(*args, **kwargs)
            
            # 存入缓存
            cache.set(cache_key, result, ttl)
            
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            cache_key = generate_cache_key(
                f"{prefix}:{func.__name__}",
                args=str(args),
                kwargs=kwargs
            )
            
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl)
            
            return result
        
        # 根据函数类型返回对应包装器
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


class RateLimiter:
    """简单的速率限制器"""
    
    def __init__(self):
        self._requests: dict = {}
        self._windows: dict = {}
    
    def check(self, key: str, max_requests: int = 60, window_seconds: int = 60) -> bool:
        """
        检查是否超过限制
        返回 True 表示允许，False 表示被限制
        """
        now = datetime.now()
        
        if key not in self._requests:
            self._requests[key] = []
            self._windows[key] = now
        
        # 检查是否需要重置窗口
        if (now - self._windows[key]).total_seconds() > window_seconds:
            self._requests[key] = []
            self._windows[key] = now
        
        # 检查请求数
        if len(self._requests[key]) >= max_requests:
            return False
        
        # 记录请求
        self._requests[key].append(now)
        return True
    
    def get_remaining(self, key: str, max_requests: int = 60) -> int:
        """获取剩余请求数"""
        return max(0, max_requests - len(self._requests.get(key, [])))


# 全局速率限制器
rate_limiter = RateLimiter()


def rate_limit(max_requests: int = 60, window_seconds: int = 60, key_func: Callable = None):
    """
    速率限制装饰器
    key_func: 生成限制键的函数，默认为 IP 地址
    """
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(request, *args, **kwargs):
            # 生成限制键
            if key_func:
                limit_key = key_func(request)
            else:
                # 默认使用客户端 IP
                limit_key = request.client.host if request.client else "unknown"
            
            if not rate_limiter.check(limit_key, max_requests, window_seconds):
                from fastapi import HTTPException
                raise HTTPException(
                    status_code=429,
                    detail="请求过于频繁，请稍后再试"
                )
            
            return await func(request, *args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator
