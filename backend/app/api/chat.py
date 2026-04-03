"""
对话 API
"""
from fastapi import APIRouter, Depends, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from ..core.database import get_db
from ..models.agent import Agent
from ..workflows.engine import WorkflowEngine
from .auth import get_current_user_id

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    session_id: str = None


@router.post("/{agent_id}")
async def chat(
    agent_id: str,
    data: ChatRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """与 Agent 对话"""
    # 加载 Agent
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id)
    )
    agent = result.scalar_one_or_none()
    
    if not agent:
        return {"error": "Agent not found"}
    
    # 执行工作流
    workflow = WorkflowEngine(agent.workflow_definition)
    response = await workflow.run(data.message)
    
    # 更新消息计数
    agent.message_count = (agent.message_count or 0) + 1
    await db.commit()
    
    return {
        "response": response,
        "session_id": data.session_id or "new",
    }
