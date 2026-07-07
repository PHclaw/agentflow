"""
测试 chat API
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.agent import Agent


class TestChatAPI:
    """Chat API 测试"""

    @pytest.mark.asyncio
    async def test_chat_unauthenticated(
        self,
        async_client: AsyncClient,
        test_agent: Agent,
    ):
        """测试未认证访问"""
        response = await async_client.post(
            f"/api/v1/chat/{test_agent.id}",
            json={"message": "Hello"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_chat_with_tools_unauthenticated(
        self,
        async_client: AsyncClient,
        test_agent: Agent,
    ):
        """测试未认证访问 with-tools 端点"""
        response = await async_client.post(
            f"/api/v1/chat/{test_agent.id}/with-tools",
            json={"message": "Hello"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_multi_agent_chat_unauthenticated(
        self,
        async_client: AsyncClient,
    ):
        """测试未认证访问 multi-agent 端点"""
        response = await async_client.post(
            "/api/v1/chat/multi-agent",
            json={"message": "Hello", "agent_ids": ["agent-1"]},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_multi_agent_chat_missing_agent_ids(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        """测试缺少 agent_ids"""
        response = await async_client.post(
            "/api/v1/chat/multi-agent",
            headers=auth_headers,
            json={"message": "Hello", "agent_ids": []},
        )
        # 404 because the route expects a specific path, validation happens after
        assert response.status_code in [400, 404, 422]

    @pytest.mark.asyncio
    async def test_get_stats_unauthenticated(
        self,
        async_client: AsyncClient,
        test_agent: Agent,
    ):
        """测试未认证访问 stats 端点"""
        response = await async_client.get(f"/api/v1/chat/{test_agent.id}/stats")
        assert response.status_code == 401

    @pytest.mark.asyncio
    @patch("app.api.chat.IntegratedAgentRuntime")
    async def test_chat_success(
        self,
        mock_runtime_class,
        async_client: AsyncClient,
        auth_headers: dict,
        test_agent: Agent,
    ):
        """测试对话成功（mock runtime）"""
        # Mock runtime
        mock_runtime = AsyncMock()
        mock_runtime.initialize = AsyncMock()
        mock_runtime.chat = AsyncMock(return_value="Hello! How can I help you?")
        mock_runtime.get_stats = AsyncMock(return_value={"messages": 1})
        mock_runtime.session = MagicMock()
        mock_runtime.session.id = "session-123"
        mock_runtime_class.return_value = mock_runtime

        response = await async_client.post(
            f"/api/v1/chat/{test_agent.id}",
            headers=auth_headers,
            json={"message": "Hello"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["response"] == "Hello! How can I help you?"
        assert data["session_id"] == "session-123"

    @pytest.mark.asyncio
    @patch("app.api.chat.IntegratedAgentRuntime")
    async def test_chat_with_tools_success(
        self,
        mock_runtime_class,
        async_client: AsyncClient,
        auth_headers: dict,
        test_agent: Agent,
    ):
        """测试带工具对话成功"""
        mock_runtime = AsyncMock()
        mock_runtime.initialize = AsyncMock()
        mock_runtime.chat_with_tools = AsyncMock(return_value="Tool result")
        mock_runtime.get_stats = AsyncMock(return_value={"messages": 1})
        mock_runtime.session = MagicMock()
        mock_runtime.session.id = "session-456"
        mock_runtime_class.return_value = mock_runtime

        response = await async_client.post(
            f"/api/v1/chat/{test_agent.id}/with-tools",
            headers=auth_headers,
            json={"message": "Search for X"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["response"] == "Tool result"

    @pytest.mark.asyncio
    @patch("app.api.chat.IntegratedAgentRuntime")
    async def test_multi_agent_chat_success(
        self,
        mock_runtime_class,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        """测试多 Agent 对话成功"""
        mock_runtime = AsyncMock()
        mock_runtime.initialize = AsyncMock()
        mock_runtime.multi_agent_chat = AsyncMock(
            return_value={"agent-1": "Response 1", "agent-2": "Response 2"}
        )
        mock_runtime.session = MagicMock()
        mock_runtime.session.id = "session-789"
        mock_runtime_class.return_value = mock_runtime

        response = await async_client.post(
            "/api/v1/chat/multi-agent",
            headers=auth_headers,
            json={"message": "Hello all", "agent_ids": ["agent-1", "agent-2"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert data["results"]["agent-1"] == "Response 1"

    @pytest.mark.asyncio
    @patch("app.api.chat.IntegratedAgentRuntime")
    async def test_get_stats_success(
        self,
        mock_runtime_class,
        async_client: AsyncClient,
        auth_headers: dict,
        test_agent: Agent,
    ):
        """测试获取统计成功"""
        mock_runtime = AsyncMock()
        mock_runtime.initialize = AsyncMock()
        mock_runtime.get_stats = AsyncMock(
            return_value={"messages": 10, "sessions": 2}
        )
        mock_runtime_class.return_value = mock_runtime

        response = await async_client.get(
            f"/api/v1/chat/{test_agent.id}/stats",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["messages"] == 10
        assert data["sessions"] == 2

    @pytest.mark.asyncio
    @patch("app.api.chat.IntegratedAgentRuntime")
    async def test_chat_agent_not_found(
        self,
        mock_runtime_class,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        """测试 Agent 不存在"""
        mock_runtime = AsyncMock()
        mock_runtime.initialize = AsyncMock(
            side_effect=ValueError("Agent not found")
        )
        mock_runtime_class.return_value = mock_runtime

        response = await async_client.post(
            "/api/v1/chat/nonexistent-agent",
            headers=auth_headers,
            json={"message": "Hello"},
        )
        assert response.status_code == 404
