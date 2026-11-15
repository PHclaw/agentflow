"""
订阅配额（Entitlement）测试。

覆盖 P0 的核心承诺：套餐分级**真正生效**。
此前 Subscription.can_create_agent() / can_send_message() 是死代码，
注册不建订阅、创建 Agent 和发消息也从不校验，这些用例把它钉住。
"""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.agent import Agent
from app.models.subscription import PlanType, Subscription
from app.models.user import User
from app.services.entitlement import (
    Resource,
    consume,
    ensure_subscription,
    release,
)

#: 创建 Agent 的最小请求体。AgentCreate 只有 name 是必填。
AGENT_BODY = {"name": "测试 Agent"}


def _make_agent(db: AsyncSession, user: User, name: str, agent_id: str) -> Agent:
    agent = Agent(
        id=agent_id,
        user_id=user.external_id,
        name=name,
        description="",
        workflow_definition={"nodes": [], "edges": []},
    )
    db.add(agent)
    return agent


async def _sub_of(db: AsyncSession, user: User):
    return await db.scalar(
        select(Subscription).where(Subscription.user_id == user.id)
    )


class TestSubscriptionLifecycle:
    """订阅记录的创建时机。"""

    @pytest.mark.asyncio
    async def test_register_creates_free_subscription(
        self, async_client: AsyncClient, async_db: AsyncSession
    ):
        """注册即开通免费订阅。

        这是原先最要命的漏洞：auth.py 只建 User，不建 Subscription，
        导致每个用户都没有订阅记录，所有配额判定都无从谈起。
        """
        email = f"sub-{uuid.uuid4().hex[:8]}@test.com"
        resp = await async_client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "SecurePass123!", "nickname": "Sub"},
        )
        assert resp.status_code == 200, resp.text

        user = await async_db.scalar(select(User).where(User.email == email))
        sub = await _sub_of(async_db, user)
        assert sub is not None, "注册后必须立刻有订阅记录"
        assert sub.plan == PlanType.FREE.value
        assert sub.status == "active"

    @pytest.mark.asyncio
    async def test_lazy_creates_subscription_for_legacy_user(
        self, async_client: AsyncClient, async_db: AsyncSession,
        test_user: User, auth_headers: dict,
    ):
        """老用户（直接建库、没有订阅记录）也能被补上。

        只靠注册时创建不够：功能上线前就注册的用户永远没有订阅，
        一进产品就会被判定成超额。
        """
        assert await _sub_of(async_db, test_user) is None

        await async_client.get(
            "/api/v1/billing/subscription", headers=auth_headers
        )

        sub = await _sub_of(async_db, test_user)
        assert sub is not None
        assert sub.plan == PlanType.FREE.value

    @pytest.mark.asyncio
    async def test_agents_used_initialized_from_real_count(
        self, async_db: AsyncSession, test_user: User
    ):
        """agents_used 用真实存量初始化，而不是从 0 开始。

        否则老用户明明有 3 个 Agent，界面却显示 0/1，
        而且因为 0 < 1 还能再建一个，额度形同虚设。
        """
        for i in range(3):
            _make_agent(async_db, test_user, f"Old {i}", f"old-agent-{i}")
        await async_db.commit()

        sub = await ensure_subscription(async_db, test_user.external_id)

        assert sub.agents_used == 3


