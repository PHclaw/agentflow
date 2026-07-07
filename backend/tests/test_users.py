"""
测试 users API
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class TestUsersAPI:
    """Users API 测试"""

    @pytest.mark.asyncio
    async def test_get_me_success(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_user: User,
    ):
        """测试获取当前用户信息"""
        response = await async_client.get(
            "/api/v1/users/me",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user.email
        assert "id" in data
        assert "nickname" in data

    @pytest.mark.asyncio
    async def test_get_me_unauthenticated(
        self,
        async_client: AsyncClient,
    ):
        """测试未认证访问"""
        response = await async_client.get("/api/v1/users/me")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_me_invalid_token(
        self,
        async_client: AsyncClient,
    ):
        """测试无效 token"""
        response = await async_client.get(
            "/api/v1/users/me",
            headers={"Authorization": "Bearer invalid_token"},
        )
        assert response.status_code == 401
