from __future__ import annotations

from typing import Any

from app.schemas import AgentOwnerOut, AgentPublicOut
from app.services.skill.taxonomy import category_of_agent


def _system_text(agent) -> str:
    from app.services.skill.invocation import _resolve_system_text

    return _resolve_system_text(getattr(agent, "system_prompt_enc", None) or "")


def _triggers(agent) -> list[str]:
    raw = getattr(agent, "triggers", None) or []
    out: list[str] = []
    for t in raw:
        s = str(t).strip()
        if s and s not in out:
            out.append(s[:64])
    return out[:16]


def to_public(agent) -> AgentPublicOut:
    """使用者视角：不含说明文档与内部 Prompt；路由元数据公开可见。"""
    cat_id, cat_name = category_of_agent(agent)
    return AgentPublicOut(
        id=agent.id,
        name=agent.name,
        description=agent.description,
        specialty=getattr(agent, "specialty", None) or "",
        category=cat_id,
        categoryName=cat_name,
        routerBlurb=getattr(agent, "router_blurb", None) or "",
        triggers=_triggers(agent),
        tags=agent.tags or [],
        authorName=agent.author_name,
        version=agent.version,
        changelog=agent.changelog or "",
        status=agent.status,
        visibility=agent.visibility,
        mdDoc=agent.md_doc or "",
        variables=agent.variables or [],
        examples=agent.examples or [],
        totalCalls=agent.total_calls,
        publishedAt=agent.published_at,
    )


def to_owner(agent) -> AgentOwnerOut:
    public = to_public(agent).model_dump(by_alias=True)
    public["mdDoc"] = agent.md_doc or ""
    return AgentOwnerOut(
        **public,
        modelName=agent.model_name,
        modelParams=agent.model_params or {},
        systemPrompt=_system_text(agent),
        userPromptTemplate=agent.user_prompt_template,
        workflow=agent.workflow or {},
    )


def serialize_for_role(agent, user_id: str) -> AgentPublicOut | AgentOwnerOut:
    if agent.author_id == user_id:
        return to_owner(agent)
    return to_public(agent)


def to_plaza_item(agent, *, viewer_id: str | None = None) -> dict[str, Any]:
    """广场/收藏卡片：面向用户的公开简介，不含 Prompt 等内部细节。"""
    cat_id, cat_name = category_of_agent(agent)
    return {
        "id": agent.id,
        "name": agent.name,
        "description": agent.description,
        "specialty": getattr(agent, "specialty", None) or "",
        "category": cat_id,
        "categoryName": cat_name,
        "routerBlurb": getattr(agent, "router_blurb", None) or "",
        "triggers": _triggers(agent),
        "tags": agent.tags or [],
        "authorName": agent.author_name,
        "version": agent.version,
        "changelog": agent.changelog or "",
        "status": agent.status,
        "visibility": agent.visibility,
        "examples": agent.examples or [],
        "totalCalls": agent.total_calls,
        "publishedAt": agent.published_at,
        "isMine": bool(viewer_id and agent.author_id == viewer_id),
    }
