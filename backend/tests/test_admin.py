"""
管理后台测试。

覆盖三件事：
1. **权限边界** —— 非管理员必须拿不到数据，前端隐藏入口不算数
2. **行为可见** —— 概览 / 列表 / 明细的聚合数字要对得上
3. **改套餐生效** —— 管理员改完，用户那边额度真的变了（而不只是改了个字段）
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.agent import Agent
from app.models.subscription import PlanType, Subscription
from app.models.user import User, UserRole
from app.services.entitlement import ensure_subscription
from app.services.roles import apply_configured_role


async def _make_user(db: AsyncSession, email: str | None = None, **kw) -> User:
    from app.api.auth import get_password_hash

    user = User(
        email=email or f"u-{uuid.uuid4().hex[:8]}@test.com",
        password_hash=get_password_hash("testpassword"),
        is_verified=True,
        **kw,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def _make_agent(db: AsyncSession, owner: User, name: str, messages: int = 0) -> Agent:
    agent = Agent(
        id=str(uuid.uuid4()),
        user_id=owner.external_id,
        name=name,
        description="",
        workflow_definition={"nodes": [], "edges": []},
        message_count=messages,
    )
    db.add(agent)
    return agent


# --------------------------------------------------------------------------
# 角色授予
# --------------------------------------------------------------------------


class TestRoleGrant:
    """ADMIN_EMAILS 白名单的行为。"""

    def test_matching_email_is_granted(self, monkeypatch, test_user: User):
        monkeypatch.setattr(settings, "ADMIN_EMAILS", test_user.email, raising=False)

        assert apply_configured_role(test_user) is True
        assert test_user.role == UserRole.ADMIN.value

    def test_email_match_is_case_and_space_insensitive(self, monkeypatch, test_user: User):
        """配置习惯各异，真按原样比对会出现「配了却没生效」。"""
        monkeypatch.setattr(
            settings, "ADMIN_EMAILS", f"  {test_user.email.upper()} , other@test.com ",
            raising=False,
        )

        assert apply_configured_role(test_user) is True

    def test_non_matching_email_is_untouched(self, monkeypatch, test_user: User):
        monkeypatch.setattr(settings, "ADMIN_EMAILS", "someone@else.com", raising=False)

        assert apply_configured_role(test_user) is False
        assert test_user.role == UserRole.USER.value

    def test_empty_allowlist_is_a_noop(self, monkeypatch, test_user: User):
        """没配白名单时不应该把任何人变成管理员，也不该报错。"""
        monkeypatch.setattr(settings, "ADMIN_EMAILS", "", raising=False)

        assert apply_configured_role(test_user) is False
        assert test_user.role == UserRole.USER.value

    def test_removing_from_allowlist_does_not_revoke(self, monkeypatch, test_user: User):
        """只授予、不回收。

        登录时静默降级一个正在用后台的账号，体验上更像 bug；
        手工提权过的账号也会被配置悄悄覆盖。撤销必须是显式动作。
        """
        test_user.role = UserRole.ADMIN.value
        monkeypatch.setattr(settings, "ADMIN_EMAILS", "", raising=False)

        assert apply_configured_role(test_user) is False
        assert test_user.role == UserRole.ADMIN.value

    def test_already_admin_returns_false(self, monkeypatch, test_user: User):
        """已经是管理员就不算「变更」，避免每次请求都写库。"""
        test_user.role = UserRole.ADMIN.value
        monkeypatch.setattr(settings, "ADMIN_EMAILS", test_user.email, raising=False)

        assert apply_configured_role(test_user) is False


class TestRoleExposure:
    """角色的对外暴露与生效路径。"""

    @pytest.mark.asyncio
    async def test_login_grants_admin_from_allowlist(
        self, monkeypatch, async_client: AsyncClient, test_user: User
    ):
        monkeypatch.setattr(settings, "ADMIN_EMAILS", test_user.email, raising=False)

        resp = await async_client.post(
            "/api/v1/auth/login",
            json={"email": test_user.email, "password": "testpassword"},
        )

        assert resp.status_code == 200
        assert resp.json()["user"]["role"] == UserRole.ADMIN.value

    @pytest.mark.asyncio
    async def test_me_exposes_role(
        self, async_client: AsyncClient, test_user: User, auth_headers: dict
    ):
        resp = await async_client.get("/api/v1/users/me", headers=auth_headers)

        assert resp.status_code == 200
        body = resp.json()
        assert body["role"] == UserRole.USER.value
        assert body["is_admin"] is False

    @pytest.mark.asyncio
    async def test_me_grants_admin_when_configured(
        self, monkeypatch, async_client: AsyncClient, test_user: User, auth_headers: dict
    ):
        """改配置 + 刷新页面即可生效，不必等用户重新登录。"""
        monkeypatch.setattr(settings, "ADMIN_EMAILS", test_user.email, raising=False)

        resp = await async_client.get("/api/v1/users/me", headers=auth_headers)

        assert resp.status_code == 200
        assert resp.json()["is_admin"] is True


# --------------------------------------------------------------------------
# 权限边界
# --------------------------------------------------------------------------


class TestAdminAccess:
    """管理接口必须挡住非管理员。"""

    ENDPOINTS = [
        ("get", "/api/v1/admin/overview"),
        ("get", "/api/v1/admin/users"),
        ("get", "/api/v1/admin/users/some-id"),
        ("patch", "/api/v1/admin/users/some-id/subscription"),
    ]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("method,path", ENDPOINTS)
    async def test_requires_authentication(
        self, async_client: AsyncClient, method: str, path: str
    ):
        resp = await getattr(async_client, method)(path)
        assert resp.status_code == 401

    @pytest.mark.asyncio
    @pytest.mark.parametrize("method,path", ENDPOINTS)
    async def test_rejects_normal_user(
        self, async_client: AsyncClient, auth_headers: dict, method: str, path: str
    ):
        """普通用户必须 403。

        前端隐藏入口只是体验；能改 localStorage 就能绕过，
        所以权限判定必须在后端独立成立。
        """
        kwargs = {"headers": auth_headers}
        if method == "patch":
            kwargs["json"] = {"plan": "pro"}
        resp = await getattr(async_client, method)(path, **kwargs)
        assert resp.status_code == 403


# --------------------------------------------------------------------------
# 行为可见
# --------------------------------------------------------------------------


class TestOverview:
    @pytest.mark.asyncio
    async def test_overview_counts(
        self, async_client: AsyncClient, async_db: AsyncSession,
        test_user: User, admin_headers: dict,
    ):
        other = await _make_user(async_db)
        _make_agent(async_db, other, "A1", messages=5)
        _make_agent(async_db, other, "A2", messages=7)
        await async_db.commit()

        resp = await async_client.get("/api/v1/admin/overview", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()

        assert body["users"]["total"] == 2
        assert body["content"]["agents"] == 2
        assert body["content"]["messages"] == 12

    @pytest.mark.asyncio
    async def test_plan_distribution_covers_all_tiers(
        self, async_client: AsyncClient, admin_headers: dict
    ):
        """每一档都要出现（哪怕是 0），否则前端画不出完整的分布。"""
        from app.api.billing import PLANS

        resp = await async_client.get("/api/v1/admin/overview", headers=admin_headers)

        plans = {p["plan"] for p in resp.json()["plans"]}
        assert plans == set(PLANS)

    @pytest.mark.asyncio
    async def test_users_without_subscription_count_as_free(
        self, async_client: AsyncClient, async_db: AsyncSession,
        test_user: User, admin_headers: dict,
    ):
        """没有订阅记录的账号也要算进免费版。

        功能上线前注册的老用户就是这种状态；漏掉他们会导致各档相加
        对不上总用户数，看起来像统计算错了。
        """
        await _make_user(async_db)  # 直接建库，没有订阅记录

        resp = await async_client.get("/api/v1/admin/overview", headers=admin_headers)
        body = resp.json()

        free = next(p for p in body["plans"] if p["plan"] == "free")
        assert free["count"] == body["users"]["total"]


class TestUserList:
    @pytest.mark.asyncio
    async def test_returns_behavior_aggregates(
        self, async_client: AsyncClient, async_db: AsyncSession,
        test_user: User, admin_headers: dict,
    ):
        _make_agent(async_db, test_user, "我的 Agent", messages=9)
        await async_db.commit()
        await ensure_subscription(async_db, test_user.external_id)

        resp = await async_client.get("/api/v1/admin/users", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()

        assert body["total"] == 1
        row = body["items"][0]
        assert row["email"] == test_user.email
        assert row["agent_count"] == 1
        assert row["message_count"] == 9
        assert row["plan"] == PlanType.FREE.value

    @pytest.mark.asyncio
    async def test_search_by_email(
        self, async_client: AsyncClient, async_db: AsyncSession,
        test_user: User, admin_headers: dict,
    ):
        await _make_user(async_db, email="findme@test.com")
        await _make_user(async_db, email="other@test.com")

        resp = await async_client.get(
            "/api/v1/admin/users?search=findme", headers=admin_headers
        )
        body = resp.json()

        assert body["total"] == 1
        assert body["items"][0]["email"] == "findme@test.com"

    @pytest.mark.asyncio
    async def test_filter_by_plan(
        self, async_client: AsyncClient, async_db: AsyncSession,
        test_user: User, admin_headers: dict,
    ):
        sub = await ensure_subscription(async_db, test_user.external_id)
        sub.plan = PlanType.PRO.value
        await async_db.commit()

        resp = await async_client.get(
            "/api/v1/admin/users?plan=pro", headers=admin_headers
        )
        body = resp.json()

        assert body["total"] == 1
        assert body["items"][0]["plan"] == PlanType.PRO.value

    @pytest.mark.asyncio
    async def test_rejects_unknown_plan_filter(
        self, async_client: AsyncClient, admin_headers: dict
    ):
        resp = await async_client.get(
            "/api/v1/admin/users?plan=enterprise", headers=admin_headers
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_pagination(
        self, async_client: AsyncClient, async_db: AsyncSession,
        test_user: User, admin_headers: dict,
    ):
        for _ in range(3):
            await _make_user(async_db)

        resp = await async_client.get(
            "/api/v1/admin/users?limit=2&offset=0", headers=admin_headers
        )
        body = resp.json()

        assert body["total"] == 4
        assert len(body["items"]) == 2


class TestUserDetail:
    @pytest.mark.asyncio
    async def test_returns_profile_agents_and_sessions(
        self, async_client: AsyncClient, async_db: AsyncSession,
        test_user: User, admin_headers: dict,
    ):
        agent = _make_agent(async_db, test_user, "演示 Agent", messages=3)
        await async_db.commit()

        from app.models.agent import ChatSession

        async_db.add(ChatSession(
            id="sess-1",
            agent_id=agent.id,
            user_id=test_user.external_id,
            messages=[
                {"role": "user", "content": "帮我写个周报"},
                {"role": "assistant", "content": "好的"},
            ],
        ))
        await async_db.commit()

        resp = await async_client.get(
            f"/api/v1/admin/users/{test_user.external_id}", headers=admin_headers
        )
        assert resp.status_code == 200
        body = resp.json()

        assert body["user"]["email"] == test_user.email
        assert body["stats"]["agents"] == 1
        assert body["stats"]["sessions"] == 1
        assert body["agents"][0]["name"] == "演示 Agent"
        # 会话标题取第一条用户消息，管理端才能一眼看出这段对话在聊什么
        assert body["recent_sessions"][0]["title"] == "帮我写个周报"
        assert body["recent_sessions"][0]["agent_name"] == "演示 Agent"
        assert body["recent_sessions"][0]["message_count"] == 2

    @pytest.mark.asyncio
    async def test_unknown_user_returns_404(
        self, async_client: AsyncClient, admin_headers: dict
    ):
        resp = await async_client.get(
            "/api/v1/admin/users/does-not-exist", headers=admin_headers
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_session_count_is_not_capped_by_recent_limit(
        self, async_client: AsyncClient, async_db: AsyncSession,
        test_user: User, admin_headers: dict,
    ):
        """会话数统计必须是真实总数，不能被「最近 20 条」的展示上限截断。

        否则超过 20 条的用户永远显示成 20，和列表页数字对不上。
        """
        from app.models.agent import ChatSession

        total = 25
        for i in range(total):
            async_db.add(ChatSession(
                id=f"sess-{i}",
                agent_id="whatever",
                user_id=test_user.external_id,
                messages=[{"role": "user", "content": f"第 {i} 轮"}],
            ))
        await async_db.commit()

        resp = await async_client.get(
            f"/api/v1/admin/users/{test_user.external_id}", headers=admin_headers
        )
        body = resp.json()

        assert body["stats"]["sessions"] == total
        # 明细列表仍然只给最近若干条，避免一次拉几千条会话把响应撑爆
        assert len(body["recent_sessions"]) == 20

    @pytest.mark.asyncio
    async def test_session_count_matches_list_view(
        self, async_client: AsyncClient, async_db: AsyncSession,
        test_user: User, admin_headers: dict,
    ):
        """详情页与列表页的会话数必须一致 —— 它们本该是同一个数。"""
        from app.models.agent import ChatSession

        for i in range(23):
            async_db.add(ChatSession(
                id=f"cmp-{i}",
                agent_id="a",
                user_id=test_user.external_id,
                messages=[],
            ))
        await async_db.commit()

        listed = (await async_client.get(
            "/api/v1/admin/users", headers=admin_headers
        )).json()["items"][0]["session_count"]
        detail = (await async_client.get(
            f"/api/v1/admin/users/{test_user.external_id}", headers=admin_headers
        )).json()["stats"]["sessions"]

        assert listed == detail == 23

    @pytest.mark.asyncio
    async def test_lazy_creates_subscription_for_legacy_user(
        self, async_client: AsyncClient, async_db: AsyncSession,
        admin_headers: dict,
    ):
        """看老用户的详情不该因为「没有订阅记录」而崩。"""
        legacy = await _make_user(async_db, email="legacy@test.com")

        resp = await async_client.get(
            f"/api/v1/admin/users/{legacy.external_id}", headers=admin_headers
        )

        assert resp.status_code == 200
        assert resp.json()["subscription"]["plan"] == PlanType.FREE.value


# --------------------------------------------------------------------------
# 改套餐
# --------------------------------------------------------------------------


class TestSetSubscription:
    @pytest.mark.asyncio
    async def test_upgrades_plan(
        self, async_client: AsyncClient, async_db: AsyncSession,
        test_user: User, admin_headers: dict,
    ):
        await ensure_subscription(async_db, test_user.external_id)

        resp = await async_client.patch(
            f"/api/v1/admin/users/{test_user.external_id}/subscription",
            json={"plan": "pro"},
            headers=admin_headers,
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["previous_plan"] == PlanType.FREE.value
        assert body["plan"] == PlanType.PRO.value
        assert body["status"] == "active"

    @pytest.mark.asyncio
    async def test_actual_quota_is_raised(
        self, async_client: AsyncClient, async_db: AsyncSession,
        test_user: User, admin_headers: dict,
    ):
        """关键用例：改完套餐，用户那边的额度必须**真的**变了。

        只断言「plan 字段被改了」是不够的 —— 之前的功能就是字段在、
        判定是死代码。
        """
        await ensure_subscription(async_db, test_user.external_id)

        # 免费版只能建 1 个
        first = await async_client.post(
            "/api/v1/agents", json={"name": "A1"}, headers=admin_headers
        )
        assert first.status_code == 200
        blocked = await async_client.post(
            "/api/v1/agents", json={"name": "A2"}, headers=admin_headers
        )
        assert blocked.status_code == 402

        # 管理员开通专业版
        upgraded = await async_client.patch(
            f"/api/v1/admin/users/{test_user.external_id}/subscription",
            json={"plan": "pro"},
            headers=admin_headers,
        )
        assert upgraded.status_code == 200

        # 现在能建到专业版的上限
        second = await async_client.post(
            "/api/v1/agents", json={"name": "A2"}, headers=admin_headers
        )
        assert second.status_code == 200, "改完套餐后额度没有实际提升"

        sub = await async_db.scalar(
            select(Subscription).where(Subscription.user_id == test_user.id)
        )
        assert sub.is_pro is True

    @pytest.mark.asyncio
    async def test_downgrade_does_not_touch_usage(
        self, async_client: AsyncClient, async_db: AsyncSession,
        test_user: User, admin_headers: dict,
    ):
        """改套餐只调额度，不清已用量 —— 需要归零得显式勾选。"""
        sub = await ensure_subscription(async_db, test_user.external_id)
        sub.plan = PlanType.PRO.value
        sub.messages_used = 42
        await async_db.commit()

        resp = await async_client.patch(
            f"/api/v1/admin/users/{test_user.external_id}/subscription",
            json={"plan": "free"},
            headers=admin_headers,
        )

        assert resp.status_code == 200
        assert resp.json()["messages_used"] == 42

    @pytest.mark.asyncio
    async def test_reset_usage_flag_clears_counter(
        self, async_client: AsyncClient, async_db: AsyncSession,
        test_user: User, admin_headers: dict,
    ):
        sub = await ensure_subscription(async_db, test_user.external_id)
        sub.messages_used = 42
        await async_db.commit()

        resp = await async_client.patch(
            f"/api/v1/admin/users/{test_user.external_id}/subscription",
            json={"plan": "pro", "reset_usage": True},
            headers=admin_headers,
        )

        assert resp.status_code == 200
        assert resp.json()["messages_used"] == 0

    @pytest.mark.asyncio
    async def test_creates_subscription_when_missing(
        self, async_client: AsyncClient, async_db: AsyncSession,
        admin_headers: dict,
    ):
        """老用户没有订阅记录时，改套餐应该顺手建一条而不是报错。"""
        legacy = await _make_user(async_db, email="nosub@test.com")

        resp = await async_client.patch(
            f"/api/v1/admin/users/{legacy.external_id}/subscription",
            json={"plan": "team"},
            headers=admin_headers,
        )

        assert resp.status_code == 200
        assert resp.json()["plan"] == PlanType.TEAM.value

    @pytest.mark.asyncio
    async def test_rejects_unknown_plan(
        self, async_client: AsyncClient, test_user: User, admin_headers: dict
    ):
        resp = await async_client.patch(
            f"/api/v1/admin/users/{test_user.external_id}/subscription",
            json={"plan": "enterprise"},
            headers=admin_headers,
        )
        assert resp.status_code == 400
        assert "enterprise" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_unknown_user_returns_404(
        self, async_client: AsyncClient, admin_headers: dict
    ):
        resp = await async_client.patch(
            "/api/v1/admin/users/nope/subscription",
            json={"plan": "pro"},
            headers=admin_headers,
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_expired_status_is_cleared_on_manual_grant(
        self, async_client: AsyncClient, async_db: AsyncSession,
        test_user: User, admin_headers: dict,
    ):
        """手工开通必须把 status 置为 active。

        否则用户看着是新套餐，但 ``is_pro`` 因为 status=past_due 判定为假，
        表现就是「改了没生效」。
        """
        sub = await ensure_subscription(async_db, test_user.external_id)
        sub.status = "past_due"
        await async_db.commit()

        resp = await async_client.patch(
            f"/api/v1/admin/users/{test_user.external_id}/subscription",
            json={"plan": "pro"},
            headers=admin_headers,
        )

        assert resp.status_code == 200
        assert resp.json()["status"] == "active"

        refreshed = await async_db.scalar(
            select(Subscription).where(Subscription.user_id == test_user.id)
        )
        assert refreshed.is_pro is True


# --------------------------------------------------------------------------
# 概览扩展与趋势
# --------------------------------------------------------------------------


class TestOverviewExtended:
    @pytest.mark.asyncio
    async def test_includes_conversion_and_content_depth(
        self, async_client: AsyncClient, async_db: AsyncSession,
        test_user: User, admin_headers: dict,
    ):
        other = await _make_user(async_db)
        sub = await ensure_subscription(async_db, other.external_id)
        sub.plan = PlanType.TEAM.value
        await async_db.commit()

        body = (await async_client.get(
            "/api/v1/admin/overview", headers=admin_headers
        )).json()

        assert body["users"]["total"] == 2
        assert body["users"]["paid"] == 1
        assert body["users"]["conversion"] == 50.0
        # 关键字段一个都不能少，前端整块卡片都靠它渲染
        for field in ("new_1d", "new_7d", "new_30d", "never_logged_in", "admins", "disabled"):
            assert field in body["users"]
        for field in ("knowledge_bases", "documents", "document_bytes"):
            assert field in body["content"]

    @pytest.mark.asyncio
    async def test_conversion_is_zero_with_no_users(
        self, async_client: AsyncClient, admin_headers: dict
    ):
        """分母为 0 时返回 0，而不是除零崩掉。"""
        body = (await async_client.get(
            "/api/v1/admin/overview", headers=admin_headers
        )).json()
        assert body["users"]["conversion"] == 0.0


class TestTrends:
    @pytest.mark.asyncio
    async def test_returns_requested_number_of_days_with_gaps_filled(
        self, async_client: AsyncClient, admin_headers: dict
    ):
        """没有数据的日期也要补 0 —— 前端按固定长度画柱子，
        缺日期会让整张图的横轴错位。
        """
        body = (await async_client.get(
            "/api/v1/admin/trends?days=7", headers=admin_headers
        )).json()

        assert body["days"] == 7
        assert len(body["series"]) == 7
        # 日期必须连续且升序
        dates = [p["date"] for p in body["series"]]
        assert dates == sorted(dates)
        for point in body["series"]:
            assert set(point) == {"date", "new_users", "new_sessions", "active_users"}
        # 最后一天应当是今天
        from datetime import datetime, timezone
        assert dates[-1] == datetime.now(timezone.utc).strftime("%Y-%m-%d")

    @pytest.mark.asyncio
    async def test_counts_todays_new_user(
        self, async_client: AsyncClient, async_db: AsyncSession,
        test_user: User, admin_headers: dict,
    ):
        await _make_user(async_db)

        body = (await async_client.get(
            "/api/v1/admin/trends?days=3", headers=admin_headers
        )).json()

        assert body["series"][-1]["new_users"] == 2
        assert body["totals"]["new_users"] == 2

    @pytest.mark.asyncio
    async def test_rejects_out_of_range_days(
        self, async_client: AsyncClient, admin_headers: dict
    ):
        assert (await async_client.get(
            "/api/v1/admin/trends?days=1", headers=admin_headers
        )).status_code == 422


class TestTopAgents:
    @pytest.mark.asyncio
    async def test_ranks_by_message_count(
        self, async_client: AsyncClient, async_db: AsyncSession,
        test_user: User, admin_headers: dict,
    ):
        _make_agent(async_db, test_user, "冷门", messages=1)
        _make_agent(async_db, test_user, "热门", messages=99)
        await async_db.commit()

        body = (await async_client.get(
            "/api/v1/admin/agents/top", headers=admin_headers
        )).json()

        assert body["items"][0]["name"] == "热门"
        assert body["items"][0]["message_count"] == 99
        assert body["items"][0]["owner_email"] == test_user.email

    @pytest.mark.asyncio
    async def test_marks_workflow_agents(
        self, async_client: AsyncClient, async_db: AsyncSession,
        test_user: User, admin_headers: dict,
    ):
        """走工作流与直连模型的 Agent 排查时表现不同，要能分辨。"""
        plain = _make_agent(async_db, test_user, "直连", messages=5)
        flow = _make_agent(async_db, test_user, "编排", messages=5)
        flow.workflow_definition = {"nodes": [{"id": "n1"}], "edges": []}
        await async_db.commit()

        items = (await async_client.get(
            "/api/v1/admin/agents/top", headers=admin_headers
        )).json()["items"]
        by_name = {i["name"]: i for i in items}

        assert by_name["直连"]["has_workflow"] is False
        assert by_name["编排"]["has_workflow"] is True


# --------------------------------------------------------------------------
# 会话分页与内容
# --------------------------------------------------------------------------


class TestUserSessions:
    @pytest.mark.asyncio
    async def test_paginates(
        self, async_client: AsyncClient, async_db: AsyncSession,
        test_user: User, admin_headers: dict,
    ):
        from app.models.agent import ChatSession

        for i in range(7):
            async_db.add(ChatSession(
                id=f"pg-{i}", agent_id="a", user_id=test_user.external_id,
                messages=[{"role": "user", "content": f"第 {i} 问"}],
            ))
        await async_db.commit()

        first = (await async_client.get(
            f"/api/v1/admin/users/{test_user.external_id}/sessions?limit=3&offset=0",
            headers=admin_headers,
        )).json()
        second = (await async_client.get(
            f"/api/v1/admin/users/{test_user.external_id}/sessions?limit=3&offset=3",
            headers=admin_headers,
        )).json()

        assert first["total"] == 7
        assert len(first["items"]) == 3
        assert len(second["items"]) == 3
        # 两页不能有重叠
        assert {i["id"] for i in first["items"]} & {i["id"] for i in second["items"]} == set()

    @pytest.mark.asyncio
    async def test_unknown_user_returns_404(
        self, async_client: AsyncClient, admin_headers: dict
    ):
        resp = await async_client.get(
            "/api/v1/admin/users/nope/sessions", headers=admin_headers
        )
        assert resp.status_code == 404


class TestSessionDetail:
    @pytest.mark.asyncio
    async def test_returns_full_messages(
        self, async_client: AsyncClient, async_db: AsyncSession,
        test_user: User, admin_headers: dict,
    ):
        from app.models.agent import ChatSession

        agent = _make_agent(async_db, test_user, "对话 Agent")
        await async_db.commit()
        async_db.add(ChatSession(
            id="detail-1", agent_id=agent.id, user_id=test_user.external_id,
            messages=[
                {"role": "user", "content": "帮我写周报"},
                {"role": "assistant", "content": "好的，请提供要点"},
            ],
        ))
        await async_db.commit()

        body = (await async_client.get(
            "/api/v1/admin/sessions/detail-1", headers=admin_headers
        )).json()

        assert body["message_count"] == 2
        assert body["messages"][0]["content"] == "帮我写周报"
        assert body["messages"][1]["role"] == "assistant"
        assert body["agent_name"] == "对话 Agent"
        assert body["user_email"] == test_user.email

    @pytest.mark.asyncio
    async def test_deleted_agent_is_labelled(
        self, async_client: AsyncClient, async_db: AsyncSession,
        test_user: User, admin_headers: dict,
    ):
        """Agent 删了会话还在，不能显示成空白。"""
        from app.models.agent import ChatSession

        async_db.add(ChatSession(
            id="orphan-1", agent_id="已删除的-id", user_id=test_user.external_id,
            messages=[{"role": "user", "content": "hi"}],
        ))
        await async_db.commit()

        body = (await async_client.get(
            "/api/v1/admin/sessions/orphan-1", headers=admin_headers
        )).json()

        assert body["agent_name"] == "（已删除的 Agent）"

    @pytest.mark.asyncio
    async def test_unknown_session_returns_404(
        self, async_client: AsyncClient, admin_headers: dict
    ):
        assert (await async_client.get(
            "/api/v1/admin/sessions/nope", headers=admin_headers
        )).status_code == 404


# --------------------------------------------------------------------------
# 列表筛选与排序
# --------------------------------------------------------------------------


class TestUserFilters:
    @pytest.mark.asyncio
    async def test_sort_by_message_count(
        self, async_client: AsyncClient, async_db: AsyncSession,
        test_user: User, admin_headers: dict,
    ):
        quiet = await _make_user(async_db, email="quiet@test.com")
        loud = await _make_user(async_db, email="loud@test.com")
        _make_agent(async_db, quiet, "Q", messages=1)
        _make_agent(async_db, loud, "L", messages=50)
        await async_db.commit()

        body = (await async_client.get(
            "/api/v1/admin/users?sort=message_count&order=desc", headers=admin_headers
        )).json()

        assert body["items"][0]["email"] == "loud@test.com"

    @pytest.mark.asyncio
    async def test_sort_puts_never_logged_in_last(
        self, async_client: AsyncClient, async_db: AsyncSession,
        test_user: User, admin_headers: dict,
    ):
        """从没登录过的账号不该霸占「最近登录」榜首。"""
        never = await _make_user(async_db, email="never@test.com")
        assert never.last_login_at is None

        body = (await async_client.get(
            "/api/v1/admin/users?sort=last_login_at&order=desc", headers=admin_headers
        )).json()

        assert body["items"][-1]["email"] == "never@test.com"

    @pytest.mark.asyncio
    async def test_filter_by_role(
        self, async_client: AsyncClient, async_db: AsyncSession,
        test_user: User, admin_headers: dict,
    ):
        await _make_user(async_db)

        body = (await async_client.get(
            "/api/v1/admin/users?role=admin", headers=admin_headers
        )).json()

        assert body["total"] == 1
        assert body["items"][0]["email"] == test_user.email

    @pytest.mark.asyncio
    async def test_filter_by_never_logged_in(
        self, async_client: AsyncClient, async_db: AsyncSession,
        test_user: User, admin_headers: dict,
    ):
        # 先给 test_user 一个登录时间，否则它也会落进「从未登录」里
        test_user.last_login_at = datetime.now(timezone.utc).replace(tzinfo=None)

        fresh = await _make_user(async_db, email="nvr@test.com")
        await _make_user(async_db, email="logged@test.com")
        logged = await async_db.scalar(
            select(User).where(User.email == "logged@test.com")
        )
        logged.last_login_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await async_db.commit()

        body = (await async_client.get(
            "/api/v1/admin/users?activity=never", headers=admin_headers
        )).json()

        assert body["total"] == 1
        assert body["items"][0]["id"] == fresh.external_id

    @pytest.mark.asyncio
    async def test_filter_by_disabled_status(
        self, async_client: AsyncClient, async_db: AsyncSession,
        test_user: User, admin_headers: dict,
    ):
        off = await _make_user(async_db, email="off@test.com")
        off.is_active = False
        await async_db.commit()

        body = (await async_client.get(
            "/api/v1/admin/users?status=disabled", headers=admin_headers
        )).json()

        assert body["total"] == 1
        assert body["items"][0]["email"] == "off@test.com"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("query", [
        "sort=drop_table",
        "role=superuser",
        "status=whatever",
        "activity=sleeping",
        "plan=enterprise",
    ])
    async def test_rejects_unknown_filter_values(
        self, async_client: AsyncClient, admin_headers: dict, query: str
    ):
        """非法筛选值要明确报 400，而不是静默忽略当成「没筛」。"""
        resp = await async_client.get(
            f"/api/v1/admin/users?{query}", headers=admin_headers
        )
        assert resp.status_code == 400, query


# --------------------------------------------------------------------------
# 账号启停
# --------------------------------------------------------------------------


class TestUserStatus:
    @pytest.mark.asyncio
    async def test_disable_and_reenable(
        self, async_client: AsyncClient, async_db: AsyncSession,
        admin_headers: dict,
    ):
        target = await _make_user(async_db, email="toggle@test.com")

        off = await async_client.patch(
            f"/api/v1/admin/users/{target.external_id}/status",
            json={"is_active": False}, headers=admin_headers,
        )
        assert off.status_code == 200
        assert off.json()["is_active"] is False

        on = await async_client.patch(
            f"/api/v1/admin/users/{target.external_id}/status",
            json={"is_active": True}, headers=admin_headers,
        )
        assert on.status_code == 200
        assert on.json()["is_active"] is True

    @pytest.mark.asyncio
    async def test_cannot_disable_self(
        self, async_client: AsyncClient, test_user: User, admin_headers: dict
    ):
        """把自己锁在门外，界面上没有任何路能救回来。"""
        resp = await async_client.patch(
            f"/api/v1/admin/users/{test_user.external_id}/status",
            json={"is_active": False}, headers=admin_headers,
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_disabled_user_cannot_login(
        self, async_client: AsyncClient, async_db: AsyncSession,
        admin_headers: dict,
    ):
        target = await _make_user(async_db, email="blocked@test.com")

        await async_client.patch(
            f"/api/v1/admin/users/{target.external_id}/status",
            json={"is_active": False}, headers=admin_headers,
        )
        resp = await async_client.post(
            "/api/v1/auth/login",
            json={"email": "blocked@test.com", "password": "testpassword"},
        )

        assert resp.status_code == 403
        assert "停用" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_disable_immediately_invalidates_existing_token(
        self, async_client: AsyncClient, async_db: AsyncSession,
        admin_headers: dict,
    ):
        """**核心用例**：停用必须让已签发的 token 立刻失效。

        token 有效期是 7 天。如果只在登录处校验，被停用的人拿着旧 token
        还能继续用满一周，管理员的「停用」就是个摆设。
        """
        from app.api.auth import create_token

        target = await _make_user(async_db, email="revoke@test.com")
        target_token = create_token(target.external_id)
        victim_headers = {"Authorization": f"Bearer {target_token}"}

        # 停用前：token 可用
        assert (await async_client.get(
            "/api/v1/users/me", headers=victim_headers
        )).status_code == 200

        await async_client.patch(
            f"/api/v1/admin/users/{target.external_id}/status",
            json={"is_active": False}, headers=admin_headers,
        )

        # 停用后：同一个 token 立刻不可用
        after = await async_client.get("/api/v1/users/me", headers=victim_headers)
        assert after.status_code == 401

    @pytest.mark.asyncio
    async def test_reenable_restores_access(
        self, async_client: AsyncClient, async_db: AsyncSession,
        admin_headers: dict,
    ):
        """启用之后，原来的 token 又能用了 —— 不要求用户重新登录。"""
        from app.api.auth import create_token

        target = await _make_user(async_db, email="back@test.com")
        headers = {"Authorization": f"Bearer {create_token(target.external_id)}"}

        await async_client.patch(
            f"/api/v1/admin/users/{target.external_id}/status",
            json={"is_active": False}, headers=admin_headers,
        )
        assert (await async_client.get(
            "/api/v1/users/me", headers=headers
        )).status_code == 401

        await async_client.patch(
            f"/api/v1/admin/users/{target.external_id}/status",
            json={"is_active": True}, headers=admin_headers,
        )
        assert (await async_client.get(
            "/api/v1/users/me", headers=headers
        )).status_code == 200

    @pytest.mark.asyncio
    async def test_unknown_user_returns_404(
        self, async_client: AsyncClient, admin_headers: dict
    ):
        resp = await async_client.patch(
            "/api/v1/admin/users/nope/status",
            json={"is_active": False}, headers=admin_headers,
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_requires_admin(
        self, async_client: AsyncClient, test_user: User, auth_headers: dict
    ):
        resp = await async_client.patch(
            f"/api/v1/admin/users/{test_user.external_id}/status",
            json={"is_active": False}, headers=auth_headers,
        )
        assert resp.status_code == 403
