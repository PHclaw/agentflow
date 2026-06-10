"""
整合版 Agent 运行时

使用 agent-* 库生态
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json
import logging

from ..models.agent import Agent, ChatSession
from ..integrations import config, tracer
from ..integrations.prompts_outputs import prompt_manager, output_parser
from ..integrations.tools_memory import tool_manager, MemoryManager, ConversationMemory
from ..services.llm import LLMService
from ..services.knowledge import KnowledgeService


class IntegratedAgentRuntime:
    """
    整合版 Agent 运行时
    
    整合了：
    - agent-config-loader: 配置管理
    - agent-observability: 追踪
    - agent-prompt-templates: 提示词模板
    - agent-output-parser: 输出解析
    - agent-tool-registry: 工具管理
    - agent-memory-store: 记忆管理
    """
    
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
        self.llm: Optional[LLMService] = None
        self.knowledge: Optional[KnowledgeService] = None
        self.memory: Optional[ConversationMemory] = None
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
        
        # 初始化 LLM
        model_config = self.agent.model_config or {}
        self.llm = LLMService(
            provider=model_config.get("provider", "openai"),
            model=model_config.get("model"),
        )
        
        # 初始化记忆管理
        memory_manager = MemoryManager(
            backend=config.get("MEMORY_BACKEND", "in_memory"),
            config={"redis_url": config.redis_url}
        )
        
        # 初始化知识库
        kb_id = self.agent.knowledge_base_id
        if kb_id:
            self.knowledge = KnowledgeService(self.db, kb_id)
    
    @tracer.trace_chat
    async def chat(
        self,
        message: str,
        session_id: Optional[str] = None,
        stream: bool = False,
    ) -> str:
        """
        对话（整合版）
        
        自动追踪、使用模板、解析输出
        """
        # 开始追踪
        span_id = tracer.start_span(
            name="chat",
            agent_id=self.agent_id,
            session_id=session_id
        )
        
        try:
            # 加载或创建会话
            await self._load_or_create_session(session_id)
            
            # 初始化记忆
            self.memory = ConversationMemory(
                session_id=self.session.id,
                memory_manager=MemoryManager()
            )
            
            # 获取历史
            history = await self.memory.get_history()
            
            # 获取模板
            template_name = self.agent.template or "qa"
            
            # RAG 上下文
            context = ""
            if self.knowledge:
                context = await self.knowledge.get_context(message)
            
            # 构建消息
            messages = prompt_manager.build_messages(
                template_name=template_name,
                user_message=message,
                history=history,
                context=context
            )
            
            # 调用 LLM
            response = await self.llm.chat(
                messages=messages,
                temperature=self.agent.temperature or 0.7,
                stream=stream
            )
            
            # 解析输出
            parsed = output_parser.parse(response, format="auto")
            
            # 检查工具调用
            if parsed.get("tool"):
                tool_result = await tool_manager.execute(
                    tool_name=parsed["tool"],
                    **parsed.get("input", {})
                )
                
                # 如果工具调用成功，可能需要再次调用 LLM
                if tool_result.get("success"):
                    # 简化：直接返回工具结果
                    response = json.dumps(
                        tool_result["result"],
                        ensure_ascii=False,
                    )
            
            # 保存记忆
            await self.memory.add_message("user", message)
            await self.memory.add_message("assistant", response)
            
            # 更新统计
            self.agent.message_count = (self.agent.message_count or 0) + 1
            await self.db.commit()
            
            # 结束追踪
            tracer.end_span(span_id)
            
            return response
            
        except Exception as e:
            tracer.end_span(span_id, error=e)
            raise
    
    async def chat_with_tools(
        self,
        message: str,
        session_id: Optional[str] = None,
    ) -> str:
        """
        带工具调用的对话（整合版）
        
        使用 agent-tool-registry 管理工具
        """
        await self._load_or_create_session(session_id)
        
        # 获取工具 schema
        tools = tool_manager.get_tool_schemas()
        
        # 获取历史
        history = await self.memory.get_history() if self.memory else []
        history.append({"role": "user", "content": message})
        
        # 调用 LLM（带工具）
        # TODO: 实现 function calling
        response = await self.llm.chat(messages=history)
        
        # 解析工具调用
        parsed = output_parser.parse(response, format="tool_call")
        
        if parsed and parsed.get("tool"):
            # 执行工具
            tool_result = await tool_manager.execute(
                tool_name=parsed["tool"],
                **parsed.get("input", {})
            )
            
            # 再次调用 LLM
            history.append({"role": "assistant", "content": response})
            history.append({
                "role": "user",
                "content": f"工具结果：{json.dumps(tool_result, ensure_ascii=False)}"
            })
            
            final_response = await self.llm.chat(messages=history)
            return final_response
        
        return response
    
    async def multi_agent_chat(
        self,
        message: str,
        agent_ids: List[str],
        session_id: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        多 Agent 协作（整合 agent-orchestrator）
        
        让多个 Agent 协作完成任务
        """
        try:
            from agent_orchestrator import Workflow, AgentWrapper, Context
            
            # 创建 Agent 包装器
            agents = []
            for aid in agent_ids:
                runtime = IntegratedAgentRuntime(aid, self.db, self.user_id)
                await runtime.initialize()
                
                wrapper = AgentWrapper(
                    name=aid,
                    handler=lambda msg, r=runtime: r.chat(msg)
                )
                agents.append(wrapper)
            
            # 创建工作流
            workflow = Workflow()
            workflow.sequential(agents)
            
            # 执行
            context = Context()
            context.set_state("input", message)
            
            result = await workflow.run(context)
            
            return {"result": result.get_state("output", "")}
            
        except ImportError:
            # 回退：顺序执行
            results = {}
            for aid in agent_ids:
                runtime = IntegratedAgentRuntime(aid, self.db, self.user_id)
                await runtime.initialize()
                results[aid] = await runtime.chat(message, session_id)
            
            return results
    
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
    
    async def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "agent_id": self.agent_id,
            "message_count": self.agent.message_count or 0,
            "tracing": tracer.get_stats()
        }
