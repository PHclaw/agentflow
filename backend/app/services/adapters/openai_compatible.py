from __future__ import annotations

import json
import threading
import time
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import urlparse

import httpx
from openai import AsyncOpenAI

from app.config import get_settings
from app.services.adapters.base import ChatChunk, ChatResult, ModelAdapter

# 单例 client 缓存：(api_key, base_url) -> (client, created_monotonic)
_CLIENT_CACHE: dict[tuple[str, str], tuple[AsyncOpenAI, float]] = {}
_CLIENT_LOCK = threading.Lock()
_CLIENT_TTL_SECONDS = 30 * 60


def clear_client_cache() -> None:
    """清空 AsyncOpenAI 缓存（密钥轮换 / 配置热重载时调用）。"""
    with _CLIENT_LOCK:
        _CLIENT_CACHE.clear()


def _httpx_timeout() -> httpx.Timeout:
    settings = get_settings()
    return httpx.Timeout(
        settings.openai_timeout_seconds,
        connect=settings.openai_connect_timeout_seconds,
    )


def _httpx_client(**kwargs: Any) -> httpx.AsyncClient:
    """内网模型网关勿走系统代理（Windows trust_env 会导致 ChatZOC 502）。"""
    return httpx.AsyncClient(trust_env=False, timeout=_httpx_timeout(), **kwargs)


def _get_or_create_client(api_key: str, base_url: str | None) -> AsyncOpenAI:
    """复用 AsyncOpenAI 实例；带锁 + TTL，避免永久持有旧密钥客户端。"""
    url = base_url or ""
    cache_key = (api_key, url)
    now = time.monotonic()

    with _CLIENT_LOCK:
        entry = _CLIENT_CACHE.get(cache_key)
        if entry is not None:
            client, created = entry
            if now - created < _CLIENT_TTL_SECONDS:
                return client
            _CLIENT_CACHE.pop(cache_key, None)

        http_client = httpx.AsyncClient(trust_env=False, timeout=_httpx_timeout())
        client = AsyncOpenAI(
            api_key=api_key,
            base_url=url,
            http_client=http_client,
            max_retries=get_settings().openai_max_retries,
        )
        _CLIENT_CACHE[cache_key] = (client, now)
        return client


def _normalize_openai_base(url: str) -> str:
    """确保 OpenAI 兼容 base 以 /v1 结尾（ChatZOC 需要 /v1/chat/completions）。"""
    u = (url or "").rstrip("/")
    if not u:
        return u
    path = urlparse(u).path or ""
    if path.endswith("/v1") or path.endswith("/v1/"):
        return u.rstrip("/")
    return f"{u}/v1"


def _is_chatzoc(model_name: str, base_url: str | None) -> bool:
    settings = get_settings()
    if settings.chatzoc_base_url or settings.chatzoc_api_key:
        return True
    blob = f"{model_name or ''} {base_url or ''} {settings.model_base_url or ''}".lower()
    return "chatzoc" in blob or "10.168.100.20" in blob


