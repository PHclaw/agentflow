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
from datetime import datetime, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..core.logging import logger
from ..models.agent import Agent
from ..models.group import AgentGroup, GroupMessage, MessageReaction, MessageRead
from ..models.subscription import Subscription
from ..services import group_files
from ..services.entitlement import Resource
from ..services.entitlement import check as check_quota
from ..services.entitlement import consume as consume_quota
from ..services.group_chat import (
    build_chain_prompt,
    build_handoff_prompt,
    build_recruit_prompt,
    build_reply_message,
    build_reroute_message,
    display_name_of_user,
    find_agent_by_name,
    format_reply_content,
    load_agents,
    looks_like_refusal,
    parse_handoff,
    parse_need_member,
    parse_next,
    resolve_user,
    route_task,
    save_message,
    says_nobody,
    strip_handoff,
    strip_protocol,
)
from ..services.group_recruit import (
    join_group,
    member_payload,
    recruit_member,
)
from ..services.integrated_runtime import IntegratedAgentRuntime
from ..services.llm import LLMService, humanize_llm_error
from .auth import get_current_user_id
from .deps import current_subscription

router = APIRouter()


# ---------------------------------------------------------------- schemas
class GroupCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    agent_ids: List[str] = Field(default_factory=list)
    route_mode: str = Field(default="auto", pattern="^(auto|manual|off)$")
    # 协作设置：single = 一人接活；chain = 成员之间接力补充
    settings: Optional[dict] = None


class GroupUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = None
    agent_ids: Optional[List[str]] = None
    route_mode: Optional[str] = Field(default=None, pattern="^(auto|manual|off)$")
    settings: Optional[dict] = None


class EditMessage(BaseModel):
    content: str = Field(..., min_length=1, max_length=8000)


class ReactRequest(BaseModel):
    emoji: str = Field(..., min_length=1, max_length=16)


class SendMessage(BaseModel):
    content: str = Field(..., min_length=1, max_length=8000)
    # 指定由谁回复；不传则走路由
    agent_id: Optional[str] = None
    # 引用哪条消息（飞书式引用回复），仅允许引用本群内的消息
    reply_to: Optional[int] = None
    # llm = 纯大模型（快） / pi = PiAgent（可读写工作区、生成真实文件）
    execution_mode: str = Field(default="llm", pattern="^(llm|pi)$")
    # 已上传到本群的文件（stored_name 列表），随消息一起交付给接手的成员
    file_names: List[str] = Field(default_factory=list)
    # @ 全体成员：只做标记与高亮，不触发所有人分别回复（成本与噪音都不可控）
    mention_all: bool = False


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
                # 前端要把自动招募的成员标出来，并在移出时提示会彻底删除
                "auto_created": bool((a.settings or {}).get("auto_created")),
            }
            for a in agents
        ],
        "created_at": group.created_at.isoformat() if group.created_at else None,
    }


