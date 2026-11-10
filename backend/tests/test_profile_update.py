"""
个人资料修改测试。

背景：设置页的「个人资料」原先整页是写死的假数据（Admin User /
admin@example.com / AgentFlow Inc.），输入框用 defaultValue、保存按钮没有
onClick —— 而后端当时也只有 GET /me，没有任何写入接口。两边一起补上之后，
这些用例把契约钉住。
"""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.roles import apply_configured_role

#: 1x1 的 PNG，用来测上传
PNG_1PX = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c6300010000050001"
    "0d0a2db40000000049454e44ae426082"
)


async def _me(client: AsyncClient, headers: dict) -> dict:
    resp = await client.get("/api/v1/users/me", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


class TestProfileRead:
    @pytest.mark.asyncio
    async def test_me_includes_phone(self, async_client: AsyncClient, auth_headers: dict):
        """phone 是这次新增的可编辑字段，读接口必须一起返回。

        漏了它的话前端拿不到初始值，用户每次进设置页手机号都是空的。
        """
        body = await _me(async_client, auth_headers)
        assert "phone" in body
        assert body["email"]


class TestProfileUpdate:
    @pytest.mark.asyncio
    async def test_updates_nickname_and_trims(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """昵称首尾空格要去掉，否则库里存的是 ' 小明 '，显示时多个缩进。"""
        resp = await async_client.patch(
            "/api/v1/users/me", json={"nickname": "  小明  "}, headers=auth_headers
        )

        assert resp.status_code == 200, resp.text
        assert resp.json()["nickname"] == "小明"

    @pytest.mark.asyncio
    async def test_empty_nickname_falls_back_to_none(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """允许清空昵称（界面回退用邮箱前缀），但不该存成空串。"""
        await async_client.patch(
            "/api/v1/users/me", json={"nickname": "小明"}, headers=auth_headers
        )

        resp = await async_client.patch(
            "/api/v1/users/me", json={"nickname": "   "}, headers=auth_headers
        )

        assert resp.status_code == 200
        assert resp.json()["nickname"] is None

    @pytest.mark.asyncio
    async def test_omitted_field_is_untouched(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """只传一个字段时另一个不能被动。

        PATCH 的语义是部分更新；全量覆盖会让「改昵称」顺带清掉手机号。
        """
        await async_client.patch(
            "/api/v1/users/me",
            json={"nickname": "小明", "phone": "13800008888"},
            headers=auth_headers,
        )

        resp = await async_client.patch(
            "/api/v1/users/me", json={"nickname": "小红"}, headers=auth_headers
        )

        assert resp.json()["nickname"] == "小红"
        assert resp.json()["phone"] == "13800008888", "没传的字段被清掉了"

    @pytest.mark.asyncio
    async def test_empty_string_clears_phone(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """空串才代表「要清空」。

        ``phone=None`` 在 Pydantic 里与「不传」无法区分，会被当成不改动。
        真正要清空必须发空串 —— 这是个容易踩的坑，用例守住它。
        """
        await async_client.patch(
            "/api/v1/users/me", json={"phone": "13800008888"}, headers=auth_headers
        )

        resp = await async_client.patch(
            "/api/v1/users/me", json={"phone": ""}, headers=auth_headers
        )

        assert resp.status_code == 200
        assert resp.json()["phone"] is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize("bad", ["abc123", "123", "!!!", "1380000888812345"])
    async def test_rejects_malformed_phone(
        self, async_client: AsyncClient, auth_headers: dict, bad: str
    ):
        resp = await async_client.patch(
            "/api/v1/users/me", json={"phone": bad}, headers=auth_headers
        )
        assert resp.status_code == 400
        assert "手机号" in resp.json()["detail"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("good", [
        "13800008888",           # 大陆 11 位
        "+8613800008888",        # 带国际前缀
        "+86 138-0000-8888",     # 带分隔符
        "138 0000 8888",
        "+14155552671",          # 美国
        "+442071838750",         # 英国
        "2071838750",            # 不带前缀的 10 位
    ])
    async def test_accepts_valid_phones(
        self, async_client: AsyncClient, auth_headers: dict, good: str
    ):
        """收紧位数上限时不能把正常国际号也拒了。

        E.164 上限 15 位，这里同时覆盖大陆 / 美国 / 英国与带分隔符的写法。
        """
        resp = await async_client.patch(
            "/api/v1/users/me", json={"phone": good}, headers=auth_headers
        )
        assert resp.status_code == 200, f"{good} 被误拒"
        assert resp.json()["phone"] == good.strip()

    @pytest.mark.asyncio
    async def test_rejects_duplicate_phone(
        self, async_client: AsyncClient, async_db: AsyncSession,
        auth_headers: dict,
    ):
        """phone 是唯一索引，撞号要给一句看得懂的提示。

        不拦的话唯一约束会炸成 500，用户只看到「服务器错误」。
        """
        from app.api.auth import get_password_hash

        other = User(
            email=f"dup-{uuid.uuid4().hex[:6]}@test.com",
            password_hash=get_password_hash("x"),
            phone="13900001111",
            is_verified=True,
        )
        async_db.add(other)
        await async_db.commit()

        resp = await async_client.patch(
            "/api/v1/users/me", json={"phone": "13900001111"}, headers=auth_headers
        )

        assert resp.status_code == 409
        assert "已被其他账号使用" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_email_cannot_be_changed_here(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """邮箱不在这条接口的能力范围内。

        它是登录标识、ADMIN_EMAILS 的匹配键、验证码投递目标三者的共同依赖，
        自助修改必须配套完整流程。**请求体里多带的 email 应被直接忽略**，
        而不是静默改掉。
        """
        resp = await async_client.patch(
            "/api/v1/users/me",
            json={"nickname": "小明", "email": "attacker@evil.com"},
            headers=auth_headers,
        )

        assert resp.status_code == 200
        assert resp.json()["email"] != "attacker@evil.com"

    @pytest.mark.asyncio
    async def test_requires_authentication(self, async_client: AsyncClient):
        resp = await async_client.patch("/api/v1/users/me", json={"nickname": "x"})
        assert resp.status_code == 401


class TestAvatar:
    @pytest.mark.asyncio
    async def test_upload_returns_servable_url(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        resp = await async_client.post(
            "/api/v1/users/me/avatar",
            files={"file": ("a.png", PNG_1PX, "image/png")},
            headers=auth_headers,
        )

        assert resp.status_code == 200, resp.text
        url = resp.json()["avatar"]
        assert url.startswith("/static/avatars/")
        assert url.endswith(".png")

        # 关键：返回的地址必须真的能取到图，否则前端显示一张破图
        fetched = await async_client.get(url)
        assert fetched.status_code == 200
        assert fetched.content == PNG_1PX

    @pytest.mark.asyncio
    async def test_upload_ignores_client_filename(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """文件名必须按 UUID 重写。

        客户端给的名字可以是 ``../../app/core/config.py``，直接用就会写出
        目录之外。
        """
        resp = await async_client.post(
            "/api/v1/users/me/avatar",
            files={"file": ("../../evil.png", PNG_1PX, "image/png")},
            headers=auth_headers,
        )

        assert resp.status_code == 200
        name = resp.json()["avatar"].rsplit("/", 1)[-1]
        assert "/" not in name and "\\" not in name and ".." not in name
        assert name.endswith(".png")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("filename", ["a.php", "a.txt", "a.svg", "noext"])
    async def test_rejects_non_image_extension(
        self, async_client: AsyncClient, auth_headers: dict, filename: str
    ):
        """扩展名白名单，而不是信客户端声明的 content-type。

        SVG 尤其要拦：它能内联脚本，被当成头像渲染时就是 XSS 入口。
        """
        resp = await async_client.post(
            "/api/v1/users/me/avatar",
            files={"file": (filename, b"x", "application/octet-stream")},
            headers=auth_headers,
        )

        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_rejects_oversize(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        big = b"\x00" * (2 * 1024 * 1024 + 1)
        resp = await async_client.post(
            "/api/v1/users/me/avatar",
            files={"file": ("big.png", big, "image/png")},
            headers=auth_headers,
        )

        assert resp.status_code == 400
        assert "2MB" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_replaces_previous_avatar(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """换头像时旧文件要被清掉，否则每人换一次就留一个孤儿文件。"""
        first = await async_client.post(
            "/api/v1/users/me/avatar",
            files={"file": ("a.png", PNG_1PX, "image/png")},
            headers=auth_headers,
        )
        old_url = first.json()["avatar"]

        second = await async_client.post(
            "/api/v1/users/me/avatar",
            files={"file": ("b.png", PNG_1PX, "image/png")},
            headers=auth_headers,
        )
        new_url = second.json()["avatar"]
        assert new_url != old_url

        # 旧地址应已 404（文件删除），新地址可访问
        assert (await async_client.get(old_url)).status_code == 404
        assert (await async_client.get(new_url)).status_code == 200

    @pytest.mark.asyncio
    async def test_delete_removes_file_and_reference(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        created = await async_client.post(
            "/api/v1/users/me/avatar",
            files={"file": ("a.png", PNG_1PX, "image/png")},
            headers=auth_headers,
        )
        url = created.json()["avatar"]

        deleted = await async_client.request(
            "DELETE", "/api/v1/users/me/avatar", headers=auth_headers
        )
        assert deleted.status_code == 200
        assert deleted.json()["avatar"] is None

        # 数据库引用与文件都要清
        me = await _me(async_client, auth_headers)
        assert me["avatar"] is None
        assert (await async_client.get(url)).status_code == 404

    @pytest.mark.asyncio
    async def test_delete_without_avatar_is_noop(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """没有头像时点删除不该报错。"""
        resp = await async_client.request(
            "DELETE", "/api/v1/users/me/avatar", headers=auth_headers
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_requires_authentication(self, async_client: AsyncClient):
        resp = await async_client.post(
            "/api/v1/users/me/avatar",
            files={"file": ("a.png", PNG_1PX, "image/png")},
        )
        assert resp.status_code == 401
