"""
LLM 服务 - 统一接口
"""
from typing import AsyncIterator, Callable
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
import asyncio

from ..core.config import settings


class LLMNotConfiguredError(RuntimeError):
    """没有任何可用的模型凭证（.env 与「大模型 API 配置」都是空的）。"""


# 配置类错误重试没有任何意义，只会让用户白等。
# 实测：完全没有密钥时，SDK 的连接错误被重试 3 次，请求要卡 25 秒才返回，
# 最终还只给出英文的 "Connection error."，用户完全无从下手。
_NON_RETRYABLE_MARKERS = (
    "invalid api key",
    "incorrect api key",
    "no api key",
    "authentication",
    "unauthorized",
    "permission",
    "connection error",
    "connection refused",
    "not found",
    "does not exist",
    "nodename nor servname",
    "getaddrinfo",
)
_RETRYABLE_MARKERS = (
    "timeout",
    "timed out",
    "rate limit",
    "429",
    "500",
    "502",
    "503",
    "504",
    "overloaded",
)


def is_retryable_error(exc: Exception) -> bool:
    """只重试「值得重试」的异常（超时 / 限流 / 服务端 5xx）。

    认证失败、连接错误、模型不存在等属于配置问题，重试不会成功。
    """
    text = f"{exc.__class__.__name__} {exc}".lower()
    if any(marker in text for marker in _NON_RETRYABLE_MARKERS):
        return False
    return any(marker in text for marker in _RETRYABLE_MARKERS)


def humanize_llm_error(exc: Exception) -> str:
    """把模型调用异常翻译成用户可操作的中文提示。

    界面直接展示这个字符串，因此不能把 SDK 的英文原始信息透出去
    （例如只有 "Connection error." 时用户完全不知道该做什么）。
    """
    if isinstance(exc, LLMNotConfiguredError):
        return str(exc)

    from .llm_config import humanize_provider_error

    return humanize_provider_error(exc)


