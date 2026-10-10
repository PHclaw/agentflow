"""
Agent CRUD API — 数据库版本
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, List
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..core.database import get_db
from ..models.agent import Agent
from .auth import get_current_user_id

router = APIRouter()


class WorkflowNode(BaseModel):
    """工作流节点

    字段必须与前端 ReactFlow 的节点结构对齐：前端保存的是
    {id, type, position, data}，节点的配置（模型、提示词、响应模板等）全部在 data 里。

    这里额外放开 extra：本类原先只声明 {id, type, config}，pydantic 默认忽略
    未声明字段，导致前端传来的 position 与 data 被静默丢弃，
    工作流保存后节点配置全部变为空。放开 extra 可避免以后前端新增字段时重蹈覆辙。
    """
    model_config = ConfigDict(extra="allow")

    id: str = ""
    type: str = "llm"
    position: dict = {}
    data: dict = {}
    config: dict = {}


class WorkflowEdge(BaseModel):
    """工作流边

    sourceHandle 用于区分条件节点的 yes / no 分支，必须保留。
    """
    model_config = ConfigDict(extra="allow")

    id: str = ""
    source: str = ""
    target: str = ""
    sourceHandle: Optional[str] = None
    condition: Optional[dict] = None


class WorkflowDefinition(BaseModel):
    """工作流定义"""
    nodes: List[WorkflowNode] = []
    edges: List[WorkflowEdge] = []
    entry: str = "start"


class ModelConfig(BaseModel):
    """模型配置"""
    provider: str = "openai"
    model: str = "gpt-4o-mini"
    temperature: float = 0.7
    max_tokens: int = 2000


class AgentCreate(BaseModel):
    """创建 Agent"""
    name: str
    description: Optional[str] = None
    workflow_definition: Optional[WorkflowDefinition] = None
    llm_config: Optional[ModelConfig] = None


class AgentUpdate(BaseModel):
    """更新 Agent"""
    name: Optional[str] = None
    description: Optional[str] = None
    workflow_definition: Optional[WorkflowDefinition] = None
    llm_config: Optional[ModelConfig] = None
    is_active: Optional[bool] = None


# ----- 辅助 -----

def _agent_to_dict(agent: Agent) -> dict:
    """将 Agent ORM 对象转为前端需要的格式"""
    mc = agent.model_config or {}
    return {
        "id": agent.id,
        "name": agent.name,
        "description": agent.description or "",
        "model": mc.get("model", "gpt-4o-mini"),
        "status": "active" if agent.is_active else "inactive",
        "message_count": agent.message_count or 0,
        "is_active": agent.is_active,
        # 编辑器靠这个字段回填画布；此前这里漏了它，
        # 导致每次打开工作流编辑器都是空画布，已保存的工作流看起来凭空消失
        "workflow_definition": agent.workflow_definition or {"nodes": [], "edges": []},
        "created_at": agent.created_at.isoformat() if agent.created_at else "",
        "updated_at": agent.updated_at.isoformat() if agent.updated_at else "",
    }


# ----- 路由 -----

@router.post("")
async def create_agent(
    data: AgentCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """创建 Agent"""
    agent = Agent(
        user_id=user_id,
        name=data.name,
        description=data.description or "",
        workflow_definition=(
            data.workflow_definition.model_dump()
            if data.workflow_definition
            else {"nodes": [], "edges": []}
        ),
        model_config=(
            data.llm_config.model_dump()
            if data.llm_config
            else {"provider": "openai", "model": "gpt-4o-mini", "temperature": 0.7}
        ),
        settings={},
        is_active=True,
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return _agent_to_dict(agent)


@router.get("")
async def list_agents(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """列出用户的 Agents"""
    stmt = (
        select(Agent)
        .where(Agent.user_id == user_id)
        .order_by(Agent.created_at.desc())
    )
    result = await db.execute(stmt)
    agents = result.scalars().all()
    return [_agent_to_dict(a) for a in agents]


@router.get("/{agent_id}")
async def get_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """获取 Agent 详情"""
    agent = await db.get(Agent, agent_id)
    if not agent or agent.user_id != user_id:
        raise HTTPException(status_code=404, detail="Agent not found")
    return _agent_to_dict(agent)


@router.put("/{agent_id}")
async def update_agent(
    agent_id: str,
    data: AgentUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """更新 Agent"""
    agent = await db.get(Agent, agent_id)
    if not agent or agent.user_id != user_id:
        raise HTTPException(status_code=404, detail="Agent not found")

    update_data = data.model_dump(exclude_unset=True)
    key_map = {
        "llm_config": "model_config",
    }

    for key, value in update_data.items():
        if value is None:
            continue
        db_key = key_map.get(key, key)
        if db_key == "model_config" and hasattr(value, "model_dump"):
            setattr(agent, db_key, value.model_dump())
        elif db_key == "workflow_definition" and hasattr(value, "model_dump"):
            setattr(agent, db_key, value.model_dump())
        else:
            setattr(agent, db_key, value)

    await db.commit()
    await db.refresh(agent)
    return _agent_to_dict(agent)


@router.delete("/{agent_id}")
async def delete_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """删除 Agent"""
    agent = await db.get(Agent, agent_id)
    if not agent or agent.user_id != user_id:
        raise HTTPException(status_code=404, detail="Agent not found")

    await db.delete(agent)
    await db.commit()
    return {"message": "Deleted successfully"}
