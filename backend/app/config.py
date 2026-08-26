"""Skill 运行时配置桥接（兼容 Model Lab 的 get_settings 接口）。"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.config import settings as core


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    dashscope_api_key: str = ""
    model_base_url: str = ""
    chatzoc_api_key: str = ""
    chatzoc_base_url: str = ""
    chatzoc_agent_type: str = "chatzoc_9b_B"
    default_model: str = "gpt-4o-mini"
    optimize_model: str = "gpt-4o-mini"

    openai_timeout_seconds: float = 120.0
    openai_connect_timeout_seconds: float = 30.0
    openai_max_retries: int = 2

    log_dir: str = "logs"
    log_level: str = "INFO"
    log_retention_days: int = 30
    log_to_console: bool = True

    semantic_scholar_api_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings(
        dashscope_api_key=core.DASHSCOPE_API_KEY or core.OPENAI_API_KEY,
        model_base_url=core.MODEL_BASE_URL or core.DEEPSEEK_BASE_URL,
        chatzoc_api_key=core.CHATZOC_API_KEY or core.DASHSCOPE_API_KEY or core.OPENAI_API_KEY,
        chatzoc_base_url=core.CHATZOC_BASE_URL or core.MODEL_BASE_URL or core.DEEPSEEK_BASE_URL,
        chatzoc_agent_type=core.CHATZOC_AGENT_TYPE,
        default_model=core.DEFAULT_MODEL or core.OPENAI_MODEL or "gpt-4o-mini",
        optimize_model=core.OPTIMIZE_MODEL or core.DEFAULT_MODEL or core.OPENAI_MODEL or "gpt-4o-mini",
        log_level=core.LOG_LEVEL,
        semantic_scholar_api_key=core.SEMANTIC_SCHOLAR_API_KEY,
    )


def reload_settings() -> Settings:
    get_settings.cache_clear()
    try:
        from app.services.adapters.openai_compatible import clear_client_cache

        clear_client_cache()
    except Exception:  # noqa: BLE001
        pass
    return get_settings()
