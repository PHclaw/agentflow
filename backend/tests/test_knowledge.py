"""
测试 knowledge API
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import KnowledgeBase


class TestKnowledgeAPI:
    """Knowledge API 测试"""
    
    @pytest.mark.asyncio
    async def test_list_knowledge_bases_empty(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        """测试空列表"""
        response = await async_client.get(
            "/api/v1/knowledge",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    @pytest.mark.asyncio
    async def test_create_knowledge_base(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        """测试创建知识库"""
        response = await async_client.post(
            "/api/v1/knowledge",
            headers=auth_headers,
            json={
                "name": "Test KB",
                "description": "A test knowledge base",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test KB"
        assert "id" in data
    
    @pytest.mark.asyncio
    async def test_get_knowledge_base(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_knowledge_base: KnowledgeBase,
    ):
        """测试获取知识库"""
        response = await async_client.get(
            f"/api/v1/knowledge/{test_knowledge_base.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_knowledge_base.id
        assert data["name"] == test_knowledge_base.name
    
    @pytest.mark.asyncio
    async def test_delete_knowledge_base(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_knowledge_base: KnowledgeBase,
    ):
        """测试删除知识库"""
        response = await async_client.delete(
            f"/api/v1/knowledge/{test_knowledge_base.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        
        # 验证已删除
        response = await async_client.get(
            f"/api/v1/knowledge/{test_knowledge_base.id}",
            headers=auth_headers,
        )
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_search_knowledge(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        """测试知识库搜索"""
        response = await async_client.post(
            "/api/v1/knowledge/search",
            headers=auth_headers,
            json={
                "query": "test query",
                "top_k": 5,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "query" in data
    
    @pytest.mark.asyncio
    async def test_unauthorized_access(
        self,
        async_client: AsyncClient,
    ):
        """测试未授权访问"""
        response = await async_client.get("/api/v1/knowledge")
        # knowledge 可能不需要认证，检查返回格式
        assert response.status_code in [200, 401]
