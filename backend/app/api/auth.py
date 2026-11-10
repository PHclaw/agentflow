"""
认证 API — 数据库版本
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta, timezone
import bcrypt
from jose import jwt, JWTError

from ..core.database import get_db
from ..core.config import settings
from ..core.rate_limiter import get_limiter
from ..models.user import User
from ..core.default_agent import build_default_agent
from ..services.entitlement import new_free_subscription
from ..services.password_policy import validate_password
from ..services.roles import apply_configured_role
from ..services.mailer import MailNotConfigured, send_verification_code
from ..services.verification import (
    PURPOSE_REGISTER,
    consume_code,
    issue_code,
    verify_code,
)

logger = logging.getLogger(__name__)

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_token(user_id: str, password_changed_at=None) -> str:
    """签发 token。

    ``password_changed_at`` 会以 unix 时间戳写进 payload。改密码时这个值被刷新，
    之后所有**签发时间更早**的 token 都在校验时被判失效 —— 这是「改密码能把
    已登录的其它设备踢掉」的唯一实现方式，否则 7 天有效期的 token 会一直好用。
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {"sub": user_id, "exp": expire}
    if password_changed_at is not None:
        ts = password_changed_at
        if isinstance(ts, datetime):
            ts = ts.replace(tzinfo=ts.tzinfo or timezone.utc).timestamp()
        payload["pwd_ts"] = ts
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


