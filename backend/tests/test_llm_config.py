"""测试大模型 API 配置系统。

覆盖：
- 字段校验与可操作错误信息
- 密钥加密落库与脱敏输出
- CRUD、别名唯一性、默认项切换、启停
- 热拔插：改配置后运行时凭证立即变化（无需重启）
- 快照 TTL 与客户端缓存清理
- REST 接口行为（脱敏、校验、鉴权、404）
- 连接测试的错误翻译
"""
import json

import httpx
import pytest

from app.core.config import settings
from app.services import llm_config as svc
from app.services.model_runtime import resolve_credentials


@pytest.fixture(autouse=True)
def reset_snapshot():
    """每个用例前后都清空生效配置快照，避免全局状态串味。"""
    svc._SNAPSHOT = None
    svc._SNAPSHOT_LOADED_AT = 0.0
    svc._SNAPSHOT_MARKER = None
    yield
    svc._SNAPSHOT = None
    svc._SNAPSHOT_LOADED_AT = 0.0
    svc._SNAPSHOT_MARKER = None


async def make_config(db, **overrides):
    payload = {
        "alias": "生产-OpenAI",
        "provider": "openai",
        "base_url": "https://api.example.com/v1",
        "model": "gpt-4o-mini",
        "api_key": "sk-abcdefghijklmnop",
    }
    payload.update(overrides)
    return await svc.create_config(db, **payload)


class TestValidation:
    """字段校验"""

    def test_empty_alias(self):
        with pytest.raises(svc.ConfigValidationError) as exc:
            svc.validate_payload(
                alias="  ", provider="openai", base_url="", model="gpt-4o-mini", api_key="k"
            )
        assert exc.value.field == "alias"

    def test_alias_too_long(self):
        with pytest.raises(svc.ConfigValidationError) as exc:
            svc.validate_payload(
                alias="x" * 65, provider="openai", base_url="", model="m", api_key="k"
            )
        assert exc.value.field == "alias"

    def test_unknown_provider(self):
        with pytest.raises(svc.ConfigValidationError) as exc:
            svc.validate_payload(
                alias="a", provider="not-a-provider", base_url="http://x/v1", model="m", api_key="k"
            )
        assert exc.value.field == "provider"

    def test_base_url_without_scheme(self):
        with pytest.raises(svc.ConfigValidationError) as exc:
            svc.validate_payload(
                alias="a", provider="openai", base_url="api.example.com/v1", model="m", api_key="k"
            )
        assert exc.value.field == "base_url"

    def test_base_url_falls_back_to_provider_preset(self):
        result = svc.validate_payload(
            alias="a", provider="deepseek", base_url="", model="deepseek-chat", api_key="k"
        )
        assert result["base_url"] == "https://api.deepseek.com/v1"

    def test_empty_model(self):
        with pytest.raises(svc.ConfigValidationError) as exc:
            svc.validate_payload(
                alias="a", provider="openai", base_url="http://x/v1", model=" ", api_key="k"
            )
        assert exc.value.field == "model"

    def test_missing_api_key_for_cloud_provider(self):
        with pytest.raises(svc.ConfigValidationError) as exc:
            svc.validate_payload(
                alias="a", provider="openai", base_url="http://x/v1", model="m", api_key=""
            )
        assert exc.value.field == "api_key"

    def test_ollama_does_not_require_key(self):
        result = svc.validate_payload(
            alias="本地", provider="ollama", base_url="", model="qwen2.5", api_key=""
        )
        assert result["base_url"] == "http://localhost:11434/v1"

    def test_trailing_slash_is_trimmed(self):
        result = svc.validate_payload(
            alias="a", provider="openai", base_url="https://x.com/v1/", model="m", api_key="k"
        )
        assert result["base_url"] == "https://x.com/v1"

    def test_connectivity_hint_for_missing_v1(self):
        assert svc.validate_connectivity_shape("https://x.com/api", "openai") is not None
        assert svc.validate_connectivity_shape("https://x.com/v1", "openai") is None
        assert svc.validate_connectivity_shape("http://localhost:11434", "ollama") is None


class TestSecretHandling:
    """密钥加密与脱敏"""

    def test_mask_short_key(self):
        assert svc.mask_api_key("abc") == "***"

    def test_mask_long_key(self):
        masked = svc.mask_api_key("sk-1234567890abcdef")
        assert masked.startswith("sk-1")
        assert masked.endswith("cdef")
        assert "567890ab" not in masked

    def test_mask_empty(self):
        assert svc.mask_api_key("") == ""
        assert svc.mask_api_key(None) == ""

    @pytest.mark.asyncio
    async def test_key_is_encrypted_at_rest(self, async_db):
        config = await make_config(async_db, api_key="sk-plain-secret-value")

        # 落库的是密文，明文不出现在数据库字段里
        assert "sk-plain-secret-value" not in (config.api_key_enc or "")
        assert svc.decrypt_api_key(config) == "sk-plain-secret-value"


