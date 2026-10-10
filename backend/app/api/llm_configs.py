"""大模型 API 配置接口。

提供配置的增删改查、默认项切换、启用/停用与连接测试。
API Key 只以脱敏形式返回，永不回传明文。

热拔插：所有写操作都会让运行时快照失效，下一条模型请求即使用新配置，
无需重启服务。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user_id
from app.core.database import get_db
from app.models.llm_config import LLMProviderConfig
from app.services import llm_config as svc

router = APIRouter(dependencies=[Depends(get_current_user_id)])


# ---------------------------------------------------------------------------
# 请求模型
# ---------------------------------------------------------------------------


class ConfigCreateRequest(BaseModel):
    alias: str
    provider: str
    base_url: str = ""
    model: str
    api_key: str = ""
    description: str = ""
    temperature: float = 0.7
    max_tokens: int = 2048
    is_default: bool = False


class ConfigUpdateRequest(BaseModel):
    alias: Optional[str] = None
    provider: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    # 不传 / 传 null 表示保持原密钥；传空串表示清空
    api_key: Optional[str] = None
    description: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


class ActiveToggleRequest(BaseModel):
    is_active: bool


class ConnectionTestRequest(BaseModel):
    provider: str = "openai-compatible"
    base_url: str
    model: str
    api_key: str = ""


class ConnectionTestResponse(BaseModel):
    ok: bool
    message: str


# ---------------------------------------------------------------------------
# 序列化
# ---------------------------------------------------------------------------


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _to_dict(config: LLMProviderConfig, *, effective_id: str | None = None) -> dict[str, Any]:
    """脱敏输出。只暴露密钥是否存在与掩码预览。"""
    api_key = svc.decrypt_api_key(config)

    return {
        "id": config.id,
        "alias": config.alias,
        "provider": config.provider,
        "base_url": config.base_url or "",
        "model": config.model or "",
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "description": config.description or "",
        "is_default": bool(config.is_default),
        "is_active": bool(config.is_active),
        "has_api_key": bool(config.api_key_enc),
        "api_key_masked": svc.mask_api_key(api_key),
        "last_tested_at": _iso(config.last_tested_at),
        "last_test_ok": config.last_test_ok,
        "last_test_error": config.last_test_error,
        "created_at": _iso(config.created_at),
        "updated_at": _iso(config.updated_at),
        "is_effective": bool(effective_id) and config.id == effective_id,
    }


def _validation_error(exc: svc.ConfigValidationError) -> HTTPException:
    # 保持 detail 为字符串，前端已有的错误解析逻辑可直接展示
    return HTTPException(422, detail=f"{exc.message}（字段：{exc.field}）")


async def _load(db: AsyncSession, config_id: str) -> LLMProviderConfig:
    config = await svc.get_config(db, config_id)
    if config is None:
        raise HTTPException(404, "配置不存在")
    return config


# ---------------------------------------------------------------------------
# 元数据与当前生效项（必须注册在 /{config_id} 之前）
# ---------------------------------------------------------------------------


@router.get("/providers")
async def list_providers() -> dict[str, Any]:
    """可选 provider 预设与建议模型，供前端下拉选择。"""
    return {
        "providers": svc.providers_catalog(),
        "protocol_note": "当前仅支持 OpenAI 兼容协议端点（OpenAI / DeepSeek / Ollama / 百炼 / vLLM / OneAPI 等）",
    }


@router.get("/active")
async def get_effective_config(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """查看当前真正生效的配置（可能是 .env 回退）。"""
    active = await svc.ensure_fresh(db)
    if active is None:
        return {
            "source": "none",
            "alias": None,
            "provider": None,
            "base_url": "",
            "model": "",
            "api_key_masked": "",
            "message": "尚未配置任何大模型 API，且 .env 中也没有可用凭证",
        }
    return {
        "source": active.source,
        "id": active.id,
        "alias": active.alias,
        "provider": active.provider,
        "base_url": active.base_url,
        "model": active.model,
        "api_key_masked": active.masked_key(),
        "message": "来自 .env 回退" if active.source == "env" else "来自大模型 API 配置",
    }


@router.post("/test", response_model=ConnectionTestResponse)
async def test_draft(data: ConnectionTestRequest) -> ConnectionTestResponse:
    """测试尚未保存的草稿配置（用于「填写时先验证」）。"""
    ok, message = await svc.test_connection(
        base_url=data.base_url, api_key=data.api_key, model=data.model
    )
    return ConnectionTestResponse(ok=ok, message=message)


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


@router.get("")
async def list_configs(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    active = await svc.ensure_fresh(db)
    configs = await svc.list_configs(db)
    return {
        "configs": [_to_dict(c, effective_id=active.id if active else None) for c in configs],
        "effective_id": active.id if active else None,
        "effective_source": active.source if active else "none",
    }


@router.post("")
async def create_config(
    data: ConfigCreateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    try:
        config = await svc.create_config(
            db,
            alias=data.alias,
            provider=data.provider,
            base_url=data.base_url,
            model=data.model,
            api_key=data.api_key,
            description=data.description,
            temperature=data.temperature,
            max_tokens=data.max_tokens,
            is_default=data.is_default,
            owner_id=None,  # 平台级配置（预留按用户隔离的能力）
        )
    except svc.ConfigValidationError as exc:
        raise _validation_error(exc) from exc

    active = await svc.ensure_fresh(db)
    return _to_dict(config, effective_id=active.id if active else None)


@router.get("/{config_id}")
async def get_config_detail(config_id: str, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    config = await _load(db, config_id)
    active = await svc.ensure_fresh(db)
    return _to_dict(config, effective_id=active.id if active else None)


@router.put("/{config_id}")
async def update_config(
    config_id: str,
    data: ConfigUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    config = await _load(db, config_id)
    try:
        config = await svc.update_config(
            db,
            config,
            alias=data.alias,
            provider=data.provider,
            base_url=data.base_url,
            model=data.model,
            api_key=data.api_key,
            description=data.description,
            temperature=data.temperature,
            max_tokens=data.max_tokens,
        )
    except svc.ConfigValidationError as exc:
        raise _validation_error(exc) from exc

    active = await svc.ensure_fresh(db, force=True)
    return _to_dict(config, effective_id=active.id if active else None)


@router.delete("/{config_id}")
async def delete_config(config_id: str, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    config = await _load(db, config_id)
    await svc.delete_config(db, config)
    return {"message": "删除成功", "id": config_id}


@router.post("/{config_id}/default")
async def make_default(config_id: str, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """设为默认项（同时启用），切换过程不影响其它配置。"""
    config = await _load(db, config_id)
    config = await svc.set_default(db, config)
    active = await svc.ensure_fresh(db, force=True)
    return _to_dict(config, effective_id=active.id if active else None)


@router.post("/{config_id}/active")
async def toggle_active(
    config_id: str,
    data: ActiveToggleRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    config = await _load(db, config_id)
    try:
        config = await svc.set_active(db, config, data.is_active)
    except svc.ConfigValidationError as exc:
        raise _validation_error(exc) from exc

    active = await svc.ensure_fresh(db, force=True)
    return _to_dict(config, effective_id=active.id if active else None)


@router.post("/{config_id}/test", response_model=ConnectionTestResponse)
async def test_saved_config(config_id: str, db: AsyncSession = Depends(get_db)) -> ConnectionTestResponse:
    """测试已保存配置，并把结果记录到配置上便于界面展示。"""
    config = await _load(db, config_id)
    api_key = svc.decrypt_api_key(config)

    ok, message = await svc.test_connection(
        base_url=config.base_url, api_key=api_key, model=config.model
    )
    await svc.record_test_result(db, config, ok, message)
    return ConnectionTestResponse(ok=ok, message=message)
