"""大模型 API 配置服务：持久化、热加载与连接校验。

设计要点
--------
1. **单一凭证出口**：``app.services.model_runtime.resolve_credentials`` 是全项目
   唯一的模型凭证来源，这里维护的「当前生效配置」快照就是喂给它的数据源。
2. **热拔插**：所有增删改都会 ``invalidate()``，立即刷新快照并清空底层 SDK
   客户端缓存，因此改完下一条请求就生效，无需重启。
3. **多进程一致性**：快照带 TTL（``LLM_CONFIG_CACHE_TTL_SECONDS``），配合请求
   级 ``ensure_fresh()``，多 worker 部署下最迟 TTL 秒后一致。
4. **密钥安全**：API Key 以 Fernet 密文落库，接口层只返回脱敏值；
   仅在内存快照中短暂持有明文。

仅支持 **OpenAI 兼容协议** 的端点（OpenAI / DeepSeek / Ollama / 百炼 / vLLM /
OneAPI 等）。原生 Anthropic 协议需要额外的适配器，暂不在本系统范围内。
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.paths import models_catalog_path
from app.logging_setup import get_logger
from app.models.llm_config import LLMProviderConfig
from app.security import decrypt_text, encrypt_text

logger = get_logger("llm_config")

# 支持的 provider 及其默认端点。requires_key=False 表示本地推理服务通常无需密钥。
PROVIDER_PRESETS: dict[str, dict[str, Any]] = {
    "openai": {
        "label": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "requires_key": True,
        "hint": "官方端点，需要 sk- 开头的密钥",
    },
    "deepseek": {
        "label": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "requires_key": True,
        "hint": "DeepSeek 开放平台",
    },
    "ollama": {
        "label": "Ollama（本地）",
        "base_url": "http://localhost:11434/v1",
        "requires_key": False,
        "hint": "本地推理，通常无需密钥",
    },
    "openai-compatible": {
        "label": "OpenAI 兼容网关",
        "base_url": "",
        "requires_key": True,
        "hint": "vLLM / OneAPI / 百炼 / 自建网关等，需以 /v1 结尾",
    },
    "chatzoc": {
        "label": "ChatZOC / 内网模型",
        "base_url": "",
        "requires_key": True,
        "hint": "内网 OpenAI 兼容网关",
    },
}

ALLOWED_PROVIDERS = tuple(PROVIDER_PRESETS.keys())


class ConfigValidationError(ValueError):
    """字段校验失败，携带出错的字段名便于前端定位。"""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field
        self.message = message


# ---------------------------------------------------------------------------
# 当前生效配置快照（热加载核心）
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ActiveConfig:
    """内存中的生效配置。api_key 为明文，仅存活于进程内。"""

    id: str | None
    alias: str
    provider: str
    base_url: str
    api_key: str
    model: str
    temperature: float
    max_tokens: int
    source: str  # "database" | "env"

    def masked_key(self) -> str:
        return mask_api_key(self.api_key)


_SNAPSHOT_LOCK = threading.RLock()
_SNAPSHOT: ActiveConfig | None = None
_SNAPSHOT_LOADED_AT: float = 0.0
_SNAPSHOT_MARKER: str | None = None


def _env_fallback() -> ActiveConfig | None:
    """数据库没有可用配置时回退到 .env（保持既有部署行为）。"""
    from app.config import get_settings

    s = get_settings()
    api_key = s.chatzoc_api_key or s.dashscope_api_key or ""
    base_url = s.chatzoc_base_url or s.model_base_url or ""
    if not api_key and not base_url:
        return None
    return ActiveConfig(
        id=None,
        alias=".env",
        provider="openai-compatible",
        base_url=base_url,
        api_key=api_key,
        model=s.default_model or s.optimize_model or "",
        temperature=0.7,
        max_tokens=2048,
        source="env",
    )


def get_active() -> ActiveConfig | None:
    """同步读取快照；未加载过时返回 None（由调用方回退 .env）。"""
    with _SNAPSHOT_LOCK:
        return _SNAPSHOT


def _set_snapshot(config: ActiveConfig | None, marker: str | None) -> bool:
    """写入快照；返回是否发生了变化（变化时需要清理 SDK 客户端缓存）。"""
    global _SNAPSHOT, _SNAPSHOT_LOADED_AT, _SNAPSHOT_MARKER

    with _SNAPSHOT_LOCK:
        changed = marker != _SNAPSHOT_MARKER or (
            _SNAPSHOT is not None and config is not None and _SNAPSHOT.id != config.id
        )
        _SNAPSHOT = config
        _SNAPSHOT_MARKER = marker
        _SNAPSHOT_LOADED_AT = time.monotonic()
        return changed


def invalidate() -> None:
    """使快照立即失效（增删改后调用），并清空底层客户端缓存。"""
    global _SNAPSHOT_LOADED_AT, _SNAPSHOT_MARKER

    with _SNAPSHOT_LOCK:
        _SNAPSHOT_LOADED_AT = 0.0
        _SNAPSHOT_MARKER = None
    clear_llm_client_cache()


def clear_llm_client_cache() -> None:
    """清理适配器里缓存的 AsyncOpenAI 实例，避免继续持有旧密钥。"""
    try:
        from app.services.adapters import clear_client_cache

        clear_client_cache()
    except Exception:  # noqa: BLE001 - 清理失败不应影响主流程
        logger.warning("清理模型客户端缓存失败", exc_info=True)


async def ensure_fresh(db: AsyncSession, *, force: bool = False) -> ActiveConfig | None:
    """确保快照新鲜；返回当前生效配置（可能为 None 表示回退 .env）。

    ``force=True`` 时忽略 TTL 立即回源数据库（CRUD 之后、启动时使用）。
    """
    from app.services.adapters import clear_client_cache as _clear

    global _SNAPSHOT_LOADED_AT

    with _SNAPSHOT_LOCK:
        loaded_at = _SNAPSHOT_LOADED_AT
        fresh = (not force) and loaded_at > 0 and (time.monotonic() - loaded_at) < settings.LLM_CONFIG_CACHE_TTL_SECONDS

    if fresh:
        return get_active()

    row = await _select_effective(db)
    if row is None:
        config = _env_fallback()
        marker = "env" if config else "empty"
    else:
        try:
            api_key = decrypt_text(row.api_key_enc) if row.api_key_enc else ""
        except ValueError:
            logger.error("配置 %s 的 API Key 解密失败，已跳过", row.id)
            config = None
            marker = f"decrypt-failed:{row.id}"
        else:
            config = ActiveConfig(
                id=row.id,
                alias=row.alias,
                provider=row.provider,
                base_url=row.base_url or "",
                api_key=api_key,
                model=row.model or "",
                temperature=row.temperature or 0.7,
                max_tokens=row.max_tokens or 2048,
                source="database",
            )
            marker = f"{row.id}:{row.updated_at.isoformat() if row.updated_at else ''}"

    changed = _set_snapshot(config, marker)
    if changed:
        _clear()
        logger.info(
            "生效配置已切换 alias=%s provider=%s source=%s",
            config.alias if config else "-",
            config.provider if config else "-",
            config.source if config else "-",
        )
    return config


async def _select_effective(db: AsyncSession) -> LLMProviderConfig | None:
    """优先取「默认且启用」的配置，其次取最近更新的启用配置。"""
    stmt = (
        select(LLMProviderConfig)
        .where(LLMProviderConfig.is_active.is_(True))
        .order_by(LLMProviderConfig.is_default.desc(), LLMProviderConfig.updated_at.desc())
        .limit(1)
    )
    return await db.scalar(stmt)


# ---------------------------------------------------------------------------
# 密钥脱敏
# ---------------------------------------------------------------------------


def mask_api_key(key: str | None) -> str:
    """只保留首尾少量字符，中间打码。"""
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return f"{key[:4]}{'*' * 6}{key[-4:]}"


def decrypt_api_key(config: LLMProviderConfig) -> str:
    """解密配置中的 API Key；为空或解密失败时返回空串。"""
    if not config.api_key_enc:
        return ""
    try:
        return decrypt_text(config.api_key_enc)
    except ValueError:
        logger.error("配置 %s 的 API Key 解密失败", config.id)
        return ""


def is_stale() -> bool:
    """快照是否已过期（供请求级刷新提前短路，避免每个请求都查库）。"""
    with _SNAPSHOT_LOCK:
        loaded_at = _SNAPSHOT_LOADED_AT
    if loaded_at <= 0:
        return True
    return (time.monotonic() - loaded_at) >= settings.LLM_CONFIG_CACHE_TTL_SECONDS


# ---------------------------------------------------------------------------
# 校验
# ---------------------------------------------------------------------------


def validate_payload(
    *,
    alias: str,
    provider: str,
    base_url: str,
    model: str,
    api_key: str | None = None,
    require_key: bool = True,
) -> dict[str, str]:
    """校验并归一化字段；不通过则抛 ConfigValidationError。

    Returns:
        归一化后的 {"alias", "provider", "base_url", "model"}
    """
    alias = (alias or "").strip()
    if not alias:
        raise ConfigValidationError("alias", "别名不能为空")
    if len(alias) > 64:
        raise ConfigValidationError("alias", "别名最长 64 个字符")

    provider = (provider or "").strip().lower()
    if provider not in PROVIDER_PRESETS:
        raise ConfigValidationError(
            "provider",
            f"不支持的 provider：{provider}（可选：{', '.join(ALLOWED_PROVIDERS)}）",
        )

    base_url = (base_url or "").strip().rstrip("/")
    if base_url:
        if not base_url.startswith(("http://", "https://")):
            raise ConfigValidationError("base_url", "端点必须以 http:// 或 https:// 开头")
    else:
        base_url = PROVIDER_PRESETS[provider]["base_url"]
    if not base_url:
        raise ConfigValidationError("base_url", "端点不能为空（例如 https://api.openai.com/v1）")

    model = (model or "").strip()
    if not model:
        raise ConfigValidationError("model", "默认模型不能为空")

    needs_key = PROVIDER_PRESETS[provider]["requires_key"]
    if require_key and needs_key and not (api_key or "").strip():
        raise ConfigValidationError("api_key", f"{PROVIDER_PRESETS[provider]['label']} 需要填写 API Key")

    return {"alias": alias, "provider": provider, "base_url": base_url, "model": model}


def validate_connectivity_shape(base_url: str, provider: str) -> str | None:
    """返回非致命的配置建议（不阻断保存）。

    例如端点没以 /v1 结尾是常见错误，虽然不绝对（有些网关路由不同），
    但值得在界面上提示一句。
    """
    if provider == "ollama":
        return None
    normalized = base_url.rstrip("/")
    if not normalized.endswith(("/v1", "/v1beta", "/openai")):
        return "端点通常需要以 /v1 结尾（例如 https://api.openai.com/v1）"
    return None


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


async def list_configs(db: AsyncSession) -> list[LLMProviderConfig]:
    stmt = select(LLMProviderConfig).order_by(
        LLMProviderConfig.is_default.desc(),
        LLMProviderConfig.updated_at.desc(),
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_config(db: AsyncSession, config_id: str) -> LLMProviderConfig | None:
    return await db.get(LLMProviderConfig, config_id)


async def _assert_alias_available(db: AsyncSession, alias: str, *, exclude_id: str | None = None) -> None:
    stmt = select(LLMProviderConfig).where(LLMProviderConfig.alias == alias)
    if exclude_id:
        stmt = stmt.where(LLMProviderConfig.id != exclude_id)
    if await db.scalar(stmt):
        raise ConfigValidationError("alias", f"别名「{alias}」已被占用")


async def create_config(
    db: AsyncSession,
    *,
    alias: str,
    provider: str,
    base_url: str,
    model: str,
    api_key: str,
    description: str = "",
    temperature: float = 0.7,
    max_tokens: int = 2048,
    is_default: bool = False,
    owner_id: str | None = None,
) -> LLMProviderConfig:
    normalized = validate_payload(
        alias=alias, provider=provider, base_url=base_url, model=model, api_key=api_key
    )
    await _assert_alias_available(db, normalized["alias"])

    is_first = not await db.scalar(select(LLMProviderConfig.id).limit(1))
    config = LLMProviderConfig(
        id=str(uuid.uuid4()),
        owner_id=owner_id,
        alias=normalized["alias"],
        provider=normalized["provider"],
        base_url=normalized["base_url"],
        api_key_enc=encrypt_text((api_key or "").strip()),
        model=normalized["model"],
        description=(description or "").strip()[:255],
        temperature=float(temperature),
        max_tokens=int(max_tokens),
        # 第一条配置自动成为默认项，避免出现「有配置但没有默认」的空档
        is_default=bool(is_default) or is_first,
        is_active=True,
    )
    db.add(config)
    await db.commit()
    await db.refresh(config)

    if config.is_default:
        await _demote_others(db, config.id)
        await db.commit()
        await db.refresh(config)

    invalidate()
    return config


async def update_config(
    db: AsyncSession,
    config: LLMProviderConfig,
    *,
    alias: str | None = None,
    provider: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    description: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> LLMProviderConfig:
    """更新配置。``api_key`` 传 None 表示保持原密钥不变，传空串表示清空。"""
    target_provider = (provider if provider is not None else config.provider) or config.provider
    normalized = validate_payload(
        alias=alias if alias is not None else config.alias,
        provider=target_provider,
        base_url=base_url if base_url is not None else config.base_url,
        model=model if model is not None else config.model,
        # 保留原密钥时不做「必填」校验
        api_key=api_key if api_key is not None else (config.api_key_enc and "keep"),
        require_key=api_key is not None,
    )
    await _assert_alias_available(db, normalized["alias"], exclude_id=config.id)

    config.alias = normalized["alias"]
    config.provider = normalized["provider"]
    config.base_url = normalized["base_url"]
    config.model = normalized["model"]

    if api_key is not None:
        config.api_key_enc = encrypt_text(api_key.strip())
    if description is not None:
        config.description = (description or "").strip()[:255]
    if temperature is not None:
        config.temperature = float(temperature)
    if max_tokens is not None:
        config.max_tokens = int(max_tokens)

    config.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(config)

    invalidate()
    return config


async def delete_config(db: AsyncSession, config: LLMProviderConfig) -> None:
    was_default = config.is_default
    await db.delete(config)
    await db.commit()

    # 删掉默认项后自动补一个，避免出现无默认状态
    if was_default:
        fallback = await _select_effective(db)
        if fallback is not None:
            fallback.is_default = True
            await db.commit()

    invalidate()


async def _demote_others(db: AsyncSession, keep_id: str) -> None:
    await db.execute(
        update(LLMProviderConfig)
        .where(LLMProviderConfig.id != keep_id, LLMProviderConfig.is_default.is_(True))
        .values(is_default=False)
    )


async def set_default(db: AsyncSession, config: LLMProviderConfig) -> LLMProviderConfig:
    await _demote_others(db, config.id)
    config.is_default = True
    config.is_active = True  # 设为默认即视为启用
    config.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(config)

    invalidate()
    return config


async def set_active(db: AsyncSession, config: LLMProviderConfig, active: bool) -> LLMProviderConfig:
    if not active and config.is_default:
        raise ConfigValidationError("is_active", "默认配置不能停用，请先把其它配置设为默认")
    config.is_active = active
    config.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(config)

    invalidate()
    return config


# ---------------------------------------------------------------------------
# 连接测试
# ---------------------------------------------------------------------------


def _friendly_error(exc: Exception) -> str:
    """把底层异常翻译成用户能直接行动的提示。

    httpx 常把真正的失败原因放在异常链（``__cause__`` / ``__context__``）里，
    自身 ``str()`` 可能为空，所以要把整条链上的文本和类型名拼起来判断。
    """
    chain: list[str] = []
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        chain.append(str(current))
        chain.append(current.__class__.__name__)
        current = current.__cause__ or current.__context__

    blob = " ".join(part for part in chain if part)
    lowered = blob.lower()
    status = getattr(exc, "status_code", None)

    if status in (401, 403) or "401" in lowered or "403" in lowered or "invalid api key" in lowered:
        return "认证失败：API Key 无效或没有该模型权限"
    if "does not exist" in lowered or "model_not_found" in lowered or "unknown model" in lowered:
        return "模型不存在：请检查模型名是否被该端点支持"
    if any(k in lowered for k in (
        "nodename nor servname", "name or service not known", "getaddrinfo",
        "name resolution", "name does not resolve",
    )):
        return "域名解析失败：请检查端点域名是否正确"
    if "ssleoferror" in lowered or "unexpected_eof" in lowered:
        # 域名不可达时 TLS 握手会被中断，这里不要误报成「证书问题」
        return "无法连接到端点：请确认域名可解析且网络可达"
    if "certificate" in lowered or "certificate_verify_failed" in lowered:
        return "TLS 校验失败：请确认端点证书有效"
    if "timeout" in lowered or "timed out" in lowered:
        return "连接超时：端点无响应或网络不通"
    if "refused" in lowered:
        return "连接被拒绝：端点未启动或端口不对"
    if status == 404 or "404" in lowered:
        return "路径不存在：端点通常需要以 /v1 结尾"
    if "all connection attempts failed" in lowered or "connecterror" in lowered or "connect" in lowered:
        return "无法连接到端点：请确认地址与端口正确、服务已启动且网络可达"
    return f"连接失败：{chain[0][:200] if chain and chain[0] else exc.__class__.__name__}"


async def test_connection(
    *,
    base_url: str,
    api_key: str,
    model: str,
    timeout: int | None = None,
) -> tuple[bool, str]:
    """连通性校验：先探测 /models（不消耗 token），失败再退回最小对话请求。

    Returns:
        (是否通过, 说明信息)
    """
    base_url = (base_url or "").strip().rstrip("/")
    timeout = timeout or settings.LLM_CONFIG_TEST_TIMEOUT
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    try:
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
            probe = await client.get(f"{base_url}/models", headers=headers)
            if probe.status_code < 400:
                return True, "连接正常（已获取模型列表）"

            # /models 不可用（部分网关不实现）时，用最小对话请求兜底验证
            if probe.status_code in (401, 403):
                return False, "认证失败：API Key 无效或没有访问权限"

            chat = await client.post(
                f"{base_url}/chat/completions",
                headers={**headers, "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 1,
                    "temperature": 0,
                },
            )
            if chat.status_code < 400:
                return True, "连接正常（已通过最小对话请求验证）"

            detail = ""
            try:
                body = chat.json()
                detail = str(body.get("error", {}).get("message") or body.get("message") or "")
            except Exception:  # noqa: BLE001
                detail = chat.text[:200]

            if chat.status_code in (401, 403):
                return False, "认证失败：API Key 无效或没有访问权限"
            if chat.status_code == 404:
                return False, "路径不存在：端点通常需要以 /v1 结尾"
            if chat.status_code == 400 and "model" in detail.lower():
                return False, f"模型不可用：{detail or model}"
            return False, f"端点返回 {chat.status_code}：{detail or '请检查配置'}"

    except Exception as exc:  # noqa: BLE001 - 需要翻译成用户可读提示
        logger.info("连接测试失败 base_url=%s err=%r", base_url, exc)
        return False, _friendly_error(exc)


async def record_test_result(
    db: AsyncSession, config: LLMProviderConfig, ok: bool, message: str
) -> LLMProviderConfig:
    """把测试结果写回配置，便于界面直接展示。"""
    config.last_tested_at = datetime.now(timezone.utc)
    config.last_test_ok = ok
    config.last_test_error = None if ok else message[:500]
    await db.commit()
    await db.refresh(config)
    return config


# ---------------------------------------------------------------------------
# 前端元数据
# ---------------------------------------------------------------------------


def providers_catalog() -> list[dict[str, Any]]:
    """返回可选 provider 及其建议模型（来自 config/models.json）。"""
    models = _catalog_models()
    catalog = []
    for key, preset in PROVIDER_PRESETS.items():
        catalog.append({
            "value": key,
            "label": preset["label"],
            "base_url": preset["base_url"],
            "requires_key": preset["requires_key"],
            "hint": preset["hint"],
            "models": [
                {"name": m["name"], "display_name": m.get("display_name") or m["name"]}
                for m in models
                if (m.get("provider") or "").lower() in (key, key.split("-")[0])
            ],
        })
    return catalog


def _catalog_models() -> list[dict[str, Any]]:
    path: Path = models_catalog_path()
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.warning("模型清单解析失败: %s", path)
        return []
    models = data.get("models") or []
    return [m for m in models if isinstance(m, dict) and m.get("name")]
