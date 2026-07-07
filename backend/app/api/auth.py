"""
认证 API — 数据库版本
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta, timezone
import bcrypt
from jose import jwt, JWTError

from ..core.database import get_db
from ..core.config import settings
from ..models.user import User

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


async def get_current_user_id(token: str = Depends(oauth2_scheme)) -> str:
    """解析 token 获取用户 ID"""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user_id
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)) -> User:
    """解析 token 获取完整的用户对象"""
    user_id = await get_current_user_id(token)
    user = await db.scalar(select(User).where(User.external_id == user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


class RegisterRequest(BaseModel):
    email: str
    password: str
    nickname: str = None

    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "StrongPass123!",
                "nickname": "张三"
            }
        }


def validate_password(password: str) -> tuple[bool, str]:
    """验证密码强度"""
    if len(password) < 8:
        return False, "密码长度至少 8 位"
    if not any(c.isupper() for c in password):
        return False, "密码必须包含大写字母"
    if not any(c.islower() for c in password):
        return False, "密码必须包含小写字母"
    if not any(c.isdigit() for c in password):
        return False, "密码必须包含数字"
    return True, ""


@router.post("/register")
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """用户注册"""
    # 验证密码强度
    is_valid, message = validate_password(request.password)
    if not is_valid:
        raise HTTPException(status_code=400, detail=message)

    # 检查邮箱是否已注册
    existing = await db.scalar(select(User).where(User.email == request.email))
    if existing:
        raise HTTPException(status_code=400, detail="该邮箱已被注册")

    user = User(
        email=request.email,
        password_hash=get_password_hash(request.password),
        nickname=request.nickname or request.email.split("@")[0],
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_token(user.external_id)
    return {
        "token": token,
        "token_type": "bearer",
        "user": {
            "id": user.external_id,
            "email": user.email,
            "nickname": user.nickname,
        },
    }


class LoginRequest(BaseModel):
    email: str
    password: str

    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "StrongPass123!"
            }
        }


class RefreshTokenRequest(BaseModel):
    token: str

    class Config:
        json_schema_extra = {
            "example": {
                "token": "your_refresh_token"
            }
        }


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

    class Config:
        json_schema_extra = {
            "example": {
                "old_password": "OldPass123!",
                "new_password": "NewPass456!"
            }
        }


@router.post("/login")
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    """用户登录"""
    user = await db.scalar(select(User).where(User.email == request.email))
    if not user:
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    if not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="邮箱或密码错误")

    user.last_login_at = datetime.now()
    await db.commit()

    token = create_token(user.external_id)
    return {
        "token": token,
        "token_type": "bearer",
        "expires_in": settings.JWT_EXPIRE_MINUTES * 60,
        "user": {
            "id": user.external_id,
            "email": user.email,
            "nickname": user.nickname or user.email.split("@")[0],
        },
    }


@router.post("/refresh")
async def refresh_token(request: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    """刷新 Token"""
    try:
        payload = jwt.decode(request.token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")

        user = await db.scalar(select(User).where(User.external_id == user_id))
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        new_token = create_token(user.external_id)
        return {
            "token": new_token,
            "token_type": "bearer",
            "expires_in": settings.JWT_EXPIRE_MINUTES * 60,
        }
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """修改密码"""
    # 验证旧密码
    if not verify_password(request.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="旧密码错误")

    # 验证新密码强度
    is_valid, message = validate_password(request.new_password)
    if not is_valid:
        raise HTTPException(status_code=400, detail=message)

    # 更新密码
    user.password_hash = get_password_hash(request.new_password)
    await db.commit()

    return {"message": "密码已修改"}


@router.get("/me")
async def get_me(user: User = Depends(get_current_user)):
    """获取当前用户信息"""
    return {
        "id": user.external_id,
        "email": user.email,
        "nickname": user.nickname,
        "avatar": user.avatar,
        "is_active": user.is_active,
        "is_verified": user.is_verified,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
    }
