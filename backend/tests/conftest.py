"""
测试配置
"""
import pytest
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from ..models.base import Base
from ..models.user import User
from ..models.agent import Agent, ChatSession


# 测试数据库 URL
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
TEST_SYNC_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def async_db():
    """异步数据库会话"""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with async_session() as session:
        yield session
    
    await engine.dispose()


@pytest.fixture(scope="function")
def sync_db():
    """同步数据库会话"""
    engine = create_engine(TEST_SYNC_DATABASE_URL, echo=False)
    Base.metadata.create_all(engine)
    
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    yield session
    
    session.close()
    engine.dispose()


@pytest.fixture
async def test_user(async_db: AsyncSession) -> User:
    """创建测试用户"""
    user = User(
        id="test-user-001",
        email="test@example.com",
        username="testuser",
        hashed_password="hashed_password",
        is_active=True,
    )
    async_db.add(user)
    await async_db.commit()
    await async_db.refresh(user)
    return user


@pytest.fixture
async def test_agent(async_db: AsyncSession, test_user: User) -> Agent:
    """创建测试 Agent"""
    agent = Agent(
        id="test-agent-001",
        user_id=test_user.id,
        name="Test Agent",
        description="A test agent",
        model_config={
            "provider": "openai",
            "model": "gpt-4o-mini",
        },
        temperature=0.7,
        template="qa",
    )
    async_db.add(agent)
    await async_db.commit()
    await async_db.refresh(agent)
    return agent
