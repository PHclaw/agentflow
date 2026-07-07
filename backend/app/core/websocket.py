"""WebSocket 支持 - 实时通信"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from typing import Dict, List
import json
import asyncio
from datetime import datetime

router = APIRouter()


class ConnectionManager:
    """WebSocket 连接管理器"""
    
    def __init__(self):
        # 用户连接池 {user_id: [websocket]}
        self.user_connections: Dict[str, List[WebSocket]] = {}
        # Agent 连接池 {agent_id: [websocket]}
        self.agent_connections: Dict[str, List[WebSocket]] = {}
        # 全局订阅 {channel: [websocket]}
        self.channels: Dict[str, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, user_id: str = None, agent_id: str = None, channel: str = None):
        """建立连接"""
        await websocket.accept()
        
        if user_id:
            if user_id not in self.user_connections:
                self.user_connections[user_id] = []
            self.user_connections[user_id].append(websocket)
        
        if agent_id:
            if agent_id not in self.agent_connections:
                self.agent_connections[agent_id] = []
            self.agent_connections[agent_id].append(websocket)
        
        if channel:
            if channel not in self.channels:
                self.channels[channel] = []
            self.channels[channel].append(websocket)
    
    def disconnect(self, websocket: WebSocket, user_id: str = None, agent_id: str = None, channel: str = None):
        """断开连接"""
        if user_id and user_id in self.user_connections:
            if websocket in self.user_connections[user_id]:
                self.user_connections[user_id].remove(websocket)
        
        if agent_id and agent_id in self.agent_connections:
            if websocket in self.agent_connections[agent_id]:
                self.agent_connections[agent_id].remove(websocket)
        
        if channel and channel in self.channels:
            if websocket in self.channels[channel]:
                self.channels[channel].remove(websocket)
    
    async def send_to_user(self, user_id: str, message: dict):
        """发送消息给指定用户"""
        if user_id in self.user_connections:
            disconnected = []
            for ws in self.user_connections[user_id]:
                try:
                    await ws.send_json(message)
                except:
                    disconnected.append(ws)
            # 清理断开的连接
            for ws in disconnected:
                self.disconnect(ws, user_id=user_id)
    
    async def send_to_agent(self, agent_id: str, message: dict):
        """发送消息给指定 Agent"""
        if agent_id in self.agent_connections:
            disconnected = []
            for ws in self.agent_connections[agent_id]:
                try:
                    await ws.send_json(message)
                except:
                    disconnected.append(ws)
            for ws in disconnected:
                self.disconnect(ws, agent_id=agent_id)
    
    async def broadcast_to_channel(self, channel: str, message: dict):
        """广播消息到频道"""
        if channel in self.channels:
            disconnected = []
            for ws in self.channels[channel]:
                try:
                    await ws.send_json(message)
                except:
                    disconnected.append(ws)
            for ws in disconnected:
                self.disconnect(ws, channel=channel)
    
    async def send_to_all(self, message: dict):
        """发送给所有连接"""
        all_connections = (
            list(self.user_connections.values()) +
            list(self.agent_connections.values()) +
            list(self.channels.values())
        )
        for connections in all_connections:
            for ws in connections:
                try:
                    await ws.send_json(message)
                except:
                    pass


# 全局连接管理器
manager = ConnectionManager()


@router.websocket("/ws/chat/{agent_id}")
async def websocket_chat(websocket: WebSocket, agent_id: str):
    """Agent 聊天 WebSocket"""
    await manager.connect(websocket, agent_id=agent_id)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # 处理消息类型
            msg_type = message.get("type")
            
            if msg_type == "message":
                # 用户发送消息
                await websocket.send_json({
                    "type": "ack",
                    "message_id": message.get("message_id"),
                    "status": "received",
                    "timestamp": datetime.now().isoformat()
                })
                
                # 广播到 Agent 频道
                await manager.broadcast_to_channel(f"agent:{agent_id}", {
                    "type": "user_message",
                    "message": message.get("content"),
                    "timestamp": datetime.now().isoformat()
                })
                
            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})
                
    except WebSocketDisconnect:
        manager.disconnect(websocket, agent_id=agent_id)


@router.websocket("/ws/workflow/{workflow_id}")
async def websocket_workflow(websocket: WebSocket, workflow_id: str):
    """工作流执行 WebSocket"""
    await manager.connect(websocket, channel=f"workflow:{workflow_id}")
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "subscribe":
                # 订阅工作流执行状态
                await websocket.send_json({
                    "type": "subscribed",
                    "workflow_id": workflow_id,
                    "timestamp": datetime.now().isoformat()
                })
            elif message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
                
    except WebSocketDisconnect:
        manager.disconnect(websocket, channel=f"workflow:{workflow_id}")


@router.websocket("/ws/user")
async def websocket_user(websocket: WebSocket):
    """用户通知 WebSocket"""
    # 从查询参数获取用户 ID
    user_id = websocket.query_params.get("user_id")
    if not user_id:
        await websocket.close(code=4001, reason="Missing user_id")
        return
    
    await manager.connect(websocket, user_id=user_id)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
                
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id=user_id)


# 广播接口 - 用于内部服务
@router.post("/broadcast/user/{user_id}")
async def broadcast_to_user(user_id: str, message: dict):
    """向用户广播消息"""
    await manager.send_to_user(user_id, message)
    return {"status": "ok"}


@router.post("/broadcast/agent/{agent_id}")
async def broadcast_to_agent(agent_id: str, message: dict):
    """向 Agent 广播消息"""
    await manager.send_to_agent(agent_id, message)
    return {"status": "ok"}


@router.post("/broadcast/channel/{channel}")
async def broadcast_to_channel(channel: str, message: dict):
    """向频道广播消息"""
    await manager.broadcast_to_channel(channel, message)
    return {"status": "ok"}


@router.get("/connections/stats")
async def get_connection_stats():
    """获取连接统计"""
    return {
        "user_connections": len(manager.user_connections),
        "agent_connections": len(manager.agent_connections),
        "channels": len(manager.channels),
        "total": sum(
            len(conns) 
            for conns in list(manager.user_connections.values()) + 
                       list(manager.agent_connections.values()) +
                       list(manager.channels.values())
        )
    }
