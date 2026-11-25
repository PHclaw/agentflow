"""邮箱验证码：签发、校验、频率控制。

存储策略
--------
优先 Redis，不可用时退回**数据库**：::

    Redis 可用   →  多 worker / 多实例共享，生产推荐
    Redis 不可用 →  存到数据库（同样跨重启、跨 worker，只是慢一点）

⚠️ **这里曾经退回「进程内存」，那是个真 bug，别改回去。**
内存存储扛不住两件必然会发生的事：

1. ``scripts/dev-backend.ps1`` 用 ``uvicorn --reload`` 启动，改一次 Python
   文件就重启一次 worker，内存里的验证码全部蒸发。它装的
   ``requirements-lite.txt`` 又刻意不含 Redis —— 开发时最常走的这条路，
   恰好每次改代码都把用户的码丢掉。
2. 多 worker / 多副本且没配 Redis：签发落在 A 进程、校验落在 B 进程。

两者症状完全一样：用户收到邮件、填进去，得到「验证码已过期，请重新获取」，
**而且远没到 TTL**。键不是过期了，是根本不存在了 —— 这个失败点极难查，
因为它看起来像「有效期配短了」。

数据库是本项目**必然存在**的依赖（Redis 不是），所以拿它当兜底：
不需要引入任何额外组件，就能同时解决上面两条。

安全策略
--------
- 验证码只存 **哈希**（以 JWT_SECRET_KEY 加盐），落库/缓存里看不到明文
- 单个码最多试错 ``CODE_MAX_ATTEMPTS`` 次，超过即作废（防 6 位码爆破）
- 校验成功 **立即删除**，防重放
- 同一邮箱有重发冷却与每小时上限（防把接口当免费发信机）
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.core.config import settings

logger = logging.getLogger(__name__)

# 验证码用途。文案侧（verification_copy）依赖这几个常量，
# 新增用途在这里加一处即可，不要在文案模块里另起一套。
PURPOSE_REGISTER = "register"
PURPOSE_LOGIN = "login"
PURPOSE_PASSWORD_RESET = "password_reset"


# --------------------------------------------------------------------------
# 返回结构
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class IssueOutcome:
    """签发结果。"""

    ok: bool
    code: str = ""
    error: str = ""
    retry_after: int = 0


@dataclass(frozen=True)
class VerifyOutcome:
    """校验结果。"""

    ok: bool
    error: str = ""


# --------------------------------------------------------------------------
# 存储后端
# --------------------------------------------------------------------------


class _MemoryStore:
    """进程内存存储（无 Redis 时的兜底）。"""

    def __init__(self) -> None:
        self._data: dict[str, tuple[str, float]] = {}

    def _purge(self) -> None:
        """顺手清理过期键，避免长期运行内存持续增长。"""
        now = time.time()
        stale = [k for k, (_, exp) in self._data.items() if exp and exp <= now]
        for k in stale:
            self._data.pop(k, None)

    async def get(self, key: str) -> str | None:
        self._purge()
        item = self._data.get(key)
        return item[0] if item else None

    async def set(self, key: str, value: str, ttl: int) -> None:
        self._data[key] = (value, time.time() + ttl if ttl > 0 else 0)

    async def delete(self, key: str) -> None:
        self._data.pop(key, None)

    async def incr(self, key: str, ttl: int) -> int:
        """自增计数；键不存在时按 ttl 初始化。"""
        self._purge()
        item = self._data.get(key)
        count = int(item[0]) + 1 if item else 1
        expire = item[1] if item else (time.time() + ttl if ttl > 0 else 0)
        self._data[key] = (str(count), expire)
        return count

    async def ttl(self, key: str) -> int:
        self._purge()
        item = self._data.get(key)
        if not item or not item[1]:
            return -1
        return max(0, int(item[1] - time.time()))

    def clear(self) -> None:
        self._data.clear()


class _RedisStore:
    """Redis 存储。键名自带前缀，避免与业务缓存撞车。"""

    def __init__(self, client) -> None:
        self._client = client

    async def get(self, key: str) -> str | None:
        val = await self._client.get(key)
        return val.decode() if isinstance(val, bytes) else val

    async def set(self, key: str, value: str, ttl: int) -> None:
        await self._client.set(key, value, ex=ttl if ttl > 0 else None)

    async def delete(self, key: str) -> None:
        await self._client.delete(key)

    async def incr(self, key: str, ttl: int) -> int:
        count = await self._client.incr(key)
        if count == 1:
            await self._client.expire(key, ttl)
        return int(count)

    async def ttl(self, key: str) -> int:
        return int(await self._client.ttl(key))

    def clear(self) -> None:
        """Redis 下不做整体清空（可能误删线上数据）。"""


class _DbStore:
    """数据库存储（无 Redis 时的兜底）。**持久**，跨重启、跨进程共享。

    键值语义与 ``_MemoryStore`` 完全一致 —— 尤其是 ``ttl <= 0`` 表示
    永不过期（存成 ``expires_at = NULL``）。调用方不该需要知道自己落在
    哪个后端上，所以这里连 ``ttl`` 的返回值含义都对齐（-1 表示无此键或
    永不过期）。

    并发：本流程是低频的（同一个人几分钟才发一次码），所以读写走普通的
    SELECT + 写回，不引 ``SELECT FOR UPDATE`` —— SQLite 下它是空操作，
    为了「每小时最多 5 次」这种限额去给 PostgreSQL 加行锁不划算。
    极端并发下计数可能少记一次，对限流强度没有实际影响。
    """

    @staticmethod
    def _session():
        # 测试注入点优先。测试库是每个用例独立的 SQLite 文件，不注入的话
        # 这里会开到**真实库**上去 —— 见 ``use_db_store_for_tests``。
        #
        # 注入的是「工厂」（async_sessionmaker），调一次拿会话；
        # 而 get_async_session_factory() 返回的也是工厂，所以还要再调一次。
        if _DB_SESSION_FACTORY is not None:
            return _DB_SESSION_FACTORY()
        # 延迟导入：本模块在 main 的启动阶段就被导入，那时数据库模块未必
        # 已就绪，顶层导入容易绕成循环依赖。
        from app.core.database import get_async_session_factory

        return get_async_session_factory()()

    @staticmethod
    def _expiry(ttl: int) -> datetime | None:
        """``ttl <= 0`` → ``None``，即永不过期（与内存后端同义）。"""
        if ttl <= 0:
            return None
        return datetime.utcnow() + timedelta(seconds=ttl)

    @staticmethod
    def _alive(row, now: datetime) -> bool:
        return row is not None and (row.expires_at is None or row.expires_at > now)

    async def get(self, key: str) -> str | None:
        from sqlalchemy import select

        from app.models.verification import VerificationCode

        async with self._session() as session:
            row = await session.scalar(
                select(VerificationCode).where(VerificationCode.key == key)
            )
            if not self._alive(row, datetime.utcnow()):
                return None
            return row.value

    async def set(self, key: str, value: str, ttl: int) -> None:
        from app.models.verification import VerificationCode

        async with self._session() as session:
            # merge 是「有则更新、无则插入」，不需要各数据库方言各写一套 upsert
            await session.merge(
                VerificationCode(
                    key=key,
                    value=value,
                    expires_at=self._expiry(ttl),
                    updated_at=datetime.utcnow(),
                )
            )
            await session.commit()

    async def delete(self, key: str) -> None:
        from sqlalchemy import delete as sa_delete

        from app.models.verification import VerificationCode

        async with self._session() as session:
            await session.execute(
                sa_delete(VerificationCode).where(VerificationCode.key == key)
            )
            await session.commit()

    async def incr(self, key: str, ttl: int) -> int:
        from sqlalchemy import select

        from app.models.verification import VerificationCode

        now = datetime.utcnow()
        async with self._session() as session:
            row = await session.scalar(
                select(VerificationCode).where(VerificationCode.key == key)
            )
            if self._alive(row, now):
                # 窗口在第一次计数时就固定下来，后续自增不延长它 ——
                # 否则「每小时上限」会变成「只要一直发就永远不算超」
                count = int(row.value or 0) + 1
                expires_at = row.expires_at
            else:
                count = 1
                expires_at = self._expiry(ttl)
            await session.merge(
                VerificationCode(
                    key=key, value=str(count), expires_at=expires_at, updated_at=now
                )
            )
            await session.commit()
            return count

    async def ttl(self, key: str) -> int:
        from sqlalchemy import select

        from app.models.verification import VerificationCode

        async with self._session() as session:
            row = await session.scalar(
                select(VerificationCode).where(VerificationCode.key == key)
            )
            if row is None or row.expires_at is None:
                return -1
            return max(0, int((row.expires_at - datetime.utcnow()).total_seconds()))

    async def purge_expired(self) -> int:
        """删掉已过期的行。

        内存后端是在每次访问时顺手清（``_purge``）；这里的数据是落盘的，
        不清会一直堆积，所以也留一个入口。调用时机由调用方决定 ——
        目前是启动时清一次。
        """
        from sqlalchemy import delete as sa_delete

        from app.models.verification import VerificationCode

        async with self._session() as session:
            result = await session.execute(
                sa_delete(VerificationCode).where(
                    VerificationCode.expires_at.is_not(None),
                    VerificationCode.expires_at <= datetime.utcnow(),
                )
            )
            await session.commit()
            return int(result.rowcount or 0)

    def clear(self) -> None:
        """生产后端不做整体清空（会误删其它进程正在用的码）。"""


_memory = _MemoryStore()
_store_cache = None
_redis_resolved = False

#: 数据库后端的会话工厂注入点（仅测试用）。见 ``use_db_store_for_tests``。
_DB_SESSION_FACTORY = None


async def _get_store():
    """解析存储后端，只探测一次。

    顺序：Redis（配了且连得上）→ 数据库。**兜底绝不是进程内存**，
    理由见模块开头那段 —— 一句话：内存扛不住 ``--reload`` 重启 worker，
    也跨不了进程，用户会看到「还没到期就说已过期」。
    """
    global _store_cache, _redis_resolved
    if _redis_resolved:
        return _store_cache

    try:
        import redis.asyncio as aioredis

        client = aioredis.from_url(
            settings.REDIS_URL,
            socket_connect_timeout=1,
            socket_timeout=1,
            decode_responses=False,
        )
        await client.ping()
        store = _RedisStore(client)
        logger.info("验证码存储：Redis（%s）", settings.REDIS_URL)
    except Exception as exc:  # noqa: BLE001 - 连不上 Redis 不该影响注册
        logger.info(
            "验证码存储：Redis 不可用（%s），改用数据库（跨重启 / 跨 worker 有效）",
            exc,
        )
        store = _DbStore()

    # **这两句必须在 await 之后**。原先 `_redis_resolved = True` 写在 ping
    # 前面，探测还没结束就宣称「已解析」，并发进来的第二个请求会读到
    # `_store_cache is None`，然后拿 None 当存储用 —— 直接 AttributeError。
    _store_cache = store
    _redis_resolved = True
    return _store_cache


async def log_store_backend() -> None:
    """启动时打一条日志，说明验证码落在哪个后端上。

    以前这个函数叫 ``warn_if_no_redis``：那时候没有 Redis 就退回进程内存，
    是个必须显式警告的危险状态。现在兜底是数据库，跨进程和重启都没问题，
    所以它降级成一条普通日志 —— 留着是为了让运维能一眼确认走的是哪条路。
    """
    store = await _get_store()
    if isinstance(store, _DbStore):
        try:
            removed = await store.purge_expired()
            if removed:
                logger.info("验证码存储：清理了 %d 条过期记录", removed)
        except Exception as exc:  # noqa: BLE001 - 清理失败不该挡住启动
            logger.warning("验证码过期记录清理失败：%s", exc)


def use_memory_for_tests() -> None:
    """强制使用内存后端并清空（仅供测试）。

    刻意不重置后端探测结果：否则每个用例都会去尝试连一次 Redis，
    探测失败要等满 socket 超时，上百个用例会白白多花上百秒。
    """
    global _store_cache, _redis_resolved
    _store_cache = _memory
    _redis_resolved = True
    _memory.clear()


def use_db_store_for_tests(session_factory=None) -> None:
    """强制使用数据库后端，并把会话工厂指到测试库（仅供测试）。

    ``session_factory`` 是 ``async_sessionmaker``（与
    ``app.core.database.get_async_session_factory()`` 的返回值同类型）。
    不注入就传 None，那会走真实库 —— 测试不要这么用。

    不注入的话 ``_DbStore`` 会开到**真实库**上去。与
    ``llm_config.use_test_db_for_tests`` 同一套路。
    """
    global _DB_SESSION_FACTORY, _store_cache, _redis_resolved
    _DB_SESSION_FACTORY = session_factory
    _store_cache = _DbStore()
    _redis_resolved = True


def simulate_worker_restart() -> None:
    """测试用：模拟 uvicorn worker 重启 —— 丢掉已解析的后端句柄，重新解析。

    真进程重启会把模块级全局一起丢掉；这里只丢「后端句柄」，**数据库本身
    当然还在** —— 它正是要验证的那一层。用它守住这条回归：

        发码（worker A）→ 重启 → 校验（worker B）必须仍然成功。

    改造前后端是进程内存，这条路径必然是「验证码已过期」。
    """
    global _store_cache, _redis_resolved
    _store_cache = None
    _redis_resolved = False


def reset_for_tests() -> None:
    """清空已存数据（仅供测试）。"""
    _memory.clear()


# --------------------------------------------------------------------------
# 键与哈希
# --------------------------------------------------------------------------


def _code_key(email: str, purpose: str) -> str:
    return f"vcode:code:{purpose}:{email.lower()}"


def _cooldown_key(email: str, purpose: str) -> str:
    return f"vcode:cooldown:{purpose}:{email.lower()}"


def _hourly_key(email: str, purpose: str) -> str:
    return f"vcode:hourly:{purpose}:{email.lower()}"


def _digest(email: str, code: str, purpose: str) -> str:
    """验证码哈希。以 JWT_SECRET_KEY 作为盐，避免离线撞库。"""
    raw = f"{email.lower()}:{code}:{purpose}:{settings.JWT_SECRET_KEY}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _generate_code() -> str:
    """密码学安全的定长数字码。"""
    upper = 10 ** settings.CODE_LENGTH
    return str(secrets.randbelow(upper)).zfill(settings.CODE_LENGTH)


# --------------------------------------------------------------------------
# 对外接口
# --------------------------------------------------------------------------


async def issue_code(email: str, purpose: str = PURPOSE_REGISTER) -> IssueOutcome:
    """签发验证码。

    频率控制通过则生成新码并写入存储；调用方拿到 ``code`` 后自行发信。
    """
    store = await _get_store()

    # 1) 重发冷却
    cool_key = _cooldown_key(email, purpose)
    if await store.get(cool_key) is not None:
        wait = await store.ttl(cool_key)
        return IssueOutcome(
            ok=False,
            error=f"验证码刚刚已发送，请 {max(wait, 1)} 秒后再试",
            retry_after=max(wait, 1),
        )

    # 2) 每小时上限
    count = await store.incr(_hourly_key(email, purpose), ttl=3600)
    if count > settings.CODE_HOURLY_LIMIT:
        return IssueOutcome(
            ok=False,
            error=f"该邮箱获取验证码过于频繁（每小时最多 {settings.CODE_HOURLY_LIMIT} 次），请稍后再试",
            retry_after=3600,
        )

    # 3) 落库 + 置冷却
    code = _generate_code()
    payload = json.dumps({
        "h": _digest(email, code, purpose),
        "n": 0,
        "c": time.time(),
    })
    await store.set(_code_key(email, purpose), payload, settings.CODE_TTL_SECONDS)
    # 只有配了正的冷却时间才落冷却键。
    # 存储层里 ttl<=0 的语义是「永不过期」，若配置成 0 还照写，
    # 冷却键就永远在，该邮箱会被永久锁死。
    if settings.CODE_RESEND_INTERVAL > 0:
        await store.set(cool_key, "1", settings.CODE_RESEND_INTERVAL)

    return IssueOutcome(ok=True, code=code)


async def verify_code(email: str, code: str,
                      purpose: str = PURPOSE_REGISTER,
                      *, consume: bool = True) -> VerifyOutcome:
    """校验验证码。

    ``consume=True``（默认）：校验通过即作废，防重放。
    ``consume=False``：只校验，**不删除**。

    为什么需要 ``consume=False``——这是「码还没到期却提示已过期」的真身：

    ``/register`` 里校验码只是**第一道**关卡，后面还有「邮箱是否已注册」和
    「密码强度」。原来校验通过就立刻删码，于是用户因为密码太弱（或邮箱已被
    注册）被退回，改一改再点一次注册时，码已经没了 —— 他看到的是
    「验证码已过期，请重新获取」，而手上这个码才拿到几十秒。
    用户无从判断，只会觉得「验证码过期太快」。

    所以注册流程用 ``consume=False`` 先验，等所有关卡都过了再
    ``consume_code`` 真正消费。
    """
    if not code:
        return VerifyOutcome(False, "请输入验证码")

    store = await _get_store()
    key = _code_key(email, purpose)
    raw = await store.get(key)
    if not raw:
        return VerifyOutcome(False, "验证码已过期，请重新获取")

    try:
        data = json.loads(raw)
    except ValueError:
        await store.delete(key)
        return VerifyOutcome(False, "验证码已失效，请重新获取")

    if hmac.compare_digest(data.get("h", ""), _digest(email, code, purpose)):
        if consume:
            await store.delete(key)
        return VerifyOutcome(True)

    # 试错计数；超过上限直接作废，避免被暴力枚举
    data["n"] = int(data.get("n", 0)) + 1
    if data["n"] >= settings.CODE_MAX_ATTEMPTS:
        await store.delete(key)
        return VerifyOutcome(False, "验证码错误次数过多，请重新获取")

    remain_ttl = max(1, int(data.get("c", time.time()) + settings.CODE_TTL_SECONDS - time.time()))
    await store.set(key, json.dumps(data), remain_ttl)
    left = settings.CODE_MAX_ATTEMPTS - data["n"]
    return VerifyOutcome(False, f"验证码不正确，还可尝试 {left} 次")


async def consume_code(email: str, code: str,
                       purpose: str = PURPOSE_REGISTER) -> None:
    """手动作废某个邮箱的验证码（例如注册成功后清理）。"""
    store = await _get_store()
    await store.delete(_code_key(email, purpose))
