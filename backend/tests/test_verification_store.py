"""验证码存储：跨 worker 重启不能丢码。

这份文件守的是一个真实故障。兜底存储原本是 uvicorn worker 的**进程内存**，
而 ``scripts/dev-backend.ps1`` 用 ``uvicorn --reload`` 启动、装的
``requirements-lite.txt`` 又刻意不含 Redis —— 于是改一次 Python 文件就重启
一次 worker，内存里的验证码全部蒸发。用户侧的观察是：

    收到邮件 → 填进去 → 「验证码已过期，请重新获取」，**而且远没到 TTL**

键不是过期了，是根本不存在了。所以这些用例的断言重点不是「TTL 够不够长」，
而是**换一个进程来读，码还在不在**。
"""
import asyncio
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.base import Base
from app.models.verification import VerificationCode
from app.services import verification

EMAILD = "store-test@example.com"


@pytest.fixture
async def db_codes(tmp_path):
    """把验证码存储指到临时 SQLite **文件**，并强制使用数据库后端。

    用文件而不是 ``:memory:``：内存 SQLite 每条连接是一个独立的库，
    跨会话读不到数据，就测不出「持久」这件事（而那正是要测的）。
    """
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'codes.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    verification.use_db_store_for_tests(factory)
    try:
        yield factory
    finally:
        verification._DB_SESSION_FACTORY = None
        await engine.dispose()


# ---------------------------------------------------------------------------
# 核心回归：码要能跨进程活下来
# ---------------------------------------------------------------------------


class TestSurvivesWorkerRestart:
    async def test_code_verifies_after_worker_restart(self, db_codes):
        """发码 → worker 重启 → 校验，必须成功。

        改造前这条必然失败：码只存在发码那个进程的内存里，
        重启后新进程读不到，用户看到「验证码已过期」。
        """
        outcome = await verification.issue_code(EMAILD, verification.PURPOSE_REGISTER)
        assert outcome.ok

        # 模拟 uvicorn --reload 重启 worker：
        # 进程内存清空，存储后端重新解析（数据库当然还在）
        verification._memory.clear()
        verification.simulate_worker_restart()

        result = await verification.verify_code(
            EMAILD, outcome.code, verification.PURPOSE_REGISTER
        )

        assert result.ok is True, result.error

    async def test_restart_does_not_resurrect_the_code(self, db_codes):
        """反过来也要成立：校验成功后重启，那个码不能再被复用。"""
        outcome = await verification.issue_code(EMAILD, verification.PURPOSE_REGISTER)
        assert (await verification.verify_code(EMAILD, outcome.code)).ok

        verification._memory.clear()
        verification.simulate_worker_restart()

        again = await verification.verify_code(EMAILD, outcome.code)
        assert again.ok is False, "已作废的码在重启后又能用了"

    async def test_cooldown_also_survives_restart(self, db_codes):
        """重发冷却同理。只在内存里的话，重启一次就能绕过每小时限额。"""
        assert (await verification.issue_code(EMAILD)).ok

        verification.simulate_worker_restart()

        second = await verification.issue_code(EMAILD)
        assert second.ok is False
        assert second.retry_after > 0

    async def test_hourly_limit_survives_restart(self, db_codes):
        """每小时上限也要扛重启 —— 否则反复重启就能把接口当免费发信机。"""
        original_limit = verification.settings.CODE_HOURLY_LIMIT
        original_cool = verification.settings.CODE_RESEND_INTERVAL
        verification.settings.CODE_HOURLY_LIMIT = 3
        # 冷却会挡住连发。这里要测的是计数，所以先把冷却关掉 ——
        # 顺便也覆盖了 CODE_RESEND_INTERVAL=0 这条分支。
        verification.settings.CODE_RESEND_INTERVAL = 0
        try:
            for _ in range(3):
                out = await verification.issue_code(EMAILD, verification.PURPOSE_LOGIN)
                assert out.ok, out.error

            verification.simulate_worker_restart()

            over = await verification.issue_code(EMAILD, verification.PURPOSE_LOGIN)
            assert over.ok is False
            assert "频繁" in over.error
        finally:
            verification.settings.CODE_HOURLY_LIMIT = original_limit
            verification.settings.CODE_RESEND_INTERVAL = original_cool


# ---------------------------------------------------------------------------
# 后端选择
# ---------------------------------------------------------------------------


