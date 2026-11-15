"""
修改密码测试。

核心是**改完密码后旧 token 必须失效**。原来的系统根本没有改密码接口，
而 token 是无状态 JWT、有效期 7 天 —— 意味着账号被盗后改密码也踢不掉人。
"""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import create_token, get_password_hash, verify_password
from app.models.user import User
from app.services.password_policy import validate_password

OLD = "OldPass123!"
NEW = "NewStrong456!"


async def _login(client: AsyncClient, email: str, password: str) -> str:
    resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


class TestPasswordPolicy:
    """注册与改密码共用的强度规则。"""

    @pytest.mark.parametrize("bad", [
        "short", "1234567", "12345678", "password", "admin123",
        "aaaaaaaa", "11111111", "",
    ])
    def test_rejects(self, bad):
        with pytest.raises(ValueError):
            validate_password(bad)

    @pytest.mark.parametrize("good", [
        "Str0ng-Pass!", "correct horse battery", "abcd1234EFGH",
        "这是一段足够长的中文密码测试",
    ])
    def test_accepts(self, good):
        assert validate_password(good) == good.strip()

    def test_strips_surrounding_space(self):
        """首尾空格不该算进密码强度，也不该存进库。"""
        assert validate_password("  abcdefg1  ") == "abcdefg1"


class TestRegisterEnforcesPolicy:
    """注册侧也要拦弱密码。

    只给改密码加校验的话，会出现「注册能设 1 位密码、改的时候反而被拒」。
    """

    @pytest.mark.asyncio
    async def test_rejects_weak_password(self, async_client: AsyncClient):
        resp = await async_client.post(
            "/api/v1/auth/register",
            json={"email": f"weak-{uuid.uuid4().hex[:6]}@test.com", "password": "123"},
        )
        assert resp.status_code == 400
        assert "密码" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_accepts_strong_password(
        self, async_client: AsyncClient, async_db: AsyncSession
    ):
        email = f"ok-{uuid.uuid4().hex[:6]}@test.com"
        resp = await async_client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "Str0ng-Pass!"},
        )
        assert resp.status_code == 200, resp.text

        user = await async_db.scalar(select(User).where(User.email == email))
        assert verify_password("Str0ng-Pass!", user.password_hash)


class TestChangePassword:
    @pytest.mark.asyncio
    async def test_changes_hash(
        self, async_client: AsyncClient, async_db: AsyncSession, auth_headers: dict,
        test_user: User,
    ):
        resp = await async_client.post(
            "/api/v1/auth/change-password",
            json={"old_password": "testpassword", "new_password": NEW},
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text

        await async_db.refresh(test_user)
        assert verify_password(NEW, test_user.password_hash)
        assert not verify_password("testpassword", test_user.password_hash)

    @pytest.mark.asyncio
    async def test_rejects_wrong_old_password(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        resp = await async_client.post(
            "/api/v1/auth/change-password",
            json={"old_password": "not-my-password", "new_password": NEW},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "当前密码不正确" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_rejects_same_password(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        resp = await async_client.post(
            "/api/v1/auth/change-password",
            json={"old_password": "testpassword", "new_password": "testpassword"},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "相同" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_rejects_weak_new_password(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        resp = await async_client.post(
            "/api/v1/auth/change-password",
            json={"old_password": "testpassword", "new_password": "123"},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "密码" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_requires_authentication(self, async_client: AsyncClient):
        resp = await async_client.post(
            "/api/v1/auth/change-password",
            json={"old_password": "x", "new_password": "y"},
        )
        assert resp.status_code == 401


class TestPasswordChangeInvalidatesTokens:
    """改密后旧 token 失效 —— 这个功能存在的全部理由。"""

    @pytest.mark.asyncio
    async def test_old_token_stops_working(
        self, async_client: AsyncClient, test_user: User
    ):
        token = await _login(async_client, test_user.email, "testpassword")

        # 改密前能用
        assert (await async_client.get(
            "/api/v1/users/me", headers={"Authorization": f"Bearer {token}"}
        )).status_code == 200

        changed = await async_client.post(
            "/api/v1/auth/change-password",
            json={"old_password": "testpassword", "new_password": NEW},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert changed.status_code == 200

        # 同一个 token 再用来就必须被拒
        after = await async_client.get(
            "/api/v1/users/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert after.status_code == 401, "改密后旧 token 仍然可用"

    @pytest.mark.asyncio
    async def test_new_login_gets_working_token(
        self, async_client: AsyncClient, test_user: User
    ):
        """改完用新密码重新登录，必须能正常用。

        少了这条，用户改完密码就被锁死了 —— 那是最糟的结果。
        """
        token = await _login(async_client, test_user.email, "testpassword")
        await async_client.post(
            "/api/v1/auth/change-password",
            json={"old_password": "testpassword", "new_password": NEW},
            headers={"Authorization": f"Bearer {token}"},
        )

        new_token = await _login(async_client, test_user.email, NEW)
        resp = await async_client.get(
            "/api/v1/users/me", headers={"Authorization": f"Bearer {new_token}"}
        )
        assert resp.status_code == 200, resp.text

    @pytest.mark.asyncio
    async def test_old_password_cannot_login(
        self, async_client: AsyncClient, test_user: User
    ):
        token = await _login(async_client, test_user.email, "testpassword")
        await async_client.post(
            "/api/v1/auth/change-password",
            json={"old_password": "testpassword", "new_password": NEW},
            headers={"Authorization": f"Bearer {token}"},
        )

        resp = await async_client.post(
            "/api/v1/auth/login",
            json={"email": test_user.email, "password": "testpassword"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_token_issued_before_any_change_still_works(
        self, async_client: AsyncClient, test_user: User
    ):
        """从未改过密码的用户，老 token 必须照常能用。

        否则这次部署升级会把所有在线用户一次性踢下线。
        """
        token = await _login(async_client, test_user.email, "testpassword")
        assert (await async_client.get(
            "/api/v1/users/me", headers={"Authorization": f"Bearer {token}"}
        )).status_code == 200


class TestTokenPwdClaim:
    """pwd_ts 声明本身的语义。"""

    def test_absent_when_never_changed(self):
        token = create_token("uid-1", None)
        from jose import jwt
        from app.core.config import settings

        payload = jwt.decode(token, settings.JWT_SECRET_KEY,
                             algorithms=[settings.JWT_ALGORITHM])
        assert "pwd_ts" not in payload

    def test_present_when_changed(self):
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        token = create_token("uid-1", now)
        from jose import jwt
        from app.core.config import settings

        payload = jwt.decode(token, settings.JWT_SECRET_KEY,
                             algorithms=[settings.JWT_ALGORITHM])
        assert payload["pwd_ts"] == pytest.approx(now.timestamp(), abs=2)

    def test_naive_datetime_is_handled(self):
        """库里读出来的 DateTime 可能没有 tzinfo，不能因此 500。"""
        from datetime import datetime

        token = create_token("uid-1", datetime(2026, 10, 13, 9, 0, 0))
        from jose import jwt
        from app.core.config import settings

        payload = jwt.decode(token, settings.JWT_SECRET_KEY,
                             algorithms=[settings.JWT_ALGORITHM])
        assert payload["pwd_ts"] > 0