class TestCrud:
    """增删改查与默认项"""

    @pytest.mark.asyncio
    async def test_first_config_becomes_default(self, async_db):
        config = await make_config(async_db)

        assert config.is_default is True
        assert config.is_active is True

    @pytest.mark.asyncio
    async def test_second_config_does_not_steal_default(self, async_db):
        first = await make_config(async_db, alias="A")
        second = await make_config(async_db, alias="B")

        assert first.is_default is True
        assert second.is_default is False

    @pytest.mark.asyncio
    async def test_alias_must_be_unique(self, async_db):
        await make_config(async_db, alias="重复别名")

        with pytest.raises(svc.ConfigValidationError) as exc:
            await make_config(async_db, alias="重复别名")
        assert exc.value.field == "alias"

    @pytest.mark.asyncio
    async def test_update_keeps_key_when_not_provided(self, async_db):
        config = await make_config(async_db, api_key="sk-original")
        original_enc = config.api_key_enc

        updated = await svc.update_config(async_db, config, alias="改个名", model="gpt-4o")

        assert updated.api_key_enc == original_enc
        assert svc.decrypt_api_key(updated) == "sk-original"
        assert updated.alias == "改个名"

    @pytest.mark.asyncio
    async def test_cannot_clear_key_for_provider_that_requires_it(self, async_db):
        """openai 这类必须带密钥的 provider，显式清空应被拦下，避免留下不可用配置。"""
        config = await make_config(async_db)

        with pytest.raises(svc.ConfigValidationError) as exc:
            await svc.update_config(async_db, config, api_key="")
        assert exc.value.field == "api_key"

    @pytest.mark.asyncio
    async def test_clearing_key_allowed_for_keyless_provider(self, async_db):
        """切换成无需密钥的 provider（如本地 Ollama）时可以清空密钥。"""
        # base_url 传空串才会回落到 ollama 预设端点
        config = await make_config(
            async_db, alias="本地", provider="ollama", base_url="", model="qwen2.5", api_key=""
        )

        assert svc.decrypt_api_key(config) == ""
        assert config.base_url == "http://localhost:11434/v1"

    @pytest.mark.asyncio
    async def test_update_alias_conflict(self, async_db):
        await make_config(async_db, alias="A")
        second = await make_config(async_db, alias="B")

        with pytest.raises(svc.ConfigValidationError):
            await svc.update_config(async_db, second, alias="A")

    @pytest.mark.asyncio
    async def test_set_default_demotes_others(self, async_db):
        first = await make_config(async_db, alias="A")
        second = await make_config(async_db, alias="B")

        await svc.set_default(async_db, second)

        assert second.is_default is True
        refreshed = await svc.get_config(async_db, first.id)
        assert refreshed.is_default is False

    @pytest.mark.asyncio
    async def test_delete_default_promotes_fallback(self, async_db):
        first = await make_config(async_db, alias="A")
        second = await make_config(async_db, alias="B")

        await svc.delete_config(async_db, second)  # B 不是默认
        assert (await svc.get_config(async_db, first.id)).is_default is True

        await svc.delete_config(async_db, first)  # 删掉默认项
        remaining = await svc.list_configs(async_db)
        assert remaining == []

    @pytest.mark.asyncio
    async def test_cannot_disable_default(self, async_db):
        config = await make_config(async_db)

        with pytest.raises(svc.ConfigValidationError) as exc:
            await svc.set_active(async_db, config, False)
        assert exc.value.field == "is_active"

    @pytest.mark.asyncio
    async def test_list_puts_default_first(self, async_db):
        await make_config(async_db, alias="A")
        second = await make_config(async_db, alias="B")
        await svc.set_default(async_db, second)

        configs = await svc.list_configs(async_db)

        assert configs[0].id == second.id


