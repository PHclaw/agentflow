"""
测试配置
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from httpx import AsyncClient

from app.core.database import Base, get_db
from app.models.user import User
from app.models.agent import Agent, ChatSession, KnowledgeBase
from app.main import app
from app.api.auth import create_token, get_password_hash


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


@pytest.fixture(autouse=True)
def _disable_real_db_refresh():
    """停掉中间件「用真实数据库刷新大模型配置快照」。

    ``main.refresh_llm_config`` 跑在依赖解析之前，只能自己开连接，
    绕开了 ``get_db`` 的测试覆盖 —— 它会把**真实库**里的配置写进全局快照。
    结果是测试库里刚建的配置永远拿不到 ``is_effective`` 标记，
    断言「生效配置是哪个」的用例全部失真（而且不报错，是静默的错值）。
    """
    from app.services import llm_config as _llm_cfg

    _llm_cfg.use_test_db_for_tests()
    yield


@pytest.fixture(autouse=True)
def _auth_email_defaults(monkeypatch):
    """默认关闭邮箱验证码校验。

    注册接口现在要带验证码，但既有用例（test_auth / test_knowledge /
    test_integration 等 9 处）只是拿它换一个 token，逐个改造成「先取码再注册」
    收益很低。这里统一关掉，专门验证验证码流程的用例
    （tests/test_auth_email_code.py）自行打开开关。
    """
    from app.core.config import settings
    from app.core.rate_limiter import get_limiter
    from app.services import verification

    monkeypatch.setattr(settings, "REQUIRE_EMAIL_CODE", False, raising=False)
    # 强制走内存后端，避免每个用例都去尝试连一次 Redis
    verification.use_memory_for_tests()
    # 限流器是全局单例，计数不清理会跨用例累积
    get_limiter().reset()
    yield
    verification.reset_for_tests()
    get_limiter().reset()


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
        email="test@example.com",
        password_hash=get_password_hash("testpassword"),
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
        user_id=test_user.external_id,
        name="Test Agent",
        description="A test agent",
        model_config={
            "provider": "openai",
            "model": "gpt-4o-mini",
        },
        # 空工作流：默认的 Agent 就是这种状态，/chat 会走 IntegratedAgentRuntime。
        # 配了工作流的 Agent 会改走 workflow_runtime，那条分支在 test_chat.py 里
        # 用专门的 Agent 覆盖，避免这里影响其他依赖 test_agent 的用例。
        workflow_definition={
            "nodes": [],
            "edges": [],
        },
    )
    async_db.add(agent)
    await async_db.commit()
    await async_db.refresh(agent)
    return agent


@pytest.fixture
async def pro_subscription(async_db: AsyncSession, test_user: User):
    """把测试用户升级到专业版。

    免费版只允许 1 个 Agent，需要多个 Agent 的用例必须先升级，
    否则第二个 Agent 会被配额拦下 —— 那正是我们要的行为，
    但不该让它污染与配额无关的用例。
    """
    from sqlalchemy import select

    from app.models.subscription import PlanType, Subscription

    sub = await async_db.scalar(
        select(Subscription).where(Subscription.user_id == test_user.id)
    )
    if sub is None:
        sub = Subscription(
            user_id=test_user.id, plan=PlanType.PRO.value, status="active"
        )
        async_db.add(sub)
    else:
        sub.plan = PlanType.PRO.value
        sub.status = "active"
    await async_db.commit()
    await async_db.refresh(sub)
    return sub


@pytest.fixture
async def admin_headers(async_db: AsyncSession, test_user: User) -> dict:
    """把 test_user 提升为管理员，并返回管理员身份的请求头。

    和 auth_headers 指向同一个账号，所以同一个用例里不要两个都用 ——
    用哪个决定这次请求是管理员还是普通用户。
    """
    from app.models.user import UserRole

    test_user.role = UserRole.ADMIN.value
    await async_db.commit()
    await async_db.refresh(test_user)
    return {"Authorization": f"Bearer {create_token(test_user.external_id)}"}


@pytest.fixture
async def test_knowledge_base(
    async_db: AsyncSession, test_user: User
) -> KnowledgeBase:
    """创建测试知识库

    必须带上user_id：知识库现在按账号隔离，接口会校验归属。
    """
    kb = KnowledgeBase(
        id="test-kb-001",
        agent_id="test-agent-001",
        user_id=test_user.external_id,
        name="Test KB",
        description="A test knowledge base",
    )
    async_db.add(kb)
    await async_db.commit()
    await async_db.refresh(kb)
    return kb


@pytest.fixture
async def async_client(async_db: AsyncSession):
    """异步 HTTP 客户端"""
    from app.core.database import get_db
    from httpx import ASGITransport
    
    async def override_get_db():
        yield async_db
    
    app.dependency_overrides[get_db] = override_get_db
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    
    app.dependency_overrides.clear()


@pytest.fixture
async def auth_headers(test_user: User) -> dict:
    """认证请求头"""
    token = create_token(user_id=test_user.external_id)
    return {"Authorization": f"Bearer {token}"}