def _message_payload(
    m: GroupMessage,
    reactions: Optional[dict[int, list[dict]]] = None,
    readers: Optional[dict[int, list[str]]] = None,
) -> dict:
    meta = dict(m.meta or {})
    if meta.get("edited_at"):
        meta["edited"] = True
    return {
        "id": m.id,
        "sender_type": m.sender_type,
        "sender_id": m.sender_id,
        "sender_name": m.sender_name,
        "content": "" if m.is_revoked else m.content,
        "meta": meta,
        "is_revoked": bool(m.is_revoked),
        "reactions": (reactions or {}).get(m.id, []),
        "read_by": (readers or {}).get(m.id, []),
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


async def _message_extras(
    db: AsyncSession, group_id: str, message_ids: list[int], user_id: str
) -> tuple[dict[int, list[dict]], dict[int, list[str]]]:
    """批量取表情回应与已读人，避免 N+1。"""
    reactions: dict[int, list[dict]] = {}
    readers: dict[int, list[str]] = {}
    if not message_ids:
        return reactions, readers

    rows = (
        await db.execute(
            select(MessageReaction).where(
                MessageReaction.group_id == group_id,
                MessageReaction.message_id.in_(message_ids),
            )
        )
    ).scalars().all()
    for r in rows:
        reactions.setdefault(r.message_id, []).append(
            {"emoji": r.emoji, "user_id": r.user_id, "mine": r.user_id == user_id}
        )

    rows = (
        await db.execute(
            select(MessageRead).where(
                MessageRead.group_id == group_id,
                MessageRead.message_id.in_(message_ids),
            )
        )
    ).scalars().all()
    for r in rows:
        readers.setdefault(r.message_id, []).append(r.user_id)

    return reactions, readers


async def _recruit_and_join(
    db: AsyncSession,
    group: AgentGroup,
    agents: List[Agent],
    task: str,
    user_id: str,
    reply_to: Optional[int],
    role_hint: Optional[str] = None,
) -> tuple[Optional[Agent], str, Optional[GroupMessage]]:
    """按任务招一个人并加入群。

    role_hint 是接活的人自己说的「缺什么角色」，比从任务里重新推断更准。
    返回 (新成员, 提示文案, 系统消息)。招不到时新成员为 None，文案是原因。
    agents 会被就地追加——调用方不用再查一次库。
    """
    recruited, note = await recruit_member(
        db, group, task, agents, user_id, role_hint=role_hint
    )
    if recruited is None:
        return None, note, None

    join_group(group, recruited)
    await db.commit()
    agents.append(recruited)

    # 能力摘要只留前两句，别把整段描述抄进系统消息——那是给模型看的
    brief = " ".join((note or "").split())[:60]
    join_text = f"已将「{recruited.name}」拉入群聊"
    if brief:
        join_text += f" · {brief}"
    join_msg = await save_message(
        db, group.id, "system", join_text,
        meta={"reply_to": reply_to, "member_joined": recruited.id},
    )
    await db.commit()
    return recruited, join_text, join_msg


async def _summarize_chain(
    db: AsyncSession,
    group: AgentGroup,
    agents: List[Agent],
    original_task: str,
    contributions: List[tuple[str, str]],
    asked_by: str,
) -> Optional[str]:
    """把接力链上各人的结论整合成一段。

    没有这一步，用户看到的是几段并列的专家意见，得自己拼。
    协作要有收束——这是「一组人干活」和「一个人答完」最明显的差别。
    """
    if len(contributions) < 2:
        return None

    blocks = "\n\n".join(f"【{name}】\n{text}" for name, text in contributions)
    prompt = (
        f"{asked_by} 提出的任务：\n{original_task}\n\n"
        f"群里几位同事分别完成了这些部分：\n{blocks}\n\n"
        "请把以上各部分整合成一段结论，交给提问的人。\n"
        "要求：\n"
        "1. 直接给整合后的结论与行动建议，不要复述各段内容\n"
        "2. 指出各段之间如果存在冲突或需要取舍的地方\n"
        "3. 说明还缺哪些输入才能落到可执行\n"
        "4. 不要编造前面同事没有给出的数字或事实"
    )

    try:
        cfg: dict[str, Any] = {}
        for a in agents:
            c = a.model_config or {}
            if c.get("provider"):
                cfg = c
                break
        llm = LLMService(provider=cfg.get("provider", "openai"), model=cfg.get("model"))
        raw = await llm.chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1200,
        )
    except Exception as exc:  # noqa: BLE001 - 汇总失败不该让整轮对话失败
        logger.warning("chain summary failed: %s", exc)
        return None

    text = strip_protocol((raw or "").strip())
    return text or None


def _member_event(msg: GroupMessage, agent: Agent, reason: str) -> str:
    return (
        "data: "
        + json.dumps(
            {
                "type": "member_joined",
                "id": msg.id,
                "member": member_payload(agent),
                "content": msg.content,
                "reason": reason,
                "reply_to": msg.meta.get("reply_to"),
            },
            ensure_ascii=False,
        )
        + "\n\n"
    )


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
        settings=data.settings or {},
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
    if data.settings is not None:
        # 合并而不是整体覆盖：前端只传要改的字段，
        # 整体替换会把 auto_recruit 之类的既有设置冲掉
        merged = dict(group.settings or {})
        merged.update(data.settings)
        group.settings = merged
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