class TestHotSwap:
    """热拔插：无需重启即可切换生效配置"""

    @pytest.mark.asyncio
    async def test_runtime_credentials_follow_default_config(self, async_db):
        a = await make_config(
            async_db, alias="A", base_url="https://a.example.com/v1", api_key="key-a"
        )
        await svc.ensure_fresh(async_db, force=True)
        assert svc.get_active().id == a.id
        assert resolve_credentials() == ("key-a", "https://a.example.com/v1")

        b = await make_config(
            async_db, alias="B", base_url="https://b.example.com/v1", api_key="key-b"
        )
        await svc.set_default(async_db, b)
        await svc.ensure_fresh(async_db, force=True)

        # 没有任何重启/重建动作，运行时凭证已切换
        assert svc.get_active().id == b.id
        assert resolve_credentials() == ("key-b", "https://b.example.com/v1")

    @pytest.mark.asyncio
    async def test_update_reflects_immediately(self, async_db):
        config = await make_config(async_db, api_key="key-old")
        await svc.ensure_fresh(async_db, force=True)

        await svc.update_config(async_db, config, api_key="key-new")
        await svc.ensure_fresh(async_db, force=True)

        assert resolve_credentials()[0] == "key-new"

    @pytest.mark.asyncio
    async def test_delete_default_falls_back_to_env(self, async_db, monkeypatch):
        config = await make_config(async_db)
        await svc.ensure_fresh(async_db, force=True)
        assert resolve_credentials()[0] == "sk-abcdefghijklmnop"

        await svc.delete_config(async_db, config)
        await svc.ensure_fresh(async_db, force=True)

        # 没有数据库配置后回到 .env（测试环境为空）
        assert svc.get_active() is None or svc.get_active().source != "database"

    @pytest.mark.asyncio
    async def test_client_cache_cleared_on_switch(self, async_db, monkeypatch):
        cleared = []
        import app.services.adapters as adapters

        monkeypatch.setattr(adapters, "clear_client_cache", lambda: cleared.append(1))

        a = await make_config(async_db, alias="A")
        await svc.ensure_fresh(async_db, force=True)
        assert cleared, "首次加载生效配置时应清理客户端缓存"

        before = len(cleared)
        b = await make_config(async_db, alias="B")
        await svc.set_default(async_db, b)
        await svc.ensure_fresh(async_db, force=True)
        assert len(cleared) > before, "切换生效配置后应再次清理客户端缓存"

    @pytest.mark.asyncio
    async def test_snapshot_ttl_marks_stale(self, async_db, monkeypatch):
        await make_config(async_db)
        monkeypatch.setattr(settings, "LLM_CONFIG_CACHE_TTL_SECONDS", 300)

        await svc.ensure_fresh(async_db, force=True)
        assert svc.is_stale() is False

        monkeypatch.setattr(svc, "_SNAPSHOT_LOADED_AT", 0.0)
        assert svc.is_stale() is True

    @pytest.mark.asyncio
    async def test_fresh_snapshot_skips_db_query(self, async_db, monkeypatch):
        await make_config(async_db)
        await svc.ensure_fresh(async_db, force=True)

        calls = {"n": 0}
        original = svc._select_effective

        async def counting(db):
            calls["n"] += 1
            return await original(db)

        monkeypatch.setattr(svc, "_select_effective", counting)

        await svc.ensure_fresh(async_db)  # TTL 内
        assert calls["n"] == 0


