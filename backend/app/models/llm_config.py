"""大模型 API 配置模型。

支持用户自行填写 API Key / 端点 / 模型，并可在运行时热切换。
API Key 以密文存储（Fernet），接口层只返回脱敏后的值。

owner_id 目前恒为 NULL（平台级配置，单机自托管场景）。
保留该字段是为了将来平滑扩展到「每个用户一套自己的配置」。
"""
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text

from app.core.base import Base


class LLMProviderConfig(Base):
    """大模型 API 配置"""

    __tablename__ = "llm_provider_configs"

    id = Column(String(36), primary_key=True)
    # NULL = 平台级配置（当前不支持按用户隔离）
    owner_id = Column(String(36), nullable=True, index=True)

    # 用户可读的别名，例如「生产-OpenAI」「本地 Ollama」
    alias = Column(String(64), nullable=False, unique=True, index=True)

    # openai | anthropic | deepseek | ollama | openai-compatible
    provider = Column(String(32), nullable=False)
    base_url = Column(String(255), nullable=False, default="")
    # Fernet 密文
    api_key_enc = Column(Text, nullable=False, default="")

    model = Column(String(128), nullable=False, default="")
    temperature = Column(Float, nullable=False, default=0.7)
    max_tokens = Column(Integer, nullable=False, default=2048)

    description = Column(String(255), nullable=False, default="")

    is_default = Column(Boolean, nullable=False, default=False, index=True)
    is_active = Column(Boolean, nullable=False, default=True)

    # 最近一次连接测试结果（便于界面直接展示）
    last_tested_at = Column(DateTime, nullable=True)
    last_test_ok = Column(Boolean, nullable=True)
    last_test_error = Column(String(500), nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