class TestBackendSelection:
    async def test_falls_back_to_database_not_memory(self, monkeypatch):
        """Redis 连不上时要落到**数据库**，不是进程内存。

        这是本次修复的落点：兜底选内存就等于「重启即丢码」。
        """
        monkeypatch.setattr(
            verification.settings, "REDIS_URL", "redis://127.0.0.1:1/0", raising=False
        )
        verification._DB_SESSION_FACTORY = None
        verification.simulate_worker_restart()

        store = await verification._get_store()

        assert isinstance(store, verification._DbStore)
        assert not isinstance(store, verification._MemoryStore)

    async def test_memory_backend_still_available_for_tests(self):
        """内存后端保留给测试用：不必为每个用例起一个库。"""
        verification.use_memory_for_tests()

        store = await verification._get_store()

        assert isinstance(store, verification._MemoryStore)


# ---------------------------------------------------------------------------
# 数据库后端本身的语义
# ---------------------------------------------------------------------------


class TestDbStore:
    async def test_roundtrip(self, db_codes):
        store = await verification._get_store()

        await store.set("k1", "v1", 60)
        assert await store.get("k1") == "v1"
        assert 0 < await store.ttl("k1") <= 60

        await store.delete("k1")
        assert await store.get("k1") is None
        assert await store.ttl("k1") == -1

    async def test_zero_ttl_means_never_expire(self, db_codes):
        """``ttl <= 0`` 是「永不过期」，与内存后端同义。

        ``CODE_RESEND_INTERVAL=0`` 会走到这条 —— 那时候冷却键必须永久存在，
        否则「关掉冷却」会变成「冷却只生效一瞬间」。
        """
        store = await verification._get_store()

        await store.set("forever", "1", 0)

        assert await store.get("forever") == "1"
        assert await store.ttl("forever") == -1

    async def test_expired_row_reads_as_missing(self, db_codes):
        store = await verification._get_store()
        await store.set("gone", "1", 60)

        async with db_codes() as session:
            row = await session.scalar(
                select(VerificationCode).where(VerificationCode.key == "gone")
            )
            row.expires_at = datetime.utcnow() - timedelta(seconds=1)
            await session.commit()

        assert await store.get("gone") is None

    async def test_incr_does_not_extend_the_window(self, db_codes):
        """计数窗口在第一次就固定，后续自增不能延长它。

        延长的话，「每小时最多 5 次」会变成「只要一直发就永远不算超」。
        """
        store = await verification._get_store()

        assert await store.incr("cnt", 60) == 1
        first = await store.ttl("cnt")

        await asyncio.sleep(1.1)

        assert await store.incr("cnt", 60) == 2
        second = await store.ttl("cnt")

        assert second < first, "自增把窗口往后推了"

    async def test_incr_restarts_after_expiry(self, db_codes):
        store = await verification._get_store()

        await store.set("cnt2", "7", 60)
        async with db_codes() as session:
            row = await session.scalar(
                select(VerificationCode).where(VerificationCode.key == "cnt2")
            )
            row.expires_at = datetime.utcnow() - timedelta(seconds=1)
            await session.commit()

        assert await store.incr("cnt2", 60) == 1, "过期后应从 1 重新计数"

    async def test_purge_removes_only_expired(self, db_codes):
        store = await verification._get_store()
        await store.set("fresh", "1", 600)
        await store.set("forever", "1", -1)
        async with db_codes() as session:
            session.add(
                VerificationCode(
                    key="dead",
                    value="1",
                    expires_at=datetime.utcnow() - timedelta(seconds=5),
                    updated_at=datetime.utcnow(),
                )
            )
            await session.commit()

        removed = await store.purge_expired()

        assert removed >= 1
        assert await store.get("fresh") == "1"
        assert await store.get("forever") == "1"
        assert await store.get("dead") is None

    async def test_expired_code_is_rejected_not_silently_accepted(self, db_codes):
        """真过期了也必须拒 —— 别把「持久化」做成「永不过期」。"""
        outcome = await verification.issue_code(EMAILD, verification.PURPOSE_REGISTER)
        assert outcome.ok

        async with db_codes() as session:
            key = verification._code_key(EMAILD, verification.PURPOSE_REGISTER)
            row = await session.scalar(
                select(VerificationCode).where(VerificationCode.key == key)
            )
            row.expires_at = datetime.utcnow() - timedelta(seconds=1)
            await session.commit()

        result = await verification.verify_code(EMAILD, outcome.code)

        assert result.ok is False
        assert "过期" in result.error
