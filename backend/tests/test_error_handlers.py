"""
测试全局异常处理器的响应格式

回归点：曾经的 exception_handler(404) 会把所有业务 404 的 detail
替换为「Route xxx not found」，导致前端拿不到真正的失败原因。
"""
import pytest


class TestHttpExceptionHandler:
    """HTTPException 的 detail 必须原样透出"""

    @pytest.mark.asyncio
    async def test_business_404_keeps_detail(
        self, async_client, test_knowledge_base, auth_headers
    ):
        response = await async_client.get(
            f"/api/v1/knowledge/{test_knowledge_base.id}/documents/999999/download",
            headers=auth_headers,
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "文档不存在"

    @pytest.mark.asyncio
    async def test_unknown_route_returns_generic_detail(self, async_client):
        response = await async_client.get("/api/v1/definitely-not-a-route")

        assert response.status_code == 404
        assert "不存在" in response.json()["detail"]
        assert response.json()["path"] == "/api/v1/definitely-not-a-route"

    @pytest.mark.asyncio
    async def test_401_keeps_detail(self, async_client):
        response = await async_client.get("/api/v1/users/me")

        assert response.status_code == 401
        assert "detail" in response.json()

    @pytest.mark.asyncio
    async def test_400_keeps_detail(self, async_client, test_user):
        response = await async_client.post(
            "/api/v1/auth/register",
            json={"email": test_user.email, "password": "whatever"},
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "该邮箱已被注册"
