"""控制台「成长面板」数据接口的测试。

守住三件事：

1. 活跃度是**按天去重的会话数** —— 同一条会话当天既新建又有消息，只算 1
2. 「今天还没开始用」不能把连续天数清零（那是假信号，会被读成断签）
3. 数据全部来自真实落库记录：空账号拿到的是 0，不是编造出来的曲线
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent, ChatSession, KnowledgeBase
from app.models.user import User

pytestmark = pytest.mark.asyncio

URL = "/api/v1/agents/stats/activity"


def _day(offset: int, hour: int = 10) -> datetime:
    """相对今天的第 offset 天（负数为过去）的某个时刻，naive UTC。

    必须去掉 tzinfo：库里存的就是 naive UTC。带时区写进去，SQLite 会把
    ``+00:00`` 原样存成字符串，``func.date()`` 出来的格式就和查询时不一致了。
    """
    base = datetime.now(timezone.utc).replace(
        hour=hour, minute=0, second=0, microsecond=0
    )
    return (base + timedelta(days=offset)).replace(tzinfo=None)


def _key(offset: int) -> str:
    return _day(offset).strftime("%Y-%m-%d")


async def _session(
    db: AsyncSession,
    uid: str,
    created: datetime,
    updated: Optional[datetime] = None,
) -> ChatSession:
    row = ChatSession(
        agent_id="agent-1",
        user_id=uid,
        messages=[],
        created_at=created,
        updated_at=updated or created,
    )
    db.add(row)
    return row


class TestActivitySeries:
    async def test_same_day_create_and_chat_counts_once(
        self, async_client: AsyncClient, auth_headers: dict,
        async_db: AsyncSession, test_user: User,
    ):
        """当天新建、当天又聊过的会话，当天只算 1 次。

        这是最容易写错的地方：created 和 updated 两份计数直接相加会算成 2，
        热力图上就是把某一天的活跃度凭空翻倍。
        """
        await _session(async_db, test_user.external_id,
                       created=_day(0, hour=1), updated=_day(0, hour=9))
        await async_db.commit()

        resp = await async_client.get(URL, headers=auth_headers)

        assert resp.status_code == 200
        assert resp.json()["daily"]["activity"].get(_key(0)) == 1

    async def test_session_continued_on_later_day_counts_again(
        self, async_client: AsyncClient, auth_headers: dict,
        async_db: AsyncSession, test_user: User,
    ):
        """昨天建的会话今天继续聊，今天也该算一次。

        只看 created_at 的话，老会话再活跃也不会在热力图上留下痕迹 ——
        那样这张图反映的其实是「新建数」，不是「活跃度」。
        """
        await _session(async_db, test_user.external_id,
                       created=_day(-1, hour=20), updated=_day(0, hour=9))
        await async_db.commit()

        daily = (await async_client.get(URL, headers=auth_headers)).json()["daily"]["activity"]

        assert daily.get(_key(-1)) == 1
        assert daily.get(_key(0)) == 1

    async def test_counts_only_own_sessions(
        self, async_client: AsyncClient, auth_headers: dict,
        async_db: AsyncSession, test_user: User,
    ):
        """别人的会话不能算进我的热力图。"""
        await _session(async_db, "someone-else", created=_day(0, hour=5))
        await async_db.commit()

        body = (await async_client.get(URL, headers=auth_headers)).json()

        assert body["daily"]["activity"] == {}
        assert body["activeDays"] == 0


class TestStreaks:
    async def test_today_not_started_does_not_break_streak(
        self, async_client: AsyncClient, auth_headers: dict,
        async_db: AsyncSession, test_user: User,
    ):
        """今天还没开口，连续天数不能被清零。

        改成 0 的话，用户每天早上一进控制台都看到「连续 0 天」，
        会被读成断签 —— 而真相只是他今天还没开始用。
        """
        for offset in (-1, -2, -3):
            await _session(async_db, test_user.external_id, created=_day(offset))
        await async_db.commit()

        body = (await async_client.get(URL, headers=auth_headers)).json()

        assert body["currentStreak"] == 3
        assert body["longestStreak"] == 3
        assert body["activeDays"] == 3

    async def test_gap_breaks_clear_streak(
        self, async_client: AsyncClient, auth_headers: dict,
        async_db: AsyncSession, test_user: User,
    ):
        """昨天断了就是断了，不能还显示连续。"""
        for offset in (-2, -3):
            await _session(async_db, test_user.external_id, created=_day(offset))
        await async_db.commit()

        body = (await async_client.get(URL, headers=auth_headers)).json()

        assert body["currentStreak"] == 0
        assert body["longestStreak"] == 2   # 历史最长仍然是 2

    async def test_today_active_extends_streak(
        self, async_client: AsyncClient, auth_headers: dict,
        async_db: AsyncSession, test_user: User,
    ):
        for offset in (0, -1):
            await _session(async_db, test_user.external_id, created=_day(offset))
        await async_db.commit()

        body = (await async_client.get(URL, headers=auth_headers)).json()

        assert body["currentStreak"] == 2


class TestGrowthSeries:
    async def test_growth_sums_new_agents_and_knowledge_bases(
        self, async_client: AsyncClient, auth_headers: dict,
        async_db: AsyncSession, test_user: User,
    ):
        uid = test_user.external_id
        async_db.add(Agent(user_id=uid, name="A1",
                           workflow_definition={}, model_config={}, created_at=_day(-1)))
        async_db.add(KnowledgeBase(user_id=uid, name="KB1", created_at=_day(-1)))
        async_db.add(KnowledgeBase(user_id=uid, name="KB2", created_at=_day(-1)))
        await async_db.commit()

        daily = (await async_client.get(URL, headers=auth_headers)).json()["daily"]["growth"]

        assert daily.get(_key(-1)) == 3

    async def test_growth_does_not_leak_into_activity(
        self, async_client: AsyncClient, auth_headers: dict,
        async_db: AsyncSession, test_user: User,
    ):
        """两条序列必须彼此独立 —— 叠加在一起的话，切换标签页就没区别了。"""
        async_db.add(Agent(user_id=test_user.external_id, name="A1",
                           workflow_definition={}, model_config={}, created_at=_day(-1)))
        await async_db.commit()

        body = (await async_client.get(URL, headers=auth_headers)).json()

        assert body["daily"]["growth"].get(_key(-1)) == 1
        assert body["daily"]["activity"] == {}


class TestCompanion:
    async def test_companion_days_counts_join_day_as_day_one(
        self, async_client: AsyncClient, auth_headers: dict,
        async_db: AsyncSession, test_user: User,
    ):
        test_user.created_at = _day(-99)
        await async_db.commit()

        body = (await async_client.get(URL, headers=auth_headers)).json()

        # 注册当天就算第 1 天，否则新用户看到的是「陪伴 0 天」
        assert body["companionDays"] == 100

    async def test_fresh_account_degrades_to_zeros(
        self, async_client: AsyncClient, auth_headers: dict, test_user: User
    ):
        """空账号拿到全 0，而不是报错或编造。

        这块面板是锦上添花的东西，不能因为没数据就把整个控制台带崩。
        """
        body = (await async_client.get(URL, headers=auth_headers)).json()

        assert body["totalSessions"] == 0
        assert body["activeDays"] == 0
        assert body["currentStreak"] == 0
        assert body["longestStreak"] == 0
        assert body["daily"] == {"activity": {}, "growth": {}}
        assert body["companionDays"] == 1

    async def test_window_is_reported_back(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """回显窗口起止，前端画格子要对齐到它，不能自己猜。"""
        body = (await async_client.get(URL, params={"days": 30},
                                       headers=auth_headers)).json()

        assert body["days"] == 30
        assert body["end"] == _key(0)
        assert body["start"] == _key(-29)
