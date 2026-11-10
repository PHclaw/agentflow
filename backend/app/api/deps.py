"""
跨 API 模块共用的 FastAPI 依赖。

单独放一个模块而不是塞进 ``services/entitlement.py``：依赖要 import
``api.auth.get_current_user_id``，而 ``api.auth`` 又要 import
``services.entitlement``，放一起会形成循环导入。
service 层不反向依赖 api 层，这条边界值得用文件位置固定下来。
"""
from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..models.subscription import Subscription
from ..models.user import User
from ..services.entitlement import ensure_subscription
from .auth import get_current_user_id


async def current_user(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> User:
    """当前用户的 ORM 对象。

    ``get_current_user_id`` 只解 JWT、不查库；需要用户字段（角色、状态、
    邮箱）时用这个。
    """
    user = await db.scalar(select(User).where(User.external_id == user_id))
    if user is None:
        # token 还没过期但账号已被删除，必须拦住，否则后续会写出无所属的数据
        raise HTTPException(status_code=401, detail="账号不存在，请重新登录")
    return user


async def require_admin(user: User = Depends(current_user)) -> User:
    """要求管理员身份，否则 403。

    权限必须在后端拦。前端隐藏入口只是体验，改个 localStorage 或直接
    发请求就能绕过。
    """
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


async def current_subscription(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> Subscription:
    """当前用户的订阅。

    懒创建 + 周期重置：老用户没有订阅记录时顺手补一个免费版，
    周期过期时归零用量。业务代码拿到的永远是可直接判定额度的对象。
    """
    return await ensure_subscription(db, user_id)
