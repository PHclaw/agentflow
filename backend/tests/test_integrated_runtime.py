"""
整合运行时测试
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.integrated_runtime import IntegratedAgentRuntime
from app.models.agent import Agent, ChatSession
from app.models.user import User


class TestIntegratedAgentRuntime:
    """IntegratedAgentRuntime 测试"""
    
    @pytest.mark.asyncio
    async def test_initialize(
        self,
        async_db: AsyncSession,
        test_agent: Agent,
    ):
        """测试初始化"""
        runtime = IntegratedAgentRuntime(
            agent_id=test_agent.id,
            db=async_db,
            user_id=test_agent.user_id,
        )
        
        await runtime.initialize()
        
        assert runtime.agent is not None
        assert runtime.agent.id == test_agent.id
        assert runtime.llm is not None
    
    @pytest.mark.asyncio
    async def test_chat_basic(
        self,
        async_db: AsyncSession,
        test_agent: Agent,
    ):
        """测试基本对话"""
        runtime = IntegratedAgentRuntime(
            agent_id=test_agent.id,
            db=async_db,
            user_id=test_agent.user_id,
        )
        
        await runtime.initialize()
        
        # Mock LLM
        runtime.llm.chat = AsyncMock(return_value="Hello! How can I help you?")
        
        response = await runtime.chat(message="Hello")
        
        assert response is not None
        assert len(response) > 0
    
    @pytest.mark.asyncio
    async def test_chat_with_session(
        self,
        async_db: AsyncSession,
        test_agent: Agent,
    ):
        """测试带会话的对话"""
        runtime = IntegratedAgentRuntime(
            agent_id=test_agent.id,
            db=async_db,
            user_id=test_agent.user_id,
        )
        
        await runtime.initialize()
        runtime.llm.chat = AsyncMock(return_value="Response")
        
        # 第一次对话
        response1 = await runtime.chat(message="Message 1")
        
        # 第二次对话（同一会话）
        response2 = await runtime.chat(
            message="Message 2",
            session_id=runtime.session.id,
        )
        
        assert response1 is not None
        assert response2 is not None
    
    @pytest.mark.asyncio
    async def test_chat_with_tools(
        self,
        async_db: AsyncSession,
        test_agent: Agent,
    ):
        """测试带工具调用的对话"""
        runtime = IntegratedAgentRuntime(
            agent_id=test_agent.id,
            db=async_db,
            user_id=test_agent.user_id,
        )
        
        await runtime.initialize()
        runtime.llm.chat = AsyncMock(return_value='{"tool": "search", "input": {"query": "test"}}')
        
        # Mock tool manager
        with patch("..services.integrated_runtime.tool_manager") as mock_tool:
            mock_tool.execute = AsyncMock(return_value={"success": True, "result": "search results"})
            
            response = await runtime.chat_with_tools(message="Search for test")
            
            assert response is not None
    
    @pytest.mark.asyncio
    async def test_multi_agent_chat(
        self,
        async_db: AsyncSession,
        test_agent: Agent,
    ):
        """测试多 Agent 协作"""
        runtime = IntegratedAgentRuntime(
            agent_id=test_agent.id,
            db=async_db,
            user_id=test_agent.user_id,
        )
        
        await runtime.initialize()
        runtime.llm.chat = AsyncMock(return_value="Agent response")
        
        # 使用同一个 agent ID 模拟多 agent
        results = await runtime.multi_agent_chat(
            message="Hello",
            agent_ids=[test_agent.id],
        )
        
        assert results is not None
        assert "result" in results or test_agent.id in results
    
    @pytest.mark.asyncio
    async def test_get_stats(
        self,
        async_db: AsyncSession,
        test_agent: Agent,
    ):
        """测试获取统计信息"""
        runtime = IntegratedAgentRuntime(
            agent_id=test_agent.id,
            db=async_db,
            user_id=test_agent.user_id,
        )
        
        await runtime.initialize()
        
        stats = await runtime.get_stats()
        
        assert stats["agent_id"] == test_agent.id
        assert "message_count" in stats
        assert "tracing" in stats


class TestPromptIntegration:
    """提示词整合测试"""
    
    def test_prompt_manager_import(self):
        """测试提示词管理器导入"""
        from app.integrations.prompts_outputs import prompt_manager
        
        assert prompt_manager is not None
    
    def test_build_messages(self):
        """测试构建消息"""
        from app.integrations.prompts_outputs import prompt_manager
        
        messages = prompt_manager.build_messages(
            template_name="qa",
            user_message="Hello",
            history=[],
            context="",
        )
        
        assert isinstance(messages, list)
        assert len(messages) > 0


class TestOutputParserIntegration:
    """输出解析整合测试"""
    
    def test_output_parser_import(self):
        """测试输出解析器导入"""
        from app.integrations.prompts_outputs import output_parser
        
        assert output_parser is not None
    
    def test_parse_json(self):
        """测试解析 JSON"""
        from app.integrations.prompts_outputs import output_parser
        
        result = output_parser.parse('{"key": "value"}', format="json")
        
        assert result is not None
        assert result.get("key") == "value"


class TestToolManagerIntegration:
    """工具管理整合测试"""
    
    def test_tool_manager_import(self):
        """测试工具管理器导入"""
        from app.integrations.tools_memory import tool_manager
        
        assert tool_manager is not None
    
    def test_get_tool_schemas(self):
        """测试获取工具 schema"""
        from app.integrations.tools_memory import tool_manager
        
        schemas = tool_manager.get_tool_schemas()
        
        assert isinstance(schemas, list)


class TestMemoryIntegration:
    """记忆管理整合测试"""
    
    def test_memory_manager_import(self):
        """测试记忆管理器导入"""
        from app.integrations.tools_memory import MemoryManager
        
        manager = MemoryManager()
        
        assert manager is not None
    
    def test_conversation_memory(self):
        """测试对话记忆"""
        from app.integrations.tools_memory import ConversationMemory, MemoryManager
        
        memory = ConversationMemory(
            session_id="test-session",
            memory_manager=MemoryManager(),
        )
        
        assert memory is not None
