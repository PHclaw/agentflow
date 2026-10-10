"""
核心配置
"""
from pydantic import field_validator
from pydantic_settings import BaseSettings
from typing import Any, List
from functools import lru_cache


class Settings(BaseSettings):
    APP_NAME: str = "AgentFlow"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    
    # 数据库 - SQLite 备用方案
    DATABASE_URL: str = "sqlite+aiosqlite:///./agentflow.db"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # JWT
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7
    
    # LLM 配置
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-3-haiku"
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"

    # Skill 运行时（Model Lab 兼容）
    DASHSCOPE_API_KEY: str = ""
    MODEL_BASE_URL: str = ""
    CHATZOC_API_KEY: str = ""
    CHATZOC_BASE_URL: str = ""
    CHATZOC_AGENT_TYPE: str = "chatzoc_9b_B"
    DEFAULT_MODEL: str = ""
    OPTIMIZE_MODEL: str = ""
    SEMANTIC_SCHOLAR_API_KEY: str = ""
    
    # Embedding
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    
    # 大模型 API 配置热加载：生效配置的快照最多缓存多少秒
    # 同一进程内改完立即生效；多 worker 部署下最迟该秒数后一致
    LLM_CONFIG_CACHE_TTL_SECONDS: int = 5
    # 连接测试超时（秒）
    LLM_CONFIG_TEST_TIMEOUT: int = 20
    
    # PiAgent 运行时（可选引擎，参考 AlphaLens 的 piagent 实现）
    # 开启后可通过 /api/v1/pi/{agent_id}/stream 调用外部 agent CLI（pi）
    PIAGENT_ENABLED: bool = False
    PIAGENT_EXE: str = "pi"
    PIAGENT_TIMEOUT: int = 180
    # pi 默认 provider 是 google；这里可覆盖成 openai/anthropic 等与项目一致的厂商
    PIAGENT_PROVIDER: str = ""
    PIAGENT_MODEL: str = ""
    # 每个 Agent 一个独立工作区；留空则用 uploads/pi_workspace/<agent_id>
    PIAGENT_WORKSPACE_ROOT: str = ""
    # 技能目录；留空则用仓库根的 skills/
    PIAGENT_SKILLS_DIR: str = ""
    
    # CORS（支持逗号分隔字符串，便于 docker-compose 注入）
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        return v
    
    # 文件存储
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE: int = 50 * 1024 * 1024  # 50MB
    
    # 限制
    FREE_AGENTS: int = 1
    FREE_MESSAGES: int = 100
    PRO_AGENTS: int = 5
    PRO_MESSAGES: int = 5000
    
    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_FREE: str = ""
    STRIPE_PRICE_PRO: str = "price_pro_monthly"
    STRIPE_PRICE_TEAM: str = "price_team_monthly"
    
    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
