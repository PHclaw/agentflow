"""
数据库 - PostgreSQL + SQLite 备用方案
"""
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from sqlalchemy.pool import StaticPool

from .config import settings
from .seed import seed_templates
from .base import Base

# 数据库状态
USE_MEMORY_MODE = False

# 异步引擎和会话（延迟初始化）
_engine = None
_async_session = None


def _init_engine():
    """初始化数据库引擎"""
    global _engine, USE_MEMORY_MODE
    
    if _engine is not None:
        return _engine
    
    db_url = settings.DATABASE_URL
    
    # 检查是否使用 SQLite（备用方案）
    if "sqlite" in db_url or not db_url:
        USE_MEMORY_MODE = False
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "agentflow.db")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        sqlite_url = f"sqlite+aiosqlite:///{db_path}"
        _engine = create_async_engine(
            sqlite_url,
            echo=settings.DEBUG,
            poolclass=StaticPool,
            connect_args={"check_same_thread": False}
        )
        print(f"Using SQLite database: {db_path}")
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
    """初始化数据库"""
    global USE_MEMORY_MODE

    engine = get_engine()

    try:
        # 先初始化 pgvector 扩展（仅 PostgreSQL）
        if not USE_MEMORY_MODE and "postgresql" in str(settings.DATABASE_URL):
            try:
                async with engine.begin() as conn:
                    await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                print("pgvector extension initialized")
            except Exception as e:
                print(f"Warning: Could not initialize pgvector: {e}")

        # 创建所有表
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        mode = "Memory (NOT persistent)" if USE_MEMORY_MODE else "File-based (persistent)"
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