class TestAgentQuota:
    """Agent 数量配额。"""

    @pytest.mark.asyncio
    async def test_free_plan_blocks_second_agent(
        self, async_client: AsyncClient, test_user: User, auth_headers: dict
    ):
        """免费版建第二个 Agent 必须被拦下，并返回可操作的错误信息。"""
        first = await async_client.post(
            "/api/v1/agents", json=AGENT_BODY, headers=auth_headers
        )
        assert first.status_code == 200

        second = await async_client.post(
            "/api/v1/agents", json=AGENT_BODY, headers=auth_headers
        )
        assert second.status_code == 402

        body = second.json()
        assert body["error"] == "QUOTA_EXCEEDED"
        assert body["resource"] == "agents"
        assert body["used"] == 1
        assert body["limit"] == settings.FREE_AGENTS
        # 要告诉用户「升级能得到什么」，而不是一句干巴巴的「配额不足」
        assert body["next_limit"] == settings.PRO_AGENTS
        assert str(settings.PRO_AGENTS) in body["message"]

    @pytest.mark.asyncio
    async def test_pro_plan_allows_more_agents(
        self, async_client: AsyncClient, auth_headers: dict, pro_subscription
    ):
        """专业版的额度高于免费版。"""
        created = 0
        for i in range(settings.PRO_AGENTS):
            resp = await async_client.post(
                "/api/v1/agents", json={"name": f"Pro {i}"}, headers=auth_headers
            )
            if resp.status_code == 200:
                created += 1
        assert created == settings.PRO_AGENTS

    @pytest.mark.asyncio
    async def test_deleting_agent_frees_the_slot(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """删除 Agent 必须释放名额。

        agents_used 记的是「当前存量」而不是历史累计，
        否则用户删掉 Agent 后依然无法新建，会以为是产品 bug。
        """
        first = await async_client.post(
            "/api/v1/agents", json=AGENT_BODY, headers=auth_headers
        )
        assert first.status_code == 200
        agent_id = first.json()["id"]

        blocked = await async_client.post(
            "/api/v1/agents", json=AGENT_BODY, headers=auth_headers
        )
        assert blocked.status_code == 402

        deleted = await async_client.delete(
            f"/api/v1/agents/{agent_id}", headers=auth_headers
        )
        assert deleted.status_code == 200

        again = await async_client.post(
            "/api/v1/agents", json=AGENT_BODY, headers=auth_headers
        )
        assert again.status_code == 200, "删掉 Agent 后应该能再建"

    @pytest.mark.asyncio
    async def test_over_quota_legacy_user_can_still_delete(
        self, async_client: AsyncClient, async_db: AsyncSession,
        test_user: User, auth_headers: dict,
    ):
        """超额存量用户：不能新建，但可以删除（只限增量，不锁存量）。"""
        for i in range(2):
            _make_agent(async_db, test_user, f"Legacy {i}", f"legacy-{i}")
        await async_db.commit()

        blocked = await async_client.post(
            "/api/v1/agents", json=AGENT_BODY, headers=auth_headers
        )
        assert blocked.status_code == 402
        assert blocked.json()["used"] == 2
        assert blocked.json()["limit"] == settings.FREE_AGENTS

        removed = await async_client.delete(
            "/api/v1/agents/legacy-0", headers=auth_headers
        )
        assert removed.status_code == 200

        sub = await _sub_of(async_db, test_user)
        assert sub.agents_used == 1


class TestMessageQuota:
    """消息配额。"""

    @pytest.mark.asyncio
    async def test_message_quota_blocks_chat(
        self, async_client: AsyncClient, async_db: AsyncSession,
        test_user: User, test_agent: Agent, auth_headers: dict,
    ):
        """消息额度用尽后，对话要被拦在模型调用之前。"""
        sub = await ensure_subscription(async_db, test_user.external_id)
        sub.messages_used = settings.FREE_MESSAGES
        await async_db.commit()

        resp = await async_client.post(
            f"/api/v1/chat/{test_agent.id}",
            json={"message": "hello"},
            headers=auth_headers,
        )
        assert resp.status_code == 402

        body = resp.json()
        assert body["error"] == "QUOTA_EXCEEDED"
        assert body["resource"] == "messages"
        assert body["limit"] == settings.FREE_MESSAGES

    @pytest.mark.asyncio
    async def test_pro_plan_gets_more_messages(
        self, async_client: AsyncClient, async_db: AsyncSession,
        test_user: User, test_agent: Agent, auth_headers: dict, pro_subscription,
    ):
        """专业版的消息额度高于免费版，同样的用量下不会被拦。"""
        sub = await ensure_subscription(async_db, test_user.external_id)
        sub.messages_used = settings.FREE_MESSAGES
        await async_db.commit()

        resp = await async_client.post(
            f"/api/v1/chat/{test_agent.id}",
            json={"message": "hello"},
            headers=auth_headers,
        )
        # 没到 pro 的上限，不该被配额拦下（可能因模型未配而报 503，但不是 402）
        assert resp.status_code != 402


class TestBillingApi:
    """计费接口返回的必须是真实数据。"""

    @pytest.mark.asyncio
    async def test_subscription_endpoint_reports_real_usage(
        self, async_client: AsyncClient, test_user: User, auth_headers: dict
    ):
        """原先没有订阅记录时返回全 0 的假数据，现在要反映真实用量。"""
        created = await async_client.post(
            "/api/v1/agents", json=AGENT_BODY, headers=auth_headers
        )
        assert created.status_code == 200

        resp = await async_client.get(
            "/api/v1/billing/subscription", headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()

        assert data["plan"] == "free"
        assert data["agents_used"] == 1
        assert data["agents_limit"] == settings.FREE_AGENTS
        assert data["messages_used"] == 0
        assert data["messages_limit"] == settings.FREE_MESSAGES
        # 周期字段必须填上，前端才能显示「下次重置时间」
        assert data["current_period_end"] is not None

    def test_plans_limits_come_from_settings(self):
        """套餐额度必须和配置同源。

        前端 SettingsPage 曾经把免费版写成「3 个 Agent / 1000 条消息」，
        和配置里的 1 / 100 对不上，用户看到的额度和实际能用的不是一回事。
        落地页更夸张：写的是「无限 Agent / 100,000 次对话」。
        """
        from app.api.billing import PLANS

        for code, agents, messages in (
            ("free", settings.FREE_AGENTS, settings.FREE_MESSAGES),
            ("pro", settings.PRO_AGENTS, settings.PRO_MESSAGES),
            ("team", settings.TEAM_AGENTS, settings.TEAM_MESSAGES),
        ):
            assert PLANS[code]["agents"] == agents
            assert PLANS[code]["messages"] == messages
            # features 文案里的数字也要跟着额度走
            assert f"{agents}个Agent" in PLANS[code]["features"]
            assert f"{messages}条消息/月" in PLANS[code]["features"]


class TestPlanTiers:
    """不同档位必须拿到**不同**的额度。

    这里盯的是一个真实存在过的 bug：额度用 ``is_pro`` 二分计算，
    而 ``is_pro`` 对 pro 与 team **都返回真**，于是团队版拿到的是专业版的额度，
    套餐页却写着另一个数字。
    """

    @pytest.mark.asyncio
    async def test_team_gets_more_than_pro(
        self, async_client: AsyncClient, async_db: AsyncSession,
        test_user: User, auth_headers: dict, pro_subscription,
    ):
        pro_usage = (await async_client.get(
            "/api/v1/billing/subscription", headers=auth_headers
        )).json()

        sub = await ensure_subscription(async_db, test_user.external_id)
        sub.plan = PlanType.TEAM.value
        await async_db.commit()

        team_usage = (await async_client.get(
            "/api/v1/billing/subscription", headers=auth_headers
        )).json()

        assert pro_usage["plan"] == PlanType.PRO.value
        assert team_usage["plan"] == PlanType.TEAM.value
        assert team_usage["agents_limit"] == settings.TEAM_AGENTS
        assert team_usage["messages_limit"] == settings.TEAM_MESSAGES
        # 团队版是更高一档，额度不该和专业版相同
        assert (team_usage["agents_limit"], team_usage["messages_limit"]) != (
            pro_usage["agents_limit"], pro_usage["messages_limit"]
        )

    @pytest.mark.asyncio
    async def test_team_quota_actually_allows_more_agents(
        self, async_client: AsyncClient, async_db: AsyncSession,
        test_user: User, auth_headers: dict,
    ):
        """团队版能建到自己的上限，而不只是数字上写着更大。"""
        sub = await ensure_subscription(async_db, test_user.external_id)
        sub.plan = PlanType.TEAM.value
        await async_db.commit()

        created = 0
        for i in range(settings.PRO_AGENTS + 1):
            resp = await async_client.post(
                "/api/v1/agents", json={"name": f"T{i}"}, headers=auth_headers
            )
            if resp.status_code == 200:
                created += 1
        # 超过专业版上限仍能继续建，说明用的确实是团队版额度
        assert created == settings.PRO_AGENTS + 1

    @pytest.mark.asyncio
    async def test_upgrade_hint_points_to_next_tier(
        self, async_client: AsyncClient, async_db: AsyncSession,
        test_user: User, auth_headers: dict,
    ):
        """升级提示要指向下一档，而不是一律指向专业版。

        团队版用户已经到顶，再提示「升级后为 5」是错的。
        """
        sub = await ensure_subscription(async_db, test_user.external_id)
        sub.plan = PlanType.FREE.value
        sub.agents_used = settings.FREE_AGENTS
        await async_db.commit()

        free_blocked = await async_client.post(
            "/api/v1/agents", json={"name": "F"}, headers=auth_headers
        )
        assert free_blocked.status_code == 402
        assert free_blocked.json()["next_limit"] == settings.PRO_AGENTS

        sub.plan = PlanType.PRO.value
        sub.agents_used = settings.PRO_AGENTS
        await async_db.commit()

        pro_blocked = await async_client.post(
            "/api/v1/agents", json={"name": "P"}, headers=auth_headers
        )
        assert pro_blocked.status_code == 402
        assert pro_blocked.json()["next_limit"] == settings.TEAM_AGENTS


class TestPeriodReset:
    """计费周期的懒重置。"""

    @pytest.mark.asyncio
    async def test_new_subscription_has_period_initialized(
        self, async_db: AsyncSession, test_user: User
    ):
        """新建订阅必须当场初始化周期。

        ``current_period_end`` 为 None 时，``_roll_period`` 会走「首期」分支
        并把 ``messages_used`` 一并归零。不在这里初始化的话，用户之后发的
        每条消息都会被抹掉，消息额度形同虚设。
        """
        sub = await ensure_subscription(async_db, test_user.external_id)

        assert sub.current_period_start is not None
        assert sub.current_period_end is not None

    @pytest.mark.asyncio
    async def test_expired_period_resets_usage(
        self, async_db: AsyncSession, test_user: User
    ):
        """到期后归零用量并顺延周期。

        不起定时任务：漏跑一次配额就会永久卡死。
        """
        sub = await ensure_subscription(async_db, test_user.external_id)
        sub.messages_used = 999
        sub.current_period_end = (
            datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1)
        )
        await async_db.commit()

        rolled = await ensure_subscription(async_db, test_user.external_id)

        assert rolled.messages_used == 0
        end = rolled.current_period_end
        end = end if end.tzinfo else end.replace(tzinfo=timezone.utc)
        assert end > datetime.now(timezone.utc), "周期必须顺延到未来"

    @pytest.mark.asyncio
    async def test_active_period_keeps_usage(
        self, async_db: AsyncSession, test_user: User
    ):
        """周期未到时不能归零，否则用户每个月都会被重置。"""
        sub = await ensure_subscription(async_db, test_user.external_id)
        sub.messages_used = 42
        await async_db.commit()

        same = await ensure_subscription(async_db, test_user.external_id)

        assert same.messages_used == 42


class TestMessageConsumptionOnChat:
    """对话成功后消息用量必须真的累加。

    这条链路此前完全没有覆盖 —— 而它恰好是「配额生效」的另一半：
    只拦不记的话，`messages_used` 永远是 0，用户一辈子都撞不到上限，
    额度形同虚设。（Agent 数量那半边靠增删维护，没有这个问题。）
    """

    @staticmethod
    async def _used(db: AsyncSession, user: User) -> int:
        """当前已用消息数。

        测试与请求处理共用同一个 Session，且 sessionmaker 设了
        ``expire_on_commit=False``，所以这里读到的就是请求刚改过的那个对象。
        订阅还没被懒创建时返回 0，而不是对 None 调 refresh。
        """
        sub = await db.scalar(
            select(Subscription).where(Subscription.user_id == user.id)
        )
        return (sub.messages_used or 0) if sub else 0

    @pytest.mark.asyncio
    @patch("app.api.chat.IntegratedAgentRuntime")
    async def test_non_stream_chat_increments_usage(
        self, mock_runtime_class, async_client: AsyncClient,
        async_db: AsyncSession, test_user: User, test_agent: Agent, auth_headers: dict,
    ):
        mock_runtime = AsyncMock()
        mock_runtime.initialize = AsyncMock()
        mock_runtime.chat = AsyncMock(return_value="好的")
        mock_runtime.get_stats = AsyncMock(return_value={})
        mock_runtime.session = MagicMock()
        mock_runtime.session.id = "sess-1"
        mock_runtime_class.return_value = mock_runtime

        assert await self._used(async_db, test_user) == 0

        resp = await async_client.post(
            f"/api/v1/chat/{test_agent.id}",
            json={"message": "你好"},
            headers=auth_headers,
        )
        assert resp.status_code == 200

        assert await self._used(async_db, test_user) == 1

    @pytest.mark.asyncio
    @patch("app.api.chat.IntegratedAgentRuntime")
    async def test_with_tools_chat_increments_usage(
        self, mock_runtime_class, async_client: AsyncClient,
        async_db: AsyncSession, test_user: User, test_agent: Agent, auth_headers: dict,
    ):
        mock_runtime = AsyncMock()
        mock_runtime.initialize = AsyncMock()
        mock_runtime.chat_with_tools = AsyncMock(return_value="结果")
        mock_runtime.get_stats = AsyncMock(return_value={})
        mock_runtime.session = MagicMock()
        mock_runtime.session.id = "sess-2"
        mock_runtime_class.return_value = mock_runtime

        resp = await async_client.post(
            f"/api/v1/chat/{test_agent.id}/with-tools",
            json={"message": "查一下"},
            headers=auth_headers,
        )
        assert resp.status_code == 200

        assert await self._used(async_db, test_user) == 1

    @pytest.mark.asyncio
    @patch("app.api.chat.IntegratedAgentRuntime")
    async def test_multi_agent_increments_usage(
        self, mock_runtime_class, async_client: AsyncClient,
        async_db: AsyncSession, test_user: User, auth_headers: dict,
    ):
        mock_runtime = AsyncMock()
        mock_runtime.initialize = AsyncMock()
        mock_runtime.multi_agent_chat = AsyncMock(return_value={"a": "1"})
        mock_runtime.session = MagicMock()
        mock_runtime.session.id = "sess-3"
        mock_runtime_class.return_value = mock_runtime

        resp = await async_client.post(
            "/api/v1/chat/multi-agent",
            json={"message": "一起讨论", "agent_ids": ["a", "b"]},
            headers=auth_headers,
        )
        assert resp.status_code == 200

        assert await self._used(async_db, test_user) == 1

    @pytest.mark.asyncio
    @patch("app.integrations.tools_memory.ConversationMemory")
    @patch("app.integrations.tools_memory.MemoryManager")
    @patch("app.integrations.prompts_outputs.prompt_manager")
    @patch("app.api.chat.IntegratedAgentRuntime")
    async def test_stream_chat_increments_usage(
        self, mock_runtime_class, mock_prompt_manager, mock_memory_mgr,
        mock_conv_memory, async_client: AsyncClient, async_db: AsyncSession,
        test_user: User, test_agent: Agent, auth_headers: dict,
    ):
        """流式是前端实际走的主路径，不能漏。

        它的用量累加发生在响应返回之后（模型调用在 generator 里），
        比非流式更容易漏记。
        """
        async def fake_stream(*args, **kwargs):
            for chunk in ("你", "好"):
                yield chunk

        mock_conv_memory.return_value.get_history = AsyncMock(return_value=[])
        mock_conv_memory.return_value.add_message = AsyncMock()
        mock_prompt_manager.build_messages = MagicMock(return_value=[])

        mock_runtime = AsyncMock()
        mock_runtime.initialize = AsyncMock()
        mock_runtime._load_or_create_session = AsyncMock()
        mock_runtime.session = MagicMock()
        mock_runtime.session.id = "sess-stream"
        mock_runtime.knowledge = None
        mock_runtime.agent = MagicMock()
        mock_runtime.agent.template = "qa"
        mock_runtime.agent.model_config = {}
        mock_runtime.agent.message_count = 0
        mock_runtime.llm.chat_stream = fake_stream
        mock_runtime_class.return_value = mock_runtime

        resp = await async_client.post(
            f"/api/v1/chat/{test_agent.id}",
            json={"message": "你好", "stream": True},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        # SSE 的 JSON 会把中文转义成 \uXXXX，不能直接断言原文；
        # 出现 done 事件即说明 generator 跑到了最后（accumulate 就在它前面）
        assert '"type": "done"' in resp.text

        assert await self._used(async_db, test_user) == 1

    @pytest.mark.asyncio
    @patch("app.api.chat.IntegratedAgentRuntime")
    async def test_failed_chat_does_not_consume(
        self, mock_runtime_class, async_client: AsyncClient,
        async_db: AsyncSession, test_user: User, test_agent: Agent, auth_headers: dict,
    ):
        """模型调用失败不能计费。

        用户没得到回复却扣了额度，是会被投诉的那类 bug。
        """
        mock_runtime = AsyncMock()
        mock_runtime.initialize = AsyncMock()
        mock_runtime.chat = AsyncMock(side_effect=RuntimeError("模型挂了"))
        mock_runtime_class.return_value = mock_runtime

        resp = await async_client.post(
            f"/api/v1/chat/{test_agent.id}",
            json={"message": "你好"},
            headers=auth_headers,
        )
        assert resp.status_code == 500

        assert await self._used(async_db, test_user) == 0, "失败的调用不该扣额度"

    @pytest.mark.asyncio
    @patch("app.api.chat.IntegratedAgentRuntime")
    async def test_usage_accumulates_across_turns(
        self, mock_runtime_class, async_client: AsyncClient,
        async_db: AsyncSession, test_user: User, test_agent: Agent, auth_headers: dict,
    ):
        """连发三条要记成 3，而不是被反复重置成 1。

        新建订阅时若没初始化计费周期，_roll_period 会把 messages_used 清零，
        表现就是「发了多少条都显示 0」。
        """
        mock_runtime = AsyncMock()
        mock_runtime.initialize = AsyncMock()
        mock_runtime.chat = AsyncMock(return_value="好的")
        mock_runtime.get_stats = AsyncMock(return_value={})
        mock_runtime.session = MagicMock()
        mock_runtime.session.id = "sess-multi-turn"
        mock_runtime_class.return_value = mock_runtime

        for i in range(3):
            resp = await async_client.post(
                f"/api/v1/chat/{test_agent.id}",
                json={"message": f"第 {i} 句"},
                headers=auth_headers,
            )
            assert resp.status_code == 200
            assert await self._used(async_db, test_user) == i + 1


class TestMeteringCoverage:
    """防止「新加了对话接口却忘了接配额」。

    P0 时我只把配额接在 ``/chat/*`` 上，把 pi 引擎整条链路漏掉了 ——
    而没有工作流的 Agent 恰好**默认走 pi**（前端 ``effectiveEngine =
    hasWorkflow ? 'builtin' : engine``），用户聊了半天额度一点没动。

    这类遗漏靠人记是靠不住的，所以这里扫描路由处理函数的源码：
    只要它直接引用了会跑模型的运行时，就必须同时调用 ``check_quota``。

    **能力边界**：只能发现「处理函数里直接出现这些标记」的情况。
    如果模型调用被藏在 service 内部（比如 ``KnowledgeService.rag_query``），
    源码里看不到标记，这个测试盯不住 —— 那种情况需要在 service 层另想办法。
    """

    #: 出现这些标记，说明这个处理函数会真的跑模型
    LLM_MARKERS = (
        "IntegratedAgentRuntime",
        "pi_agent_runner.",
        "workflow_runtime.",
        "skill_service.call_agent",
    )

    def test_every_llm_endpoint_checks_quota(self):
        import importlib
        import inspect
        import pkgutil

        import app.api

        missing = []
        checked = 0
        scanned = []

        # 自动发现 app.api 下的所有模块，而不是写死模块名：
        # 新增一个 api 模块时不用回来改这里，它会被自动扫到。
        # （app.routes 在这个 FastAPI 版本里是 _IncludedRouter 包装，展平不了）
        for mod in pkgutil.iter_modules(app.api.__path__):
            module = importlib.import_module(f"app.api.{mod.name}")
            router = getattr(module, "router", None)
            if router is None:
                continue
            for route in router.routes:
                if "POST" not in (getattr(route, "methods", None) or set()):
                    continue
                handler = getattr(route, "endpoint", None)
                if handler is None:
                    continue
                try:
                    source = inspect.getsource(handler)
                except (OSError, TypeError):
                    continue

                scanned.append(f"{mod.name}{route.path}")
                if not any(marker in source for marker in self.LLM_MARKERS):
                    continue

                checked += 1
                if "check_quota" not in source:
                    missing.append(
                        f"{mod.name}{route.path}  ->  {handler.__name__}"
                    )

        # 断言确实扫到了东西。如果标记全失效（运行时被改名），
        # 这个测试会「全绿但什么都没检查」，必须让它自己暴露出来。
        assert len(scanned) > 10, f"只扫描到 {len(scanned)} 个 POST 接口，发现逻辑可能已失效"
        assert checked >= 6, f"只识别出 {checked} 个会调模型的接口，标记可能已失效"

        assert not missing, (
            "以下接口会调用模型但没有配额校验，请接入 check_quota / consume_quota：\n  "
            + "\n  ".join(missing)
        )


class TestQuotaHelpers:
    """用量累加与释放的原语。"""

    @pytest.mark.asyncio
    async def test_consume_and_release(
        self, async_db: AsyncSession, test_user: User
    ):
        sub = await ensure_subscription(async_db, test_user.external_id)

        await consume(async_db, sub, Resource.MESSAGES, 3)
        assert sub.messages_used == 3

        await release(async_db, sub, Resource.MESSAGES, 1)
        assert sub.messages_used == 2

    @pytest.mark.asyncio
    async def test_release_never_goes_negative(
        self, async_db: AsyncSession, test_user: User
    ):
        """计数器可能因为历史数据对不上，释放时不能翻负。"""
        sub = await ensure_subscription(async_db, test_user.external_id)
        sub.messages_used = 1
        await async_db.commit()

        await release(async_db, sub, Resource.MESSAGES, 99)

        assert sub.messages_used == 0
