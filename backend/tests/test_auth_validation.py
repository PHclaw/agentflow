"""
测试认证接口的入参校验

回归点：RegisterRequest / LoginRequest 的 email 曾声明为 str，
任意字符串（如 "not-an-email"）都能通过校验并注册成功。
"""
import pytest


class TestEmailValidation:
    """邮箱格式必须被校验"""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "bad_email",
        ["not-an-email", "missing-at.com", "trailing@", "@no-local.com", ""],
    )
    async def test_register_rejects_invalid_email(self, async_client, bad_email):
        response = await async_client.post(
            "/api/v1/auth/register",
            json={"email": bad_email, "password": "Smoke@12345"},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_accepts_valid_email(self, async_client):
        response = await async_client.post(
            "/api/v1/auth/register",
            json={"email": "brand.new@example.com", "password": "Smoke@12345"},
        )

        assert response.status_code == 200
        assert response.json()["user"]["email"] == "brand.new@example.com"

    @pytest.mark.asyncio
    async def test_login_rejects_invalid_email(self, async_client):
        response = await async_client.post(
            "/api/v1/auth/login",
            json={"email": "not-an-email", "password": "whatever"},
        )

        assert response.status_code == 422
