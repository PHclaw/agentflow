"""
订阅权益与配额（Entitlement）。

在此之前，``Subscription`` 表和 ``Subscription.can_create_agent()`` /
``can_send_message()`` 都是死代码：注册时不建订阅，创建 Agent 和发消息也
从不校验，``agents_used`` / ``messages_used`` 永远是 0。本模块把它们接进
真实业务流程。

三个设计取舍：

1. **懒创建订阅**，不只靠注册时创建。历史用户没有订阅记录，只靠注册时
   创建会让老用户一进产品就被判定成超额。
2. **agents_used 记「当前存量」而非「历史累计」**：创建 +1、删除 -1。
   否则删掉 Agent 不释放名额，用户会以为产品有 bug。
3. **周期懒重置**：到期时归零 ``messages_used`` 并顺延周期，不起定时任务。
   定时任务漏跑一次，配额就会永久卡死。
"""
import enum
import logging
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..models.agent import Agent
from ..models.subscription import PlanType, Subscription
from ..models.user import User

logger = logging.getLogger(__name__)

#: 计费周期长度。免费与月付都按 30 天滚动，避免处理大小月与跨年。
PERIOD_DAYS = 30

#: 配额超限的 HTTP 状态码。402 语义最贴切（需付费才能继续），
#: 前端据此与 403「无权限」区分开：弹升级引导，而不是提示无权访问。
HTTP_QUOTA_EXCEEDED = 402


class Resource(str, enum.Enum):
    """受配额约束的资源。"""

    AGENTS = "agents"
    MESSAGES = "messages"


class QuotaExceeded(Exception):
    """配额超限。

    不用 HTTPException 而用自定义异常，由 ``main.py`` 的异常处理器统一转成
    402 + 结构化响应体。若直接抛 HTTPException，detail 会被包成
    ``{"detail": {...}}``，前端现有的错误解析会把它 ``String()`` 成
    ``"[object Object]"``，拿不到 error code。
    """

    def __init__(self, resource, used, limit, plan, next_limit, message):
        super().__init__(message)
        self.resource = resource
        self.used = used
        self.limit = limit
        self.plan = plan
        self.next_limit = next_limit
        self.message = message

    def to_payload(self) -> dict:
        return {
            "error": "QUOTA_EXCEEDED",
            "resource": self.resource.value,
            "used": self.used,
            "limit": self.limit,
            "plan": self.plan,
            "next_limit": self.next_limit,
            "message": self.message,
        }


# --------------------------------------------------------------------------
# 内部工具
# --------------------------------------------------------------------------


