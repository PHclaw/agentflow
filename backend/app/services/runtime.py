"""
Agent 运行时
"""
from typing import Optional, List, AsyncIterator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json

from ..models.agent import Agent, ChatSession
from ..workflows.engine import WorkflowEngine
from ..services.llm import LLMService
from ..services.knowledge import KnowledgeService
from ..services.tools import tool_service


class AgentRuntime:
    """Agent 运行时"""
    
    def __init__(
        self,
        agent_id: str,
        db: AsyncSession,
        user_id: str = None,
    ):
        self.agent_id = agent_id
        self.db = db
        self.user_id = user_id
        
        self.agent: Optional[Agent] = None
        self.workflow: Optional[WorkflowEngine] = None
        self.llm: Optional[LLMService] = None
        self.knowledge: Optional[KnowledgeService] = None
        self.session: Optional[ChatSession] = None
    
    async def initialize(self):
        """初始化"""
        # 加载 Agent 配置
        result = await self.db.execute(
            select(Agent).where(Agent.id == self.agent_id)
        )
        self.agent = result.scalar_one_or_none()
        
        if not self.agent:
            raise ValueError(f"Agent not found: {self.agent_id}")
        
        # 初始化工作流引擎
        self.workflow = WorkflowEngine(self.agent.workflow_definition)
        
        # 初始化 LLM
        model_config = self.agent.model_config or {}
        self.llm = LLMService(
            provider=model_config.get("provider", "openai"),
            model=model_config.get("model"),
        )
    
    async def chat(
        self,
        message: str,
        session_id: Optional[str] = None,
        stream: bool = False,
    ) -> str:
        """对话"""
        # 加载或创建会话
        await self._load_or_create_session(session_id)
        
        # 获取历史消息
        history = self.session.messages or []
        
        # 添加用户消息
        history.append({"role": "user", "content": message})
        
        # 执行工作流
        response = await self.workflow.run(message)
        
        # 添加助手回复
        history.append({"role": "assistant", "content": response})
        
        # 保存会话
        self.session.messages = history
        await self.db.commit()
        
        # 更新统计
        self.agent.message_count = (self.agent.message_count or 0) + 1
        await self.db.commit()
        
        return response
    
    async def chat_with_tools(
        self,
        message: str,
        session_id: Optional[str] = None,
    ) -> str:
        """带工具调用的对话"""
        # 加载历史
        await self._load_or_create_session(session_id)
        history = self.session.messages or []
        history.append({"role": "user", "content": message})
        
        # 第一次调用 LLM
        response = await self.llm.chat(
            messages=history,
            temperature=0.7,
        )
        
        # 检查是否需要工具调用
        # 简化实现，实际应解析 function_call
        
        # 保存
        history.append({"role": "assistant", "content": response})
        self.session.messages = history
        await self.db.commit()
        
        return response
    
    async def chat_with_rag(
        self,
        message: str,
        session_id: Optional[str] = None,
        kb_id: Optional[str] = None,
    ) -> str:
        """带 RAG 的对话"""
        # 获取知识库上下文
        context = ""
        if kb_id:
            kb_service = KnowledgeService(self.db, kb_id)
            context = await kb_service.get_context(message)
        
        # 构建消息
        await self._load_or_create_session(session_id)
        history = self.session.messages or []
        
        # 添加系统提示
        if context:
            system_message = {
                "role": "system",
                "content": f"参考以下信息回答问题：\n\n{context}"
            }
            messages = [system_message] + history + [{"role": "user", "content": message}]
        else:
            messages = history + [{"role": "user", "content": message}]
        
        # 调用 LLM
        response = await self.llm.chat(messages=messages)
        
        # 保存
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": response})
        self.session.messages = history
        await self.db.commit()
        
        return response
    
    async def _load_or_create_session(self, session_id: Optional[str]):
        """加载或创建会话"""
        if session_id:
            result = await self.db.execute(
                select(ChatSession).where(ChatSession.id == session_id)
            )
            self.session = result.scalar_one_or_none()
        
        if not self.session:
            self.session = ChatSession(
                agent_id=self.agent_id,
                user_id=self.user_id,
                messages=[],
            )
            self.db.add(self.session)
            await self.db.commit()
            await self.db.refresh(self.session)
    
    async def get_history(self, session_id: str) -> List[dict]:
        """获取对话历史"""
        result = await self.db.execute(
            select(ChatSession).where(ChatSession.id == session_id)
        )
        session = result.scalar_one_or_none()
        
        if not session:
            return []
        
        return session.messages or []
    
    async def clear_history(self, session_id: str):
        """清空对话历史"""
        result = await self.db.execute(
            select(ChatSession).where(ChatSession.id == session_id)
        )
        session = result.scalar_one_or_none()
        
        if session:
            session.messages = []
            await self.db.commit()
