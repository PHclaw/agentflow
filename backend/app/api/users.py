"""
用户 API — 数据库版本
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..core.database import get_db
from ..models.user import User
from .auth import get_current_user_id

router = APIRouter()


@router.get("/me")
async def get_me(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """获取当前用户信息"""
    user = await db.scalar(select(User).where(User.external_id == user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "id": user.external_id,
        "email": user.email,
        "nickname": user.nickname,
        "avatar": user.avatar,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }
