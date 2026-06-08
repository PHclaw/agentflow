"""
认证 API
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta
import bcrypt
from jose import jwt, JWTError

from ..core.database import get_db
from ..core.config import settings

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode('utf-8'), hashed.encode('utf-8'))


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def create_token(user_id: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
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


# 简化实现：使用内存存储演示
_users = {}


class RegisterRequest(BaseModel):
    email: str
    password: str
    nickname: str = None


@router.post("/register")
async def register(request: RegisterRequest):
    """注册（简化版）"""
    if request.email in _users:
        raise HTTPException(status_code=400, detail="该邮箱已被注册")
    
    user_id = f"user_{len(_users)}"
    _users[request.email] = {
        "id": user_id,
        "email": request.email,
        "nickname": request.nickname or request.email.split('@')[0],
        "password_hash": get_password_hash(request.password),
    }
    
    # 注册后自动登录，返回token
    token = create_token(user_id)
    
    return {
        "token": token,
        "user": {
            "id": user_id,
            "email": request.email,
            "nickname": request.nickname or request.email.split('@')[0],
        }
    }


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/login")
async def login(request: LoginRequest):
    """登录"""
    user = _users.get(request.email)
    
    if not user:
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    
    if not verify_password(request.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    
    token = create_token(user["id"])
    
    return {"token": token, "token_type": "bearer", "user": {"id": user["id"], "email": user["email"], "nickname": user.get("nickname", user["email"].split('@')[0])}}
