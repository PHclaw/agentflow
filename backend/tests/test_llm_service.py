"""
测试 LLM 服务统一接口

覆盖 app/services/llm.py：
- 默认模型选择
- 按 provider 分发到各自的 chat 实现
- _retry 的指数退避与重试次数上限
- embed 的 OpenAI 路径

所有用例均不发起真实网络请求。
"""
import pytest

from app.services import llm as llm_module
from app.services.llm import LLMService


class TestDefaultModel:
    """默认模型选择"""

    def test_known_providers(self):
        assert LLMService(provider="openai")._get_default_model("openai")
        assert LLMService(provider="anthropic")._get_default_model("anthropic")
        assert LLMService(provider="deepseek")._get_default_model("deepseek") == "deepseek-chat"

    def test_unknown_provider_falls_back(self):
        assert LLMService(provider="nonexistent")._get_default_model("nonexistent") == "gpt-4o-mini"

    def test_explicit_model_is_kept(self):
        assert LLMService(provider="openai", model="gpt-4o").model == "gpt-4o"


class TestChatDispatch:
    """按 provider 分发"""

    @pytest.mark.asyncio
    async def test_openai(self):
        svc = LLMService(provider="openai")
        seen = {}

        async def fake(messages, temperature, max_tokens, stream):
            seen.update(messages=messages, temperature=temperature, stream=stream)
            return "openai-reply"

        svc._chat_openai = fake
        assert await svc.chat([{"role": "user", "content": "hi"}], temperature=0.3) == "openai-reply"
        assert seen["temperature"] == 0.3
        assert seen["stream"] is False

    @pytest.mark.asyncio
    async def test_anthropic(self):
        svc = LLMService(provider="anthropic")
        svc._chat_anthropic = lambda *a, **k: _async_return("anthropic-reply")
        assert await svc.chat([{"role": "user", "content": "hi"}]) == "anthropic-reply"

    @pytest.mark.asyncio
    async def test_deepseek(self):
        svc = LLMService(provider="deepseek")
        svc._chat_deepseek = lambda *a, **k: _async_return("deepseek-reply")
        assert await svc.chat([{"role": "user", "content": "hi"}]) == "deepseek-reply"

    @pytest.mark.asyncio
    async def test_unknown_provider_raises(self):
        svc = LLMService(provider="unknown-provider")
        with pytest.raises(ValueError, match="Unknown provider"):
            await svc.chat([{"role": "user", "content": "hi"}])


class TestRetry:
    """_retry 的退避行为"""

    @pytest.fixture
    def no_sleep(self, monkeypatch):
        slept = []

        async def fake_sleep(seconds):
            slept.append(seconds)

        monkeypatch.setattr(llm_module.asyncio, "sleep", fake_sleep)
        return slept

    @pytest.mark.asyncio
    async def test_first_call_succeeds(self, no_sleep):
        svc = LLMService(provider="openai")
        calls = {"n": 0}

        async def ok():
            calls["n"] += 1
            return "done"

        assert await svc._retry(ok) == "done"
        assert calls["n"] == 1
        assert no_sleep == []

    @pytest.mark.asyncio
    async def test_succeeds_after_transient_failures(self, no_sleep):
        svc = LLMService(provider="openai")
        calls = {"n": 0}

        async def flaky():
            calls["n"] += 1
            if calls["n"] < 3:
                raise RuntimeError("transient")
            return "recovered"

        assert await svc._retry(flaky) == "recovered"
        assert calls["n"] == 3
        assert no_sleep == [1, 2]

    @pytest.mark.asyncio
    async def test_gives_up_after_three_attempts(self, no_sleep):
        svc = LLMService(provider="openai")
        calls = {"n": 0}

        async def always_fail():
            calls["n"] += 1
            raise RuntimeError("down")

        with pytest.raises(RuntimeError, match="down"):
            await svc._retry(always_fail)

        assert calls["n"] == 3
        assert no_sleep == [1, 2]


class TestEmbed:
    """嵌入向量"""

    @pytest.mark.asyncio
    async def test_openai_embedding(self):
        class FakeEmbeddingResponse:
            data = [type("D", (), {"embedding": [0.1, 0.2, 0.3]})()]

        class FakeEmbeddings:
            async def create(self, model, input):  # noqa: A002
                return FakeEmbeddingResponse()

        class FakeClient:
            embeddings = FakeEmbeddings()

        svc = LLMService(provider="openai")
        svc._client = FakeClient()

        assert await svc.embed("hello") == [0.1, 0.2, 0.3]

    @pytest.mark.asyncio
    async def test_non_openai_uses_sentence_transformers(self, monkeypatch):
        """非 OpenAI provider 走 sentence-transformers（本地未安装时优雅降级为 ImportError）"""
        svc = LLMService(provider="anthropic")

        with pytest.raises((ImportError, ModuleNotFoundError)):
            await svc.embed("hello")


class TestChatStream:
    """流式输出分发"""

    @pytest.mark.asyncio
    async def test_stream_yields_chunks(self):
        svc = LLMService(provider="openai")

        async def fake_stream(messages, temperature, max_tokens):
            for chunk in ["你", "好"]:
                yield chunk

        svc._chat_openai_stream = fake_stream

        chunks = [c async for c in svc.chat_stream([{"role": "user", "content": "hi"}])]
        assert chunks == ["你", "好"]


def _async_return(value):
    async def _inner(*args, **kwargs):
        return value

    return _inner()
