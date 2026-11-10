"""
管理后台 API。

只对 admin 角色开放（``require_admin``）。三类能力：

1. **看行为** —— 平台概览、用户列表、单个用户的画像与明细
2. **调套餐** —— 给指定用户设定订阅版本
3. **管技能** —— 增删改技能广场的 Skill（写 ``skills/<slug>/SKILL.md``）

设计取舍：

- 用户列表的聚合（Agent 数 / 会话数 / 消息数）用**相关子查询**而不是
  逐个用户再查一遍，避免 N+1。用户量上千时这里仍然是一条 SQL。
- 改套餐只改 ``plan`` 和 ``status``，**不动用量计数器**。管理员给的是额度，
  不是清除已用量；需要重置得显式传 ``reset_usage``。
- 每次改套餐都写日志（谁改的、改成什么），便于事后追责 —— 这是能绕过
  计费的操作，不留痕是不行的。
- 技能是**文件**不是数据库行，所以「删除技能」是真的删目录。写路径的
  slug 校验、原子写、缓存失效都在 ``skill.store`` 里，这里只做鉴权与入参。
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from ..core.database import get_db
from ..models.agent import Agent, ChatSession, KnowledgeBase
from ..models.document import Document
from ..models.subscription import PlanType, Subscription
from ..models.user import User, UserRole
from ..services.entitlement import new_free_subscription
from ..services.skill import store as skill_store
from ..services import skill_package
from .billing import PLANS
from .chat import _session_title
from .deps import require_admin

logger = logging.getLogger(__name__)

router = APIRouter()

#: 用户详情里最多展示多少条最近会话。统计总数不受这个限制。
RECENT_SESSION_LIMIT = 20


def _iso(dt) -> Optional[str]:
    return dt.isoformat() if dt else None


def _aware(dt):
    """SQLite 取回来的时间没有时区，和 aware 的 now 比较会抛 TypeError。"""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# --------------------------------------------------------------------------
# 聚合子查询
# --------------------------------------------------------------------------
#
# Agent / ChatSession 的 user_id 存的是 User.external_id（字符串），
# 而 Subscription.user_id 指向 users.id（整数）。两套标识不能混用，
# 写错会静默返回 0。

_AGENT_COUNT = (
    select(func.count(Agent.id))
    .where(Agent.user_id == User.external_id)
    .scalar_subquery()
)

_SESSION_COUNT = (
    select(func.count(ChatSession.id))
    .where(ChatSession.user_id == User.external_id)
    .scalar_subquery()
)

_MESSAGE_COUNT = (
    select(func.coalesce(func.sum(Agent.message_count), 0))
    .where(Agent.user_id == User.external_id)
    .scalar_subquery()
)

_KB_COUNT = (
    select(func.count(KnowledgeBase.id))
    .where(KnowledgeBase.user_id == User.external_id)
    .scalar_subquery()
)

_LAST_SESSION_AT = (
    select(func.max(ChatSession.updated_at))
    .where(ChatSession.user_id == User.external_id)
    .scalar_subquery()
)


# --------------------------------------------------------------------------
# 概览
# --------------------------------------------------------------------------


@router.get("/overview")
async def get_overview(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """平台概览：用户、活跃、内容量、套餐分布、付费转化。"""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    since_1d = now - timedelta(days=1)
    since_7d = now - timedelta(days=7)
    since_30d = now - timedelta(days=30)

    total_users = await db.scalar(select(func.count(User.id))) or 0
    new_1d = await db.scalar(
        select(func.count(User.id)).where(User.created_at >= since_1d)
    ) or 0
    new_7d = await db.scalar(
        select(func.count(User.id)).where(User.created_at >= since_7d)
    ) or 0
    new_30d = await db.scalar(
        select(func.count(User.id)).where(User.created_at >= since_30d)
    ) or 0
    # 活跃按「N 天内登录过」算。没有埋点，登录时间是目前唯一可靠的活跃信号。
    active_7d = await db.scalar(
        select(func.count(User.id)).where(User.last_login_at >= since_7d)
    ) or 0
    active_30d = await db.scalar(
        select(func.count(User.id)).where(User.last_login_at >= since_30d)
    ) or 0
    # 从没登录过的账号（注册完就再没回来）值得单独看一眼，是转化漏斗的第一道漏
    never_logged_in = await db.scalar(
        select(func.count(User.id)).where(User.last_login_at.is_(None))
    ) or 0
    admins = await db.scalar(
        select(func.count(User.id)).where(User.role == UserRole.ADMIN.value)
    ) or 0
    disabled = await db.scalar(
        select(func.count(User.id)).where(User.is_active.is_(False))
    ) or 0

    total_agents = await db.scalar(select(func.count(Agent.id))) or 0
    total_sessions = await db.scalar(select(func.count(ChatSession.id))) or 0
    total_messages = await db.scalar(
        select(func.coalesce(func.sum(Agent.message_count), 0))
    ) or 0
    total_kbs = await db.scalar(select(func.count(KnowledgeBase.id))) or 0
    total_docs = await db.scalar(select(func.count(Document.id))) or 0
    total_doc_bytes = await db.scalar(
        select(func.coalesce(func.sum(Document.file_size), 0))
    ) or 0

    plan_rows = (
        await db.execute(
            select(Subscription.plan, func.count(Subscription.id))
            .group_by(Subscription.plan)
        )
    ).all()
    plan_counts = {plan or PlanType.FREE.value: count for plan, count in plan_rows}
    # 没订阅记录的用户（功能上线前注册、且一直没触发懒创建）也算免费版，
    # 否则各档相加会对不上总用户数
    subscribed = sum(plan_counts.values())
    if total_users > subscribed:
        plan_counts[PlanType.FREE.value] = (
            plan_counts.get(PlanType.FREE.value, 0) + (total_users - subscribed)
        )

    distribution = [
        {"plan": code, "name": PLANS.get(code, {}).get("name", code), "count": plan_counts.get(code, 0)}
        for code in PLANS
    ]
    paid_users = sum(
        count for code, count in plan_counts.items() if code != PlanType.FREE.value
    )

    return {
        "users": {
            "total": total_users,
            "new_1d": new_1d,
            "new_7d": new_7d,
            "new_30d": new_30d,
            "active_7d": active_7d,
            "active_30d": active_30d,
            "never_logged_in": never_logged_in,
            "admins": admins,
            "disabled": disabled,
            "paid": paid_users,
            # 付费转化率。分母为 0 时返回 0 而不是报错。
            "conversion": round(paid_users / total_users * 100, 1) if total_users else 0.0,
        },
        "content": {
            "agents": total_agents,
            "sessions": total_sessions,
            "messages": total_messages,
            "knowledge_bases": total_kbs,
            "documents": total_docs,
            "document_bytes": total_doc_bytes,
        },
        "plans": distribution,
    }


@router.get("/trends")
async def get_trends(
    days: int = Query(14, ge=2, le=90, description="统计最近多少天"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """近 N 天的每日趋势：新增用户、新建会话、有对话活动的用户数。

    只有这三项做得出按天序列。**消息量做不出** —— ``Agent.message_count``
    是累计值，没有按天的消息流水，所以这里不编一个出来。

    日期按 UTC 切分（库里存的就是 naive UTC），跨时区部署时日期边界会偏，
    这个偏差对趋势观察可以接受。
    """
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=days - 1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    start_naive = start.replace(tzinfo=None)

    async def _daily(date_col, count_expr, extra_where=None):
        stmt = (
            select(func.date(date_col).label("d"), count_expr)
            .where(date_col >= start_naive)
            .group_by(func.date(date_col))
        )
        if extra_where is not None:
            stmt = stmt.where(extra_where)
        rows = (await db.execute(stmt)).all()
        # func.date() 在 SQLite 返回字符串、Postgres 返回 date，统一成字符串
        return {str(d): int(c or 0) for d, c in rows}

    new_users = await _daily(User.created_at, func.count(User.id))
    new_sessions = await _daily(ChatSession.created_at, func.count(ChatSession.id))
    active_users = await _daily(
        ChatSession.updated_at, func.count(func.distinct(ChatSession.user_id))
    )

    series = []
    for i in range(days):
        day = (start + timedelta(days=i)).strftime("%Y-%m-%d")
        series.append({
            "date": day,
            "new_users": new_users.get(day, 0),
            "new_sessions": new_sessions.get(day, 0),
            "active_users": active_users.get(day, 0),
        })

    return {
        "days": days,
        "start": series[0]["date"],
        "end": series[-1]["date"],
        "series": series,
        "totals": {
            "new_users": sum(p["new_users"] for p in series),
            "new_sessions": sum(p["new_sessions"] for p in series),
            "active_users": sum(p["active_users"] for p in series),
        },
    }


@router.get("/agents/top")
async def top_agents(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """最活跃的 Agent 排行。"""
    session_count = (
        select(func.count(ChatSession.id))
        .where(ChatSession.agent_id == Agent.id)
        .scalar_subquery()
    )
    last_active = (
        select(func.max(ChatSession.updated_at))
        .where(ChatSession.agent_id == Agent.id)
        .scalar_subquery()
    )

    rows = (
        await db.execute(
            select(
                Agent,
                User.email,
                session_count.label("session_count"),
                last_active.label("last_active_at"),
            )
            .outerjoin(User, User.external_id == Agent.user_id)
            .order_by(
                func.coalesce(Agent.message_count, 0).desc(),
                session_count.desc(),
            )
            .limit(limit)
        )
    ).all()

    return {
        "items": [
            {
                "id": agent.id,
                "name": agent.name,
                "owner_email": email,
                "message_count": agent.message_count or 0,
                "session_count": session_count or 0,
                "is_active": agent.is_active,
                "has_workflow": bool(
                    (agent.workflow_definition or {}).get("nodes")
                ),
                "created_at": _iso(agent.created_at),
                "last_active_at": _iso(last_active_at),
            }
            for agent, email, session_count, last_active_at in rows
        ]
    }


# --------------------------------------------------------------------------
# 用户列表 / 明细
# --------------------------------------------------------------------------


class PlanChangeRequest(BaseModel):
    #: free / pro / team
    plan: str
    #: 是否同时把用量计数器归零（新周期重新开始算）
    reset_usage: bool = False


def _user_row(row) -> dict:
    user: User = row[0]
    last_login = _aware(user.last_login_at)
    last_session = _aware(row.last_session_at)
    # 最后活跃取「登录」与「最后一次对话」里更晚的那个：
    # 长期挂着登录态、但一直在聊天的用户，只看登录时间会被误判成不活跃
    candidates = [t for t in (last_login, last_session) if t]
    last_active = max(candidates) if candidates else None

    return {
        "id": user.external_id,
        "email": user.email,
        "nickname": user.nickname,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": _iso(user.created_at),
        "last_login_at": _iso(user.last_login_at),
        "last_active_at": _iso(last_active),
        "plan": row.plan or PlanType.FREE.value,
        "plan_status": row.status or "active",
        "agents_used": row.agents_used or 0,
        "messages_used": row.messages_used or 0,
        "agent_count": row.agent_count or 0,
        "session_count": row.session_count or 0,
        "message_count": row.message_count or 0,
    }


@router.get("/users")
async def list_users(
    search: str = Query("", description="按邮箱或昵称模糊匹配"),
    plan: str = Query("", description="按套餐过滤"),
    role: str = Query("", description="按角色过滤：admin / user"),
    status: str = Query("", description="按状态过滤：active / disabled"),
    activity: str = Query(
        "", description="按活跃度过滤：active_7d / active_30d / dormant / never"
    ),
    sort: str = Query("created_at", description="排序字段"),
    order: str = Query("desc", description="asc / desc"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """用户列表，带用量与行为聚合，支持搜索 / 多维筛选 / 排序。"""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    filters = []

    if search.strip():
        like = f"%{search.strip()}%"
        filters.append(or_(User.email.ilike(like), User.nickname.ilike(like)))

    if plan.strip():
        if plan not in PLANS:
            raise HTTPException(status_code=400, detail=f"未知套餐：{plan}")
        if plan == PlanType.FREE.value:
            # 免费版包含「没有订阅记录」的账号，用 IS NULL 兜住
            filters.append(
                or_(
                    Subscription.plan == PlanType.FREE.value,
                    Subscription.plan.is_(None),
                )
            )
        else:
            filters.append(Subscription.plan == plan)

    if role.strip():
        if role not in (UserRole.ADMIN.value, UserRole.USER.value):
            raise HTTPException(status_code=400, detail=f"未知角色：{role}")
        filters.append(User.role == role)

    if status.strip():
        if status == "active":
            filters.append(User.is_active.is_(True))
        elif status == "disabled":
            filters.append(User.is_active.is_(False))
        else:
            raise HTTPException(status_code=400, detail=f"未知状态：{status}")

    if activity.strip():
        since_7d = now - timedelta(days=7)
        since_30d = now - timedelta(days=30)
        activity_filter = {
            "active_7d": User.last_login_at >= since_7d,
            "active_30d": User.last_login_at >= since_30d,
            # 「沉睡」是 30 天前登录过、但近 30 天没来的那批
            "dormant": User.last_login_at < since_30d,
            "never": User.last_login_at.is_(None),
        }.get(activity)
        if activity_filter is None:
            raise HTTPException(status_code=400, detail=f"未知活跃度：{activity}")
        filters.append(activity_filter)

    base = select(User.id).outerjoin(Subscription, Subscription.user_id == User.id)
    if filters:
        base = base.where(*filters)
    total = len((await db.execute(base)).all())

    agent_count = _AGENT_COUNT.label("agent_count")
    session_count = _SESSION_COUNT.label("session_count")
    message_count = _MESSAGE_COUNT.label("message_count")

    # 排序字段走白名单映射，不把用户输入拼进 SQL
    sortable = {
        "created_at": User.created_at,
        "last_login_at": User.last_login_at,
        "email": User.email,
        "agent_count": agent_count,
        "session_count": session_count,
        "message_count": message_count,
    }
    if sort not in sortable:
        raise HTTPException(
            status_code=400,
            detail=f"未知排序字段：{sort}，可选 {'/'.join(sortable)}",
        )

    column = sortable[sort]
    # NULL 统一排在最后：从没登录过的账号不该霸占「最近」榜首
    direction = column.asc() if order == "asc" else column.desc()

    stmt = (
        select(
            User,
            Subscription.plan,
            Subscription.status,
            Subscription.agents_used,
            Subscription.messages_used,
            agent_count,
            session_count,
            message_count,
            _LAST_SESSION_AT.label("last_session_at"),
        )
        .outerjoin(Subscription, Subscription.user_id == User.id)
        .order_by(column.is_(None), direction)
        .limit(limit)
        .offset(offset)
    )
    if filters:
        stmt = stmt.where(*filters)

    rows = (await db.execute(stmt)).all()
    return {
        "items": [_user_row(r) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
        "sort": sort,
        "order": order,
    }


@router.get("/users/{user_id}")
async def get_user_detail(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """单个用户的画像与行为明细。

    ``user_id`` 用 external_id（对外暴露的 ID），不是自增主键。
    """
    user = await db.scalar(select(User).where(User.external_id == user_id))
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    sub = await db.scalar(
        select(Subscription).where(Subscription.user_id == user.id)
    )

    agents = (
        await db.execute(
            select(Agent)
            .where(Agent.user_id == user_id)
            .order_by(Agent.created_at.desc())
        )
    ).scalars().all()

    # 最近会话只取 20 条用于展示，但「会话数」统计必须是真实总数 ——
    # 直接拿 len(sessions) 会让超过 20 条的用户永远显示成 20，
    # 和列表页的数字对不上，看起来像统计坏了。
    sessions = (
        await db.execute(
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .order_by(ChatSession.updated_at.desc())
            .limit(RECENT_SESSION_LIMIT)
        )
    ).scalars().all()

    session_total = await db.scalar(
        select(func.count(ChatSession.id)).where(ChatSession.user_id == user_id)
    ) or 0

    # 知识库连同文档量与占用空间。占用是知识库最容易被忽略的限额维度，
    # 管理端要能一眼看出谁在占空间。
    kb_rows = (
        await db.execute(
            select(KnowledgeBase)
            .where(KnowledgeBase.user_id == user_id)
            .order_by(KnowledgeBase.created_at.desc())
        )
    ).scalars().all()
    kb_items = []
    for kb in kb_rows:
        doc_count, doc_bytes = (
            await db.execute(
                select(
                    func.count(Document.id),
                    func.coalesce(func.sum(Document.file_size), 0),
                ).where(Document.kb_id == kb.id)
            )
        ).one()
        kb_items.append({
            "id": kb.id,
            "name": kb.name,
            "document_count": int(doc_count or 0),
            "bytes": int(doc_bytes or 0),
            "created_at": _iso(kb.created_at),
        })

    agent_names = {a.id: a.name for a in agents}
    session_items = [_session_row(s, agent_names) for s in sessions]

    last_login = _aware(user.last_login_at)
    last_session = _aware(sessions[0].updated_at) if sessions else None
    candidates = [t for t in (last_login, last_session) if t]

    return {
        "user": {
            "id": user.external_id,
            "email": user.email,
            "phone": user.phone,
            "nickname": user.nickname,
            "role": user.role,
            "is_active": user.is_active,
            "is_verified": user.is_verified,
            "created_at": _iso(user.created_at),
            "last_login_at": _iso(user.last_login_at),
            "last_active_at": _iso(max(candidates) if candidates else None),
        },
        "subscription": {
            "plan": sub.plan if sub else PlanType.FREE.value,
            "status": sub.status if sub else "active",
            "agents_used": (sub.agents_used or 0) if sub else 0,
            "messages_used": (sub.messages_used or 0) if sub else 0,
            "current_period_start": _iso(sub.current_period_start) if sub else None,
            "current_period_end": _iso(sub.current_period_end) if sub else None,
            "cancel_at_period_end": bool(sub.cancel_at_period_end) if sub else False,
            "stripe_subscription_id": (sub.stripe_subscription_id if sub else None),
        },
        "stats": {
            "agents": len(agents),
            "sessions": session_total,
            "messages": sum(a.message_count or 0 for a in agents),
            "knowledge_bases": len(kb_items),
            "documents": sum(k["document_count"] for k in kb_items),
            "document_bytes": sum(k["bytes"] for k in kb_items),
        },
        "agents": [
            {
                "id": a.id,
                "name": a.name,
                "description": a.description or "",
                "message_count": a.message_count or 0,
                "is_active": a.is_active,
                # 走工作流的 Agent 与直连模型的 Agent，排查问题时表现完全不同，
                # 列表里要能分辨
                "has_workflow": bool((a.workflow_definition or {}).get("nodes")),
                "model": (a.model_config or {}).get("model"),
                "knowledge_base_id": a.knowledge_base_id,
                "created_at": _iso(a.created_at),
            }
            for a in agents
        ],
        "knowledge_bases": kb_items,
        # 保留字段名兼容旧调用方，实际就是最近 RECENT_SESSION_LIMIT 条
        "recent_sessions": session_items,
        "recent_session_limit": RECENT_SESSION_LIMIT,
    }


# --------------------------------------------------------------------------
# 设定订阅版本
# --------------------------------------------------------------------------


@router.patch("/users/{user_id}/subscription")
async def set_user_subscription(
    user_id: str,
    data: PlanChangeRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """给指定用户设定订阅版本。

    目前是「线下收款 + 管理员手工开通」模式，所以这里没有走支付，
    直接改套餐。接入支付渠道后这里应该只保留「补偿性调整」的用途。
    """
    if data.plan not in PLANS:
        raise HTTPException(
            status_code=400,
            detail=f"未知套餐：{data.plan}，可选 {'/'.join(PLANS)}",
        )

    user = await db.scalar(select(User).where(User.external_id == user_id))
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    sub = await db.scalar(select(Subscription).where(Subscription.user_id == user.id))
    if sub is None:
        sub = new_free_subscription(user.id)
        db.add(sub)
        await db.flush()

    before = sub.plan
    sub.plan = data.plan
    # 手工开通一律置为 active：否则用户会拿到一个新套餐却因为 status=past_due
    # 而判定为非 pro，看起来「改了没生效」。
    sub.status = "active"
    if data.reset_usage:
        sub.messages_used = 0

    await db.commit()
    await db.refresh(sub)

    # 能绕过计费的操作必须留痕
    logger.info(
        "管理员 %s 将用户 %s 的套餐从 %s 改为 %s（reset_usage=%s）",
        admin.email, user.email, before, data.plan, data.reset_usage,
    )

    return {
        "user_id": user.external_id,
        "email": user.email,
        "previous_plan": before,
        "plan": sub.plan,
        "status": sub.status,
        "agents_used": sub.agents_used or 0,
        "messages_used": sub.messages_used or 0,
        "reset_usage": data.reset_usage,
    }


# --------------------------------------------------------------------------
# 会话：分页与内容
# --------------------------------------------------------------------------


async def _agent_names(db: AsyncSession, agent_ids: list[str]) -> dict[str, str]:
    ids = [a for a in set(agent_ids) if a]
    if not ids:
        return {}
    rows = (await db.execute(
        select(Agent.id, Agent.name).where(Agent.id.in_(ids))
    )).all()
    return {aid: name for aid, name in rows}


def _session_row(session: ChatSession, names: dict[str, str]) -> dict:
    messages = session.messages or []
    return {
        "id": session.id,
        "agent_id": session.agent_id,
        # Agent 可能已被删除，会话还在。留个说明，不要显示成空白
        "agent_name": names.get(session.agent_id, "（已删除的 Agent）"),
        "title": _session_title(messages) or "（空对话）",
        "message_count": len(messages),
        "created_at": _iso(session.created_at),
        "updated_at": _iso(session.updated_at),
    }


@router.get("/users/{user_id}/sessions")
async def list_user_sessions(
    user_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """某个用户的会话列表（分页）。

    用户详情里只给最近若干条，翻更早的历史走这里。
    """
    user = await db.scalar(select(User).where(User.external_id == user_id))
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    total = await db.scalar(
        select(func.count(ChatSession.id)).where(ChatSession.user_id == user_id)
    ) or 0

    sessions = (
        await db.execute(
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .order_by(ChatSession.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()

    names = await _agent_names(db, [s.agent_id for s in sessions])

    return {
        "items": [_session_row(s, names) for s in sessions],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/sessions/{session_id}")
async def get_session_detail(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """单个会话的完整消息内容。

    **管理权限等同于可读全部用户对话**。这是排查问题的必要能力，但授权时
    要有这个认知：拿到 admin 就等于能看所有人的原始聊天记录。
    """
    session = await db.get(ChatSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")

    user = await db.scalar(select(User).where(User.external_id == session.user_id))
    names = await _agent_names(db, [session.agent_id])

    messages = [
        {
            "role": m.get("role"),
            "content": m.get("content"),
            "created_at": m.get("created_at") or m.get("timestamp"),
            # 工作区产物的下载地址，管理端只做展示
            "files": m.get("files") or [],
        }
        for m in (session.messages or [])
    ]

    return {
        "id": session.id,
        "agent_id": session.agent_id,
        "agent_name": names.get(session.agent_id, "（已删除的 Agent）"),
        "user_id": session.user_id,
        "user_email": user.email if user else None,
        "title": _session_title(session.messages) or "（空对话）",
        "message_count": len(messages),
        "created_at": _iso(session.created_at),
        "updated_at": _iso(session.updated_at),
        "messages": messages,
    }


# --------------------------------------------------------------------------
# 账号启停
# --------------------------------------------------------------------------


class UserStatusRequest(BaseModel):
    is_active: bool


@router.patch("/users/{user_id}/status")
async def set_user_status(
    user_id: str,
    data: UserStatusRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """启用 / 停用账号。

    停用会立即生效：``get_current_user_id`` 每次请求都核对 ``is_active``，
    旧 token 也会被拦下，同时在登录处拒绝重新登录。
    """
    # 不允许停用自己：一不小心就把自己锁在门外，而且界面上没有任何路能救回来
    if user_id == admin.external_id:
        raise HTTPException(status_code=400, detail="不能停用当前登录的账号")

    user = await db.scalar(select(User).where(User.external_id == user_id))
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    user.is_active = data.is_active
    await db.commit()
    await db.refresh(user)

    logger.info(
        "管理员 %s 将用户 %s 设为%s",
        admin.email, user.email, "启用" if data.is_active else "停用",
    )

    return {
        "user_id": user.external_id,
        "email": user.email,
        "is_active": user.is_active,
    }


# ---------------------------------------------------------------------------
# 技能管理
#
# 技能是**文件**（``skills/<slug>/SKILL.md``）而不是数据库行，所以这里的
# 「增删改」真的在动文件系统。slug 校验、原子写、缓存失效都在
# ``skill.store`` 里，这里只负责鉴权和入参形状。
#
# 不支持改名：改 slug 意味着「删旧建新」，会丢掉调用计数与评分。
# 要改就删掉重建，这是明确的产品取舍而不是遗漏。
# ---------------------------------------------------------------------------


class SkillWriteRequest(BaseModel):
    """新建 / 更新技能的请求体。"""

    slug: str = Field(
        ..., min_length=1, max_length=64,
        description="目录名，只能包含小写字母、数字、连字符",
    )
    frontmatter: dict[str, Any] = Field(
        ..., description="SKILL.md 的 JSON frontmatter，name 与 systemPrompt 必填",
    )
    body: str = Field("", description="围栏之后的 Markdown 正文")


class SkillMetaOut(BaseModel):
    """技能列表项。"""

    slug: str
    id: str
    name: str
    description: str = ""
    specialty: str = ""
    version: str = ""
    tags: list[Any] = []
    status: str = "published"
    visibility: str = "public"
    author_name: str = ""
    total_calls: int = 0
    avg_rating: float = 0.0
    has_scripts: bool = False
    #: True 表示命中平台保留名单，广场不展示
    hidden: bool = False
    #: SKILL.md 解析失败的原因。非空表示这个技能在广场里是「凭空消失」的
    broken: Optional[str] = None
    updated_at: Optional[str] = None


class SkillDetailOut(SkillMetaOut):
    frontmatter: dict[str, Any]
    body: str


def _skill_meta(slug: str, meta: dict[str, Any], broken: Optional[str] = None) -> dict:
    """把 frontmatter 拍平成列表项。"""
    folder = skill_store.skill_dir(slug)
    md_path = folder / skill_store.SKILL_FILENAME
    try:
        mtime = md_path.stat().st_mtime
    except OSError:
        mtime = 0.0
    return {
        "slug": slug,
        "id": str(meta.get("id") or slug),
        "name": str(meta.get("name") or slug),
        "description": str(meta.get("description") or ""),
        "specialty": str(meta.get("specialty") or ""),
        "version": str(meta.get("version") or ""),
        "tags": meta.get("tags") if isinstance(meta.get("tags"), list) else [],
        "status": str(meta.get("status") or "published"),
        "visibility": str(meta.get("visibility") or "public"),
        "author_name": str(meta.get("authorName") or ""),
        "total_calls": int(meta.get("totalCalls") or 0),
        "avg_rating": float(meta.get("avgRating") or 0),
        "has_scripts": (folder / "scripts").is_dir(),
        "hidden": slug in skill_store.HIDDEN_SLUGS,
        "broken": broken,
        "updated_at": _iso(datetime.fromtimestamp(mtime)) if mtime else None,
    }


def _skill_detail(slug: str) -> SkillDetailOut:
    meta, body = skill_store.read_skill_md(skill_store.resolve_slug(slug))
    return SkillDetailOut(**_skill_meta(slug, meta), frontmatter=meta, body=body)


@router.get("/skills", response_model=list[SkillMetaOut])
async def list_admin_skills(_: User = Depends(require_admin)):
    """技能列表（含广场不可见的保留目录）。

    与 ``GET /skills/plaza`` 的区别：那个只给用户看，这里要能看到**全部** ——
    否则管理员建完发现广场上没有，根本不知道是被保留名单挡了。
    """
    root = skill_store.skills_root()
    items: list[dict] = []
    for folder in sorted(root.iterdir(), key=lambda p: p.name):
        if not folder.is_dir() or folder.name.startswith("."):
            continue
        if not (folder / skill_store.SKILL_FILENAME).is_file():
            continue
        try:
            meta, _body = skill_store.read_skill_md(folder.name)
            broken = None
        except skill_store.SkillWriteError as exc:
            # frontmatter 坏掉的技能在广场里是直接消失的。
            # 管理端必须把它列出来，否则没人知道该去修哪个目录。
            logger.warning("技能 %s 的 SKILL.md 解析失败: %s", folder.name, exc)
            meta, broken = {}, str(exc)
        items.append(_skill_meta(folder.name, meta, broken))
    return items


@router.get("/skills/{slug}", response_model=SkillDetailOut)
async def get_admin_skill(slug: str, _: User = Depends(require_admin)):
    """单个技能的完整内容（frontmatter 与正文分开）。"""
    try:
        return _skill_detail(slug)
    except skill_store.SkillWriteError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/skills", response_model=SkillDetailOut, status_code=201)
async def create_admin_skill(
    data: SkillWriteRequest,
    admin: User = Depends(require_admin),
):
    """新建技能。slug 已存在时返回 400，不会覆盖。"""
    try:
        skill_store.create_skill(data.slug, data.frontmatter, data.body)
    except skill_store.SkillWriteError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    logger.info("管理员 %s 创建技能 %s", admin.email, data.slug)
    return _skill_detail(data.slug)


@router.patch("/skills/{slug}", response_model=SkillDetailOut)
async def update_admin_skill(
    slug: str,
    data: SkillWriteRequest,
    admin: User = Depends(require_admin),
):
    """更新已有技能的 frontmatter 与正文。

    路径里的 slug 与 body 里的不一致时以**路径**为准并拒绝请求 ——
    静默改名会让前端拿着旧 slug 继续操作，而文件已经去了别处。
    """
    if data.slug.strip().lower() != slug.strip():
        raise HTTPException(
            status_code=400,
            detail="路径中的 slug 与请求体的不一致；改名请删除后重建",
        )
    try:
        skill_store.update_skill(slug, data.frontmatter, data.body)
    except skill_store.SkillWriteError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    logger.info("管理员 %s 更新技能 %s", admin.email, slug)
    return _skill_detail(slug)


@router.delete("/skills/{slug}")
async def delete_admin_skill(slug: str, admin: User = Depends(require_admin)):
    """删除技能目录（含 scripts/）。

    平台保留目录（见 ``HIDDEN_SLUGS``）会被拒绝 —— 那些是预置资源，
    误删的代价比不能删高。
    """
    try:
        skill_store.remove_skill_dir(slug)
    except skill_store.SkillWriteError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    logger.info("管理员 %s 删除技能 %s", admin.email, slug)
    return {"message": "Deleted successfully", "slug": slug}


# ---------------------------------------------------------------------------
# 技能包导入
#
# 逐个手写 SKILL.md 只适合调文案；真正引入第三方技能（GitHub 上那些
# awesome-copilot / awesome-skills 仓库）是整包下载，里面有 SKILL.md 还有
# scripts/。所以这里收 zip。
#
# 解压的所有安全检查都在 services/skill_package.py 里（路径穿越、符号链接、
# zip bomb、覆盖既有技能），这里只做鉴权与入参。
# ---------------------------------------------------------------------------


class SkillImportRequest(BaseModel):
    #: 覆盖默认推断出的 slug。留空则用包内顶层目录名或 frontmatter.id
    slug: Optional[str] = Field(default=None, max_length=64)
    #: slug 已存在时是否覆盖。默认 False —— 覆盖是破坏性操作，必须显式确认
    overwrite: bool = False


@router.post("/skills/import/preview")
async def preview_skill_import(
    file: UploadFile = File(...),
    skill_path: Optional[str] = None,
    _: User = Depends(require_admin),
):
    """检查上传的技能包，返回将会导入什么。**不写任何文件。**

    单独拆一个 preview 而不是让前端在浏览器里解 zip：解析规则（技能目录
    下钻、slug 推断、必填字段、保留名单）必须和真正导入时完全一致，否则
    用户确认完看到的结果和预览不是一回事。同一份代码跑两遍才不会分叉。

    ``skill_path`` 用于包内存在多个技能时指定要导入哪个；留空则自动取
    **唯一最浅**的那个，同深度有多个会直接报错并列出候选。
    """
    data = await file.read()
    try:
        # 丢到线程池里跑。inspect_zip 是同步的纯 CPU/IO，直接 await 它会把
        # 事件循环占满：几十 MB 的仓库整包要遍历一万多条中央目录，期间
        # 整个服务（所有人的请求、健康检查）全部卡住。
        preview, _meta = await run_in_threadpool(
            skill_package.inspect_zip, data, skill_path=skill_path
        )
    except skill_package.PackageError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001 - 解析失败的形态很多
        logger.warning("技能包预览失败: %s", exc)
        raise HTTPException(status_code=400, detail=f"解析失败：{exc}")

    return {
        "slug": preview.slug,
        "name": preview.name,
        "description": preview.description,
        "files": preview.files,
        "file_count": preview.file_count,
        "total_bytes": preview.total_bytes,
        "has_scripts": preview.has_scripts,
        "warnings": preview.warnings,
        "exists": preview.exists,
        # 仓库整包会下钻到 skills/<name>/，把这些回给前端让管理员看得见
        # 究竟导的是哪一层，也让他能改。
        "skill_path": preview.skill_path,
        "skill_candidates": preview.skill_candidates,
        "ignored_files": preview.ignored_files,
    }


@router.post("/skills/import")
async def import_skill_package(
    file: UploadFile = File(...),
    slug: Optional[str] = None,
    overwrite: bool = False,
    skill_path: Optional[str] = None,
    name: Optional[str] = None,
    description: Optional[str] = None,
    system_prompt: Optional[str] = None,
    admin: User = Depends(require_admin),
):
    """导入技能包，落成 ``skills/<slug>/``。

    ``overwrite=False`` 且 slug 已存在时返回 409 —— 静默覆盖线上技能
    是最难排查的一类事故，必须让人显式确认。

    后四个参数是**覆盖值**：第三方包（尤其 Claude Code 生态那种）的
    frontmatter 往往不符合 AgentFlow 的字段约定，名字、描述、systemPrompt
    都需要管理员在确认框里自己定。留空则沿用包里的值。
    """
    data = await file.read()
    overrides = {
        "name": name,
        "description": description,
        "systemPrompt": system_prompt,
    }
    try:
        # 同样丢线程池：这一步要解压上万个文件、删掉同名旧目录再把新目录
        # 搬过去，在一万多个文件的技能上能跑好几分钟。占着事件循环跑，
        # 期间**整个服务都是不响应的** —— 包括 docker 的健康检查，那会让
        # 容器在导入中途被判死并重启，留下半个技能目录。
        preview = await run_in_threadpool(
            skill_package.import_zip,
            data,
            slug_override=slug,
            overwrite=overwrite,
            overrides=overrides,
            skill_path=skill_path,
        )
    except skill_package.PackageError as exc:
        # 已存在是冲突而不是请求错误，用 409 让前端能区分处理
        status = 409 if "已存在" in str(exc) else 400
        raise HTTPException(status_code=status, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.exception("技能包导入失败")
        raise HTTPException(status_code=400, detail=f"导入失败：{exc}")

    logger.info(
        "管理员 %s 导入技能包 slug=%s 文件数=%d 跳过=%d",
        admin.email,
        preview.slug,
        preview.file_count,
        preview.ignored_files,
    )
    return {
        "slug": preview.slug,
        "name": preview.name,
        "description": preview.description,
        "file_count": preview.file_count,
        "total_bytes": preview.total_bytes,
        "has_scripts": preview.has_scripts,
        "warnings": preview.warnings,
        "skill_path": preview.skill_path,
        "ignored_files": preview.ignored_files,
    }
