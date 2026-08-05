"""
对话 API（整合版）

使用 IntegratedAgentRuntime
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
from typing import Optional, List
import json

from ..core.database import get_db
from ..models.agent import Agent, ChatSession
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


class FeedbackRequest(BaseModel):
    message_id: str
    rating: str  # "up" or "down"
    comment: Optional[str] = None


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
    # 流式对话
    if data.stream:
        async def generate_sse():
            try:
                runtime = IntegratedAgentRuntime(
                    agent_id=agent_id,
                    db=db,
                    user_id=user_id,
                )
                await runtime.initialize()

                # 加载或创建会话
                await runtime._load_or_create_session(data.session_id)

                # 发送 session_id
                yield f"data: {json.dumps({'type': 'session', 'session_id': runtime.session.id})}\n\n"

                # 获取历史 + RAG 上下文
                from ..integrations.prompts_outputs import prompt_manager
                from ..integrations.tools_memory import MemoryManager, ConversationMemory

                memory = ConversationMemory(
                    session_id=runtime.session.id,
                    memory_manager=MemoryManager()
                )
                history = await memory.get_history()

                context = ""
                if runtime.knowledge:
                    context = await runtime.knowledge.get_context(data.message)

                messages = prompt_manager.build_messages(
                    template_name=runtime.agent.template or "qa",
                    user_message=data.message,
                    history=history,
                    context=context
                )

                temperature = 0.7
                if runtime.agent.model_config:
                    temperature = runtime.agent.model_config.get("temperature", 0.7)

                # 流式调用 LLM
                full_response = ""
                async for chunk in runtime.llm.chat_stream(
                    messages=messages,
                    temperature=temperature,
                ):
                    full_response += chunk
                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"

                # 保存记忆
                await memory.add_message("user", data.message)
                await memory.add_message("assistant", full_response)

                # 更新统计
                runtime.agent.message_count = (runtime.agent.message_count or 0) + 1
                await db.commit()

                # 发送完成
                yield f"data: {json.dumps({'type': 'done', 'content': full_response, 'session_id': runtime.session.id})}\n\n"

            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

        return StreamingResponse(
            generate_sse(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # 非流式对话
    try:
        runtime = IntegratedAgentRuntime(
            agent_id=agent_id,
            db=db,
            user_id=user_id,
        )

        await runtime.initialize()

        response = await runtime.chat(
            message=data.message,
            session_id=data.session_id,
            stream=False,
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


@router.get("/{agent_id}/history")
async def get_chat_history(
    agent_id: str,
    session_id: Optional[str] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取对话历史"""
    # 验证 Agent 存在
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    if session_id:
        # 获取特定会话的历史
        stmt = select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.agent_id == agent_id,
            ChatSession.user_id == user_id,
        )
        result = await db.execute(stmt)
        session = result.scalar_one_or_none()

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        return {
            "session_id": session.id,
            "agent_id": agent_id,
            "messages": session.messages or [],
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "updated_at": session.updated_at.isoformat() if session.updated_at else None,
        }
    else:
        # 获取最新会话的历史
        stmt = select(ChatSession).where(
            ChatSession.agent_id == agent_id,
            ChatSession.user_id == user_id,
        ).order_by(ChatSession.updated_at.desc()).limit(1)
        result = await db.execute(stmt)
        session = result.scalar_one_or_none()

        if not session:
            return {
                "session_id": None,
                "agent_id": agent_id,
                "messages": [],
            }

        return {
            "session_id": session.id,
            "agent_id": agent_id,
            "messages": (session.messages or [])[-limit:],
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "updated_at": session.updated_at.isoformat() if session.updated_at else None,
        }


@router.get("/{agent_id}/sessions")
async def list_sessions(
    agent_id: str,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取 Agent 的会话列表"""
    # 验证 Agent 存在
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    stmt = select(ChatSession).where(
        ChatSession.agent_id == agent_id,
        ChatSession.user_id == user_id,
    ).order_by(ChatSession.updated_at.desc()).offset(offset).limit(limit)

    result = await db.execute(stmt)
    sessions = result.scalars().all()

    # 总数
    count_stmt = select(func.count(ChatSession.id)).where(
        ChatSession.agent_id == agent_id,
        ChatSession.user_id == user_id,
    )
    total = await db.scalar(count_stmt) or 0

    return {
        "sessions": [
            {
                "id": s.id,
                "agent_id": s.agent_id,
                "message_count": len(s.messages) if s.messages else 0,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "updated_at": s.updated_at.isoformat() if s.updated_at else None,
            }
            for s in sessions
        ],
        "total": total,
    }


@router.post("/{agent_id}/feedback")
async def submit_feedback(
    agent_id: str,
    data: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """提交对话反馈（点赞/点踩）"""
    # 目前简单记录，后续可扩展为独立表
    return {
        "status": "success",
        "message_id": data.message_id,
        "rating": data.rating,
    }


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
