"""外部只读数据源（ERP）连接器接口。

提供连接器的增删改查、连通性测试与只读试查（供画布调试 / 预览脱敏结果）。
密码只以掩码形式返回，永不回传明文。所有操作按 owner_id 隔离。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user_id
from app.core.database import get_db
from app.models.erp_connector import ERPConnectorConfig
from app.security import decrypt_text, encrypt_text
from app.services.connectors import erp as connector

router = APIRouter(dependencies=[Depends(get_current_user_id)])


class ConnectorCreateRequest(BaseModel):
    alias: str
    db_type: str = "postgresql"
    host: Optional[str] = None
    port: Optional[int] = None
    database: str = ""
    # schema 与 pydantic BaseModel.schema 同名，改用 db_schema（对外 JSON 仍可用 alias）
    db_schema: Optional[str] = Field(default=None, alias="schema")
    user: Optional[str] = None
    password: str = ""
    dsn_override: Optional[str] = None
    allowed_tables: list[str] = []
    field_map: dict[str, Any] = {}
    row_limit: int = 200
    connect_timeout: int = 10


class ConnectorUpdateRequest(BaseModel):
    alias: Optional[str] = None
    db_type: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    db_schema: Optional[str] = Field(default=None, alias="schema")
    user: Optional[str] = None
    # 不传 = 保持原密码；传空串 = 清空
    password: Optional[str] = None
    dsn_override: Optional[str] = None
    allowed_tables: Optional[list[str]] = None
    field_map: Optional[dict[str, Any]] = None
    row_limit: Optional[int] = None
    connect_timeout: Optional[int] = None
    is_active: Optional[bool] = None


class QueryRequest(BaseModel):
    resource: str
    filters: dict[str, Any] = {}
    columns: list[str] = []
    limit: Optional[int] = None


def _mask_password(pw: str | None) -> str:
    if not pw:
        return ""
    if len(pw) <= 2:
        return "*" * len(pw)
    return f"{pw[0]}{'*' * (len(pw) - 2)}{pw[-1]}"


def _to_dict(cfg: ERPConnectorConfig) -> dict[str, Any]:
    """脱敏输出：只暴露密码是否存在与掩码。"""
    return {
        "id": cfg.id,
        "alias": cfg.alias,
        "db_type": cfg.db_type,
        "host": cfg.host,
        "port": cfg.port,
        "database": cfg.database,
        "schema": cfg.schema,
        "user": cfg.user,
        "has_password": bool(cfg.password_enc),
        "password_masked": _mask_password(decrypt_text(cfg.password_enc) if cfg.password_enc else ""),
        "has_dsn_override": bool(cfg.dsn_override),
        "allowed_tables": cfg.allowed_tables or [],
        "field_map": cfg.field_map or {},
        "row_limit": cfg.row_limit,
        "connect_timeout": cfg.connect_timeout,
        "is_active": bool(cfg.is_active),
    }


async def _load_owned(db: AsyncSession, conn_id: str, user_id: str) -> ERPConnectorConfig:
    cfg = await db.get(ERPConnectorConfig, conn_id)
    if not cfg or cfg.owner_id != user_id:
        raise HTTPException(404, "连接器不存在")
    return cfg


@router.get("")
async def list_connectors(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> list[dict[str, Any]]:
    rows = await db.execute(
        select(ERPConnectorConfig).where(ERPConnectorConfig.owner_id == user_id)
        .order_by(ERPConnectorConfig.alias)
    )
    return [_to_dict(c) for c in rows.scalars().all()]


@router.post("")
async def create_connector(
    data: ConnectorCreateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    if data.db_type not in connector.SUPPORTED_DB_TYPES and not data.dsn_override:
        raise HTTPException(400, f"db_type 需为 {sorted(connector.SUPPORTED_DB_TYPES)} 之一，或提供 dsn_override")
    exists = await db.scalar(
        select(ERPConnectorConfig).where(
            ERPConnectorConfig.owner_id == user_id, ERPConnectorConfig.alias == data.alias
        )
    )
    if exists:
        raise HTTPException(400, "同名下已存在连接器")

    now = datetime.now()
    cfg = ERPConnectorConfig(
        owner_id=user_id,
        alias=data.alias.strip(),
        db_type=data.db_type,
        host=data.host,
        port=data.port,
        database=data.database,
        schema=data.db_schema,
        user=data.user,
        password_enc=encrypt_text(data.password) if data.password else "",
        dsn_override=data.dsn_override,
        allowed_tables=[t for t in data.allowed_tables if isinstance(t, str)],
        field_map=data.field_map or {},
        row_limit=data.row_limit,
        connect_timeout=data.connect_timeout,
        created_at=now,
        updated_at=now,
    )
    db.add(cfg)
    await db.commit()
    await db.refresh(cfg)
    return _to_dict(cfg)


@router.patch("/{conn_id}")
async def update_connector(
    conn_id: str,
    data: ConnectorUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    cfg = await _load_owned(db, conn_id, user_id)
    payload = data.model_dump(exclude_unset=True)

    # 请求里的 db_schema 对应列名 schema（避开 BaseModel.schema 遮蔽）
    if "db_schema" in payload:
        payload["schema"] = payload.pop("db_schema")

    for field in ("alias", "db_type", "host", "port", "database", "schema", "user",
                  "dsn_override", "allowed_tables", "field_map", "row_limit",
                  "connect_timeout", "is_active"):
        if field in payload:
            setattr(cfg, field, payload[field])

    if "password" in payload and payload["password"] is not None:
        cfg.password_enc = encrypt_text(payload["password"]) if payload["password"] else ""

    cfg.updated_at = datetime.now()
    await db.commit()
    await db.refresh(cfg)
    # 改了连接参数 → 丢弃缓存引擎，下次按新配置重建
    await connector.reset_engine(cfg.id)
    return _to_dict(cfg)


@router.delete("/{conn_id}")
async def delete_connector(
    conn_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    cfg = await _load_owned(db, conn_id, user_id)
    await db.delete(cfg)
    await db.commit()
    await connector.reset_engine(cfg.id)
    return {"ok": True}


@router.post("/{conn_id}/test")
async def test_connector(
    conn_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    cfg = await _load_owned(db, conn_id, user_id)
    ok, err = await connector.test_connection(cfg)
    return {"ok": ok, "error": err}


@router.post("/{conn_id}/query")
async def query_connector(
    conn_id: str,
    data: QueryRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    """只读试查：用于画布调试 / 预览脱敏后的行。"""
    cfg = await _load_owned(db, conn_id, user_id)
    try:
        rows = await connector.read(
            cfg, resource=data.resource, filters=data.filters,
            columns=data.columns, limit=data.limit,
        )
    except connector.ConnectorError as exc:
        raise HTTPException(400, str(exc))
    return {"resource": data.resource, "count": len(rows), "rows": rows}
