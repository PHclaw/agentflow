"""
LLM 服务 - 统一接口
"""
from typing import Optional, AsyncIterator
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
import httpx

from ..core.config import settings


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
    
    def _get_client(self):
        if self._client:
            return self._client
        
        if self.provider == "openai":
            self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        elif self.provider == "anthropic":
            self._client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        
        return self._client
    
    async def chat(
        self,
        messages: list,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        stream: bool = False,
    ) -> str:
        """对话"""
        if self.provider == "openai":
            return await self._chat_openai(messages, temperature, max_tokens, stream)
        elif self.provider == "anthropic":
            return await self._chat_anthropic(messages, temperature, max_tokens, stream)
        elif self.provider == "deepseek":
            return await self._chat_deepseek(messages, temperature, max_tokens)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")
    
    async def _chat_openai(
        self,
        messages: list,
        temperature: float,
        max_tokens: int,
        stream: bool,
    ) -> str:
        client = self._get_client()
        
        response = await client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=stream,
        )
        
        if stream:
            # 流式响应
            full_content = ""
            async for chunk in response:
                if chunk.choices[0].delta.content:
                    full_content += chunk.choices[0].delta.content
            return full_content
        else:
            return response.choices[0].message.content
    
    async def _chat_anthropic(
        self,
        messages: list,
        temperature: float,
        max_tokens: int,
        stream: bool,
    ) -> str:
        client = self._get_client()
        
        # 转换消息格式
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
    
    async def _chat_deepseek(
        self,
        messages: list,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """DeepSeek API"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
                timeout=60,
            )
            
            data = response.json()
            return data["choices"][0]["message"]["content"]
    
    async def embed(self, text: str) -> list:
        """生成嵌入向量"""
        if self.provider == "openai":
            client = self._get_client()
            response = await client.embeddings.create(
                model="text-embedding-3-small",
                input=text,
            )
            return response.data[0].embedding
        else:
            # 使用 sentence-transformers
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer(settings.EMBEDDING_MODEL)
            return model.encode(text).tolist()
