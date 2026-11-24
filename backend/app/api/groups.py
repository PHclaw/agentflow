"""多智能体群聊 API。

交互流程（一次发消息）：
1. 落用户消息
2. SSE 推 routing 事件
3. 路由决定谁接（用户 @ 则直接命中）
4. 推 route_decision 事件 —— 前端据此显示「XX 接下了这个任务」
5. 落一条 system 消息，把决策留在历史里
6. 被选中的 agent 回复，内容以 `@发起人` 开头，meta.reply_to 指向用户消息
7. 推送 agent 内容（分块，前端有打字机效果）

没有人接时也会落一条 system 消息说明原因，不让用户对着空气等。
"""
import asyncio
import json
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..models.agent import Agent
from ..models.group import AgentGroup, GroupMessage
from ..models.subscription import Subscription
from ..services.entitlement import Resource
from ..services.entitlement import check as check_quota
from ..services.entitlement import consume as consume_quota
from ..services.group_chat import (
    build_reply_message,
    display_name_of_user,
    format_reply_content,
    load_agents,
    resolve_user,
    route_task,
    save_message,
)
from ..services.integrated_runtime import IntegratedAgentRuntime
from ..services.llm import humanize_llm_error
from .auth import get_current_user_id
from .deps import current_subscription

router = APIRouter()


# ---------------------------------------------------------------- schemas
class GroupCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    agent_ids: List[str] = Field(default_factory=list)
    route_mode: str = Field(default="auto", pattern="^(auto|manual|off)$")


class GroupUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = None
    agent_ids: Optional[List[str]] = None
    route_mode: Optional[str] = Field(default=None, pattern="^(auto|manual|off)$")


class SendMessage(BaseModel):
    content: str = Field(..., min_length=1, max_length=8000)
    # 指定由谁回复；不传则走路由
    agent_id: Optional[str] = None
    # 引用哪条消息（飞书式引用回复），仅允许引用本群内的消息
    reply_to: Optional[int] = None
    # llm = 纯大模型（快） / pi = PiAgent（可读写工作区、生成真实文件）
    execution_mode: str = Field(default="llm", pattern="^(llm|pi)$")


# ---------------------------------------------------------------- helpers
async def _get_group_or_404(db: AsyncSession, group_id: str, user_id: str) -> AgentGroup:
    row = await db.execute(
        select(AgentGroup).where(
            AgentGroup.id == group_id,
            AgentGroup.user_id == user_id,
        )
    )
    group = row.scalars().first()
    if not group:
        raise HTTPException(status_code=404, detail="群聊不存在")
    return group


def _group_payload(group: AgentGroup, agents: List[Agent]) -> dict:
    return {
        "id": group.id,
        "name": group.name,
        "description": group.description,
        "agent_ids": group.agent_ids or [],
        "route_mode": group.route_mode or "auto",
        "settings": group.settings or {},
        "members": [
            {
                "id": a.id,
                "name": a.name,
                "description": a.description,
                "is_active": a.is_active,
            }
            for a in agents
        ],
        "created_at": group.created_at.isoformat() if group.created_at else None,
    }


