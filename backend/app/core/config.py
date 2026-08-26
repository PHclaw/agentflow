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