def _utcnow() -> datetime:
    """naive UTC。

    列声明是 ``DateTime`` 而不是 ``TIMESTAMP WITH TIME ZONE``，SQLite 存进去
    再取回来会丢偏移量；统一按 naive UTC 读写最稳。
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _aware(dt):
    """把库里读出来的时间补上时区，才能和 aware 的 now 比较。"""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _ladder() -> list[tuple[str, int, int]]:
    """套餐阶梯 ``(plan, agent 额度, message 额度)``，由低到高。

    额度必须在同一处按 plan 排好，不能只用 ``is_pro`` 二分 ——
    ``is_pro`` 对 pro 与 team **都返回真**，二分会让团队版拿到专业版的额度，
    而套餐说明里写的又是另一个数字（这正是修复前 team 的状态：
    宣传 20 个 Agent / 50000 条消息，判定却按 PRO_AGENTS / PRO_MESSAGES 走）。
    """
    return [
        (PlanType.FREE.value, settings.FREE_AGENTS, settings.FREE_MESSAGES),
        (PlanType.PRO.value, settings.PRO_AGENTS, settings.PRO_MESSAGES),
        (PlanType.TEAM.value, settings.TEAM_AGENTS, settings.TEAM_MESSAGES),
    ]


def _plan_index(plan: str) -> int:
    for i, (code, _, _) in enumerate(_ladder()):
        if code == plan:
            return i
    # 未知套餐按最低档处理：额度被放大比被收紧危险得多
    return 0


def limits_for(sub: Subscription) -> dict:
    """该订阅各资源的额度。

    对 ``billing.get_subscription`` 也开放：用量接口返回的上限必须和
    实际判定用的是同一套数字，否则用户看到的和能用的不是一回事。
    """
    _, agents, messages = _ladder()[_plan_index(sub.plan)]
    return {Resource.AGENTS: agents, Resource.MESSAGES: messages}


def _next_limit(resource: Resource, sub: Subscription):
    """下一档的额度。

    返回 None 表示已经在最高档。给用户一个「升级能得到什么」的具体数字，
    比一句笼统的「请升级」有效得多。
    """
    ladder = _ladder()
    idx = _plan_index(sub.plan)
    if idx + 1 >= len(ladder):
        return None
    _, agents, messages = ladder[idx + 1]
    return agents if resource is Resource.AGENTS else messages


def _exceeded_message(resource: Resource, limit: int, next_limit) -> str:
    if resource is Resource.AGENTS:
        msg = f"当前套餐最多创建 {limit} 个 Agent"
    else:
        msg = f"本月消息额度已用完（上限 {limit} 条）"
    if next_limit:
        msg += f"，升级后为 {next_limit}"
    return msg


def _roll_period(sub: Subscription) -> bool:
    """周期为空或已过期时归零用量并顺延。

    返回是否有改动，供调用方决定是否 commit。
    """
    now = datetime.now(timezone.utc)
    end = _aware(sub.current_period_end)

    if end is None:
        sub.current_period_start = _utcnow()
        sub.current_period_end = _utcnow() + timedelta(days=PERIOD_DAYS)
        sub.messages_used = 0
        return True

    if now < end:
        return False

    # 已过期：按整期顺延，而不是直接从现在起算。
    # 否则一次补登会把本该在上个周期归零的用量延续到新周期，
    # 用户会发现自己这个月一开局就是超额的。
    while end <= now:
        end += timedelta(days=PERIOD_DAYS)
    sub.current_period_start = (end - timedelta(days=PERIOD_DAYS)).replace(tzinfo=None)
    sub.current_period_end = end.replace(tzinfo=None)
    sub.messages_used = 0
    return True


def new_free_subscription(user_id: int, agents_used: int = 0) -> Subscription:
    """新建一个免费订阅，周期当场初始化。

    不能在调用方直接 ``Subscription(...)`` 就完事：``current_period_end``
    为 None 时，``_roll_period`` 会把它当成「首期」并**把 messages_used
    一并归零**。注册后立刻发消息，用量会被抹掉，消息额度形同虚设。
    统一走这个工厂函数，保证周期永远有一致的初始状态。
    """
    sub = Subscription(
        user_id=user_id,
        plan=PlanType.FREE.value,
        status="active",
        agents_used=agents_used,
    )
    _roll_period(sub)
    return sub


async def _count_agents(db: AsyncSession, external_user_id: str) -> int:
    """用户当前的 Agent 存量。

    ``Agent.user_id`` 存的是 ``external_id``，而 ``Subscription.user_id``
    指向 ``users.id``，两套标识不能混用。
    """
    return await db.scalar(
        select(func.count()).select_from(Agent).where(Agent.user_id == external_user_id)
    ) or 0


# --------------------------------------------------------------------------
# 对外接口
# --------------------------------------------------------------------------


async def ensure_subscription(db: AsyncSession, external_user_id: str) -> Subscription:
    """取当前用户的订阅，没有就建一个免费版，并顺带做周期重置。"""
    user = await db.scalar(select(User).where(User.external_id == external_user_id))
    if user is None:
        # get_current_user_id 只解 JWT、不查库，用户记录被删后 token 仍然「有效」。
        # 这里必须拦住，否则会写出一个无所属的野订阅。
        raise HTTPException(status_code=401, detail="账号不存在，请重新登录")

    sub = await db.scalar(select(Subscription).where(Subscription.user_id == user.id))

    if sub is None:
        sub = new_free_subscription(
            user.id,
            # 用真实存量初始化，否则老用户会显示 0/N 却早已超额
            agents_used=await _count_agents(db, external_user_id),
        )
        db.add(sub)
        await db.flush()
        await db.commit()
        await db.refresh(sub)
        logger.info("用户 %s 无订阅记录，已懒创建免费版", external_user_id)
        return sub

    if _roll_period(sub):
        await db.commit()
    return sub


async def check(db: AsyncSession, sub: Subscription, resource: Resource) -> None:
    """配额校验，超限抛 ``QuotaExceeded``。"""
    limit = limits_for(sub)[resource]
    used = (sub.agents_used if resource is Resource.AGENTS else sub.messages_used) or 0

    if used >= limit:
        next_limit = _next_limit(resource, sub)
        raise QuotaExceeded(
            resource=resource,
            used=used,
            limit=limit,
            plan=sub.plan,
            next_limit=next_limit,
            message=_exceeded_message(resource, limit, next_limit),
        )


async def consume(db: AsyncSession, sub: Subscription, resource: Resource,
                  amount: int = 1) -> None:
    """累加用量。调用方负责 commit。"""
    field = "agents_used" if resource is Resource.AGENTS else "messages_used"
    setattr(sub, field, (getattr(sub, field) or 0) + amount)


async def release(db: AsyncSession, sub: Subscription, resource: Resource,
                  amount: int = 1) -> None:
    """释放配额（删除 Agent 时调用）。调用方负责 commit。"""
    field = "agents_used" if resource is Resource.AGENTS else "messages_used"
    setattr(sub, field, max(0, (getattr(sub, field) or 0) - amount))