class OpenAICompatibleAdapter(ModelAdapter):
    """OpenAI 兼容协议适配器（百炼 / ChatZOC / 自定义网关）。"""

    def _credentials(
        self, api_key: str | None, base_url: str | None
    ) -> tuple[str, str]:
        from app.services.model_runtime import resolve_credentials

        settings = get_settings()
        env_key, env_url = resolve_credentials()
        key = api_key or env_key
        url = base_url or env_url or settings.model_base_url
        if not key:
            raise ValueError(
                "未配置 API Key：请设置环境变量 CHATZOC_API_KEY 或 DASHSCOPE_API_KEY"
            )
        if not url:
            raise ValueError(
                "未配置 Base URL：请设置环境变量 CHATZOC_BASE_URL 或 MODEL_BASE_URL"
            )
        return key, url

    def _client(self, api_key: str | None, base_url: str | None) -> AsyncOpenAI:
        key, url = self._credentials(api_key, base_url)
        return _get_or_create_client(key, _normalize_openai_base(url))

    def _messages(self, system: str, user: str) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})
        return messages

    def _agent_type(self, model_name: str) -> str:
        settings = get_settings()
        return (settings.chatzoc_agent_type or model_name or "").strip() or model_name

    @staticmethod
    def _estimate_cost(model: str, tin: int, tout: int) -> float:
        rates = {
            "gpt-4o": (0.005, 0.015),
            "claude": (0.003, 0.015),
            "gemini": (0.001, 0.004),
            "qwen": (0.0008, 0.002),
            "deepseek": (0.0005, 0.002),
            "chatzoc": (0.0003, 0.0008),
        }
        lower = model.lower()
        pin, pout = 0.001, 0.002
        for prefix, rate in rates.items():
            if prefix in lower:
                pin, pout = rate
                break
        return round((tin / 1000) * pin + (tout / 1000) * pout, 6)

    async def _chatzoc_chat(
        self,
        model_name: str,
        *,
        system: str,
        user: str,
        temperature: float,
        max_tokens: int,
        api_key: str | None,
        base_url: str | None,
    ) -> ChatResult:
        return await self._chatzoc_chat_messages(
            model_name,
            messages=self._messages(system, user),
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=api_key,
            base_url=base_url,
        )

    async def _chatzoc_chat_messages(
        self,
        model_name: str,
        *,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        api_key: str | None,
        base_url: str | None,
    ) -> ChatResult:
        key, url = self._credentials(api_key, base_url)
        endpoint = _normalize_openai_base(url) + "/chat/completions"
        agent_type = self._agent_type(model_name)
        payload: dict[str, Any] = {
            "model": agent_type,
            "agent_type": agent_type,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        settings = get_settings()
        started = time.perf_counter()
        async with _httpx_client() as client:
            resp = await client.post(
                endpoint,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        latency_ms = int((time.perf_counter() - started) * 1000)
        if resp.status_code >= 400:
            raise RuntimeError(f"ChatZOC HTTP {resp.status_code}: {resp.text[:500]}")
        data = resp.json()
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("ChatZOC 返回空 choices")
        message = choices[0].get("message") or {}
        output = message.get("content") or ""
        usage = data.get("usage") or {}
        tin = int(usage.get("prompt_tokens") or 0)
        tout = int(usage.get("completion_tokens") or 0)
        return ChatResult(
            output=output,
            tokens_input=tin,
            tokens_output=tout,
            latency_ms=latency_ms,
            cost=self._estimate_cost(model_name, tin, tout),
            raw=data if isinstance(data, dict) else {"raw": data},
        )

    async def _chatzoc_stream(
        self,
        model_name: str,
        *,
        system: str,
        user: str,
        temperature: float,
        max_tokens: int,
        api_key: str | None,
        base_url: str | None,
    ) -> AsyncIterator[ChatChunk]:
        key, url = self._credentials(api_key, base_url)
        endpoint = _normalize_openai_base(url) + "/chat/completions"
        agent_type = self._agent_type(model_name)
        payload: dict[str, Any] = {
            "model": agent_type,
            "agent_type": agent_type,
            "messages": self._messages(system, user),
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        settings = get_settings()
        usage_tin = 0
        usage_tout = 0
        async with _httpx_client() as client:
            async with client.stream(
                "POST",
                endpoint,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                    "Accept": "text/event-stream",
                },
                json=payload,
            ) as resp:
                if resp.status_code >= 400:
                    body = (await resp.aread()).decode("utf-8", errors="replace")
                    raise RuntimeError(f"ChatZOC HTTP {resp.status_code}: {body[:500]}")
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    if line.startswith(":"):
                        continue
                    if not line.startswith("data:"):
                        continue
                    data_str = line[5:].strip()
                    if not data_str or data_str == "[DONE]":
                        if data_str == "[DONE]":
                            yield ChatChunk(
                                delta="",
                                finish_reason="stop",
                                tokens_input=usage_tin,
                                tokens_output=usage_tout,
                            )
                        continue
                    try:
                        event = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    usage = event.get("usage")
                    if isinstance(usage, dict):
                        usage_tin = int(usage.get("prompt_tokens") or usage_tin or 0)
                        usage_tout = int(
                            usage.get("completion_tokens") or usage_tout or 0
                        )
                    choices = event.get("choices") or []
                    if not choices:
                        continue
                    choice = choices[0] or {}
                    delta_obj = choice.get("delta") or {}
                    delta = delta_obj.get("content") or ""
                    finish = choice.get("finish_reason")
                    if delta or finish:
                        yield ChatChunk(
                            delta=delta,
                            finish_reason=finish,
                            tokens_input=usage_tin or None,
                            tokens_output=usage_tout or None,
                        )
        if usage_tin or usage_tout:
            yield ChatChunk(
                delta="",
                finish_reason="stop",
                tokens_input=usage_tin,
                tokens_output=usage_tout,
            )

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
        return await self.chat_messages(
            model_name,
            messages=self._messages(system, user),
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=api_key,
            base_url=base_url,
        )

    async def chat_messages(
        self,
        model_name: str,
        *,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> ChatResult:
        _, url = self._credentials(api_key, base_url)
        if _is_chatzoc(model_name, url):
            return await self._chatzoc_chat_messages(
                model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                api_key=api_key,
                base_url=base_url,
            )

        client = self._client(api_key, base_url)
        started = time.perf_counter()
        completion = await client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        latency_ms = int((time.perf_counter() - started) * 1000)
        if not completion.choices:
            raise RuntimeError("上游返回空 choices")
        choice = completion.choices[0]
        output = choice.message.content or ""
        usage = completion.usage
        tin = int(getattr(usage, "prompt_tokens", 0) or 0)
        tout = int(getattr(usage, "completion_tokens", 0) or 0)
        return ChatResult(
            output=output,
            tokens_input=tin,
            tokens_output=tout,
            latency_ms=latency_ms,
            cost=self._estimate_cost(model_name, tin, tout),
            raw=completion.model_dump(),
        )

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
        _, url = self._credentials(api_key, base_url)
        if _is_chatzoc(model_name, url):
            async for chunk in self._chatzoc_stream(
                model_name,
                system=system,
                user=user,
                temperature=temperature,
                max_tokens=max_tokens,
                api_key=api_key,
                base_url=base_url,
            ):
                yield chunk
            return

        client = self._client(api_key, base_url)
        create_kwargs: dict = {
            "model": model_name,
            "messages": self._messages(system, user),
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        try:
            stream = await client.chat.completions.create(**create_kwargs)
        except Exception:
            create_kwargs.pop("stream_options", None)
            stream = await client.chat.completions.create(**create_kwargs)

        usage_tin: int | None = None
        usage_tout: int | None = None
        async for event in stream:
            usage = getattr(event, "usage", None)
            if usage is not None:
                usage_tin = int(getattr(usage, "prompt_tokens", 0) or 0)
                usage_tout = int(getattr(usage, "completion_tokens", 0) or 0)
            if not event.choices:
                continue
            delta = event.choices[0].delta.content or ""
            finish = event.choices[0].finish_reason
            if delta or finish:
                yield ChatChunk(
                    delta=delta,
                    finish_reason=finish,
                    tokens_input=usage_tin,
                    tokens_output=usage_tout,
                )

        if usage_tin is not None or usage_tout is not None:
            yield ChatChunk(
                delta="",
                finish_reason="stop",
                tokens_input=usage_tin or 0,
                tokens_output=usage_tout or 0,
            )
