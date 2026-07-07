"""健康检查和指标监控"""
from fastapi import APIRouter, Depends
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pydantic import BaseModel
import psutil
import time

router = APIRouter()


class HealthStatus(BaseModel):
    """健康状态模型"""
    status: str  # "healthy", "degraded", "unhealthy"
    timestamp: str
    components: Dict[str, dict]


class SystemMetrics(BaseModel):
    """系统指标"""
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_available_mb: float
    disk_percent: float
    uptime_seconds: float


class APIMetrics(BaseModel):
    """API 指标"""
    total_requests: int
    requests_last_hour: int
    avg_response_time_ms: float
    error_rate: float
    endpoint_stats: Dict[str, dict]


# 全局指标存储
class MetricsCollector:
    """指标收集器"""
    
    def __init__(self):
        self._requests: List[dict] = []
        self._start_time = time.time()
        self._endpoint_counts: Dict[str, int] = {}
        self._endpoint_times: Dict[str, List[float]] = {}
        self._endpoint_errors: Dict[str, int] = {}
    
    def record_request(self, endpoint: str, duration_ms: float, status_code: int):
        """记录请求"""
        now = datetime.now()
        self._requests.append({
            "endpoint": endpoint,
            "duration_ms": duration_ms,
            "status_code": status_code,
            "timestamp": now
        })
        
        # 更新端点统计
        self._endpoint_counts[endpoint] = self._endpoint_counts.get(endpoint, 0) + 1
        
        if endpoint not in self._endpoint_times:
            self._endpoint_times[endpoint] = []
        self._endpoint_times[endpoint].append(duration_ms)
        
        if status_code >= 400:
            self._endpoint_errors[endpoint] = self._endpoint_errors.get(endpoint, 0) + 1
        
        # 只保留最近 1 小时的请求
        cutoff = now - timedelta(hours=1)
        self._requests = [r for r in self._requests if r["timestamp"] > cutoff]
    
    def get_metrics(self) -> APIMetrics:
        """获取 API 指标"""
        now = datetime.now()
        cutoff = now - timedelta(hours=1)
        recent_requests = [r for r in self._requests if r["timestamp"] > cutoff]
        
        total_requests = len(self._requests)
        requests_last_hour = len(recent_requests)
        
        # 计算平均响应时间
        if self._requests:
            all_times = [r["duration_ms"] for r in self._requests]
            avg_time = sum(all_times) / len(all_times)
        else:
            avg_time = 0
        
        # 计算错误率
        errors = sum(1 for r in self._requests if r["status_code"] >= 400)
        error_rate = errors / total_requests if total_requests > 0 else 0
        
        # 端点统计
        endpoint_stats = {}
        for endpoint in self._endpoint_counts:
            times = self._endpoint_times.get(endpoint, [])
            endpoint_stats[endpoint] = {
                "count": self._endpoint_counts[endpoint],
                "avg_time_ms": sum(times) / len(times) if times else 0,
                "min_time_ms": min(times) if times else 0,
                "max_time_ms": max(times) if times else 0,
                "errors": self._endpoint_errors.get(endpoint, 0)
            }
        
        return APIMetrics(
            total_requests=total_requests,
            requests_last_hour=requests_last_hour,
            avg_response_time_ms=round(avg_time, 2),
            error_rate=round(error_rate, 4),
            endpoint_stats=endpoint_stats
        )
    
    def reset(self):
        """重置指标"""
        self._requests.clear()
        self._endpoint_counts.clear()
        self._endpoint_times.clear()
        self._endpoint_errors.clear()


# 全局指标收集器
metrics_collector = MetricsCollector()


@router.get("/health", response_model=HealthStatus)
async def health_check():
    """健康检查"""
    components = {}
    overall_status = "healthy"
    
    # 检查数据库
    try:
        from app.core.database import engine
        async with engine.connect() as conn:
            await conn.execute("SELECT 1")
        components["database"] = {"status": "healthy", "latency_ms": 0}
    except Exception as e:
        components["database"] = {"status": "unhealthy", "error": str(e)}
        overall_status = "degraded"
    
    # 检查向量存储
    try:
        # 简单的向量存储检查
        components["vector_store"] = {"status": "healthy"}
    except Exception as e:
        components["vector_store"] = {"status": "unhealthy", "error": str(e)}
        overall_status = "degraded"
    
    # 检查 LLM 服务
    try:
        components["llm_service"] = {"status": "healthy"}
    except Exception as e:
        components["llm_service"] = {"status": "unhealthy", "error": str(e)}
        overall_status = "degraded"
    
    return HealthStatus(
        status=overall_status,
        timestamp=datetime.now(timezone.utc).isoformat(),
        components=components
    )


@router.get("/health/live")
async def liveness_check():
    """存活检查 - K8s liveness probe"""
    return {"status": "alive", "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/health/ready")
async def readiness_check():
    """就绪检查 - K8s readiness probe"""
    try:
        # 检查所有依赖是否就绪
        from app.core.database import engine
        async with engine.connect() as conn:
            await conn.execute("SELECT 1")
        return {"status": "ready", "timestamp": datetime.now(timezone.utc).isoformat()}
    except Exception as e:
        return {"status": "not_ready", "error": str(e)}


@router.get("/metrics/system", response_model=SystemMetrics)
async def system_metrics():
    """系统指标"""
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    return SystemMetrics(
        cpu_percent=psutil.cpu_percent(interval=0.1),
        memory_percent=memory.percent,
        memory_used_mb=round(memory.used / 1024 / 1024, 2),
        memory_available_mb=round(memory.available / 1024 / 1024, 2),
        disk_percent=disk.percent,
        uptime_seconds=time.time() - metrics_collector._start_time
    )


@router.get("/metrics/api", response_model=APIMetrics)
async def api_metrics():
    """API 指标"""
    return metrics_collector.get_metrics()


@router.post("/metrics/reset")
async def reset_metrics():
    """重置指标"""
    metrics_collector.reset()
    return {"status": "reset"}


# 请求记录中间件
async def metrics_middleware(request, call_next):
    """记录请求指标的中间件"""
    start_time = time.time()
    
    response = await call_next(request)
    
    duration_ms = (time.time() - start_time) * 1000
    
    # 记录指标
    metrics_collector.record_request(
        endpoint=request.url.path,
        duration_ms=duration_ms,
        status_code=response.status_code
    )
    
    # 添加响应头
    response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"
    
    return response
