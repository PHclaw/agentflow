"""
AgentFlow 整合 agent-* 库生态

Phase 1: agent-config-loader + agent-observability
"""
from typing import Optional, Dict, Any
from functools import wraps
import time

# agent-config-loader 整合
try:
    from agent_config_loader import ConfigLoader
    HAS_CONFIG_LOADER = True
except ImportError:
    HAS_CONFIG_LOADER = False
    ConfigLoader = None

# agent-observability 整合
try:
    from agent_observability import Tracer, Span, TokenUsage
    HAS_OBSERVABILITY = True
except ImportError:
    HAS_OBSERVABILITY = False
    Tracer = None


class AgentflowConfig:
    """
    整合 agent-config-loader 的配置管理
    
    支持多环境切换：
    - development (默认)
    - staging
    - production
    """
    
    _instance = None
    
    def __new__(cls, env: str = "development"):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init(env)
        return cls._instance
    
    def _init(self, env: str):
        self.env = env
        
        if HAS_CONFIG_LOADER:
            # 使用 agent-config-loader
            self._loader = ConfigLoader(
                config_dir="config",
                env=env,
                schema=self._get_schema()
            )
            self._config = self._loader.load()
        else:
            # 回退到原有配置
            from ..core.config import settings
            self._config = settings
    
    def _get_schema(self) -> Dict[str, Any]:
        """配置 schema 定义"""
        return {
            "type": "object",
            "properties": {
                "DATABASE_URL": {"type": "string"},
                "REDIS_URL": {"type": "string"},
                "OPENAI_API_KEY": {"type": "string"},
                "ANTHROPIC_API_KEY": {"type": "string"},
                "DEEPSEEK_API_KEY": {"type": "string"},
                "JWT_SECRET_KEY": {"type": "string"},
                "CORS_ORIGINS": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["DATABASE_URL", "JWT_SECRET_KEY"]
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        if HAS_CONFIG_LOADER:
            return self._config.get(key, default)
        else:
            return getattr(self._config, key.upper(), default)
    
    @property
    def database_url(self) -> str:
        return self.get("DATABASE_URL")
    
    @property
    def redis_url(self) -> str:
        return self.get("REDIS_URL")
    
    @property
    def openai_api_key(self) -> Optional[str]:
        return self.get("OPENAI_API_KEY")
    
    @property
    def anthropic_api_key(self) -> Optional[str]:
        return self.get("ANTHROPIC_API_KEY")


class AgentflowTracer:
    """
    整合 agent-observability 的追踪管理
    
    自动记录：
    - Agent 执行时间
    - Token 使用量
    - 错误和重试
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance
    
    def _init(self):
        if HAS_OBSERVABILITY:
            self._tracer = Tracer(
                service_name="agentflow",
                export_format="json"
            )
        else:
            self._tracer = None
        
        self._spans: Dict[str, Span] = {}
    
    def start_span(
        self,
        name: str,
        agent_id: str = None,
        session_id: str = None,
        **kwargs
    ) -> Optional[str]:
        """开始一个追踪 span"""
        if not HAS_OBSERVABILITY:
            return None
        
        span = self._tracer.start_span(
            name=name,
            attributes={
                "agent_id": agent_id,
                "session_id": session_id,
                **kwargs
            }
        )
        
        span_id = f"{name}_{time.time_ns()}"
        self._spans[span_id] = span
        return span_id
    
    def end_span(
        self,
        span_id: str,
        token_usage: Dict[str, int] = None,
        error: Exception = None
    ):
        """结束追踪 span"""
        if not HAS_OBSERVABILITY or span_id not in self._spans:
            return
        
        span = self._spans.pop(span_id)
        
        if token_usage:
            span.set_token_usage(
                TokenUsage(
                    prompt_tokens=token_usage.get("prompt", 0),
                    completion_tokens=token_usage.get("completion", 0),
                    total_tokens=token_usage.get("total", 0)
                )
            )
        
        if error:
            span.set_error(error)
        
        span.end()
    
    def trace_chat(self, func):
        """装饰器：自动追踪 chat 调用"""
        @wraps(func)
        async def wrapper(*args, **kwargs):
            span_id = self.start_span(
                name="chat",
                agent_id=kwargs.get("agent_id"),
                session_id=kwargs.get("session_id")
            )
            
            try:
                result = await func(*args, **kwargs)
                
                # 尝试提取 token 使用量
                if hasattr(result, "usage"):
                    self.end_span(span_id, token_usage={
                        "prompt": result.usage.prompt_tokens,
                        "completion": result.usage.completion_tokens,
                        "total": result.usage.total_tokens
                    })
                else:
                    self.end_span(span_id)
                
                return result
            except Exception as e:
                self.end_span(span_id, error=e)
                raise
        
        return wrapper
    
    def get_stats(self) -> Dict[str, Any]:
        """获取追踪统计"""
        if not HAS_OBSERVABILITY:
            return {"enabled": False}
        
        return {
            "enabled": True,
            "active_spans": len(self._spans),
            "tracer": self._tracer.export()
        }


# 全局实例
config = AgentflowConfig()
tracer = AgentflowTracer()
