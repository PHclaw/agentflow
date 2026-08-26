from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChatChunk:
    delta: str = ""
    finish_reason: str | None = None
    tokens_input: int | None = None
    tokens_output: int | None = None


@dataclass
class ChatResult:
    output: str
    tokens_input: int = 0
    tokens_output: int = 0
    latency_ms: int = 0
    cost: float = 0.0
    raw: dict[str, Any] = field(default_factory=dict)


class ModelAdapter(ABC):
    @abstractmethod
    async def chat(
        self,
        model_name: str,
        *,
        system: str,
        user: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> ChatResult:
        raise NotImplementedError

    @abstractmethod
    async def chat_stream(
        self,
        model_name: str,
        *,
        system: str,
        user: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> AsyncIterator[ChatChunk]:
        raise NotImplementedError
        yield  # pragma: no cover


def get_adapter(model_name: str) -> ModelAdapter:
    """按模型名前缀路由到适配器；当前统一走 OpenAI 兼容（百炼测试）。"""
    from app.services.adapters.openai_compatible import OpenAICompatibleAdapter

    name = (model_name or "").lower()
    # 预留多供应商扩展点
    _ = name
    return OpenAICompatibleAdapter()
