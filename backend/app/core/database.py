"""
数据库 - PostgreSQL + SQLite 备用方案
"""
import os
from pathlib import Path

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from sqlalchemy.pool import StaticPool

from .config import settings
from .seed import seed_templates
from .base import Base
# 显式导入全部模型，确保 create_all 能建出所有表（含后续新增的表）
import app.models  # noqa: F401

# 数据库状态
USE_MEMORY_MODE = False

# 异步引擎和会话（延迟初始化）
_engine = None
_async_session = None


def _resolve_sqlite_url(db_url: str) -> str:
    """定出 SQLite 的连接串。

    **必须尊重 ``DATABASE_URL`` 里的路径。** 早先这里无条件用模块位置推算
    ``<backend>/agentflow.db``，把连接串里的路径整个丢掉 —— 后果是
    ``DATABASE_URL=sqlite+aiosqlite:////data/agentflow.db`` 在容器里形同虚设：

      * alembic 迁移按 ``settings.DATABASE_URL`` 写 ``/data/agentflow.db``；
      * 应用自己读写 ``/app/agentflow.db``；
      * 于是**存在两个库**，迁移看起来成功、功能一切正常，直到容器重建
        （`docker compose down` 或重新 build）—— 用户、Agent、对话记录全没了，
        而日志里没有任何异常可循。

    只有「没配连接串」时才退回原先那个按模块位置推算的路径，保持本地开发的
    零配置行为不变。
    """
    if "sqlite" in db_url:
        return db_url

    backend_dir = Path(__file__).resolve().parents[2]
    return f"sqlite+aiosqlite:///{backend_dir / 'agentflow.db'}"


def _ensure_sqlite_parent(sqlite_url: str) -> None:
    """建好 SQLite 文件所在目录，否则首次连接会因目录不存在而失败。"""
    database = make_url(sqlite_url).database
    if not database or database == ":memory:":
        return
    Path(database).expanduser().parent.mkdir(parents=True, exist_ok=True)


def _init_engine():
    """初始化数据库引擎"""
    global _engine, USE_MEMORY_MODE
    
    if _engine is not None:
        return _engine
    
    db_url = settings.DATABASE_URL
    
    # 检查是否使用 SQLite（备用方案）
    if "sqlite" in db_url or not db_url:
        USE_MEMORY_MODE = False
        sqlite_url = _resolve_sqlite_url(db_url)
        _ensure_sqlite_parent(sqlite_url)
        _engine = create_async_engine(
            sqlite_url,
            echo=settings.DEBUG,
            poolclass=StaticPool,
            connect_args={"check_same_thread": False}
        )
        # 打印引擎**真实**的 URL，而不是我们以为的那个 —— 上面那个 bug 能藏
        # 那么久，正是因为日志打的是推算值，与实际情况无从对照。
        print(f"Using SQLite database: {_engine.url.database}")
        return _engine
    
    # 尝试使用 PostgreSQL
    try:
        _engine = create_async_engine(
            db_url,
            echo=settings.DEBUG,
            pool_pre_ping=True,
        )
        print("Using PostgreSQL database")
        return _engine
    except Exception as e:
        print(f"PostgreSQL not available: {e}")
        USE_MEMORY_MODE = True
        # 使用内存 SQLite（仅演示用）
        _engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            echo=settings.DEBUG,
            connect_args={"check_same_thread": False}
        )
        print("Using in-memory database (data will not persist!)")
        return _engine


def get_engine():
    """获取数据库引擎"""
    return _init_engine()


def get_async_session_factory():
    """获取会话工厂"""
    global _async_session
    if _async_session is None:
        engine = get_engine()
        _async_session = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_session


async def get_db():
    """获取数据库会话"""
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """初始化数据库。

    说明：这里用 ``Base.metadata.create_all`` 直接建表，适用于本地开发与测试
    （测试用内存 SQLite，每次都要重建）。**已存在的库做结构变更请走 Alembic 迁移**
    （``backend/migrations/``），不要依赖 create_all —— 它只会新建缺失的表，
    不会修改已有表的列/约束。新库用 ``alembic upgrade head`` 建，旧库用
    ``alembic stamp head`` 标记基线。
    """
    global USE_MEMORY_MODE
    
    engine = get_engine()
    
    try:
        # 创建所有表
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        # 尝试初始化 pgvector（仅 PostgreSQL）
        if not USE_MEMORY_MODE and "postgresql" in str(settings.DATABASE_URL):
            try:
                async with engine.begin() as conn:
                    await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            except Exception:
                pass  # pgvector 可能不可用
        
        # 把实际路径打出来。只说 "File-based (persistent)" 是不够的 ——
        # 曾经应用写 /app/agentflow.db、迁移写 /data/agentflow.db，两边都
        # 打着一句「已持久化」，而真正该持久化的那个文件从头到尾没人碰过。
        if USE_MEMORY_MODE:
            mode = "Memory (NOT persistent)"
        else:
            mode = f"File-based (persistent) -> {engine.url.database}"
        print(f"Database initialized: {mode}")

        # 种子数据
        async with get_async_session_factory()() as session:
            await seed_templates(session)

        return True
        
    except Exception as e:
        print(f"Database init error: {e}")
        return False


# 兼容性别名
async_session = get_async_session_factory
