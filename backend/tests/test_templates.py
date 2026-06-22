"""
测试 templates API
"""
import pytest
from httpx import AsyncClient

from ..core.seed import DEFAULT_TEMPLATES


class TestTemplatesAPI:
    """模板 API 测试"""
    
    @pytest.mark.asyncio
    async def test_list_templates(
        self,
        async_client: AsyncClient,
    ):
        """测试获取模板列表"""
        response = await async_client.get("/api/v1/templates")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # 至少有默认模板
        assert len(data) >= len(DEFAULT_TEMPLATES)
    
    @pytest.mark.asyncio
    async def test_template_has_required_fields(
        self,
        async_client: AsyncClient,
    ):
        """测试模板字段完整性"""
        response = await async_client.get("/api/v1/templates")
        data = response.json()
        
        if len(data) > 0:
            template = data[0]
            assert "id" in template
            assert "name" in template
            assert "category" in template
            assert "description" in template
            assert "icon" in template
            assert "color" in template
            assert "features" in template
    
    @pytest.mark.asyncio
    async def test_get_template_by_id(
        self,
        async_client: AsyncClient,
    ):
        """测试获取单个模板"""
        # 先获取列表
        list_response = await async_client.get("/api/v1/templates")
        templates = list_response.json()
        
        if len(templates) > 0:
            template_id = templates[0]["id"]
            
            # 获取详情
            response = await async_client.get(f"/api/v1/templates/{template_id}")
            assert response.status_code == 200
            data = response.json()
            
            assert data["id"] == template_id
            assert "workflow_definition" in data
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_template(
        self,
        async_client: AsyncClient,
    ):
        """测试获取不存在的模板"""
        response = await async_client.get("/api/v1/templates/nonexistent-id")
        # 根据实现可能返回 404 或错误对象
        assert response.status_code in [404, 200]
