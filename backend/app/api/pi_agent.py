"""PiAgent API —— 可选的外部 agent CLI 引擎。

与现有 ``/api/v1/chat`` 直连大模型的链路完全独立，互不影响：

- ``GET  /api/v1/pi/status``                     运行时就绪状态与可用技能
- ``POST /api/v1/pi/{agent_id}/stream``          流式对话（SSE）
- ``POST /api/v1/pi/{agent_id}/run``             非流式对话（便于脚本/调试）
- ``GET  /api/v1/pi/{agent_id}/workspace``       列出工作区产物
- ``GET  /api/v1/pi/{agent_id}/files/{path}``    下载产物

开关：``PIAGENT_ENABLED=true`` 才会生效，否则一律返回 503。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user_id
from app.core.config import settings
from app.core.database import get_db
from app.core.paths import pi_agent_workspace, pi_skills_root, pi_workspace_root
from app.models.agent import Agent
from app.services.pi_agent import pi_agent_runner

router = APIRouter(
    dependencies=[Depends(get_current_user_id)],
)


class PiChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    skills: Optional[list[str]] = None
    timeout: Optional[int] = None


@dataclass
class AgentContext:
    """从 ORM 对象摘出来的只读上下文，避免流式过程中再触碰数据库会话。"""

    id: str
    name: str
    description: str | None = None
    system_prompt: str = ""
    model_config: dict[str, Any] = field(default_factory=dict)
    settings: dict[str, Any] = field(default_factory=dict)


def _ensure_enabled() -> None:
    if not settings.PIAGENT_ENABLED:
        raise HTTPException(
            503,
            "PiAgent 引擎未启用：请在 backend/.env 中设置 PIAGENT_ENABLED=true",
        )


async def _load_agent_context(db: AsyncSession, agent_id: str, user_id: str) -> AgentContext:
    agent = await db.get(Agent, agent_id)
    if not agent or agent.user_id != user_id:
        raise HTTPException(404, "Agent 不存在")

    model_config = agent.model_config if isinstance(agent.model_config, dict) else {}
    agent_settings = agent.settings if isinstance(agent.settings, dict) else {}

    # 系统提示词优先取 Agent 自身配置，供 build_system_prompt 使用
    system_prompt = str(model_config.get("system_prompt") or agent_settings.get("system_prompt") or "")

    return AgentContext(
        id=agent.id,
        name=agent.name,
        description=agent.description,
        system_prompt=system_prompt,
        model_config=dict(model_config),
        settings=dict(agent_settings),
    )


def _list_available_skills() -> list[str]:
    """列出技能目录下所有含 SKILL.md 的技能名。"""
    root = pi_skills_root()
    if not root.is_dir():
        return []
    names = []
    for entry in sorted(root.iterdir()):
        if entry.is_dir() and (entry / "SKILL.md").is_file():
            names.append(entry.name)
    return names


@router.get("/status")
async def pi_status() -> dict[str, Any]:
    """探测 PiAgent 运行时就绪状态（前端可据此决定是否展示该入口）。"""
    exe = pi_agent_runner.exe
    return {
        "enabled": settings.PIAGENT_ENABLED,
        "available": exe is not None,
        "exe": exe,
        "timeout": pi_agent_runner.timeout,
        "workspace_root": str(pi_workspace_root()),
        "skills_root": str(pi_skills_root()),
        "skills": _list_available_skills() if exe else [],
    }


@router.post("/{agent_id}/run")
async def pi_run(
    agent_id: str,
    data: PiChatRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    """非流式执行，返回最终文本与产物列表。"""
    _ensure_enabled()
    ctx = await _load_agent_context(db, agent_id, user_id)

    result = await pi_agent_runner.run(
        message=data.message,
        agent_id=ctx.id,
        agent=ctx,
        session_id=data.session_id,
        skills=data.skills,
        timeout=data.timeout,
    )

    if not result["success"]:
        return {"success": False, "error": result["error"], "content": "", "files": []}

    return {
        "success": True,
        "error": None,
        "content": result["content"],
        "files": result["files"],
    }


@router.post("/{agent_id}/stream")
async def pi_stream(
    agent_id: str,
    data: PiChatRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> StreamingResponse:
    """流式对话（SSE）。

    事件类型：``log`` / ``thinking`` / ``text`` / ``tool_call`` / ``done`` / ``error``。
    ``done`` 事件携带最终文本与工作区新增产物列表。
    """
    _ensure_enabled()
    ctx = await _load_agent_context(db, agent_id, user_id)

    async def event_generator():
        try:
            async for event in pi_agent_runner.stream(
                message=data.message,
                agent_id=ctx.id,
                agent=ctx,
                session_id=data.session_id,
                skills=data.skills,
                timeout=data.timeout,
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as exc:  # noqa: BLE001 - 保证流以 error 事件收尾
            payload = {"type": "error", "content": f"执行失败：{exc}"}
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{agent_id}/workspace")
async def list_workspace(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    """列出该 Agent 工作区内的产物文件。"""
    _ensure_enabled()
    ctx = await _load_agent_context(db, agent_id, user_id)

    workspace = pi_agent_workspace(ctx.id)
    files: list[dict[str, Any]] = []

    for root, dirs, names in os.walk(workspace):
        dirs[:] = [d for d in dirs if d not in {"node_modules", "__pycache__", ".git"} and not d.startswith(".")]
        for name in names:
            if name.startswith("."):
                continue
            path = Path(root) / name
            rel = path.relative_to(workspace).as_posix()
            try:
                stat = path.stat()
            except OSError:
                continue
            files.append({
                "name": name,
                "path": rel,
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "url": f"/api/v1/pi/{ctx.id}/files/{rel}",
            })

    files.sort(key=lambda item: item["modified"], reverse=True)
    return {"files": files, "workspace": str(workspace)}


def resolve_workspace_file(workspace: Path, file_path: str) -> Path:
    """把相对路径解析为工作区内的真实文件，越界即拒绝。

    单独抽出便于直接对路径穿越场景做单元测试。
    """
    workspace = Path(workspace).resolve()
    target = (workspace / file_path).resolve()

    if workspace != target and workspace not in target.parents:
        raise HTTPException(403, "禁止访问工作区之外的文件")

    if not target.is_file():
        raise HTTPException(404, "文件不存在")

    return target


@router.get("/{agent_id}/files/{file_path:path}")
async def download_artifact(
    agent_id: str,
    file_path: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> FileResponse:
    """下载工作区产物（限制在该 Agent 的工作区内）。"""
    _ensure_enabled()
    ctx = await _load_agent_context(db, agent_id, user_id)

    target = resolve_workspace_file(pi_agent_workspace(ctx.id), file_path)

    return FileResponse(
        target,
        filename=target.name,
        media_type="application/octet-stream",
    )
