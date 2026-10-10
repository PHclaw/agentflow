"""
测试 agents API
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.agent import Agent


class TestAgentsAPI:
    """Agent API 测试"""
    
    @pytest.mark.asyncio
    async def test_list_agents_empty(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        """测试空列表"""
        response = await async_client.get(
            "/api/v1/agents",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0
    
    @pytest.mark.asyncio
    async def test_create_agent(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        """测试创建 Agent"""
        response = await async_client.post(
            "/api/v1/agents",
            headers=auth_headers,
            json={
                "name": "Test Agent",
                "description": "A test agent",
                "model_config": {
                    "provider": "openai",
                    "model": "gpt-4o-mini",
                    "temperature": 0.7,
                },
                "workflow_definition": {
                    "nodes": [
                        {"id": "start", "type": "start"},
                        {"id": "end", "type": "output"},
                    ],
                    "edges": [
                        {"from": "start", "to": "end"},
                    ],
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Agent"
        assert data["description"] == "A test agent"
        assert "id" in data
    
    @pytest.mark.asyncio
    async def test_get_agent(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_agent: Agent,
    ):
        """测试获取 Agent"""
        response = await async_client.get(
            f"/api/v1/agents/{test_agent.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_agent.id
        assert data["name"] == test_agent.name
    
    @pytest.mark.asyncio
    async def test_update_agent(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_agent: Agent,
    ):
        """测试更新 Agent"""
        response = await async_client.put(
            f"/api/v1/agents/{test_agent.id}",
            headers=auth_headers,
            json={
                "name": "Updated Agent",
                "description": "Updated description",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Agent"
    
    @pytest.mark.asyncio
    async def test_delete_agent(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_agent: Agent,
    ):
        """测试删除 Agent"""
        response = await async_client.delete(
            f"/api/v1/agents/{test_agent.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        
        # 验证已删除
        response = await async_client.get(
            f"/api/v1/agents/{test_agent.id}",
            headers=auth_headers,
        )
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_unauthorized_access(
        self,
        async_client: AsyncClient,
    ):
        """测试未授权访问"""
        response = await async_client.get("/api/v1/agents")
        assert response.status_code == 401


class TestWorkflowDefinitionRoundTrip:
    """工作流定义必须能原样存取

    这里曾经出过两个静默故障，都不报错、只会让用户以为工作流「自己消失了」：
    1. WorkflowNode 只声明 {id, type, config}，pydantic 忽略未声明字段，
       把前端传来的 data / position 整块丢弃 -> 保存后节点配置全空
    2. _agent_to_dict 不返回 workflow_definition -> 编辑器每次加载都是空画布
    """

    async def _create_agent(self, async_client: AsyncClient, auth_headers: dict) -> str:
        resp = await async_client.post(
            "/api/v1/agents",
            headers=auth_headers,
            json={"name": "工作流测试", "description": ""},
        )
        assert resp.status_code == 200
        return resp.json()["id"]

    @pytest.mark.asyncio
    async def test_put_then_get_keeps_node_data_and_position(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        """保存后读回，节点配置与坐标不能丢"""
        agent_id = await self._create_agent(async_client, auth_headers)

        definition = {
            "nodes": [
                {
                    "id": "t1",
                    "type": "trigger",
                    "position": {"x": 1, "y": 2},
                    "data": {"trigger_type": "message", "label": "开始"},
                },
                {
                    "id": "l1",
                    "type": "llm",
                    "position": {"x": 3, "y": 4},
                    "data": {"model": "gpt-4o-mini", "prompt": "{{user_message}}"},
                },
            ],
            "edges": [{"source": "t1", "target": "l1", "sourceHandle": "out"}],
        }

        put = await async_client.put(
            f"/api/v1/agents/{agent_id}",
            headers=auth_headers,
            json={"workflow_definition": definition},
        )
        assert put.status_code == 200

        got = await async_client.get(f"/api/v1/agents/{agent_id}", headers=auth_headers)
        assert got.status_code == 200
        wf = got.json()["workflow_definition"]

        assert [n["id"] for n in wf["nodes"]] == ["t1", "l1"]
        assert wf["nodes"][0]["data"]["trigger_type"] == "message"
        assert wf["nodes"][1]["data"]["prompt"] == "{{user_message}}"
        assert wf["nodes"][1]["position"] == {"x": 3, "y": 4}
        # sourceHandle 决定条件节点走哪个分支，同样不能丢
        assert wf["edges"][0]["sourceHandle"] == "out"

    @pytest.mark.asyncio
    async def test_get_always_returns_workflow_definition_field(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        """即使没配置过工作流，也要返回该字段，编辑器才能安全回填"""
        agent_id = await self._create_agent(async_client, auth_headers)

        got = await async_client.get(f"/api/v1/agents/{agent_id}", headers=auth_headers)

        assert got.status_code == 200
        assert "workflow_definition" in got.json()
