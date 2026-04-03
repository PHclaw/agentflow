"""
Agent API
"""
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List
from pydantic import BaseModel

from ..core.database import get_db
from ..models.agent import Agent
from .auth import get_current_user_id

router = APIRouter()


class WorkflowNode(BaseModel):
    """工作流节点"""
    id: str
    type: str  # llm, condition, tool, template
    config: dict = {}


class WorkflowEdge(BaseModel):
    """工作流边"""
    source: str
    target: str
    condition: Optional[dict] = None


class WorkflowDefinition(BaseModel):
    """工作流定义"""
    nodes: List[WorkflowNode]
    edges: List[WorkflowEdge]
    entry: str = "start"


class ModelConfig(BaseModel):
    """模型配置"""
    provider: str = "openai"  # openai, anthropic, deepseek
    model: str = "gpt-4o-mini"
    temperature: float = 0.7
    max_tokens: int = 2000


class AgentCreate(BaseModel):
    """创建 Agent"""
    name: str
    description: Optional[str] = None
    workflow_definition: WorkflowDefinition
    model_config: Optional[ModelConfig] = None


class AgentUpdate(BaseModel):
    """更新 Agent"""
    name: Optional[str] = None
    description: Optional[str] = None
    workflow_definition: Optional[WorkflowDefinition] = None
    model_config: Optional[ModelConfig] = None
    is_active: Optional[bool] = None


@router.post("")
async def create_agent(
    data: AgentCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """创建 Agent"""
    agent = Agent(
        user_id=user_id,
        name=data.name,
        description=data.description,
        workflow_definition=data.workflow_definition.model_dump(),
        model_config=data.model_config.model_dump() if data.model_config else {},
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    
    return {"id": agent.id, "name": agent.name}


@router.get("")
async def list_agents(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """列出用户的 Agents"""
    result = await db.execute(
        select(Agent).where(Agent.user_id == user_id).order_by(Agent.created_at.desc())
    )
    agents = result.scalars().all()
    
    return [
        {
            "id": a.id,
            "name": a.name,
            "description": a.description,
            "is_active": a.is_active,
            "message_count": a.message_count,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in agents
    ]


@router.get("/{agent_id}")
async def get_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取 Agent 详情"""
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.user_id == user_id)
    )
    agent = result.scalar_one_or_none()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    return {
        "id": agent.id,
        "name": agent.name,
        "description": agent.description,
        "workflow_definition": agent.workflow_definition,
        "model_config": agent.model_config,
        "settings": agent.settings,
        "is_active": agent.is_active,
        "message_count": agent.message_count,
    }


@router.put("/{agent_id}")
async def update_agent(
    agent_id: str,
    data: AgentUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """更新 Agent"""
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.user_id == user_id)
    )
    agent = result.scalar_one_or_none()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    for field, value in data.model_dump(exclude_unset=True).items():
        if field == "workflow_definition" and value:
            setattr(agent, field, value.model_dump() if hasattr(value, 'model_dump') else value)
        elif field == "model_config" and value:
            setattr(agent, field, value.model_dump() if hasattr(value, 'model_dump') else value)
        else:
            setattr(agent, field, value)
    
    await db.commit()
    
    return {"id": agent.id, "message": "Updated successfully"}


@router.delete("/{agent_id}")
async def delete_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """删除 Agent"""
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.user_id == user_id)
    )
    agent = result.scalar_one_or_none()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    await db.delete(agent)
    await db.commit()
    
    return {"message": "Deleted successfully"}
