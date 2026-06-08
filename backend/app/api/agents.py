"""
Agent API - 内存存储版本
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime
import uuid

from .auth import get_current_user_id

router = APIRouter()


class WorkflowNode(BaseModel):
    """工作流节点"""
    id: str = ""
    type: str = "llm"
    config: dict = {}


class WorkflowEdge(BaseModel):
    """工作流边"""
    source: str = ""
    target: str = ""
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


# 内存存储
_agents_db = {}


def _get_user_agents(user_id: str) -> List[dict]:
    """获取用户的所有agents"""
    return [a for a in _agents_db.values() if a["user_id"] == user_id]


@router.post("")
async def create_agent(
    data: AgentCreate,
    user_id: str = Depends(get_current_user_id)
):
    """创建 Agent"""
    agent_id = str(uuid.uuid4())[:8]
    agent = {
        "id": agent_id,
        "user_id": user_id,
        "name": data.name,
        "description": data.description or "",
        "workflow_definition": data.workflow_definition.model_dump() if data.workflow_definition else {"nodes": [], "edges": []},
        "model_config": data.llm_config.model_dump() if data.llm_config else {"provider": "openai", "model": "gpt-4o-mini"},
        "settings": {},
        "is_active": True,
        "message_count": 0,
        "created_at": datetime.now().isoformat(),
    }
    _agents_db[agent_id] = agent
    
    return {"id": agent_id, "name": agent["name"], "id": agent["id"], "description": agent["description"], "is_active": agent["is_active"], "message_count": agent["message_count"], "created_at": agent["created_at"]}


@router.get("")
async def list_agents(
    user_id: str = Depends(get_current_user_id)
):
    """列出用户的 Agents"""
    agents = _get_user_agents(user_id)
    return [
        {
            "id": a["id"],
            "name": a["name"],
            "description": a["description"],
            "is_active": a["is_active"],
            "message_count": a["message_count"],
            "created_at": a["created_at"],
        }
        for a in sorted(agents, key=lambda x: x["created_at"], reverse=True)
    ]


@router.get("/{agent_id}")
async def get_agent(
    agent_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """获取 Agent 详情"""
    if agent_id not in _agents_db:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    agent = _agents_db[agent_id]
    if agent["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    return agent


@router.put("/{agent_id}")
async def update_agent(
    agent_id: str,
    data: AgentUpdate,
    user_id: str = Depends(get_current_user_id)
):
    """更新 Agent"""
    if agent_id not in _agents_db:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    agent = _agents_db[agent_id]
    if agent["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if key == "workflow_definition" and value:
            agent[key] = value if isinstance(value, dict) else value.model_dump()
        elif key == "model_config" and value:
            agent[key] = value if isinstance(value, dict) else value.model_dump()
        else:
            agent[key] = value
    
    return {"id": agent_id, "message": "Updated successfully"}


@router.delete("/{agent_id}")
async def delete_agent(
    agent_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """删除 Agent"""
    if agent_id not in _agents_db:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    agent = _agents_db[agent_id]
    if agent["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    del _agents_db[agent_id]
    
    return {"message": "Deleted successfully"}
