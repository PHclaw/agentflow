"""
WebSocket 实时对话服务
支持流式响应和实时更新
"""
import asyncio
import json
from typing import Dict, List, Optional
from fastapi import WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..services.llm import LLMService


class ConnectionManager:
    """WebSocket 连接管理器"""

    def __init__(self):
        # {session_id: WebSocket}
        self.active_connections: Dict[str, WebSocket] = {}
        # {user_id: [session_ids]}
        self.user_sessions: Dict[str, List[str]] = {}

    async def connect(self, websocket: WebSocket, session_id: str, user_id: str):
        """接受 WebSocket 连接"""
        await websocket.accept()
        self.active_connections[session_id] = websocket

        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = []
        self.user_sessions[user_id].append(session_id)

    def disconnect(self, session_id: str, user_id: str):
        """断开 WebSocket 连接"""
        if session_id in self.active_connections:
            del self.active_connections[session_id]

        if user_id in self.user_sessions:
            self.user_sessions[user_id].remove(session_id)
            if not self.user_sessions[user_id]:
                del self.user_sessions[user_id]

    async def send_personal_message(self, message: dict, session_id: str):
        """发送个人消息"""
        if session_id in self.active_connections:
            await self.active_connections[session_id].send_json(message)

    async def broadcast_to_user(self, message: dict, user_id: str):
        """向用户的所有会话广播"""
        if user_id in self.user_sessions:
            for session_id in self.user_sessions[user_id]:
                await self.send_personal_message(message, session_id)


# 全局连接管理器
manager = ConnectionManager()


async def handle_streaming_chat(
    websocket: WebSocket,
    session_id: str,
    user_id: str,
    agent_id: str,
    message: str,
    db: AsyncSession
):
    """处理流式对话"""
    try:
        await manager.connect(websocket, session_id, user_id)

        # 发送开始消息
        await manager.send_personal_message({
            "type": "start",
            "session_id": session_id,
        }, session_id)

        # 创建 LLM 服务
        llm = LLMService()

        # 流式对话
        full_response = ""
        async for chunk in llm.chat_stream(
            messages=[{"role": "user", "content": message}],
            stream=True
        ):
            full_response += chunk
            await manager.send_personal_message({
                "type": "chunk",
                "content": chunk,
                "session_id": session_id,
            }, session_id)

        # 发送完成消息
        await manager.send_personal_message({
            "type": "complete",
            "content": full_response,
            "session_id": session_id,
        }, session_id)

    except WebSocketDisconnect:
        manager.disconnect(session_id, user_id)
    except Exception as e:
        await manager.send_personal_message({
            "type": "error",
            "error": str(e),
            "session_id": session_id,
        }, session_id)
        manager.disconnect(session_id, user_id)
