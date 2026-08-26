"""Skill 广场与调用 API（整合自 Model Lab skills/）。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user_id
from app.core.database import get_db
from app.schemas import (
    AgentCallRequest,
    AgentCallResponse,
    AgentPlazaItem,
    SkillResolveItem,
    SkillResolveRequest,
    SkillResolveResponse,
)
from app.services import skill_service
from app.services.skill import resolve_skills
from app.services.skill.store import get_skill
from app.services.skill.taxonomy import list_categories
from app.services.uploads import save_upload_files

router = APIRouter()


@router.get("/categories")
async def skill_categories(user_id: str = Depends(get_current_user_id)):
    _ = user_id
    return {"categories": list_categories()}


@router.get("/plaza", response_model=list[AgentPlazaItem])
async def skill_plaza(
    specialty: Optional[str] = None,
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> list[AgentPlazaItem]:
    agents = await skill_service.list_plaza_agents(
        db,
        exclude_author_id=user_id,
        specialty=specialty,
        category=category,
        curated_only=True,
    )
    return [
        AgentPlazaItem.model_validate(skill_service.to_plaza_item(a, viewer_id=user_id))
        for a in agents
    ]


@router.get("/{skill_id}")
async def get_skill_detail(
    skill_id: str,
    user_id: str = Depends(get_current_user_id),
):
    skill = get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill 不存在")
    return skill_service.serialize_for_role(skill, user_id).model_dump(by_alias=True)


@router.post("/resolve", response_model=SkillResolveResponse)
async def resolve_skill(
    payload: SkillResolveRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> SkillResolveResponse:
    try:
        items = await resolve_skills(
            db,
            user_id=user_id,
            query=payload.query,
            top_k=payload.top_k,
            recall_k=payload.recall_k,
            rerank=payload.rerank,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"选型失败: {exc}") from exc

    skills = [SkillResolveItem.model_validate(x) for x in items]
    top = skills[0] if skills else None
    return SkillResolveResponse(
        query=payload.query.strip(),
        skills=skills,
        skillId=top.skill_id if top else None,
        confidence=top.confidence if top else None,
    )


@router.post("/{skill_id}/call", response_model=AgentCallResponse)
async def call_skill(
    skill_id: str,
    payload: AgentCallRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> AgentCallResponse:
    skill = get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill 不存在")
    try:
        return await skill_service.call_agent(
            db,
            skill,
            user_id,
            payload.variables,
            conversation_id=payload.session_id,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/{skill_id}/call-with-files", response_model=AgentCallResponse)
async def call_skill_with_files(
    skill_id: str,
    message: str = Form(""),
    session_id: Optional[str] = Form(None),
    files: list[UploadFile] = File(default=[]),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> AgentCallResponse:
    skill = get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill 不存在")
    uploaded = await save_upload_files(user_id, files) if files else []
    variables = {"input": message}
    try:
        return await skill_service.call_agent(
            db,
            skill,
            user_id,
            variables,
            uploaded_files=uploaded,
            conversation_id=session_id,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc
