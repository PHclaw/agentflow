"""
对话 API（整合版）

使用 IntegratedAgentRuntime
"""
from fastapi import APIRouter, Depends, Body, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional, List

from ..core.database import get_db
from ..services.integrated_runtime import IntegratedAgentRuntime
from .auth import get_current_user_id

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    stream: bool = False


class ChatResponse(BaseModel):
    response: str
    session_id: str
    stats: Optional[dict] = None


class MultiAgentRequest(BaseModel):
    message: str
    agent_ids: List[str]
    session_id: Optional[str] = None


# 注意：/multi-agent 必须放在 /{agent_id} 之前，否则会被匹配为 agent_id
@router.post("/multi-agent")
async def multi_agent_chat(
    data: MultiAgentRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """
    多 Agent 协作
    
    使用 agent-orchestrator 协调多个 Agent
    """
    if not data.agent_ids:
        raise HTTPException(status_code=400, detail="agent_ids is required")
    
    try:
        # 使用第一个 agent 作为主运行时
        runtime = IntegratedAgentRuntime(
            agent_id=data.agent_ids[0],
            db=db,
            user_id=user_id,
        )
        
        await runtime.initialize()
        
        results = await runtime.multi_agent_chat(
            message=data.message,
            agent_ids=data.agent_ids,
            session_id=data.session_id,
        )
        
        return {
            "results": results,
            "session_id": runtime.session.id if runtime.session else None,
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Multi-agent error: {str(e)}")


@router.post("/{agent_id}", response_model=ChatResponse)
async def chat(
    agent_id: str,
    data: ChatRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """
    与 Agent 对话（整合版）
    
    使用 IntegratedAgentRuntime，自动：
    - 追踪对话
    - 使用提示词模板
    - 解析输出
    - 管理记忆
    """
    try:
        # 创建运行时
        runtime = IntegratedAgentRuntime(
            agent_id=agent_id,
            db=db,
            user_id=user_id,
        )
        
        # 初始化
        await runtime.initialize()
        
        # 对话
        response = await runtime.chat(
            message=data.message,
            session_id=data.session_id,
            stream=data.stream,
        )
        
        # 获取统计
        stats = await runtime.get_stats()
        
        return ChatResponse(
            response=response,
            session_id=runtime.session.id,
            stats=stats,
        )
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")


@router.post("/{agent_id}/with-tools", response_model=ChatResponse)
async def chat_with_tools(
    agent_id: str,
    data: ChatRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """
    带工具调用的对话
    
    使用 agent-tool-registry 管理工具
    """
    try:
        runtime = IntegratedAgentRuntime(
            agent_id=agent_id,
            db=db,
            user_id=user_id,
        )
        
        await runtime.initialize()
        
        response = await runtime.chat_with_tools(
            message=data.message,
            session_id=data.session_id,
        )
        
        stats = await runtime.get_stats()
        
        return ChatResponse(
            response=response,
            session_id=runtime.session.id,
            stats=stats,
        )
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")


@router.get("/{agent_id}/stats")
async def get_agent_stats(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """
    获取 Agent 统计信息
    
    包括消息计数、追踪数据等
    """
    try:
        runtime = IntegratedAgentRuntime(
            agent_id=agent_id,
            db=db,
            user_id=user_id,
        )
        
        await runtime.initialize()
        
        stats = await runtime.get_stats()
        
        return stats
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