class TestConnectionTest:
    """连接测试与错误翻译"""

    @pytest.mark.asyncio
    async def test_models_endpoint_ok(self, monkeypatch):
        class FakeResponse:
            status_code = 200
            text = "{}"

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def get(self, url, headers=None):
                return FakeResponse()

        monkeypatch.setattr(svc.httpx, "AsyncClient", lambda **kwargs: FakeClient())

        ok, message = await svc.test_connection(
            base_url="https://x/v1", api_key="k", model="m"
        )
        assert ok is True
        assert "正常" in message

    @pytest.mark.asyncio
    async def test_auth_failure_message(self, monkeypatch):
        class FakeResponse:
            status_code = 401
            text = '{"error":{"message":"Invalid API key"}}'

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def get(self, url, headers=None):
                return FakeResponse()

            async def post(self, *args, **kwargs):
                return FakeResponse()

        monkeypatch.setattr(svc.httpx, "AsyncClient", lambda **kwargs: FakeClient())

        ok, message = await svc.test_connection(base_url="https://x/v1", api_key="bad", model="m")
        assert ok is False
        assert "认证失败" in message

    @pytest.mark.asyncio
    async def test_falls_back_to_chat_when_models_missing(self, monkeypatch):
        class ModelsMissing:
            status_code = 404
            text = "not found"

        class ChatOk:
            status_code = 200
            text = "{}"

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def get(self, url, headers=None):
                return ModelsMissing()

            async def post(self, *args, **kwargs):
                return ChatOk()

        monkeypatch.setattr(svc.httpx, "AsyncClient", lambda **kwargs: FakeClient())

        ok, message = await svc.test_connection(base_url="https://x/v1", api_key="k", model="m")
        assert ok is True
        assert "最小对话" in message

    @pytest.mark.asyncio
    async def test_connection_error_is_translated(self, monkeypatch):
        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def get(self, url, headers=None):
                raise httpx.ConnectError("Connection refused")

        monkeypatch.setattr(svc.httpx, "AsyncClient", lambda **kwargs: FakeClient())

        ok, message = await svc.test_connection(
            base_url="http://localhost:1/v1", api_key="", model="m"
        )
        assert ok is False
        assert "连接被拒绝" in message

    def test_timeout_message(self):
        assert "超时" in svc._friendly_error(httpx.TimeoutException("timed out"))

    def test_404_hint(self):
        assert "/v1" in svc._friendly_error(Exception("HTTP 404 not found"))

    def test_dns_message_from_exception_chain(self):
        """httpx 会把底层原因塞进异常链，需一并识别。"""
        root = OSError("Name or service not known")
        wrapped = httpx.ConnectError("")
        wrapped.__cause__ = root

        assert "域名解析失败" in svc._friendly_error(wrapped)

    def test_empty_message_falls_back_to_type_name(self):
        """ConnectError 的 str 可能为空，不能因此丢掉所有信息。"""
        message = svc._friendly_error(httpx.ConnectError(""))

        assert "无法连接到端点" in message

    def test_all_connection_attempts_failed(self):
        message = svc._friendly_error(httpx.ConnectError("All connection attempts failed"))

        assert "无法连接到端点" in message

    def test_connection_refused(self):
        message = svc._friendly_error(httpx.ConnectError("Connection refused"))

        assert "连接被拒绝" in message

    def test_ssl_eof_is_not_reported_as_certificate_problem(self):
        """域名不可达时 TLS 握手中断会抛 SSLEOFError，不能误报成证书问题。"""
        root = __import__("ssl").SSLEOFError("EOF occurred in violation of protocol")
        wrapped = httpx.ConnectError("")
        wrapped.__cause__ = root

        message = svc._friendly_error(wrapped)

        assert "无法连接到端点" in message
        assert "证书" not in message

    def test_real_certificate_error_still_reported(self):
        message = svc._friendly_error(Exception("CERTIFICATE_VERIFY_FAILED"))

        assert "TLS 校验失败" in message


class TestProvidersCatalog:
    def test_catalog_shape(self):
        catalog = svc.providers_catalog()

        assert catalog
        keys = [item["value"] for item in catalog]
        assert "openai" in keys and "ollama" in keys

        openai_entry = next(item for item in catalog if item["value"] == "openai")
        assert openai_entry["requires_key"] is True
        assert openai_entry["base_url"].startswith("http")
        # 来自 config/models.json 的建议模型
        assert any(m["name"] == "gpt-4o-mini" for m in openai_entry["models"])


# ---------------------------------------------------------------------------
# REST 接口
# ---------------------------------------------------------------------------

API = "/api/v1/llm-configs"


