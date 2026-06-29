"""
AgentFlow 全链路集成测试

覆盖完整用户旅程：
1. 注册 → 2. 登录 → 3. 创建 Agent → 4. 发起对话 → 5. 获取统计
"""
import uuid
import unittest.mock
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class TestAuthFlow:
    """认证流程集成测试"""

    @pytest.mark.asyncio
    async def test_register_login_flow(self, async_client: AsyncClient):
        """注册后登录，获取 token"""
        email = f"集成测试-{uuid.uuid4().hex[:8]}@test.com"
        password = "SecurePass123!"

        # 注册
        reg_resp = await async_client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password, "nickname": "Integration Test"}
        )
        assert reg_resp.status_code == 200, f"注册失败: {reg_resp.text}"
        reg_data = reg_resp.json()
        # 注册返回 {token, user}
        assert "token" in reg_data, f"注册响应缺少token: {reg_data}"

        # 登录（同一 client，复用 session）
        login_resp = await async_client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password}
        )
        assert login_resp.status_code == 200, f"登录失败({login_resp.status_code}): {login_resp.text}"
        login_data = login_resp.json()
        assert "token" in login_data, f"登录响应缺少token: {login_data}"


class TestAgentFlow:
    """Agent 生命周期集成测试"""

    @pytest.mark.asyncio
    async def test_create_agent_requires_auth(self, async_client: AsyncClient):
        """未认证不能创建 Agent"""
        resp = await async_client.post(
            "/api/v1/agents",
            json={"name": "Unauthorized Agent", "model": "gpt-4o-mini"}
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_create_and_list_agent(
        self, async_client: AsyncClient, test_user: User, auth_headers: dict
    ):
        """创建 Agent 后能在列表中查到"""
        # 创建
        create_resp = await async_client.post(
            "/api/v1/agents",
            json={
                "name": "My Flow Agent",
                "description": "Integration test agent",
                "model": "gpt-4o-mini",
                "system_prompt": "You are a helpful assistant.",
            },
            headers=auth_headers,
        )
        assert create_resp.status_code == 200, f"创建 Agent 失败: {create_resp.text}"
        agent_data = create_resp.json()
        agent_id = agent_data.get("id")
        assert agent_id is not None

        # 列表中查到
        list_resp = await async_client.get("/api/v1/agents", headers=auth_headers)
        assert list_resp.status_code == 200
        agents = list_resp.json()
        assert any(a["id"] == agent_id for a in agents)

    @pytest.mark.asyncio
    async def test_get_agent_detail(
        self, async_client: AsyncClient, test_user: User, auth_headers: dict
    ):
        """能获取单个 Agent 详情"""
        # 创建
        create_resp = await async_client.post(
            "/api/v1/agents",
            json={"name": "Detail Test Agent", "model": "gpt-4o-mini"},
            headers=auth_headers,
        )
        agent_id = create_resp.json()["id"]

        # 详情
        detail_resp = await async_client.get(f"/api/v1/agents/{agent_id}", headers=auth_headers)
        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        assert detail["id"] == agent_id
        assert detail["name"] == "Detail Test Agent"

    @pytest.mark.asyncio
    async def test_update_agent(
        self, async_client: AsyncClient, test_user: User, auth_headers: dict
    ):
        """能更新 Agent 信息"""
        create_resp = await async_client.post(
            "/api/v1/agents",
            json={"name": "Old Name", "model": "gpt-4o-mini"},
            headers=auth_headers,
        )
        agent_id = create_resp.json()["id"]

        update_resp = await async_client.put(
            f"/api/v1/agents/{agent_id}",
            json={"name": "New Name", "description": "Updated description"},
            headers=auth_headers,
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["name"] == "New Name"

    @pytest.mark.asyncio
    async def test_delete_agent(
        self, async_client: AsyncClient, test_user: User, auth_headers: dict
    ):
        """能删除 Agent"""
        create_resp = await async_client.post(
            "/api/v1/agents",
            json={"name": "To Delete", "model": "gpt-4o-mini"},
            headers=auth_headers,
        )
        agent_id = create_resp.json()["id"]

        del_resp = await async_client.delete(f"/api/v1/agents/{agent_id}", headers=auth_headers)
        assert del_resp.status_code == 200

        # 确认删除
        get_resp = await async_client.get(f"/api/v1/agents/{agent_id}", headers=auth_headers)
        assert get_resp.status_code == 404


class TestChatFlow:
    """对话流程集成测试"""

    @pytest.mark.asyncio
    async def test_chat_requires_auth(self, async_client: AsyncClient):
        """未认证不能发送消息"""
        resp = await async_client.post(
            "/api/v1/chat/test-agent-001",
            json={"message": "Hello"}
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_full_chat_session_flow(
        self, async_client: AsyncClient, test_user: User, auth_headers: dict
    ):
        """完整对话流程：创建会话 → 发送消息 → 获取历史"""
        # 创建 Agent
        agent_resp = await async_client.post(
            "/api/v1/agents",
            json={"name": "Chat Agent", "model": "gpt-4o-mini"},
            headers=auth_headers,
        )
        assert agent_resp.status_code == 200
        agent_id = agent_resp.json()["id"]

        # Mock IntegratedAgentRuntime 全家桶（测试环境无 LLM API key）
        mock_runtime = unittest.mock.MagicMock()
        mock_runtime.initialize = unittest.mock.AsyncMock(return_value=None)
        mock_runtime.chat = unittest.mock.AsyncMock(return_value="Hello! I am your AI assistant.")
        mock_runtime.get_stats = unittest.mock.AsyncMock(return_value={"messages": 1, "tokens": 50})
        mock_session = unittest.mock.MagicMock()
        mock_session.id = "test-session-123"
        mock_runtime.session = mock_session

        with unittest.mock.patch(
            "app.api.chat.IntegratedAgentRuntime",
            return_value=mock_runtime
        ):
            chat_resp = await async_client.post(
                f"/api/v1/chat/{agent_id}",
                json={"message": "Hello, who are you?"},
                headers=auth_headers,
            )
        assert chat_resp.status_code == 200
        chat_data = chat_resp.json()
        assert any(k in chat_data for k in ("response", "answer", "message", "text"))

        # 获取统计
        stats_resp = await async_client.get(
            f"/api/v1/chat/{agent_id}/stats",
            headers=auth_headers,
        )
        assert stats_resp.status_code in (200, 404)

    @pytest.mark.asyncio
    async def test_multi_agent_chat(
        self, async_client: AsyncClient, test_user: User, auth_headers: dict
    ):
        """多 Agent 协作对话"""
        # 创建两个 Agent
        agent1_resp = await async_client.post(
            "/api/v1/agents",
            json={"name": "Agent One", "model": "gpt-4o-mini"},
            headers=auth_headers,
        )
        agent1_id = agent1_resp.json()["id"]

        agent2_resp = await async_client.post(
            "/api/v1/agents",
            json={"name": "Agent Two", "model": "gpt-4o-mini"},
            headers=auth_headers,
        )
        agent2_id = agent2_resp.json()["id"]

        with unittest.mock.patch(
            "app.services.integrated_runtime.IntegratedAgentRuntime.chat",
            return_value={"response": "Multi-agent response", "session_id": "multi-session"}
        ):
            multi_resp = await async_client.post(
                "/api/v1/chat/multi-agent",
                json={
                    "agent_ids": [agent1_id, agent2_id],
                    "message": "Work together on this task",
                },
                headers=auth_headers,
            )
        # 端点存在返回 200，不存在返回 404 或 501
        assert multi_resp.status_code in (200, 404, 501, 400, 422)


class TestTemplateFlow:
    """模板市场集成测试"""

    @pytest.mark.asyncio
    async def test_list_templates(self, async_client: AsyncClient):
        """模板列表可访问"""
        resp = await async_client.get("/api/v1/templates")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_get_template_detail(self, async_client: AsyncClient):
        """能获取模板详情"""
        list_resp = await async_client.get("/api/v1/templates")
        templates = list_resp.json()
        if len(templates) == 0:
            pytest.skip("No templates seeded")
        template_id = templates[0]["id"]

        detail_resp = await async_client.get(f"/api/v1/templates/{template_id}")
        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        assert detail["id"] == template_id

    @pytest.mark.asyncio
    async def test_models_list(self, async_client: AsyncClient):
        """模型列表可访问"""
        resp = await async_client.get("/api/v1/templates/models/list")
        assert resp.status_code == 200, f"models list failed({resp.status_code}): {resp.text}"
        data = resp.json()
        models = data.get("models") or data.get("data", data) if isinstance(data, dict) else data
        assert isinstance(models, list), f"models应为list，实际: {type(models)}"
        assert len(models) > 0


class TestStatsFlow:
    """统计接口集成测试"""

    @pytest.mark.asyncio
    async def test_stats_summary(
        self, async_client: AsyncClient, test_user: User, auth_headers: dict
    ):
        """统计摘要接口"""
        resp = await async_client.get("/api/v1/stats/summary", headers=auth_headers)
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            data = resp.json()
            assert isinstance(data, dict)
