"""
测试 auth API
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class TestAuthAPI:
    """Auth API 测试"""

    @pytest.mark.asyncio
    async def test_register_success(
        self,
        async_client: AsyncClient,
    ):
        """测试注册成功"""
        response = await async_client.post(
            "/api/v1/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "securepassword123",
                "nickname": "TestUser",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert "user" in data
        assert data["user"]["email"] == "newuser@example.com"
        assert data["user"]["nickname"] == "TestUser"

    @pytest.mark.asyncio
    async def test_register_duplicate_email(
        self,
        async_client: AsyncClient,
        test_user: User,
    ):
        """测试重复邮箱注册"""
        response = await async_client.post(
            "/api/v1/auth/register",
            json={
                "email": test_user.email,
                "password": "anotherpassword",
                "nickname": "AnotherUser",
            },
        )
        assert response.status_code == 400
        assert "已被注册" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_register_default_nickname(
        self,
        async_client: AsyncClient,
    ):
        """测试注册时不提供 nickname，使用邮箱前缀"""
        response = await async_client.post(
            "/api/v1/auth/register",
            json={
                "email": "nicknameuser@test.com",
                "password": "password123",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["user"]["nickname"] == "nicknameuser"

    @pytest.mark.asyncio
    async def test_login_success(
        self,
        async_client: AsyncClient,
        test_user: User,
    ):
        """测试登录成功"""
        response = await async_client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user.email,
                "password": "testpassword",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == test_user.email

    @pytest.mark.asyncio
    async def test_login_wrong_password(
        self,
        async_client: AsyncClient,
        test_user: User,
    ):
        """测试密码错误"""
        response = await async_client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user.email,
                "password": "wrongpassword",
            },
        )
        assert response.status_code == 401
        assert "密码错误" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_login_nonexistent_email(
        self,
        async_client: AsyncClient,
    ):
        """测试不存在的邮箱"""
        response = await async_client.post(
            "/api/v1/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "anypassword",
            },
        )
        assert response.status_code == 401
