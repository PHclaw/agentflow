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

from app.core.config import settings
from app.services import llm as llm_module
from app.services.llm import (
    LLMNotConfiguredError,
    LLMService,
    humanize_llm_error,
    is_retryable_error,
)


def _active(**over):
    """构造一个「来自数据库的生效配置」。"""
    from app.services.llm_config import ActiveConfig

    base = dict(
        id="cfg-1", alias="本地-ollama", provider="ollama",
        base_url="http://localhost:11434/v1", api_key="",
        model="glm4:latest", temperature=0.7, max_tokens=2048,
        source="database",
    )
    base.update(over)
    return ActiveConfig(**base)


class TestModelFollowsActiveConfig:
    """模型名必须跟凭证一起走生效配置。

    这是「model 'gpt-4o-mini' not found」那类 404 的最根本来源：
    ``_active_credentials()`` 只取 key/base_url，**丢掉了 model 字段**，
    于是生效配置指向本地 Ollama 的 glm4:latest 时，发出去的仍然是
    ``settings.OPENAI_MODEL``（gpt-4o-mini）。
    """

    def test_uses_model_from_active_config(self, monkeypatch):
        monkeypatch.setattr("app.services.llm_config.get_active", lambda: _active())

        assert LLMService().model == "glm4:latest"

    def test_credentials_come_from_same_config(self, monkeypatch):
        """模型与凭证必须来自同一份配置，不能各走各的。"""
        monkeypatch.setattr(
            "app.services.llm_config.get_active",
            lambda: _active(api_key="sk-local", base_url="http://localhost:11434/v1"),
        )

        svc = LLMService()

        assert svc.model == "glm4:latest"
        assert svc._active_credentials() == ("sk-local", "http://localhost:11434/v1")

    def test_env_snapshot_model_is_not_trusted(self, monkeypatch):
        """source 不是 database 的快照没有真实模型名，不该被采信。

        否则一个 .env 回退快照里的占位模型名会盖掉 settings 的真实默认值。
        """
        monkeypatch.setattr(
            "app.services.llm_config.get_active",
            lambda: _active(id=None, source="env", model="placeholder-model"),
        )

        assert LLMService().model == settings.OPENAI_MODEL

    def test_explicit_model_still_wins(self, monkeypatch):
        """显式指定的模型优先 —— 别为了修 bug 把选择能力砍掉。"""
        monkeypatch.setattr("app.services.llm_config.get_active", lambda: _active())

        assert LLMService(model="qwen2.5:7b").model == "qwen2.5:7b"

    def test_falls_back_to_env_when_no_active_config(self, monkeypatch):
        monkeypatch.setattr("app.services.llm_config.get_active", lambda: None)

        assert LLMService().model == settings.OPENAI_MODEL

    def test_active_config_without_model_falls_back(self, monkeypatch):
        """生效配置存在但没填模型名时，退回 .env 默认值而不是发空串。"""
        monkeypatch.setattr(
            "app.services.llm_config.get_active", lambda: _active(model="")
        )

        assert LLMService().model == settings.OPENAI_MODEL


class TestEffectiveModelNameHelper:
    """``llm_config.effective_model_name`` —— 模型解析的唯一权威出口。"""

    def test_prefers_database_config(self, monkeypatch):
        monkeypatch.setattr("app.services.llm_config.get_active", lambda: _active())

        from app.services.llm_config import effective_model_name

        assert effective_model_name() == "glm4:latest"

    def test_uses_fallback_when_absent(self, monkeypatch):
        monkeypatch.setattr("app.services.llm_config.get_active", lambda: None)

        from app.services.llm_config import effective_model_name

        assert effective_model_name("fallback-model") == "fallback-model"

    def test_returns_empty_string_by_default(self, monkeypatch):
        """取不到时返回空串 —— 空串是「未指定」，各调用点自己决定兜底。"""
        monkeypatch.setattr("app.services.llm_config.get_active", lambda: None)

        from app.services.llm_config import effective_model_name

        assert effective_model_name() == ""


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
                raise RuntimeError("503 Service Unavailable")
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
            raise RuntimeError("503 Service Unavailable")

        with pytest.raises(RuntimeError, match="503"):
            await svc._retry(always_fail)

        assert calls["n"] == 3
        assert no_sleep == [1, 2]

    @pytest.mark.asyncio
    async def test_configuration_error_is_not_retried(self, no_sleep):
        """配置类错误重试不会成功，必须立刻抛出（曾导致请求卡 25 秒）"""
        svc = LLMService(provider="openai")
        calls = {"n": 0}

        async def bad_config():
            calls["n"] += 1
            raise RuntimeError("Connection error.")

        with pytest.raises(RuntimeError, match="Connection error"):
            await svc._retry(bad_config)

        assert calls["n"] == 1
        assert no_sleep == []


class TestRetryableClassification:
    """哪些异常值得重试"""

    @pytest.mark.parametrize(
        "message",
        ["Request timed out", "Rate limit reached (429)", "502 Bad Gateway", "server overloaded"],
    )
    def test_retryable(self, message):
        assert is_retryable_error(RuntimeError(message)) is True

    @pytest.mark.parametrize(
        "message",
        [
            "Connection error.",
            "Invalid API key",
            "Incorrect API key provided",
            "model does not exist",
            "nodename nor servname provided",
        ],
    )
    def test_not_retryable(self, message):
        assert is_retryable_error(RuntimeError(message)) is False


class TestCredentialGuard:
    """没有凭证时必须快速失败，而不是让 SDK 重试到超时"""

    @pytest.mark.asyncio
    async def test_raises_without_any_credentials(self, monkeypatch):
        monkeypatch.setattr(llm_module.settings, "OPENAI_API_KEY", "")
        svc = LLMService(provider="openai")
        monkeypatch.setattr(svc, "_active_credentials", lambda: (None, None))

        with pytest.raises(LLMNotConfiguredError) as exc:
            svc.ensure_configured()
        assert "模型配置" in str(exc.value)

    @pytest.mark.asyncio
    async def test_passes_with_env_key(self, monkeypatch):
        monkeypatch.setattr(llm_module.settings, "OPENAI_API_KEY", "sk-test")
        svc = LLMService(provider="openai")
        monkeypatch.setattr(svc, "_active_credentials", lambda: (None, None))

        svc.ensure_configured()

    @pytest.mark.asyncio
    async def test_passes_with_only_base_url(self, monkeypatch):
        """本地端点常常没有密钥，只有 base_url 也应视为已配置"""
        monkeypatch.setattr(llm_module.settings, "OPENAI_API_KEY", "")
        svc = LLMService(provider="openai")
        monkeypatch.setattr(
            svc, "_active_credentials", lambda: (None, "http://localhost:11434/v1")
        )

        svc.ensure_configured()


class TestHumanizeError:
    """错误信息必须翻译成用户能行动的中文"""

    def test_not_configured_message_is_actionable(self):
        msg = humanize_llm_error(
            LLMNotConfiguredError("尚未配置大模型 API：请在「设置 → 模型配置」中添加密钥与端点")
        )
        assert "模型配置" in msg

    def test_bare_connection_error_is_translated(self):
        """只给一句 'Connection error.' 用户完全无从下手"""
        msg = humanize_llm_error(RuntimeError("Connection error."))

        assert msg != "Connection error."
        assert "无法连接到端点" in msg

    def test_auth_error_is_translated(self):
        assert "认证失败" in humanize_llm_error(RuntimeError("401 Invalid API key"))


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
