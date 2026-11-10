"""注册邮箱验证码的端到端测试。

覆盖：发码、注册校验、一次性、过期、试错上限、重发冷却、每小时上限、
邮箱占用、未配置发信的处理，以及「验证码不以明文落库」这条安全断言。
"""
import json
import time

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.models.user import User
from app.services import verification

pytestmark = pytest.mark.asyncio

EMAIL = "newbie@example.com"
PASSWORD = "Str0ngPassw0rd"


@pytest.fixture(autouse=True)
def _require_email_code(_auth_email_defaults, monkeypatch):
    """本文件专门验证「必须带验证码」的流程，打开开关。

    显式依赖 conftest 的 _auth_email_defaults，保证它先跑（关掉开关、切内存后端），
    我们再覆盖成 True。monkeypatch 逆序回滚，不会互相污染。
    """
    monkeypatch.setattr(settings, "REQUIRE_EMAIL_CODE", True, raising=False)


@pytest.fixture
def outbox(monkeypatch):
    """拦截发信，拿到验证码，避免测试依赖真实 SMTP。"""
    sent: list[tuple[str, str]] = []

    async def fake_send(to: str, code: str, ttl_seconds: int, purpose: str = "register") -> bool:
        sent.append((to, code))
        return True

    monkeypatch.setattr("app.api.auth.send_verification_code", fake_send)
    return sent


async def _send_code(client: AsyncClient, email: str = EMAIL):
    return await client.post("/api/v1/auth/send-code", json={"email": email})


async def _register(client: AsyncClient, code: str, email: str = EMAIL):
    return await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD, "nickname": "新用户", "code": code},
    )


# --------------------------------------------------------------------------
# 发码
# --------------------------------------------------------------------------


class TestSendCode:
    async def test_sends_code_and_reports_mail_flag(
        self, async_client: AsyncClient, outbox: list
    ):
        resp = await _send_code(async_client)

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["expires_in"] == settings.CODE_TTL_SECONDS
        assert body["resend_after"] == settings.CODE_RESEND_INTERVAL
        # 不能写死 false：本机 .env 可能已经配好 SMTP。
        # 前端靠这个字段判断要不要提示「去后端日志取码」，所以它必须如实反映配置。
        assert body["mail_enabled"] is settings.MAIL_ENABLED

        assert len(outbox) == 1
        to, code = outbox[0]
        assert to == EMAIL
        assert len(code) == settings.CODE_LENGTH and code.isdigit()

    async def test_code_is_not_stored_in_plaintext(
        self, async_client: AsyncClient, outbox: list
    ):
        """缓存里不能出现明文验证码 —— 否则存储层泄露等于直接泄露账号。"""
        await _send_code(async_client)
        code = outbox[0][1]

        store = await verification._get_store()  # noqa: SLF001 - 白盒校验安全属性
        raw = await store.get(verification._code_key(EMAIL, verification.PURPOSE_REGISTER))  # noqa: SLF001

        assert raw is not None
        assert code not in raw
        assert verification._digest(EMAIL, code, verification.PURPOSE_REGISTER) in raw  # noqa: SLF001

    async def test_rejects_already_registered_email(
        self, async_client: AsyncClient, async_db: AsyncSession, outbox: list
    ):
        async_db.add(User(email="taken@example.com", password_hash="x"))
        await async_db.commit()

        resp = await _send_code(async_client, "taken@example.com")

        assert resp.status_code == 400
        assert "已被注册" in resp.json()["detail"]
        assert outbox == []  # 不该为无效邮箱浪费一次发信

    async def test_resend_cooldown(
        self, async_client: AsyncClient, outbox: list
    ):
        assert (await _send_code(async_client)).status_code == 200
        second = await _send_code(async_client)

        assert second.status_code == 429
        assert "秒后再试" in second.json()["detail"]
        assert second.headers.get("Retry-After")
        assert len(outbox) == 1  # 冷却期内不重复发信

    async def test_hourly_limit(self, async_client: AsyncClient, outbox: list,
                                monkeypatch):
        # 关掉冷却，单独验证每小时上限
        monkeypatch.setattr(settings, "CODE_RESEND_INTERVAL", 0, raising=False)

        for _ in range(settings.CODE_HOURLY_LIMIT):
            assert (await _send_code(async_client)).status_code == 200

        blocked = await _send_code(async_client)
        assert blocked.status_code == 429
        assert "过于频繁" in blocked.json()["detail"]

    async def test_mail_not_configured_returns_actionable_error(
        self, async_client: AsyncClient, monkeypatch
    ):
        """没配 SMTP 时应给出可操作提示，而不是 500。"""
        from app.services.mailer import MailNotConfigured

        async def raise_unconfigured(to, code, ttl, purpose="register"):
            raise MailNotConfigured("邮件服务未配置：请填写 MAIL_HOST / MAIL_USER / MAIL_PASSWORD")

        monkeypatch.setattr("app.api.auth.send_verification_code", raise_unconfigured)

        resp = await _send_code(async_client)

        assert resp.status_code == 503
        assert "MAIL_HOST" in resp.json()["detail"]