class LLMService:
    """LLM 服务统一接口"""
    
    def __init__(self, provider: str = "openai", model: str = None):
        self.provider = provider
        self.model = model or self._get_default_model(provider)
        self._client = None
    
    def _get_default_model(self, provider: str) -> str:
        defaults = {
            "openai": settings.OPENAI_MODEL,
            "anthropic": settings.ANTHROPIC_MODEL,
            "deepseek": "deepseek-chat",
        }
        return defaults.get(provider, "gpt-4o-mini")
    
    def _active_credentials(self) -> tuple[str | None, str | None]:
        """取「大模型 API 配置」中当前生效的凭证（仅 OpenAI 兼容协议适用）。

        未配置或配置来自 .env 快照时返回 (None, None)，由调用方回退到 settings。
        """
        from app.services.llm_config import get_active

        active = get_active()
        if active is None or active.source != "database":
            return None, None
        return (active.api_key or None), (active.base_url or None)

    def _resolved_credentials(self) -> tuple[str | None, str | None]:
        """解析生效凭证：优先「大模型 API 配置」，否则回退 .env。"""
        api_key, base_url = self._active_credentials()
        if api_key or base_url:
            return api_key, base_url

        if self.provider == "anthropic":
            return settings.ANTHROPIC_API_KEY or None, None
        if self.provider == "deepseek":
            base = (settings.DEEPSEEK_BASE_URL or "").rstrip("/")
            return settings.DEEPSEEK_API_KEY or None, f"{base}/v1" if base else None
        return settings.OPENAI_API_KEY or None, None

    def ensure_configured(self) -> None:
        """没有凭证时立即报错，不让 SDK 反复重试把用户晾在那里。"""
        api_key, base_url = self._resolved_credentials()
        if not api_key and not base_url:
            raise LLMNotConfiguredError(
                "尚未配置大模型 API：请在「设置 → 模型配置」中添加密钥与端点，"
                "或在 backend/.env 中设置 OPENAI_API_KEY"
            )

    def _get_client(self):
        if self._client:
            return self._client

        self.ensure_configured()
        api_key, base_url = self._resolved_credentials()

        # max_retries=0：关掉 SDK 自带的重试，重试策略统一由 self._retry 控制。
        # 两层重试叠加会让失败请求卡 20 秒以上（实测 25 秒）。
        if self.provider == "openai":
            # 本地端点常常没有密钥，此时给个占位值（SDK 不允许 api_key 为空）；
            # base_url 为空则交给 SDK 用官方默认值
            self._client = AsyncOpenAI(
                api_key=api_key or "not-needed",
                max_retries=0,
                **({"base_url": base_url} if base_url else {}),
            )
        elif self.provider == "anthropic":
            # Anthropic 走原生协议，不套用 OpenAI 兼容端点
            self._client = AsyncAnthropic(api_key=api_key or "not-needed", max_retries=0)

        return self._client
    
    async def chat(
        self,
        messages: list,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        stream: bool = False,
    ) -> str:
        """对话（带重试）"""
        if self.provider == "openai":
            return await self._chat_openai(messages, temperature, max_tokens, stream)
        elif self.provider == "anthropic":
            return await self._chat_anthropic(messages, temperature, max_tokens, stream)
        elif self.provider == "deepseek":
            return await self._chat_deepseek(messages, temperature, max_tokens)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    async def _retry(self, fn: Callable, *args, **kwargs) -> str:
        """带指数退避的重试。

        只重试超时/限流/5xx；配置类错误（无密钥、认证失败、连不上端点）
        直接抛出，避免用户为必然失败的请求白等十几秒。
        """
        last_err = None
        for attempt in range(3):
            try:
                return await fn(*args, **kwargs)
            except Exception as e:
                last_err = e
                if attempt >= 2 or not is_retryable_error(e):
                    raise
                wait = 2 ** attempt
                await asyncio.sleep(wait)
        raise last_err

    async def chat_stream(
        self,
        messages: list,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> AsyncIterator[str]:
        """流式对话"""
        if self.provider == "openai":
            async for chunk in self._chat_openai_stream(messages, temperature, max_tokens):
                yield chunk
        elif self.provider == "anthropic":
            async for chunk in self._chat_anthropic_stream(messages, temperature, max_tokens):
                yield chunk

    async def _chat_openai_stream(
        self,
        messages: list,
        temperature: float,
        max_tokens: int,
    ) -> AsyncIterator[str]:
        """OpenAI 流式对话"""
        client = self._get_client()
        response = await client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        async for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    
    async def _chat_openai(
        self,
        messages: list,
        temperature: float,
        max_tokens: int,
        stream: bool,
    ) -> str:
        async def _call():
            client = self._get_client()
            response = await client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream,
            )
            if stream:
                full_content = ""
                async for chunk in response:
                    if chunk.choices[0].delta.content:
                        full_content += chunk.choices[0].delta.content
                return full_content
            else:
                return response.choices[0].message.content
        return await self._retry(_call)
    
    async def _chat_anthropic(
        self,
        messages: list,
        temperature: float,
        max_tokens: int,
        stream: bool,
    ) -> str:
        async def _call():
            client = self._get_client()
            system = None
            anthropic_messages = []
            for msg in messages:
                if msg["role"] == "system":
                    system = msg["content"]
                else:
                    anthropic_messages.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })
            response = await client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=anthropic_messages,
                temperature=temperature,
            )
            return response.content[0].text
        return await self._retry(_call)
    
    async def _chat_deepseek(
        self,
        messages: list,
        temperature: float,
        max_tokens: int,
    ) -> str:
        async def _call():
            self.ensure_configured()
            api_key, base_url = self._resolved_credentials()
            client = AsyncOpenAI(
                api_key=api_key or "not-needed",
                base_url=base_url or settings.DEEPSEEK_BASE_URL + "/v1",
                max_retries=0,
            )
            response = await client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content
        return await self._retry(_call)
    
    async def embed(self, text: str) -> list:
        """生成嵌入向量（带模型缓存）"""
        if self.provider == "openai":
            client = self._get_client()
            response = await client.embeddings.create(
                model="text-embedding-3-small",
                input=text,
            )
            return response.data[0].embedding
        else:
            if not hasattr(self, "_st_model"):
                from sentence_transformers import SentenceTransformer
                self._st_model = SentenceTransformer(settings.EMBEDDING_MODEL)
            return self._st_model.encode(text).tolist()