async def get_current_user_id(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> str:
    """从 token 解析当前用户，并确认账号仍然可用。

    这里**必须查一次库**，不能只解 JWT：token 有效期是 7 天
    （``JWT_EXPIRE_MINUTES=10080``），只靠登录时校验的话，被停用的账号
    拿着旧 token 还能继续用满一周，管理员的「停用」就成了摆设。

    查询走 ``external_id`` 唯一索引，开销可忽略。改密码的失效判断也搭这次
    查询完成，不额外多一次往返。

    账号不可用时返回 **401**（而不是 403）：前端对 401 的处理是清 token
    并跳登录页，用户重新登录时会拿到「账号已被停用」的明确原因；
    返回 403 只会让他在各个页面反复撞墙、又退不出去。
    """
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = await db.scalar(select(User).where(User.external_id == user_id))
    if user is None:
        raise HTTPException(status_code=401, detail="账号不存在，请重新登录")
    if not user.is_active:
        raise HTTPException(status_code=401, detail="账号已被停用，请联系管理员")

    # 改密后失效：token 里的 pwd_ts 早于库里记录的改密时间即拒。
    # 老 token（没有 pwd_ts）在用户从未改过密码时放行 —— 否则升级部署
    # 会把所有人一次性踢下线。
    if user.password_changed_at is not None:
        token_pwd_ts = payload.get("pwd_ts")
        if token_pwd_ts is None:
            raise HTTPException(status_code=401, detail="登录状态已过期，请重新登录")
        current = user.password_changed_at
        current = (current if current.tzinfo else current.replace(tzinfo=timezone.utc)).timestamp()
        if float(token_pwd_ts) < current - 1:
            raise HTTPException(status_code=401, detail="密码已修改，请重新登录")

    return user_id


class SendCodeRequest(BaseModel):
    email: EmailStr


@router.post("/send-code")
async def send_code(
    request: SendCodeRequest,
    req: Request,
    db: AsyncSession = Depends(get_db),
):
    """发送注册验证码。

    邮箱已注册时直接告知。这确实是个「邮箱枚举」的口子，但在注册场景下
    不告知会让用户白填一遍表单再失败，体验更差。缓解手段是双重限流：
    邮箱级（冷却 60s + 每小时上限）+ IP 级（每小时 10 次）。
    """
    # ---- IP 级限流 ----
    forwarded = (req.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
    ip = forwarded or (req.client.host if req.client else "unknown")
    # 邮箱级限流（冷却 + 每小时上限）挡不住「换邮箱刷」，这里再兜一层
    allowed, _ = await get_limiter().is_allowed(
        f"ip:{ip}", "auth:send-code",
        settings.SEND_CODE_IP_LIMIT, settings.SEND_CODE_IP_WINDOW,
    )
    if not allowed:
        raise HTTPException(status_code=429, detail="操作过于频繁，请稍后再试")

    # ---- 邮箱占用检查 ----
    existing = await db.scalar(select(User).where(User.email == request.email))
    if existing:
        raise HTTPException(status_code=400, detail="该邮箱已被注册，请直接登录")

    # ---- 签发 ----
    outcome = await issue_code(request.email, PURPOSE_REGISTER)
    if not outcome.ok:
        raise HTTPException(
            status_code=429,
            detail=outcome.error,
            headers={"Retry-After": str(outcome.retry_after)},
        )

    # ---- 投递 ----
    # 未配置发信时给出可操作的提示，而不是笼统的 500
    try:
        await send_verification_code(
            request.email,
            outcome.code,
            settings.CODE_TTL_SECONDS,
            purpose=PURPOSE_REGISTER,
        )
    except MailNotConfigured as exc:
        logger.error("邮件服务未配置：%s", exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - SMTP 的失败形态很多
        logger.exception("验证码邮件发送失败 → %s", request.email)
        raise HTTPException(
            status_code=502, detail="验证码邮件发送失败，请稍后重试或联系管理员"
        ) from exc

    return {
        "success": True,
        "message": f"验证码已发送至 {request.email}",
        "expires_in": settings.CODE_TTL_SECONDS,
        "resend_after": settings.CODE_RESEND_INTERVAL,
        # MAIL_ENABLED=false 时邮件不会真的发出，验证码只打到后端日志
        "mail_enabled": settings.MAIL_ENABLED,
    }


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    nickname: str = None
    code: str = ""


@router.post("/register")
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """注册。

    先校验验证码再落库 —— 顺序不能反：先查邮箱重名的话，攻击者不需要
    有效验证码就能枚举出哪些邮箱已注册。
    """
    verified = False
    if settings.REQUIRE_EMAIL_CODE:
        # **先验、不消费。**
        #
        # 校验码只是第一道关卡，下面还有「邮箱是否已注册」和「密码强度」。
        # 原来校验通过就立刻删码，于是用户因为密码太弱（或邮箱已注册）被退回、
        # 改完再点一次注册时，码已经没了 —— 他看到的却是「验证码已过期，
        # 请重新获取」，而手上这个码才拿到几十秒。用户只会觉得「过期太快」。
        #
        # 顺序仍然不能反：先查邮箱重名的话，攻击者不需要有效验证码就能枚举
        # 哪些邮箱已注册。所以是「先验码 → 再查重/查强度 → 最后才消费」。
        outcome = await verify_code(
            request.email, request.code, PURPOSE_REGISTER, consume=False
        )
        if not outcome.ok:
            raise HTTPException(status_code=400, detail=outcome.error)
        verified = True

    # 检查邮箱是否已注册
    existing = await db.scalar(select(User).where(User.email == request.email))
    if existing:
        raise HTTPException(status_code=400, detail="该邮箱已被注册")

    # 密码强度。注册和改密码必须共用同一套规则：只有一边校验的话，
    # 会出现「注册能设 1 位弱密码、改的时候反而被拒」的怪事。
    try:
        password = validate_password(request.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    user = User(
        email=request.email,
        password_hash=get_password_hash(password),
        nickname=request.nickname or request.email.split("@")[0],
        # 只有真的过了验证码才标记为已验证；关闭校验时保持未验证语义
        is_verified=verified,
    )
    db.add(user)
    # 注册即开通免费订阅。
    # 少了这条记录，后续所有配额校验都无从谈起—— Subscription 的
    # can_create_agent() 一直是死代码，根因就在这里。
    # flush 而不是 commit：要先拿到自增 id 才能填 Subscription.user_id。
    await db.flush()
    # 新账号自带一个可用 Agent：注册完点「对话」就能直接聊，而不是先被引去创建。
    # 它占掉免费版的 1 个名额（FREE_AGENTS=1），所以 agents_used 一并置 1。
    db.add(build_default_agent(user.external_id))
    db.add(new_free_subscription(user.id, agents_used=1))
    # 注册的邮箱也过一遍管理员白名单：新环境里管理员往往就是第一个注册的账号
    apply_configured_role(user)
    await db.commit()
    await db.refresh(user)

    # 账号已经落库，到这里才真正作废这个验证码。
    # 放在 commit 之后：万一落库失败，码还在，用户可以直接重试而不必重新收信。
    # 也不会因此被重放 —— 邮箱已存在，重复注册会先撞上「该邮箱已被注册」。
    if verified:
        await consume_code(request.email, request.code, PURPOSE_REGISTER)

    # password_changed_at 一起签进 token：改密后这个值刷新，
    # 旧 token 会在鉴权时被判失效（详见 get_current_user_id）。
    # 刚注册的用户它是 None，payload 里就不带 pwd_ts，老逻辑照常放行。
    token = create_token(user.external_id, user.password_changed_at)
    return {
        "token": token,
        "user": {
            "id": user.external_id,
            "email": user.email,
            "nickname": user.nickname,
            "role": user.role,
        },
    }


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/login")
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    """登录"""
    user = await db.scalar(select(User).where(User.email == request.email))
    if not user:
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    if not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="邮箱或密码错误")

    # 停用的账号不允许再登录。此前这里完全没有校验 ——
    # is_active 只是躺在库里没人看，管理员「停用」等于没停。
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已被停用，请联系管理员")

    user.last_login_at = datetime.now(timezone.utc)
    # 登录时同步一次角色：管理员名单是配置项，改了配置后重新登录即可生效，
    # 不需要连数据库手工改 users.role
    role_changed = apply_configured_role(user)
    await db.commit()
    if role_changed:
        await db.refresh(user)

    # password_changed_at 一起签进 token：改密后这个值刷新，
    # 旧 token 会在鉴权时被判失效（详见 get_current_user_id）。
    # 刚注册的用户它是 None，payload 里就不带 pwd_ts，老逻辑照常放行。
    token = create_token(user.external_id, user.password_changed_at)
    return {
        "token": token,
        "token_type": "bearer",
        "user": {
            "id": user.external_id,
            "email": user.email,
            "nickname": user.nickname or user.email.split("@")[0],
            "role": user.role,
        },
    }


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(min_length=1)
    new_password: str = Field(min_length=1, max_length=128)


@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """已登录用户修改密码。

    ``get_current_user_id`` 已经查过一次库并确认账号可用，这里直接复用
    ``user_id``，不再查一遍。

    改完会刷新 ``password_changed_at``，**所有已签发的 token 随之失效**
    （包括当前这个）—— 这是刻意的：账号被盗之后光改密码没用，
    得把入侵者手里的凭证一起作废。代价是用户自己在其它设备上要重新登录，
    这个取舍在安全侧是值得的，UI 上也要明确告知。
    """
    user = await db.scalar(select(User).where(User.external_id == user_id))
    if not user:
        raise HTTPException(status_code=404, detail="账号不存在")

    if not verify_password(request.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="当前密码不正确")

    try:
        new_password = validate_password(request.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if verify_password(new_password, user.password_hash):
        raise HTTPException(status_code=400, detail="新密码不能与当前密码相同")

    user.password_hash = get_password_hash(new_password)
    user.password_changed_at = datetime.now(timezone.utc)
    await db.commit()

    logger.info("用户 %s 修改了密码，旧 token 已全部失效", user_id)
    return {"success": True, "message": "密码已修改，请重新登录"}
