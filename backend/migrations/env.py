"""Alembic 迁移运行环境。

设计要点：
1. 连接串复用 ``app.core.config.settings.DATABASE_URL``，与 uvicorn 用同一份
   ``.env``，避免 alembic 与实际运行时连到不同库。
2. 使用异步引擎执行迁移（项目统一使用 SQLAlchemy asyncio）。
3. SQLite 下开启 ``render_as_batch``，否则无法通过迁移修改列/约束。
4. 导入 ``app.models`` 以确保全部模型注册进 ``Base.metadata``，
   否则 autogenerate 会把已有表误判为「需要删除」。
"""
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

import app.models  # noqa: F401  确保所有模型注册到 Base.metadata
from app.core.base import Base
from app.core.config import settings

config = context.config

# 连接串以 settings 为准
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# SQLite 不支持大部分 ALTER，需要 batch 模式重建表
_RENDER_AS_BATCH = settings.DATABASE_URL.startswith("sqlite")


def run_migrations_offline() -> None:
    """离线模式：只生成 SQL，不连接数据库。"""
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=_RENDER_AS_BATCH,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=_RENDER_AS_BATCH,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """在线模式：实际连接数据库执行迁移。"""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
