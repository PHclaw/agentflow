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
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user_id
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


class RegisterRequest(BaseModel):
    email: str
    password: str
    nickname: str = None


@router.post("/register")
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """注册"""
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
        "user": {
            "id": user.external_id,
            "email": user.email,
            "nickname": user.nickname,
        },
    }


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/login")
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    """登录"""
    user = await db.scalar(select(User).where(User.email == request.email))
    if not user:
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    if not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="邮箱或密码错误")

    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    token = create_token(user.external_id)
    return {
        "token": token,
        "token_type": "bearer",
        "user": {
            "id": user.external_id,
            "email": user.email,
            "nickname": user.nickname or user.email.split("@")[0],
        },
    }