# --------------------------------------------------------------------------
# 注册校验
# --------------------------------------------------------------------------


class TestRegisterWithCode:
    async def test_requires_code(self, async_client: AsyncClient):
        resp = await _register(async_client, code="")

        assert resp.status_code == 400
        assert "请输入验证码" in resp.json()["detail"]

    async def test_rejects_wrong_code_and_counts_down(
        self, async_client: AsyncClient, outbox: list
    ):
        await _send_code(async_client)

        resp = await _register(async_client, code="000000")

        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert "验证码不正确" in detail
        assert str(settings.CODE_MAX_ATTEMPTS - 1) in detail  # 提示剩余次数

    async def test_succeeds_with_correct_code_and_marks_verified(
        self, async_client: AsyncClient, outbox: list, async_db: AsyncSession
    ):
        await _send_code(async_client)
        code = outbox[0][1]

        resp = await _register(async_client, code=code)

        assert resp.status_code == 200
        assert resp.json()["token"]

        user = await async_db.scalar(select(User).where(User.email == EMAIL))
        assert user is not None
        assert user.is_verified is True

    async def test_code_is_single_use(
        self, async_client: AsyncClient, outbox: list, async_db: AsyncSession
    ):
        await _send_code(async_client)
        code = outbox[0][1]

        assert (await _register(async_client, code=code)).status_code == 200
        # 同一个码不能再用来注册第二个账号（防重放）
        replay = await _register(async_client, code=code, email="another@example.com")
        assert replay.status_code == 400
        assert "重新获取" in replay.json()["detail"]

    async def test_code_expires(self, async_client: AsyncClient, outbox: list):
        await _send_code(async_client)
        code = outbox[0][1]

        # 直接把存储里的过期时间改到过去，避免真的 sleep
        key = verification._code_key(EMAIL, verification.PURPOSE_REGISTER)  # noqa: SLF001
        value, _ = verification._memory._data[key]  # noqa: SLF001
        verification._memory._data[key] = (value, time.time() - 1)  # noqa: SLF001

        resp = await _register(async_client, code=code)

        assert resp.status_code == 400
        assert "已过期" in resp.json()["detail"]

    async def test_exceeding_attempts_invalidates_code(
        self, async_client: AsyncClient, outbox: list
    ):
        await _send_code(async_client)
        code = outbox[0][1]

        last = None
        for _ in range(settings.CODE_MAX_ATTEMPTS):
            last = await _register(async_client, code="000000")
            assert last.status_code == 400

        # 第 MAX_ATTEMPTS 次触发作废
        assert "错误次数过多" in last.json()["detail"]

        # 码已作废：即使拿对了也进不去
        resp = await _register(async_client, code=code)
        assert resp.status_code == 400
        assert "已过期" in resp.json()["detail"]

    async def test_code_of_other_email_is_rejected(
        self, async_client: AsyncClient, outbox: list
    ):
        """拿 A 邮箱的码去注册 B 邮箱必须失败。"""
        await _send_code(async_client, "victim@example.com")
        stolen = outbox[0][1]

        resp = await _register(async_client, code=stolen, email="attacker@example.com")

        assert resp.status_code == 400
        assert "已过期" in resp.json()["detail"]  # 攻击者邮箱根本没有待用的码

    async def test_weak_password_does_not_burn_the_code(
        self, async_client: AsyncClient, outbox: list
    ):
        """密码强度不过时，验证码**必须还在**。

        这是「用户刚拿到码就提示已过期」的根因回归测试。

        /register 的顺序是「验码 → 查重名 → 查密码强度」。原实现校验通过就
        立刻删码，于是用户密码填弱了被退回、改完再点一次注册时，码已经没了，
        他看到的是「验证码已过期，请重新获取」—— 而手上这个码才拿到几十秒，
        用户分辨不出，只会觉得「验证码过期太快」。

        所以断言分两步：第一次因密码弱被拒，同一个码第二次必须能注册成功。
        """
        await _send_code(async_client)
        code = outbox[0][1]

        weak = await async_client.post(
            "/api/v1/auth/register",
            json={"email": EMAIL, "password": "123", "nickname": "新用户", "code": code},
        )
        assert weak.status_code == 400
        assert "密码" in weak.json()["detail"]

        # 同一个码，这次密码合法 —— 必须成功，而不是报「已过期」
        ok = await _register(async_client, code=code)
        assert ok.status_code == 200, ok.json()

    async def test_email_taken_does_not_burn_the_code(
        self, async_client: AsyncClient, outbox: list
    ):
        """码校验通过、但后续关卡没过时，码不能被消费。

        正常 UI 走不到「邮箱已注册」这一步（/auth/send-code 会提前拦住，
        见那里的注释），所以这里直接从服务层签一个码来构造这个边界 ——
        它守的是同一件事：**消费必须发生在所有关卡都通过之后**。
        """
        # 1) 先把这个邮箱正常注册掉（会消费掉首个码）
        await _send_code(async_client)
        assert (await _register(async_client, code=outbox[0][1])).status_code == 200

        # 2) 绕过 send-code 的「邮箱已注册」拦截，直接签一个码
        verification._memory._data.pop(  # noqa: SLF001
            verification._cooldown_key(EMAIL, verification.PURPOSE_REGISTER), None
        )
        issued = await verification.issue_code(EMAIL, verification.PURPOSE_REGISTER)
        assert issued.ok

        dup = await _register(async_client, code=issued.code)
        assert dup.status_code == 400
        assert "已被注册" in dup.json()["detail"]

        # 码必须还在。否则用户换个邮箱重新走一遍时，只会看到「验证码已过期」
        key = verification._code_key(EMAIL, verification.PURPOSE_REGISTER)  # noqa: SLF001
        assert key in verification._memory._data  # noqa: SLF001

    async def test_successful_register_consumes_the_code(
        self, async_client: AsyncClient, outbox: list
    ):
        """注册成功后码必须真的被消费掉。

        上面两条把「校验」和「消费」拆开了，这条守住另一半：拆开之后不能
        变成「永不作废」，否则一个码可以被反复用来注册。
        """
        await _send_code(async_client)
        assert (await _register(async_client, code=outbox[0][1])).status_code == 200

        key = verification._code_key(EMAIL, verification.PURPOSE_REGISTER)  # noqa: SLF001
        assert key not in verification._memory._data  # noqa: SLF001

    async def test_disabled_flag_allows_codeless_register(
        self, async_client: AsyncClient, monkeypatch, async_db: AsyncSession
    ):
        monkeypatch.setattr(settings, "REQUIRE_EMAIL_CODE", False, raising=False)

        resp = await _register(async_client, code="")

        assert resp.status_code == 200
        user = await async_db.scalar(select(User).where(User.email == EMAIL))
        # 没走验证码就不该谎报已验证
        assert user.is_verified is False


