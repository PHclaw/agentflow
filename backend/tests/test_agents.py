"""
测试 agents API
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.user import User
from ..models.agent import Agent


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
