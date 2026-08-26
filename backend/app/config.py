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
    s = Settings()
    if not s.dashscope_api_key and core.OPENAI_API_KEY:
        s.dashscope_api_key = core.OPENAI_API_KEY
    if not s.model_base_url and core.DEEPSEEK_API_KEY:
        s.model_base_url = core.DEEPSEEK_BASE_URL
    if not s.chatzoc_api_key:
        s.chatzoc_api_key = s.dashscope_api_key
    if not s.chatzoc_base_url and s.model_base_url:
        s.chatzoc_base_url = s.model_base_url
    if not s.default_model or s.default_model == "chatzoc_9b_B":
        if core.OPENAI_API_KEY:
            s.default_model = core.OPENAI_MODEL or "gpt-4o-mini"
    if not s.optimize_model or s.optimize_model == "chatzoc_9b_B":
        s.optimize_model = s.default_model
    s.log_level = core.LOG_LEVEL or s.log_level
    return s


def reload_settings() -> Settings:
    get_settings.cache_clear()
    try:
        from app.services.adapters.openai_compatible import clear_client_cache

        clear_client_cache()
    except Exception:  # noqa: BLE001
        pass
    return get_settings()