@router.delete("/{group_id}/members/{agent_id}")
async def remove_group_member(
    group_id: str,
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """把一个成员移出群。

    自动招募出来的成员会从账号里彻底删掉——否则左侧「最近」会一直挂着
    一堆一次性的临时角色，越用越乱。手动创建的 Agent 只移出群，不删除。
    """
    group = await _get_group_or_404(db, group_id, user_id)

    ids = list(group.agent_ids or [])
    if agent_id not in ids:
        raise HTTPException(status_code=404, detail="这个成员不在该群里")

    if len(ids) == 1:
        raise HTTPException(
            status_code=400,
            detail="群里至少保留一个成员。要清空请直接删除群聊",
        )

    agent = (
        await db.execute(
            select(Agent).where(Agent.id == agent_id, Agent.user_id == user_id)
        )
    ).scalars().first()

    group.agent_ids = [i for i in ids if i != agent_id]

    auto_created = bool(agent and (agent.settings or {}).get("auto_created"))
    if auto_created:
        await db.delete(agent)

    await db.commit()
    await db.refresh(group)
    agents = await load_agents(db, group)
    payload = _group_payload(group, agents)
    payload["removed_agent_purged"] = auto_created
    return payload


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
    # 记录删了，磁盘上的文件也要一起清，否则变成没人能访问的孤儿
    group_files.purge_group_dir(group.id)
    return {"ok": True}


@router.get("/{group_id}/messages")
async def list_messages(
    group_id: str,
    limit: int = 100,
    before_id: Optional[int] = None,
    keyword: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    await _get_group_or_404(db, group_id, user_id)

    stmt = select(GroupMessage).where(GroupMessage.group_id == group_id)
    if keyword and keyword.strip():
        stmt = stmt.where(GroupMessage.content.contains(keyword.strip()))
    if before_id:
        stmt = stmt.where(GroupMessage.id < before_id)
    stmt = stmt.order_by(GroupMessage.id.desc()).limit(min(limit, 200))

    rows = await db.execute(stmt)
    msgs = list(reversed(rows.scalars().all()))
    reactions, readers = await _message_extras(
        db, group_id, [m.id for m in msgs], user_id
    )
    return {
        "messages": [_message_payload(m, reactions, readers) for m in msgs]
    }


# ---------------------------------------------------------------- 交互增强
@router.patch("/{group_id}/messages/{message_id}")
async def edit_message(
    group_id: str,
    message_id: int,
    data: EditMessage,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """编辑消息：只允许改自己发的、未撤回的用户消息。"""
    await _get_group_or_404(db, group_id, user_id)
    m = (
        await db.execute(
            select(GroupMessage).where(
                GroupMessage.id == message_id,
                GroupMessage.group_id == group_id,
                GroupMessage.sender_type == "user",
            )
        )
    ).scalars().first()
    if not m:
        raise HTTPException(status_code=404, detail="消息不存在")
    if m.is_revoked:
        raise HTTPException(status_code=400, detail="已撤回的消息不能编辑")

    meta = dict(m.meta or {})
    meta["edited_at"] = datetime.now(timezone.utc).isoformat()
    m.content = data.content.strip()
    m.meta = meta
    await db.commit()
    await db.refresh(m)
    return _message_payload(m)


@router.delete("/{group_id}/messages/{message_id}")
async def revoke_message(
    group_id: str,
    message_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """撤回消息：软删除，保留行以维持引用链。"""
    await _get_group_or_404(db, group_id, user_id)
    m = (
        await db.execute(
            select(GroupMessage).where(
                GroupMessage.id == message_id,
                GroupMessage.group_id == group_id,
            )
        )
    ).scalars().first()
    if not m:
        raise HTTPException(status_code=404, detail="消息不存在")
    if m.sender_type == "system":
        raise HTTPException(status_code=400, detail="系统消息不能撤回")
    # 用户只能撤自己的；智能体的消息由群主撤（简化：这里统一允许群成员撤）
    if m.sender_type == "user" and m.sender_id and m.sender_id != user_id:
        raise HTTPException(status_code=403, detail="只能撤回自己发的消息")

    m.is_revoked = True
    m.revoked_at = datetime.now(timezone.utc)
    m.content = ""
    await db.commit()
    return {"ok": True, "id": message_id}


@router.post("/{group_id}/messages/{message_id}/reactions")
async def toggle_reaction(
    group_id: str,
    message_id: int,
    data: ReactRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """表情回应：同一个表情再点一次就取消。"""
    await _get_group_or_404(db, group_id, user_id)
    m = (
        await db.execute(
            select(GroupMessage).where(
                GroupMessage.id == message_id, GroupMessage.group_id == group_id
            )
        )
    ).scalars().first()
    if not m or m.is_revoked:
        raise HTTPException(status_code=404, detail="消息不存在")

    row = (
        await db.execute(
            select(MessageReaction).where(
                MessageReaction.message_id == message_id,
                MessageReaction.user_id == user_id,
                MessageReaction.emoji == data.emoji,
            )
        )
    ).scalars().first()
    if row:
        await db.delete(row)
        added = False
    else:
        db.add(MessageReaction(
            message_id=message_id, group_id=group_id,
            user_id=user_id, emoji=data.emoji,
        ))
        added = True
    await db.commit()

    rows = (
        await db.execute(
            select(MessageReaction).where(MessageReaction.message_id == message_id)
        )
    ).scalars().all()
    return {
        "ok": True,
        "added": added,
        "reactions": [
            {"emoji": r.emoji, "user_id": r.user_id, "mine": r.user_id == user_id}
            for r in rows
        ],
    }


@router.post("/{group_id}/messages/{message_id}/read")
async def mark_read(
    group_id: str,
    message_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """上报已读（幂等）。"""
    await _get_group_or_404(db, group_id, user_id)
    exists = (
        await db.execute(
            select(MessageRead).where(
                MessageRead.message_id == message_id,
                MessageRead.user_id == user_id,
            )
        )
    ).scalars().first()
    if not exists:
        db.add(MessageRead(
            message_id=message_id, group_id=group_id, user_id=user_id
        ))
        await db.commit()
    return {"ok": True}


@router.post("/{group_id}/read-all")
async def mark_all_read(
    group_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """进群时一次性把当前所有消息标为已读。"""
    await _get_group_or_404(db, group_id, user_id)
    ids = (
        await db.execute(
            select(GroupMessage.id).where(GroupMessage.group_id == group_id)
        )
    ).scalars().all()
    already = set(
        (
            await db.execute(
                select(MessageRead.message_id).where(
                    MessageRead.group_id == group_id,
                    MessageRead.user_id == user_id,
                )
            )
        ).scalars().all()
    )
    for mid in ids:
        if mid not in already:
            db.add(MessageRead(message_id=mid, group_id=group_id, user_id=user_id))
    await db.commit()
    return {"ok": True, "count": len(ids)}


@router.get("/{group_id}/unread")
async def unread_count(
    group_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """群聊未读数：给群列表用。"""
    await _get_group_or_404(db, group_id, user_id)
    total = (
        await db.execute(
            select(GroupMessage.id).where(
                GroupMessage.group_id == group_id,
                GroupMessage.sender_type != "system",
            )
        )
    ).scalars().all()
    read = set(
        (
            await db.execute(
                select(MessageRead.message_id).where(
                    MessageRead.group_id == group_id, MessageRead.user_id == user_id
                )
            )
        ).scalars().all()
    )
    return {"unread": sum(1 for i in total if i not in read)}


# ---------------------------------------------------------------- 文件
@router.post("/{group_id}/files")
async def upload_group_file(
    group_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """上传文件到群聊。

    上传时还不知道会由哪个成员接手，所以先落在群目录；
    发送消息时再校验归属、复制进被选中成员的工作区。
    """
    await _get_group_or_404(db, group_id, user_id)

    content = await file.read()
    try:
        # 大小、扩展名白名单、群容量都在这一层统一校验
        info = group_files.save_bytes(group_id, file.filename or "upload.bin", content)
    except group_files.GroupFileError as exc:
        # 413 专指体积问题，前端据此提示「换个文件」而不是「重试」
        status = 413 if "上限" in str(exc) else 400
        raise HTTPException(status_code=status, detail=str(exc))

    return info


@router.get("/{group_id}/files/{stored_name}")
async def download_group_file(
    group_id: str,
    stored_name: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """下载群文件。

    必须带 Bearer 头：文件走这个接口而不是静态目录，
    否则知道文件名的人都能读，等于绕过了群归属校验。
    """
    await _get_group_or_404(db, group_id, user_id)
    try:
        path = group_files.resolve_file(group_id, stored_name)
    except group_files.GroupFileError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return FileResponse(path, filename=path.name)


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

    # 0. 文件校验：只接受真实存在于本群的文件，
    #    防止构造一个别的群的 stored_name 塞进来做越权引用。
    attachments: List[dict[str, Any]] = []
    if data.file_names:
        if len(data.file_names) > group_files.MAX_FILES_PER_MESSAGE:
            raise HTTPException(
                status_code=400,
                detail=f"一条消息最多 {group_files.MAX_FILES_PER_MESSAGE} 个文件",
            )
        for name in group_files.check_owned_by_group(group.id, data.file_names):
            try:
                attachments.append(group_files.describe(group.id, name))
            except Exception:  # noqa: BLE001 - 单个文件异常不该挡住整条消息
                continue

    # 1. 落用户消息
    user_meta: dict[str, Any] = {}
    if data.reply_to:
        user_meta["reply_to"] = data.reply_to
    if attachments:
        user_meta["files"] = attachments
    if data.mention_all:
        user_meta["mention_all"] = True
    user_msg = await save_message(
        db, group.id, "user", data.content,
        sender_name=asked_by,
        meta=user_meta or None,
    )

    # 2. 决定谁接
    mentioned = None
    mention_reason = "由你直接指定"
    if data.agent_id:
        mentioned = next((a for a in agents if a.id == data.agent_id), None)

    # 不再从正文扫 @：用户可能在引用块里转述「发给 @AI2 可以吗」，
    # 那是在问当前这个 agent，不是在指定 AI2 接活。
    # 显式指定只认前端 @ 选择器传来的 agent_id。

    # 引用某条消息继续追问时，默认由被引用的那位回应。
    # 「可以叫会数据分析的同事进行」是接着他上一句说的，
    # 换个人来接等于让对话断线——用户会觉得「我问的是你，怎么换了个人」。
    # 想改派就用 @ 选择器，它的优先级更高。
    if mentioned is None and data.reply_to:
        qrow = await db.execute(
            select(GroupMessage).where(
                GroupMessage.id == data.reply_to,
                GroupMessage.group_id == group.id,
            )
        )
        quoted_for_route = qrow.scalars().first()
        if (
            quoted_for_route is not None
            and quoted_for_route.sender_type == "agent"
            and quoted_for_route.sender_id
        ):
            mentioned = next(
                (a for a in agents if a.id == quoted_for_route.sender_id), None
            )
            if mentioned is not None:
                mention_reason = f"接着 {mentioned.name} 上一条回复继续"

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

            # 附件清单要进路由输入：否则「帮我分析这个表」会被判成信息不足，
            # 而实际上文件就在消息里。
            if attachments:
                effective_content = (
                    effective_content
                    + "\n\n"
                    + group_files.summarize_for_prompt(attachments)
                )

            # 带附件时强制走 PiAgent：纯大模型拿不到文件内容，
            # 让它回答只会有两种结果——编造内容，或者写一大段「我读不到」。
            # 这两种都不是用户想要的，所以这里直接升级执行方式。
            effective_mode = data.execution_mode
            mode_note = ""
            if attachments and effective_mode == "llm":
                try:
                    from app.services.pi_agent import pi_agent_runner

                    if pi_agent_runner.exe:
                        effective_mode = "pi"
                        mode_note = "检测到附件，已自动使用工作模式读取文件"
                    else:
                        mode_note = "未安装 PiAgent，附件只能看到文件名而读不到内容"
                except Exception:  # noqa: BLE001
                    mode_note = "PiAgent 不可用，附件只能看到文件名"

            if mode_note:
                yield f"data: {json.dumps({'type': 'mode_switch', 'execution_mode': effective_mode, 'content': mode_note}, ensure_ascii=False)}\n\n"

            agent, reason, confidence = await route_task(
                db, group, agents, effective_content,
                mentioned_agent=mentioned,
                mention_reason=mention_reason,
            )
            # 自动补人时用更自然的措辞（「接手了这个任务」而不是
            # 「接下了这个任务：群里没有对口的成员…」）
            accept_override: Optional[str] = None
            # 本轮是否由「自动补人」产生。是的话用专门的交接话术，
            # 让新成员知道它是为什么被拉进来的。
            current_is_recruited = False

            yield f"data: {json.dumps({'type': 'route_decision', 'agent': agent.name if agent else None, 'reason': reason, 'confidence': round(confidence, 2)}, ensure_ascii=False)}\n\n"

            if agent is None:
                # 没人接 —— 先试着按任务招一个对口的人进来。
                # 群设置里显式关闭（auto_recruit = false）时不招。
                allow_recruit = (group.settings or {}).get("auto_recruit", True)
                recruited = None
                join_msg = None
                fail_note = ""

                if allow_recruit:
                    # 第二个返回值成功时是提示文案，失败时是失败原因
                    recruited, fail_note, join_msg = await _recruit_and_join(
                        db, group, agents, effective_content, user_id, user_msg.id
                    )
                    if recruited is not None:
                        fail_note = ""
                else:
                    fail_note = "自动补人已关闭，可在群设置里开启"

                if recruited is None:
                    # 招不到（或已关自动补人）：保持原行为，把原因说清楚
                    detail = f"{reason}\n{fail_note}" if fail_note else reason
                    sys_msg = await save_message(
                        db, group.id, "system", detail,
                        meta={"route_reason": reason, "reply_to": user_msg.id},
                    )
                    await db.commit()
                    yield f"data: {json.dumps({'type': 'system_message', 'id': sys_msg.id, 'content': detail, 'reply_to': user_msg.id}, ensure_ascii=False)}\n\n"
                    yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
                    return

                yield _member_event(join_msg, recruited, reason)

                agent = recruited
                reason = "群里没有对口的成员，已按任务创建新成员"
                # 新成员是专门为这个任务创建的，能力必然对口，
                # 置信度给 1.0；显示「0%」会让人以为系统也不确定该派谁。
                confidence = 1.0
                accept_override = f"{recruited.name} 接手了这个任务"
                current_is_recruited = True

            # 3. 落一条系统消息，把「谁接了」写进历史
            accept_text = accept_override or f"{agent.name} 接下了这个任务：{reason}"
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

            # 群目录不在 PiAgent 的工作区里，执行前必须搬一份过去，
            # 否则模型看不到用户上传的文件，只会反问「请提供文件」。
            # 转交循环：agent 判断「这活不该我干」时，真的换人接着做。
            # 上限 2 跳，防止两个成员互相踢皮球。
            MAX_HANDOFF = 2
            hop = 0
            current_agent = agent
            visited: set[str] = {agent.id}
            task_text = effective_content
            artifacts: list[dict[str, Any]] = []
            # 协作状态：链路上每个人已经贡献的内容（谁说了什么）
            collab_mode = (group.settings or {}).get("collaboration_mode", "single")
            collab_on = collab_mode == "chain"
            max_speakers = int((group.settings or {}).get("max_speakers", 4) or 4)
            # 上限防止协作变成无限循环与成本失控，但也别太小：
            # 做一份完整方案常要文案、排版、数据、技术四五个视角。
            max_speakers = max(2, min(max_speakers, 8))
            contributions: List[tuple[str, str]] = []
            chain_focus = ""
            # 当前这一轮的发言是否已作为「链路中的一段」落过库
            part_saved = False

            while True:
                # 每轮重置：上一轮标记过「已作为链路片段落库」，
                # 这一轮是新的接手人，它的回复必须单独落库，
                # 否则最后一位的发言会整段丢失。
                part_saved = False
                # 群目录不在 PiAgent 工作区里，每轮都要给当前 agent 搬一份
                file_hint = ""
                if attachments and effective_mode == "pi":
                    try:
                        from app.services.pi_agent import pi_agent_workspace

                        copied = group_files.copy_to_workspace(
                            group.id,
                            [a["stored_name"] for a in attachments],
                            pi_agent_workspace(current_agent.id),
                        )
                        if copied:
                            file_hint = (
                                "\n\n文件已放入你的工作目录，可直接读取："
                                + "、".join(copied)
                            )
                    except Exception as exc:  # noqa: BLE001 - 复制失败不该中断对话
                        logger.warning("copy group files to workspace failed: %s", exc)

                try:
                    # 新成员用专门的交接话术：它不知道自己是「被临时招来的」，
                    # 也不知道前面发生了什么，不说清楚就会像普通成员那样回答。
                    if current_is_recruited:
                        prompt_text = build_recruit_prompt(
                            current_agent, task_text, asked_by, file_hint,
                            collaboration=collab_on, peers=agents,
                        )
                    elif contributions:
                        # 链路上的人：拿到前面所有同事的结论，接着补自己那块
                        prompt_text = build_chain_prompt(
                            current_agent, effective_content, contributions,
                            chain_focus, asked_by, peers=agents,
                        ) + file_hint
                    else:
                        prompt_text = build_reply_message(
                            current_agent, task_text + file_hint, asked_by,
                            peers=agents,
                            collaboration=collab_on,
                        )

                    if effective_mode == "pi":
                        # PiAgent：独立工作区、可读写文件、多轮工具循环，
                        # 事件逐条转发给前端（thinking / tool_call / text / done）
                        from app.services.pi_agent import pi_agent_runner

                        async for ev in pi_agent_runner.stream(
                            message=prompt_text,
                            agent_id=current_agent.id,
                            agent=current_agent,
                            session_id=None,
                        ):
                            etype = ev.get("type")
                            if etype == "done":
                                raw = ev.get("content") or ""
                                artifacts = ev.get("files") or []
                                continue
                            # 群聊事件带上 agent 标识，前端才知道是谁在动
                            yield f"data: {json.dumps({**ev, 'agent_id': current_agent.id, 'agent': current_agent.name}, ensure_ascii=False, default=str)}\n\n"
                    else:
                        runtime = IntegratedAgentRuntime(current_agent.id, db, user_id)
                        await runtime.initialize()
                        raw = await runtime.chat(prompt_text)
                except Exception as exc:  # noqa: BLE001 - 单个 agent 失败不该中断群聊
                    err = humanize_llm_error(exc) or str(exc)
                    fail_text = f"{current_agent.name} 执行失败：{err}"
                    await save_message(
                        db, group.id, "system", fail_text,
                        meta={"reply_to": user_msg.id, "error": True},
                    )
                    await db.commit()
                    yield f"data: {json.dumps({'type': 'error', 'agent': current_agent.name, 'content': fail_text}, ensure_ascii=False)}\n\n"
                    yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
                    return

                # 协作接力：[[NEXT: 名字 | 补什么]] —— 我做完了，请他补
                next_name, next_focus = parse_next(raw)
                # 回环限制：同一个成员回环一次是合理补充（文案→排版→回文案微调），
                # 但两次以上就是乒乓——两人来回弹、内容高度重复，协作没有价值。
                # 判据：接力链里已经有人出现过 2 次，就不再继续。
                bounced = any(
                    sum(1 for who, _ in contributions if who == name)
                    >= 2
                    for name in {who for who, _ in contributions}
                )
                if (
                    next_name
                    and collab_on
                    and len(contributions) < max_speakers - 1
                    and not bounced
                ):
                    target_agent = find_agent_by_name(agents, next_name)
                    if (
                        target_agent is not None
                        and target_agent.id != current_agent.id
                    ):
                        chain_focus = next_focus
                        part_text = strip_protocol(raw)
                        contributions.append((current_agent.name, part_text))

                        # 顺序：先落这位的发言，再落转交说明。
                        # 反过来的话界面上会看到「交给 X」出现在 X 开口之前。
                        await save_message(
                            db, group.id, "agent", part_text,
                            sender_id=current_agent.id,
                            sender_name=current_agent.name,
                            meta={"reply_to": user_msg.id, "chain_part": True},
                        )
                        chain_link = (
                            f"{current_agent.name} 完成了自己那部分，"
                            f"交给 {target_agent.name} 接着补"
                        )
                        chain_msg = await save_message(
                            db, group.id, "system", chain_link,
                            meta={
                                "reply_to": user_msg.id,
                                "chain_from": current_agent.id,
                                "chain_to": target_agent.id,
                                "chain_focus": next_focus,
                            },
                        )
                        await db.commit()
                        yield f"data: {json.dumps({'type': 'handoff', 'id': chain_msg.id, 'from': current_agent.name, 'from_agent_id': current_agent.id, 'to': target_agent.name, 'to_agent_id': target_agent.id, 'reason': next_focus, 'content': chain_link, 'carried': part_text, 'mode': 'chain', 'reply_to': user_msg.id}, ensure_ascii=False)}\n\n"

                        current_agent = target_agent
                        visited.add(target_agent.id)
                        raw = ""
                        artifacts = []
                        # 这一轮已经作为 chain_part 落库了，最后不要再存一遍
                        part_saved = True
                        yield f"data: {json.dumps({'type': 'agent_start', 'agent_id': current_agent.id, 'agent': current_agent.name, 'handoff': True, 'chain': True}, ensure_ascii=False)}\n\n"
                        continue

                # 检查是否要求转交（做不了，换人）
                target_name, why = parse_handoff(raw)

                # 显式的「缺人」标记最可靠：模型明确说了要补谁，直接照做。
                # 比从自然语言里猜准得多——真实模型会换着说法表达同一件事，
                # 关键词匹配漏得太多（实测「文件已审阅，无数据建模内容」就漏了）。
                need_desc = parse_need_member(raw)
                allow_recruit = (group.settings or {}).get("auto_recruit", True)

                if need_desc and allow_recruit:
                    recruited, _note, join_msg = await _recruit_and_join(
                        db, group, agents, effective_content, user_id, user_msg.id,
                        role_hint=need_desc,
                    )
                    if recruited is not None:
                        yield _member_event(join_msg, recruited, need_desc)
                        target_name = recruited.name
                        why = f"群里没有对口的成员，已创建「{recruited.name}」"
                elif not target_name and hop < MAX_HANDOFF and looks_like_refusal(raw):
                    # 兜底：模型说了「不归我管」却没输出协议标记。
                    # 这种情况任务会卡在它这里，用路由再判一次该谁接。
                    #
                    # 明确说了「群里没人能做」→ 直接招人，不要问路由。
                    # 路由只看成员描述，遇到「软件方面的东西」这种空泛描述会硬选，
                    # 把「缺人」误判成「转给那个勉强相关的人」。
                    if says_nobody(raw):
                        if allow_recruit:
                            recruited, _note, join_msg = await _recruit_and_join(
                                db, group, agents, effective_content, user_id, user_msg.id
                            )
                            if recruited is not None:
                                yield _member_event(join_msg, recruited, "群里没有对口的成员")
                                target_name = recruited.name
                                why = f"群里没有对口的成员，已创建「{recruited.name}」"
                    else:
                        # 只是「不归我管」→ 先看群里有没有更合适的人。
                        # 关键是把「谁说做不了、为什么」喂给路由：第一次路由只看到
                        # 「你执行吧」这种话，根本判断不出缺哪方面的人。
                        alt, alt_reason, _ = await route_task(
                            db,
                            group,
                            agents,
                            build_reroute_message(
                                effective_content, current_agent.name, raw
                            ),
                        )
                        if alt is not None and alt.id != current_agent.id:
                            logger.info(
                                "handoff fallback: %s -> %s (%s)",
                                current_agent.name, alt.name, alt_reason,
                            )
                            target_name, why = alt.name, alt_reason
                        elif alt is None and allow_recruit:
                            # 路由也确认无人能接 —— 转交没有意义，按任务招一个
                            recruited, _note, join_msg = await _recruit_and_join(
                                db, group, agents, effective_content, user_id, user_msg.id
                            )
                            if recruited is not None:
                                yield _member_event(join_msg, recruited, alt_reason)
                                target_name = recruited.name
                                why = f"群里没有对口的成员，已创建「{recruited.name}」"

                # 接力被拒时（人数上限到了、或目标不存在），模型留下的 NEXT
                # 标记会被静默丢掉，用户就不知道协作为什么停了。
                # 说明走系统消息，不塞进正文——塞进去看起来像模型在说话，
                # 而且打断了最后一位成员的正文。
                if not target_name and parse_next(raw)[0]:
                    if len(contributions) >= max_speakers - 1:
                        stop_note = (
                            f"已达成 {max_speakers} 位成员的协作，接力停止。"
                            f"需要更多视角可以把群设置里的「最多 {max_speakers} 人」调大"
                        )
                    elif bounced:
                        stop_note = (
                            "协作已形成闭环（成员之间来回补充过一次），接力停止。"
                            "继续来回只会重复同样的内容"
                        )
                    else:
                        stop_note = (
                            f"成员「{parse_next(raw)[0]}」不在群里或已完成本次协作，接力停止"
                        )
                    stop_msg = await save_message(
                        db, group.id, "system", stop_note,
                        meta={"reply_to": user_msg.id, "chain_stop": True},
                    )
                    await db.commit()
                    yield f"data: {json.dumps({'type': 'system_message', 'id': stop_msg.id, 'content': stop_note, 'reply_to': user_msg.id}, ensure_ascii=False)}\n\n"
                    raw = strip_protocol(raw)

                if not target_name or hop >= MAX_HANDOFF:
                    break

                next_agent = find_agent_by_name(agents, target_name)
                if next_agent is None or next_agent.id == current_agent.id:
                    # 找不到人，或要转回自己：保留原回复，不制造假转交
                    break

                # 接手的是自动创建的成员 → 用交接话术，
                # 告诉它是被为什么拉进来的、要做什么
                if (next_agent.settings or {}).get("auto_created"):
                    current_is_recruited = True

                # 转圈检测：目标在本次接力里已经接过活，说明这几个人都做不了，
                # 再转下去只是踢皮球。这时该补人，而不是继续转。
                if next_agent.id in visited:
                    if not allow_recruit:
                        break
                    recruited, _note, join_msg = await _recruit_and_join(
                        db, group, agents, effective_content, user_id, user_msg.id
                    )
                    if recruited is None:
                        break
                    yield _member_event(
                        join_msg, recruited, "现有成员都无法承担，转为补充新成员"
                    )
                    next_agent = recruited
                    current_is_recruited = True
                    why = f"现有成员都不适合，已创建「{recruited.name}」"

                visited.add(next_agent.id)

                hop += 1
                carried = strip_handoff(raw)

                # 把这一棒的发言落库：他说的「我确认了什么 / 为什么做不了」
                # 对用户是有用的信息，只在内存里传给下一位、界面上不落盘，
                # 刷新后就丢了，对话看起来就断片。
                interim_id = None
                if carried:
                    interim_msg = await save_message(
                        db, group.id, "agent", carried,
                        sender_id=current_agent.id,
                        sender_name=current_agent.name,
                        meta={
                            "reply_to": user_msg.id,
                            "interim": True,
                            "execution_mode": effective_mode,
                        },
                    )
                    interim_id = interim_msg.id
                    await db.commit()

                handoff_text = (
                    f"{current_agent.name} 把任务转交给 {next_agent.name}"
                    + (f"：{why}" if why else "")
                )
                handoff_msg = await save_message(
                    db, group.id, "system", handoff_text,
                    meta={
                        "reply_to": user_msg.id,
                        "handoff_from": current_agent.id,
                        "handoff_to": next_agent.id,
                        "handoff_reason": why,
                    },
                )
                await db.commit()
                # carried 是这一棒已经确认的内容：前端据此把它的发言留在时间线上，
                # 否则用户只看到「转交给谁」，看不到「转交前干了什么」。
                yield f"data: {json.dumps({'type': 'handoff', 'id': handoff_msg.id, 'interim_id': interim_id, 'from': current_agent.name, 'from_agent_id': current_agent.id, 'to': next_agent.name, 'to_agent_id': next_agent.id, 'reason': why, 'content': handoff_text, 'carried': carried, 'reply_to': user_msg.id}, ensure_ascii=False)}\n\n"

                # 换人，并把前一位确认的内容带过去
                task_text = build_handoff_prompt(
                    next_agent, effective_content, current_agent, carried, asked_by
                )
                current_agent = next_agent
                raw = ""
                artifacts = []

                yield f"data: {json.dumps({'type': 'agent_start', 'agent_id': current_agent.id, 'agent': current_agent.name, 'handoff': True}, ensure_ascii=False)}\n\n"

            # 5. @ 回发起人（用最后一棒 agent 的身份）
            #    必须用 strip_protocol：它连 NEXT 一起清。
            #    之前这里用的是 strip_handoff，只清 HANDOFF 与 NEED_MEMBER，
            #    于是 [[NEXT: ...]] 直接透出到界面上了。
            content = format_reply_content(current_agent, strip_protocol(raw), asked_by)

            # 纯大模型模式分块推送做打字机效果；
            # PiAgent 已经逐事件推过文字了，这里只补最终完整内容给前端替换。
            if effective_mode != "pi":
                step = 12
                for i in range(0, len(content), step):
                    yield f"data: {json.dumps({'type': 'agent_chunk', 'agent_id': current_agent.id, 'text': content[i:i + step]}, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(0.012)

            # 6. 落库（sender 用最后一棒，可能是转交后的接手人）
            # part_saved 为真说明最后这一轮已经作为链路中的一段落过库了，
            # 再存一遍会导致界面上同一条回复出现两次。
            if part_saved:
                await db.commit()
                yield f"data: {json.dumps({'type': 'agent_done', 'id': None, 'agent_id': current_agent.id, 'agent': current_agent.name, 'reply_to': user_msg.id, 'content': content, 'execution_mode': effective_mode, 'files': artifacts, 'handoff_hops': hop}, ensure_ascii=False, default=str)}\n\n"
                yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
                return

            reply_msg = await save_message(
                db, group.id, "agent", content,
                sender_id=current_agent.id,
                sender_name=current_agent.name,
                meta={
                    "reply_to": user_msg.id,
                    "mentions": [asked_by],
                    "route_reason": reason,
                    "confidence": round(confidence, 2),
                    "execution_mode": effective_mode,
                    "files": artifacts,
                    **({"handoff_hops": hop} if hop else {}),
                },
            )
            await consume_quota(db, sub, Resource.MESSAGES)
            await db.commit()

            yield f"data: {json.dumps({'type': 'agent_done', 'id': reply_msg.id, 'agent_id': current_agent.id, 'agent': current_agent.name, 'reply_to': user_msg.id, 'content': content, 'execution_mode': effective_mode, 'files': artifacts, 'handoff_hops': hop}, ensure_ascii=False, default=str)}\n\n"

            # 8. 协作汇总：整条链路的收尾。
            #    没有这一步，用户看到的是几段并列的专家意见，得自己拼成方案。
            #    放在最后，是让「综合结论」成为这段对话的自然终点。
            if collab_on and len(contributions) >= 2:
                summary_text = await _summarize_chain(
                    db, group, agents, effective_content, contributions, asked_by
                )
                if summary_text:
                    sum_msg = await save_message(
                        db, group.id, "agent", summary_text,
                        sender_name="群内协作汇总",
                        meta={"reply_to": user_msg.id, "chain_summary": True},
                    )
                    await db.commit()
                    yield f"data: {json.dumps({'type': 'agent_done', 'id': sum_msg.id, 'agent': '群内协作汇总', 'content': summary_text, 'reply_to': user_msg.id}, ensure_ascii=False, default=str)}\n\n"

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