# --------------------------------------------------------------------------
# 服务层：存储后端与 TTL
# --------------------------------------------------------------------------


class TestVerificationService:
    async def test_issue_then_verify_roundtrip(self):
        outcome = await verification.issue_code("roundtrip@example.com")
        assert outcome.ok

        ok = await verification.verify_code("roundtrip@example.com", outcome.code)
        assert ok.ok is True

        # 二次校验应失败（已作废）
        again = await verification.verify_code("roundtrip@example.com", outcome.code)
        assert again.ok is False

    async def test_cooldown_reports_remaining_seconds(self):
        await verification.issue_code("cd@example.com")
        second = await verification.issue_code("cd@example.com")

        assert second.ok is False
        assert second.retry_after > 0
        assert "秒后再试" in second.error

    async def test_generated_code_is_zero_padded(self):
        """低位数字不能丢前导零，否则用户拿到的码位数不对。"""
        for _ in range(20):
            code = verification._generate_code()  # noqa: SLF001
            assert len(code) == settings.CODE_LENGTH
            assert code.isdigit()

    async def test_store_isolated_between_purposes(self):
        """register 的码不能用来通过 reset 之类的其他用途。"""
        outcome = await verification.issue_code("purpose@example.com",
                                                verification.PURPOSE_REGISTER)
        assert outcome.ok

        other = await verification.verify_code(
            "purpose@example.com", outcome.code, "password_reset"
        )
        assert other.ok is False
        assert "已过期" in other.error
