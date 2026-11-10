"""
测试 OpenAI 兼容适配器（app/services/adapters/openai_compatible.py）

只覆盖不发网络请求的纯逻辑：URL 归一化、网关判定、消息组装、
成本估算、凭据校验、client 缓存复用与失效。
"""
import pytest

from app.services.adapters import openai_compatible as oc
from app.services.adapters.openai_compatible import OpenAICompatibleAdapter


class FakeSettings:
    def __init__(self, **kwargs):
        self.chatzoc_api_key = ""
        self.chatzoc_base_url = ""
        self.model_base_url = ""
        self.chatzoc_agent_type = ""
        self.openai_timeout_seconds = 1.0
        self.openai_connect_timeout_seconds = 1.0
        self.openai_max_retries = 0
        self.__dict__.update(kwargs)


@pytest.fixture
def adapter_settings(monkeypatch):
    def _apply(**kwargs):
        monkeypatch.setattr(oc, "get_settings", lambda: FakeSettings(**kwargs))

    return _apply


class TestNormalizeBaseUrl:
    """base URL 归一化"""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("", ""),
            ("https://api.example.com", "https://api.example.com/v1"),
            ("https://api.example.com/", "https://api.example.com/v1"),
            ("https://api.example.com/v1", "https://api.example.com/v1"),
            ("https://api.example.com/v1/", "https://api.example.com/v1"),
            ("https://api.example.com/api", "https://api.example.com/api/v1"),
        ],
    )
    def test_normalize(self, raw, expected):
        assert oc._normalize_openai_base(raw) == expected


class TestIsChatZOC:
    """ChatZOC 内网网关判定"""

    def test_enabled_by_settings(self, adapter_settings):
        adapter_settings(chatzoc_base_url="http://10.168.100.20:8000")

        assert oc._is_chatzoc("gpt-4o", None) is True

    def test_detected_from_model_name(self, adapter_settings):
        adapter_settings()

        assert oc._is_chatzoc("chatzoc_9b_B", None) is True

    def test_detected_from_base_url(self, adapter_settings):
        adapter_settings()

        assert oc._is_chatzoc("qwen", "http://10.168.100.20/v1") is True

    def test_plain_openai_is_not_chatzoc(self, adapter_settings):
        adapter_settings()

        assert oc._is_chatzoc("gpt-4o", "https://api.openai.com/v1") is False


class TestAdapterHelpers:
    """适配器的辅助方法"""

    def test_messages_includes_system_when_present(self):
        adapter = OpenAICompatibleAdapter()

        assert adapter._messages("你是助手", "你好") == [
            {"role": "system", "content": "你是助手"},
            {"role": "user", "content": "你好"},
        ]

    def test_messages_omits_empty_system(self):
        adapter = OpenAICompatibleAdapter()

        assert adapter._messages("", "你好") == [{"role": "user", "content": "你好"}]

    def test_agent_type_prefers_configured(self, adapter_settings):
        adapter_settings(chatzoc_agent_type="chatzoc_9b_B")
        adapter = OpenAICompatibleAdapter()

        assert adapter._agent_type("whatever") == "chatzoc_9b_B"

    def test_agent_type_falls_back_to_model(self, adapter_settings):
        adapter_settings()
        adapter = OpenAICompatibleAdapter()

        assert adapter._agent_type("qwen-plus") == "qwen-plus"

    @pytest.mark.parametrize(
        "model",
        ["gpt-4o", "claude-3", "gemini-pro", "qwen-plus", "deepseek-chat", "chatzoc_9b_B", "unknown-model"],
    )
    def test_estimate_cost_is_non_negative(self, model):
        cost = OpenAICompatibleAdapter._estimate_cost(model, 1000, 500)

        assert cost >= 0

    def test_estimate_cost_scales_with_tokens(self):
        small = OpenAICompatibleAdapter._estimate_cost("gpt-4o", 1000, 0)
        large = OpenAICompatibleAdapter._estimate_cost("gpt-4o", 2000, 0)

        assert large == pytest.approx(small * 2)


class TestCredentials:
    """凭据校验"""

    def test_missing_api_key_raises(self, adapter_settings, monkeypatch):
        adapter_settings()
        monkeypatch.setattr(
            oc.OpenAICompatibleAdapter,
            "_credentials",
            OpenAICompatibleAdapter._credentials,
        )
        monkeypatch.setattr(
            "app.services.model_runtime.resolve_credentials",
            lambda: ("", ""),
        )
        adapter = OpenAICompatibleAdapter()

        with pytest.raises(ValueError, match="API Key"):
            adapter._credentials(None, None)

    def test_missing_base_url_raises(self, adapter_settings, monkeypatch):
        # 同时清空 settings.model_base_url，否则会回落到 DEEPSEEK_BASE_URL 而不报错
        adapter_settings(model_base_url="")
        monkeypatch.setattr(
            "app.services.model_runtime.resolve_credentials",
            lambda: ("key-123", ""),
        )
        adapter = OpenAICompatibleAdapter()

        with pytest.raises(ValueError, match="Base URL"):
            adapter._credentials(None, None)

    def test_explicit_values_win(self, monkeypatch):
        monkeypatch.setattr(
            "app.services.model_runtime.resolve_credentials",
            lambda: ("env-key", "http://env"),
        )
        adapter = OpenAICompatibleAdapter()

        assert adapter._credentials("my-key", "http://mine") == ("my-key", "http://mine")


class TestClientCache:
    """AsyncOpenAI 实例缓存"""

    def test_same_credentials_reuse_client(self, adapter_settings):
        adapter_settings()
        oc.clear_client_cache()

        first = oc._get_or_create_client("k", "http://x/v1")
        second = oc._get_or_create_client("k", "http://x/v1")

        assert first is second

    def test_different_credentials_create_different_clients(self, adapter_settings):
        adapter_settings()
        oc.clear_client_cache()

        a = oc._get_or_create_client("k1", "http://x/v1")
        b = oc._get_or_create_client("k2", "http://x/v1")

        assert a is not b

    def test_expired_entry_is_recreated(self, adapter_settings, monkeypatch):
        adapter_settings()
        oc.clear_client_cache()
        monkeypatch.setattr(oc, "_CLIENT_TTL_SECONDS", -1)

        first = oc._get_or_create_client("k", "http://x/v1")
        second = oc._get_or_create_client("k", "http://x/v1")

        assert first is not second

    def test_clear_client_cache_empties_cache(self, adapter_settings):
        adapter_settings()
        oc.clear_client_cache()
        oc._get_or_create_client("k", "http://x/v1")

        assert len(oc._CLIENT_CACHE) == 1

        oc.clear_client_cache()

        assert len(oc._CLIENT_CACHE) == 0
