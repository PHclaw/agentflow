"""
测试 billing API
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


class TestBillingAPI:
    """Billing API 测试"""
    
    @pytest.mark.asyncio
    async def test_list_plans(
        self,
        async_client: AsyncClient,
    ):
        """测试获取定价计划列表"""
        response = await async_client.get("/api/billing/plans")
        assert response.status_code == 200
        data = response.json()
        assert "plans" in data
        assert len(data["plans"]) >= 3  # free, pro, team
        
        # 验证计划结构
        for plan in data["plans"]:
            assert "id" in plan
            assert "name" in plan
            assert "price" in plan
            assert "features" in plan
    
    @pytest.mark.asyncio
    async def test_get_plan_details(
        self,
        async_client: AsyncClient,
    ):
        """测试获取单个计划详情"""
        response = await async_client.get("/api/billing/plans/free")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "free"
        assert data["name"] == "Free"
        assert data["price"] == 0
    
    @pytest.mark.asyncio
    async def test_get_subscription_status_unauthenticated(
        self,
        async_client: AsyncClient,
    ):
        """测试未认证用户订阅状态"""
        response = await async_client.get("/api/billing/subscription")
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_get_subscription_status(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        """测试获取订阅状态"""
        response = await async_client.get(
            "/api/billing/subscription",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        # 新用户默认 free 计划
        assert "plan" in data
        assert data["plan"] in ["free", "pro", "team"]
    
    @pytest.mark.asyncio
    async def test_create_checkout_unauthenticated(
        self,
        async_client: AsyncClient,
    ):
        """测试未认证用户创建支付会话"""
        response = await async_client.post(
            "/api/billing/create-checkout-session",
            json={
                "price_id": "price_test",
                "success_url": "http://localhost/success",
                "cancel_url": "http://localhost/cancel",
            },
        )
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_create_portal_unauthenticated(
        self,
        async_client: AsyncClient,
    ):
        """测试未认证用户创建管理门户"""
        response = await async_client.post(
            "/api/billing/create-portal-session",
            json={
                "return_url": "http://localhost/account",
            },
        )
        assert response.status_code == 401