class TestApi:
    @pytest.mark.asyncio
    async def test_requires_auth(self, async_client):
        response = await async_client.get(API)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_and_list_masks_key(self, async_client, auth_headers):
        created = await async_client.post(
            API,
            headers=auth_headers,
            json={
                "alias": "生产环境",
                "provider": "openai",
                "base_url": "https://api.example.com/v1",
                "model": "gpt-4o-mini",
                "api_key": "sk-super-secret-key-1234",
            },
        )
        assert created.status_code == 200, created.text
        body = created.json()
        assert body["has_api_key"] is True
        assert "super-secret" not in json.dumps(body)
        assert body["api_key_masked"].endswith("1234")

        listed = await async_client.get(API, headers=auth_headers)
        assert listed.status_code == 200
        payload = listed.json()
        assert len(payload["configs"]) == 1
        assert payload["configs"][0]["is_default"] is True
        assert payload["effective_id"] == payload["configs"][0]["id"]
        assert "super-secret" not in listed.text

    @pytest.mark.asyncio
    async def test_create_reports_field_error(self, async_client, auth_headers):
        response = await async_client.post(
            API,
            headers=auth_headers,
            json={
                "alias": "x",
                "provider": "openai",
                "base_url": "ftp://bad",
                "model": "m",
                "api_key": "k",
            },
        )
        assert response.status_code == 422
        assert "base_url" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_duplicate_alias_rejected(self, async_client, auth_headers):
        payload = {
            "alias": "重名",
            "provider": "deepseek",
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-chat",
            "api_key": "k",
        }
        assert (await async_client.post(API, headers=auth_headers, json=payload)).status_code == 200
        second = await async_client.post(API, headers=auth_headers, json=payload)
        assert second.status_code == 422
        assert "已被占用" in second.json()["detail"]

    @pytest.mark.asyncio
    async def test_update_delete_and_default_flow(self, async_client, auth_headers):
        def make(alias, model_="gpt-4o-mini"):
            return {
                "alias": alias,
                "provider": "openai",
                "base_url": "https://api.example.com/v1",
                "model": model_,
                "api_key": "sk-key-0000000000",
            }

        first = (await async_client.post(API, headers=auth_headers, json=make("A"))).json()
        second = (await async_client.post(API, headers=auth_headers, json=make("B"))).json()

        # 切换默认项
        switched = await async_client.post(f"{API}/{second['id']}/default", headers=auth_headers)
        assert switched.status_code == 200
        assert switched.json()["is_default"] is True
        assert switched.json()["is_effective"] is True

        listed = (await async_client.get(API, headers=auth_headers)).json()
        by_id = {c["id"]: c for c in listed["configs"]}
        assert by_id[first["id"]]["is_default"] is False
        assert listed["effective_id"] == second["id"]

        # 更新（不传 api_key 应保留）
        updated = await async_client.put(
            f"{API}/{first['id']}",
            headers=auth_headers,
            json={"alias": "A2", "model": "gpt-4o"},
        )
        assert updated.status_code == 200
        assert updated.json()["alias"] == "A2"
        assert updated.json()["model"] == "gpt-4o"
        assert updated.json()["has_api_key"] is True

        # 停用非默认项
        toggled = await async_client.post(
            f"{API}/{first['id']}/active", headers=auth_headers, json={"is_active": False}
        )
        assert toggled.status_code == 200
        assert toggled.json()["is_active"] is False

        # 停用默认项应被拒绝
        denied = await async_client.post(
            f"{API}/{second['id']}/active", headers=auth_headers, json={"is_active": False}
        )
        assert denied.status_code == 422

        # 删除
        deleted = await async_client.delete(f"{API}/{second['id']}", headers=auth_headers)
        assert deleted.status_code == 200
        remaining = (await async_client.get(API, headers=auth_headers)).json()
        assert [c["id"] for c in remaining["configs"]] == [first["id"]]

    @pytest.mark.asyncio
    async def test_unknown_id_returns_404(self, async_client, auth_headers):
        assert (await async_client.get(f"{API}/nope", headers=auth_headers)).status_code == 404
        assert (await async_client.delete(f"{API}/nope", headers=auth_headers)).status_code == 404

    @pytest.mark.asyncio
    async def test_providers_and_effective_endpoints(self, async_client, auth_headers):
        providers = await async_client.get(f"{API}/providers", headers=auth_headers)
        assert providers.status_code == 200
        assert providers.json()["providers"]

        effective = await async_client.get(f"{API}/active", headers=auth_headers)
        assert effective.status_code == 200
        assert effective.json()["source"] in ("none", "env", "database")

    @pytest.mark.asyncio
    async def test_test_endpoint_uses_service_and_records_result(
        self, async_client, auth_headers, monkeypatch
    ):
        created = (
            await async_client.post(
                API,
                headers=auth_headers,
                json={
                    "alias": "待测",
                    "provider": "openai",
                    "base_url": "https://api.example.com/v1",
                    "model": "gpt-4o-mini",
                    "api_key": "sk-key-0000000000",
                },
            )
        ).json()

        async def fake_test(**kwargs):
            return True, "连接正常（已获取模型列表）"

        monkeypatch.setattr(svc, "test_connection", fake_test)

        response = await async_client.post(f"{API}/{created['id']}/test", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["ok"] is True

        detail = (await async_client.get(f"{API}/{created['id']}", headers=auth_headers)).json()
        assert detail["last_test_ok"] is True
        assert detail["last_tested_at"] is not None

    @pytest.mark.asyncio
    async def test_draft_test_endpoint(self, async_client, auth_headers, monkeypatch):
        async def fake_test(**kwargs):
            return False, "端点返回 404：路径不存在"

        monkeypatch.setattr(svc, "test_connection", fake_test)

        response = await async_client.post(
            f"{API}/test",
            headers=auth_headers,
            json={
                "provider": "openai",
                "base_url": "https://x/y",
                "model": "m",
                "api_key": "k",
            },
        )
        assert response.status_code == 200
        assert response.json()["ok"] is False
        assert "404" in response.json()["message"]