def _message_payload(m: GroupMessage) -> dict:
    return {
        "id": m.id,
        "sender_type": m.sender_type,
        "sender_id": m.sender_id,
        "sender_name": m.sender_name,
        "content": m.content,
        "meta": m.meta or {},
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


# ---------------------------------------------------------------- CRUD
@router.get("")
async def list_groups(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    rows = await db.execute(
        select(AgentGroup)
        .where(AgentGroup.user_id == user_id)
        .order_by(AgentGroup.created_at.desc())
    )
    groups = rows.scalars().all()

    out = []
    for g in groups:
        # 每个群的成员数用一次独立查询；群数量通常个位数，可接受
        count = len(g.agent_ids or [])
        last = await db.execute(
            select(GroupMessage)
            .where(GroupMessage.group_id == g.id)
            .order_by(GroupMessage.id.desc())
            .limit(1)
        )
        last_msg = last.scalars().first()
        out.append({
            "id": g.id,
            "name": g.name,
            "description": g.description,
            "member_count": count,
            "route_mode": g.route_mode or "auto",
            "last_message": (last_msg.content[:60] if last_msg else None),
            "last_active": (
                last_msg.created_at.isoformat() if last_msg and last_msg.created_at
                else (g.created_at.isoformat() if g.created_at else None)
            ),
        })
    return {"groups": out}


@router.post("")
async def create_group(
    data: GroupCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    # 只允许拉自己的 agent
    if data.agent_ids:
        rows = await db.execute(
            select(Agent).where(Agent.id.in_(data.agent_ids), Agent.user_id == user_id)
        )
        valid = {a.id for a in rows.scalars().all()}
        missing = [i for i in data.agent_ids if i not in valid]
        if missing:
            raise HTTPException(status_code=400, detail=f"以下智能体不存在或无权访问: {missing}")

    group = AgentGroup(
        user_id=user_id,
        name=data.name.strip(),
        description=data.description,
        agent_ids=list(data.agent_ids),
        route_mode=data.route_mode,
    )
    db.add(group)
    await db.commit()
    await db.refresh(group)

    agents = await load_agents(db, group)
    return _group_payload(group, agents)


@router.get("/{group_id}")
async def get_group(
    group_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    group = await _get_group_or_404(db, group_id, user_id)
    agents = await load_agents(db, group)
    return _group_payload(group, agents)


@router.patch("/{group_id}")
async def update_group(
    group_id: str,
    data: GroupUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    group = await _get_group_or_404(db, group_id, user_id)

    if data.name is not None:
        group.name = data.name.strip()
    if data.description is not None:
        group.description = data.description
    if data.route_mode is not None:
        group.route_mode = data.route_mode
    if data.agent_ids is not None:
        rows = await db.execute(
            select(Agent).where(Agent.id.in_(data.agent_ids), Agent.user_id == user_id)
        )
        valid = {a.id for a in rows.scalars().all()}
        missing = [i for i in data.agent_ids if i not in valid]
        if missing:
            raise HTTPException(status_code=400, detail=f"以下智能体不存在或无权访问: {missing}")
        group.agent_ids = list(data.agent_ids)

    await db.commit()
    await db.refresh(group)
    agents = await load_agents(db, group)
    return _group_payload(group, agents)


@router.delete("/{group_id}")
async def delete_group(
    group_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    group = await _get_group_or_404(db, group_id, user_id)
    await db.execute(
        GroupMessage.__table__.delete().where(GroupMessage.group_id == group.id)
    )
    await db.delete(group)
    await db.commit()
    return {"ok": True}


@router.get("/{group_id}/messages")
async def list_messages(
    group_id: str,
    limit: int = 100,
    before_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    await _get_group_or_404(db, group_id, user_id)

    stmt = select(GroupMessage).where(GroupMessage.group_id == group_id)
    if before_id:
        stmt = stmt.where(GroupMessage.id < before_id)
    stmt = stmt.order_by(GroupMessage.id.desc()).limit(min(limit, 200))

    rows = await db.execute(stmt)
    msgs = list(reversed(rows.scalars().all()))
    return {"messages": [_message_payload(m) for m in msgs]}


# ---------------------------------------------------------------- 发送消息（SSE）
@router.post("/{group_id}/messages")
async def send_message(
    group_id: str,
    data: SendMessage,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    sub: Subscription = Depends(current_subscription),
):
    group = await _get_group_or_404(db, group_id, user_id)
    agents = await load_agents(db, group)
    if not agents:
        raise HTTPException(status_code=400, detail="这个群还没有成员")

    # 群聊一次可能触发多个模型调用，和单聊一样要卡额度
    await check_quota(db, sub, Resource.MESSAGES)

    user = await resolve_user(db, user_id)
    asked_by = display_name_of_user(user)

    # 1. 落用户消息
    user_msg = await save_message(
        db, group.id, "user", data.content,
        sender_name=asked_by,
        meta={"reply_to": data.reply_to} if data.reply_to else None,
    )

    # 2. 决定谁接
    mentioned = None
    if data.agent_id:
        mentioned = next((a for a in agents if a.id == data.agent_id), None)

    # 不再从正文扫 @：用户可能在引用块里转述「发给 @AI2 可以吗」，
    # 那是在问当前这个 agent，不是在指定 AI2 接活。
    # 显式指定只认前端 @ 选择器传来的 agent_id。

    async def event_stream():
        try:
            # 先告诉前端「正在判断」，同时把用户消息的正式 id 带回去。
            # 前端先渲染的是负数临时 id，不换成正数的话后面的引用块找不到原文。
            yield f"data: {json.dumps({'type': 'routing', 'user_message_id': user_msg.id}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0)

            # 引用回复：把被引用的原文拼进任务，让接手的 agent 知道在回应什么。
            # 必须先校验这条消息属于本群，否则用户可以构造 id 引用别人的内容。
            effective_content = data.content
            if data.reply_to:
                qrow = await db.execute(
                    select(GroupMessage).where(
                        GroupMessage.id == data.reply_to,
                        GroupMessage.group_id == group.id,
                    )
                )
                quoted = qrow.scalars().first()
                if quoted:
                    effective_content = (
                        f"用户引用了一条历史消息：\n{quoted.content}\n\n"
                        f"针对上面的消息，用户现在说：\n{data.content}"
                    )

            agent, reason, confidence = await route_task(
                db, group, agents, effective_content, mentioned_agent=mentioned
            )

            yield f"data: {json.dumps({'type': 'route_decision', 'agent': agent.name if agent else None, 'reason': reason, 'confidence': round(confidence, 2)}, ensure_ascii=False)}\n\n"

            if agent is None:
                # 没人接：把原因留在历史里，用户能看到为什么
                sys_msg = await save_message(
                    db, group.id, "system", reason,
                    meta={"route_reason": reason, "reply_to": user_msg.id},
                )
                await db.commit()
                yield f"data: {json.dumps({'type': 'system_message', 'id': sys_msg.id, 'content': reason, 'reply_to': user_msg.id}, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
                return

            # 3. 落一条系统消息，把「谁接了」写进历史
            accept_text = f"{agent.name} 接下了这个任务：{reason}"
            sys_msg = await save_message(
                db, group.id, "system", accept_text,
                meta={
                    "route_reason": reason,
                    "confidence": round(confidence, 2),
                    "reply_to": user_msg.id,
                    "assignee": agent.id,
                },
            )
            await db.commit()
            yield f"data: {json.dumps({'type': 'system_message', 'id': sys_msg.id, 'content': accept_text, 'reply_to': user_msg.id, 'assignee': agent.id}, ensure_ascii=False)}\n\n"

            # 4. 让被选中的 agent 干活
            yield f"data: {json.dumps({'type': 'agent_start', 'agent_id': agent.id, 'agent': agent.name}, ensure_ascii=False)}\n\n"

            raw = ""
            artifacts: list[dict[str, Any]] = []

            try:
                if data.execution_mode == "pi":
                    # PiAgent：独立工作区、可读写文件、多轮工具循环，
                    # 事件逐条转发给前端（thinking / tool_call / text / done）
                    from app.services.pi_agent import pi_agent_runner

                    async for ev in pi_agent_runner.stream(
                        message=build_reply_message(agent, effective_content, asked_by),
                        agent_id=agent.id,
                        agent=agent,
                        session_id=None,
                    ):
                        etype = ev.get("type")
                        if etype == "done":
                            raw = ev.get("content") or ""
                            artifacts = ev.get("files") or []
                            continue
                        # 群聊事件带上 agent 标识，前端才知道是谁在动
                        yield f"data: {json.dumps({**ev, 'agent_id': agent.id, 'agent': agent.name}, ensure_ascii=False, default=str)}\n\n"
                else:
                    runtime = IntegratedAgentRuntime(agent.id, db, user_id)
                    await runtime.initialize()
                    raw = await runtime.chat(build_reply_message(agent, effective_content, asked_by))
            except Exception as exc:  # noqa: BLE001 - 单个 agent 失败不该中断整个群聊
                err = humanize_llm_error(exc) or str(exc)
                fail_text = f"{agent.name} 执行失败：{err}"
                await save_message(
                    db, group.id, "system", fail_text,
                    meta={"reply_to": user_msg.id, "error": True},
                )
                await db.commit()
                yield f"data: {json.dumps({'type': 'error', 'agent': agent.name, 'content': fail_text}, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
                return

            # 5. @ 回发起人
            content = format_reply_content(agent, raw, asked_by)

            # 纯大模型模式分块推送做打字机效果；
            # PiAgent 已经逐事件推过文字了，这里只补最终完整内容给前端替换。
            if data.execution_mode != "pi":
                step = 12
                for i in range(0, len(content), step):
                    yield f"data: {json.dumps({'type': 'agent_chunk', 'agent_id': agent.id, 'text': content[i:i + step]}, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(0.012)

            # 6. 落库
            reply_msg = await save_message(
                db, group.id, "agent", content,
                sender_id=agent.id,
                sender_name=agent.name,
                meta={
                    "reply_to": user_msg.id,
                    "mentions": [asked_by],
                    "route_reason": reason,
                    "confidence": round(confidence, 2),
                    "execution_mode": data.execution_mode,
                    "files": artifacts,
                },
            )
            await consume_quota(db, sub, Resource.MESSAGES)
            await db.commit()

            yield f"data: {json.dumps({'type': 'agent_done', 'id': reply_msg.id, 'agent_id': agent.id, 'reply_to': user_msg.id, 'content': content, 'execution_mode': data.execution_mode, 'files': artifacts}, ensure_ascii=False, default=str)}\n\n"
            yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"

        except Exception as exc:  # noqa: BLE001 - 流式响应里只能以事件形式报错
            await db.rollback()
            yield f"data: {json.dumps({'type': 'error', 'content': str(exc)}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
