"""外部只读数据源（ERP）连接器。

设计要点：
- **只读**：执行侧只拼 `SELECT ... WHERE <等值> LIMIT n`；filter 的值一律走
  绑定参数，绝不字符串插值；表名按白名单校验、列名按标识符正则校验；
  Postgres 连接层再叠加 `default_transaction_read_only=true`。硬隔离仍依赖
  对方下发只读账号。
- **凭证安全**：密码 Fernet 密文落库，只在内存里短暂解密拼进 URL。
- **归属隔离**：调用方须带上 owner_id，与连接器配置匹配才放行。
- **脱敏**：返回前按 field_map 套用（rename / pii 掩码 / drop），确保进入
  下游 PiAgent 上下文的数据已去敏。

引擎按连接器缓存（key 含 updated_at，改配置即失效重建），避免每次查询都
新建连接池。
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote_plus

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core.config import settings
from app.core.logging import get_logger
from app.models.erp_connector import ERPConnectorConfig
from app.security import decrypt_text

logger = get_logger("erp_connector")

# 合法 SQL 标识符：字母/数字/下划线，且不以数字开头。表名、列名都过这道闸。
_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

SUPPORTED_DB_TYPES = {"postgresql", "sqlite"}


class ConnectorError(Exception):
    """连接器层的可读错误（不向上抛栈，转成结构化错误返回给节点）。"""


# ---------------------------------------------------------------------------
# 连接串与引擎
# ---------------------------------------------------------------------------

def build_url(cfg: ERPConnectorConfig) -> str:
    """据配置拼出 SQLAlchemy 异步连接串。"""
    if cfg.dsn_override:
        return cfg.dsn_override

    db_type = (cfg.db_type or "").lower()
    if db_type == "sqlite":
        # 只读场景仍用文件库；database 为文件路径
        return f"sqlite+aiosqlite:///{cfg.database}"
    if db_type == "postgresql":
        password = decrypt_text(cfg.password_enc) if cfg.password_enc else ""
        host = cfg.host or "localhost"
        port = cfg.port or 5432
        user = quote_plus(cfg.user or "")
        pwd = quote_plus(password)
        return f"postgresql+asyncpg://{user}:{pwd}@{host}:{port}/{cfg.database}"
    raise ConnectorError(f"暂不支持的数据库类型：{db_type}（可选 postgresql / sqlite）")


def _connect_args(cfg: ERPConnectorConfig) -> dict[str, Any]:
    db_type = (cfg.db_type or "").lower()
    timeout = max(1, int(cfg.connect_timeout or settings.CONNECTOR_TIMEOUT_SECONDS))
    if db_type == "postgresql":
        # 连接层强制只读事务；即便代码有疏漏也无法写库
        return {
            "timeout": timeout,
            "server_settings": {"default_transaction_read_only": "true"},
        }
    return {}


class _EngineCache:
    def __init__(self) -> None:
        self._engines: dict[str, AsyncEngine] = {}

    def get(self, cfg: ERPConnectorConfig) -> AsyncEngine:
        stamp = cfg.updated_at.isoformat() if cfg.updated_at else "na"
        key = f"{cfg.id}@{stamp}"
        engine = self._engines.get(key)
        if engine is None:
            engine = create_async_engine(
                build_url(cfg),
                connect_args=_connect_args(cfg),
                pool_pre_ping=True,
                future=True,
            )
            self._engines[key] = engine
            logger.info("已建立连接器引擎 conn=%s db_type=%s", cfg.id, cfg.db_type)
        return engine

    async def dispose_for(self, conn_id: str) -> None:
        for key in [k for k in self._engines if k.split("@", 1)[0] == conn_id]:
            engine = self._engines.pop(key)
            await engine.dispose()


_engine_cache = _EngineCache()


async def reset_engine(conn_id: str) -> None:
    """配置变更 / 删除后丢弃缓存引擎（改密码等）。"""
    await _engine_cache.dispose_for(conn_id)


# ---------------------------------------------------------------------------
# 校验与 SQL 组装
# ---------------------------------------------------------------------------

def _check_table_whitelist(cfg: ERPConnectorConfig, table: str) -> str:
    if not _IDENT_RE.match(table or ""):
        raise ConnectorError(f"非法表名：{table!r}")
    allowed = [t for t in (cfg.allowed_tables or []) if isinstance(t, str)]
    lowered = {t.lower(): t for t in allowed}
    if table.lower() not in lowered:
        raise ConnectorError(f"表 {table!r} 不在白名单内，拒绝访问")
    return lowered[table.lower()]  # 返回白名单里的规范写法


def _check_ident(name: str) -> str:
    if not _IDENT_RE.match(name or ""):
        raise ConnectorError(f"非法标识符：{name!r}")
    return name


def _qualified_table(cfg: ERPConnectorConfig, table: str) -> str:
    if (cfg.db_type or "").lower() == "postgresql" and cfg.schema and _IDENT_RE.match(cfg.schema):
        return f"{cfg.schema}.{table}"
    return table


def _build_select(cfg: ERPConnectorConfig, table: str, columns: list[str],
                  filters: dict[str, Any], limit: int) -> tuple[str, dict[str, Any]]:
    cols = ", ".join(_check_ident(c) for c in columns) if columns else "*"
    where_parts: list[str] = []
    params: dict[str, Any] = {"__limit": int(limit)}
    for i, (key, value) in enumerate((filters or {}).items()):
        col = _check_ident(key)
        ph = f"p{i}"
        where_parts.append(f"{col} = :{ph}")
        params[ph] = value
    sql = f"SELECT {cols} FROM {_qualified_table(cfg, table)}"
    if where_parts:
        sql += " WHERE " + " AND ".join(where_parts)
    sql += " LIMIT :__limit"
    return sql, params


# ---------------------------------------------------------------------------
# 脱敏
# ---------------------------------------------------------------------------

def _mask_pii(value: Any) -> str:
    s = "" if value is None else str(value)
    if len(s) <= 2:
        return "*" * len(s)
    return f"{s[0]}{'*' * (len(s) - 2)}{s[-1]}"


def _apply_field_map(row: dict[str, Any], field_map: dict[str, Any]) -> dict[str, Any]:
    if not field_map:
        return dict(row)
    out: dict[str, Any] = {}
    for key, value in row.items():
        spec = field_map.get(key)
        if not isinstance(spec, dict):
            out[key] = value
            continue
        mask = str(spec.get("mask", "none")).lower()
        alias = str(spec.get("as") or key)
        if mask == "drop":
            continue
        if mask == "pii":
            out[alias] = _mask_pii(value)
            continue
        out[alias] = value
    return out


# ---------------------------------------------------------------------------
# 对外能力
# ---------------------------------------------------------------------------

def resolve_limit(cfg: ERPConnectorConfig, requested: int | None) -> int:
    base = int(requested or cfg.row_limit or settings.CONNECTOR_DEFAULT_ROW_LIMIT)
    return max(1, min(base, settings.CONNECTOR_MAX_ROW_LIMIT))


async def read(
    cfg: ERPConnectorConfig,
    *,
    resource: str,
    filters: dict[str, Any] | None = None,
    columns: list[str] | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """按白名单与脱敏规则读取一个资源（表）的若干行。

    只做等值过滤 + LIMIT；越权表 / 非法标识符 / 非支持库都抛 ConnectorError。
    """
    if not settings.EXTERNAL_CONNECTORS_ENABLED:
        raise ConnectorError("外部数据连接器未启用（EXTERNAL_CONNECTORS_ENABLED=false）")
    if not cfg.is_active:
        raise ConnectorError("连接器已停用")

    table = _check_table_whitelist(cfg, resource)
    row_limit = resolve_limit(cfg, limit)
    sql, params = _build_select(cfg, table, columns or [], filters or {}, row_limit)

    engine = _engine_cache.get(cfg)
    async with engine.connect() as conn:
        result = await conn.execute(text(sql), params)
        rows = [dict(m) for m in result.mappings().all()]

    field_map = cfg.field_map or {}
    masked = [_apply_field_map(r, field_map) for r in rows]
    logger.info(
        "erp_read conn=%s table=%s rows=%d limit=%d", cfg.id, table, len(masked), row_limit
    )
    return masked


async def test_connection(cfg: ERPConnectorConfig) -> tuple[bool, str | None]:
    """连通性测试：SELECT 1。返回 (ok, error)。"""
    try:
        engine = _engine_cache.get(cfg)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True, None
    except Exception as exc:  # noqa: BLE001 - 汇总成给用户看的单行原因
        logger.warning("连接器测试失败 conn=%s err=%s", cfg.id, exc)
        return False, f"{type(exc).__name__}: {exc}"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
