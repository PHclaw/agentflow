"""
测试 chat API
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4
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


class TestWorkflowBackedChat:
    """配置了工作流的 Agent：对话应按画布编排执行

    这里统一用 trigger -> response 这种不含 LLM 的编排，
    让整条链路可以脱离模型密钥被完整验证。
    """

    async def _make_agent(
        self,
        async_db: AsyncSession,
        test_user: User,
        definition: dict,
    ) -> Agent:
        agent = Agent(
            id=f"wf-agent-{uuid4().hex[:8]}",
            user_id=test_user.external_id,
            name="工作流 Agent",
            description="",
            model_config={"model": "gpt-4o-mini", "temperature": 0.7},
            workflow_definition=definition,
        )
        async_db.add(agent)
        await async_db.commit()
        await async_db.refresh(agent)
        return agent

    @pytest.mark.asyncio
    async def test_response_node_output_becomes_reply(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        async_db: AsyncSession,
        test_user: User,
    ):
        """回复取自 response 节点，且不再走 IntegratedAgentRuntime"""
        agent = await self._make_agent(
            async_db,
            test_user,
            {
                "nodes": [
                    {"id": "t1", "type": "trigger", "data": {"trigger_type": "message"}},
                    {"id": "r1", "type": "response", "data": {"response": "来自工作流的回复"}},
                ],
                "edges": [{"source": "t1", "target": "r1"}],
            },
        )

        response = await async_client.post(
            f"/api/v1/chat/{agent.id}",
            headers=auth_headers,
            json={"message": "你好"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["response"] == "来自工作流的回复"
        assert body["stats"]["engine"] == "workflow"

    @pytest.mark.asyncio
    async def test_template_style_definition_is_normalized(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        async_db: AsyncSession,
        test_user: User,
    ):
        """预置模板的写法（start/output + config + from/to）也要能跑

        项目里的模板用的正是这套写法，不归一化的话节点类型未知、
        配置为空、边上没有 source/target。
        """
        agent = await self._make_agent(
            async_db,
            test_user,
            {
                "nodes": [
                    {"id": "start", "type": "start", "label": "用户输入"},
                    {
                        "id": "end",
                        "type": "output",
                        "label": "回复用户",
                        "config": {"response": "模板写法的回复"},
                    },
                ],
                "edges": [{"from": "start", "to": "end"}],
            },
        )

        response = await async_client.post(
            f"/api/v1/chat/{agent.id}",
            headers=auth_headers,
            json={"message": "你好"},
        )

        assert response.status_code == 200
        assert response.json()["response"] == "模板写法的回复"

    @pytest.mark.asyncio
    async def test_turn_is_recorded_in_history(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        async_db: AsyncSession,
        test_user: User,
    ):
        """工作流对话也要写进会话历史，否则对话页刷新后就空了"""
        agent = await self._make_agent(
            async_db,
            test_user,
            {
                "nodes": [
                    {"id": "t1", "type": "trigger", "data": {"trigger_type": "message"}},
                    {"id": "r1", "type": "response", "data": {"response": "记住了"}},
                ],
                "edges": [{"source": "t1", "target": "r1"}],
            },
        )

        await async_client.post(
            f"/api/v1/chat/{agent.id}",
            headers=auth_headers,
            json={"message": "你好"},
        )

        history = await async_client.get(
            f"/api/v1/chat/{agent.id}/history",
            headers=auth_headers,
        )
        assert history.status_code == 200
        messages = history.json()["messages"]
        assert [m["role"] for m in messages] == ["user", "assistant"]
        assert messages[0]["content"] == "你好"
        assert messages[1]["content"] == "记住了"

    @pytest.mark.asyncio
    async def test_streaming_emits_session_chunks_and_done(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        async_db: AsyncSession,
        test_user: User,
    ):
        """流式对话要发 session / chunk / done 三类事件"""
        agent = await self._make_agent(
            async_db,
            test_user,
            {
                "nodes": [
                    {"id": "t1", "type": "trigger", "data": {"trigger_type": "message"}},
                    {"id": "r1", "type": "response", "data": {"response": "流式回复内容"}},
                ],
                "edges": [{"source": "t1", "target": "r1"}],
            },
        )

        response = await async_client.post(
            f"/api/v1/chat/{agent.id}",
            headers=auth_headers,
            json={"message": "你好", "stream": True},
        )

        assert response.status_code == 200
        text = response.text
        assert '"type": "session"' in text
        assert '"type": "chunk"' in text
        assert '"type": "done"' in text
        assert "流式回复内容" in text

    @pytest.mark.asyncio
    async def test_generated_files_are_returned_as_attachments(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        async_db: AsyncSession,
        test_user: User,
        monkeypatch,
    ):
        """智能体节点生成的产物必须作为附件返回

        工作流的回复只取文本，产物曾被整段丢弃 —— 用户看到
        「已生成会议纪要 xxx.md」却找不到文件可下载。
        """
        monkeypatch.setattr("app.core.config.settings.PIAGENT_ENABLED", True, raising=False)

        artifact = {
            "name": "会议纪要.md",
            "path": "会议纪要.md",
            "size": 2048,
            "url": "/api/v1/pi/xxx/files/会议纪要.md",
        }

        async def fake_run(message, agent_id, agent, session_id=None, skills=None, timeout=None):
            return {
                "success": True,
                "error": None,
                "content": "已生成会议纪要：会议纪要.md",
                "files": [artifact],
            }

        monkeypatch.setattr("app.services.pi_agent.pi_agent_runner.run", fake_run)

        agent = await self._make_agent(
            async_db,
            test_user,
            {
                "nodes": [
                    {"id": "t1", "type": "trigger", "data": {"trigger_type": "message"}},
                    {"id": "a1", "type": "agent", "data": {"agent_id": "self"}},
                    {"id": "r1", "type": "response", "data": {"template": "{{a1.output}}"}},
                ],
                "edges": [
                    {"source": "t1", "target": "a1"},
                    {"source": "a1", "target": "r1"},
                ],
            },
        )
        # 节点里的 agent_id 指向自己
        agent.workflow_definition["nodes"][1]["data"]["agent_id"] = agent.id
        await async_db.commit()

        response = await async_client.post(
            f"/api/v1/chat/{agent.id}",
            headers=auth_headers,
            json={"message": "整理一份会议纪要"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["files"] == [artifact]

        # 流式链路也要带上
        stream = await async_client.post(
            f"/api/v1/chat/{agent.id}",
            headers=auth_headers,
            json={"message": "整理一份会议纪要", "stream": True},
        )
        assert stream.status_code == 200
        assert '"files"' in stream.text
        assert "会议纪要.md" in stream.text

        # 历史里也要留下，否则刷新后附件就没了
        history = await async_client.get(
            f"/api/v1/chat/{agent.id}/history", headers=auth_headers
        )
        assistant_msgs = [m for m in history.json()["messages"] if m["role"] == "assistant"]
        assert assistant_msgs[-1]["files"] == [artifact]

    @pytest.mark.asyncio
    async def test_workflow_without_response_node_explains_itself(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        async_db: AsyncSession,
        test_user: User,
    ):
        """工作流没产生内容时要给出原因，而不是空白回复"""
        agent = await self._make_agent(
            async_db,
            test_user,
            {
                "nodes": [{"id": "t1", "type": "trigger", "data": {"trigger_type": "message"}}],
                "edges": [],
            },
        )

        response = await async_client.post(
            f"/api/v1/chat/{agent.id}",
            headers=auth_headers,
            json={"message": "你好"},
        )

        assert response.status_code == 200
        assert "没有产生回复内容" in response.json()["response"]
