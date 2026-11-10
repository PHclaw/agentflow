"""
用户 API — 数据库版本

个人资料原先**只能读不能写**：前端设置页摆着一排输入框和「保存更改」按钮，
但后端只有 ``GET /me``，没有任何更新接口。那排输入框等于纯装饰 ——
用户改了名字点保存，什么都不会发生，也不会有任何提示。

这里补上写入侧：

- ``PATCH /me``      改昵称 / 手机号
- ``POST /me/avatar``  上传头像
- ``DELETE /me/avatar`` 删回头像

**刻意不支持改邮箱**。邮箱在这套系统里是登录标识、``ADMIN_EMAILS`` 的匹配键、
验证码的投递目标，三处都依赖它。放开自助修改要么得走「发验证码到新地址」的
完整流程，要么就会出现「改完登不进去 / 管理员权限静默丢失」。要做就得连同
这套流程一起做，不能只开一个口子。
"""
import re
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.database import get_db
from ..core.paths import static_root
from ..models.user import User
from ..services.roles import apply_configured_role
from .auth import get_current_user_id

router = APIRouter()

#: 头像允许的扩展名与大小。白名单而不是「看 content-type」——
#: 客户端给的 content-type 不可信，扩展名 + 落盘后按扩展名配 MIME 更稳。
AVATAR_EXTS = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
AVATAR_MAX_BYTES = 2 * 1024 * 1024

#: 手机号先卡「形状」：可选 + 前缀，数字间允许空格和连字符。
#: 真正的人数校验在 ``_is_valid_phone`` —— 去掉分隔符后必须是 7~15 位数字
#: （E.164 上限 15 位）。只卡形状的话 16 位以上的号也能通过，
#: 那种字符串不可能是任何地区的有效号码。
_PHONE_RE = re.compile(r"^\+?\d[\d\s-]{5,18}\d$")


def _is_valid_phone(raw: str) -> bool:
    if not _PHONE_RE.match(raw):
        return False
    digits = re.sub(r"[\s-]", "", raw).lstrip("+")
    return digits.isdigit() and 7 <= len(digits) <= 15


class ProfileUpdate(BaseModel):
    """可自助修改的资料字段。全部可选 —— 只传要改的那些。"""

    nickname: Optional[str] = Field(default=None, max_length=50)
    phone: Optional[str] = Field(default=None, max_length=20)


def _avatar_dir() -> Path:
    """头像目录放在 static/ 下，因为只有 /static 被挂载serve。

    用户上传内容和应用静态资源混在一起不太干净，但 ``uploads/`` 并没有被
    静态服务暴露（它是工作目录），要用就得再挂一个路由。相比之下
    ``static/avatars/`` 与既有的 ``static/generated/`` 是同一类运行时产物。
    """
    d = static_root() / "avatars"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _remove_avatar_file(url: Optional[str]) -> None:
    """删掉旧头像文件。url 形如 ``/static/avatars/xxx.png``。"""
    if not url or not url.startswith("/static/avatars/"):
        return
    name = url.rsplit("/", 1)[-1]
    # 只认 UUID 开头 + 白名单扩展名，防止 url 里带路径穿越把别处文件删掉
    if not name or "/" in name or "\\" in name or ".." in name:
        return
    stem = name.rsplit(".", 1)[0]
    if "." not in name or Path(name).suffix.lower() not in AVATAR_EXTS:
        return
    try:
        uuid.UUID(stem)
    except ValueError:
        return
    p = _avatar_dir() / name
    try:
        p.unlink(missing_ok=True)
    except OSError:
        pass  # 删不掉旧文件不该让整个请求失败


@router.get("/me")
async def get_me(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """获取当前用户信息"""
    user = await db.scalar(select(User).where(User.external_id == user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 顺带同步一次角色。管理员名单是配置项，这样「改配置 + 刷新页面」就能生效，
    # 不必等用户下次登录。只在真的需要改时才写库，纯 GET 不会无谓地开事务。
    if apply_configured_role(user):
        await db.commit()

    return {
        "id": user.external_id,
        "email": user.email,
        "nickname": user.nickname,
        "avatar": user.avatar,
        "phone": user.phone,
        "is_active": user.is_active,
        "role": user.role,
        "is_admin": user.is_admin,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


@router.patch("/me")
async def update_me(
    data: ProfileUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """改昵称 / 手机号。邮箱不给改，见模块 docstring。"""
    user = await db.scalar(select(User).where(User.external_id == user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if data.nickname is not None:
        nickname = data.nickname.strip()
        # 允许清空（退回用邮箱前缀显示），但不允许只填空格
        user.nickname = nickname or None

    if data.phone is not None:
        phone = data.phone.strip()
        if phone:
            if not _is_valid_phone(phone):
                raise HTTPException(status_code=400, detail="手机号格式不正确")
            # phone 是唯一索引，撞了要给一句能看懂的提示，而不是让唯一约束炸 500
            clash = await db.scalar(
                select(User).where(User.phone == phone, User.id != user.id)
            )
            if clash:
                raise HTTPException(status_code=409, detail="该手机号已被其他账号使用")
        user.phone = phone or None

    await db.commit()
    await db.refresh(user)

    return {
        "id": user.external_id,
        "email": user.email,
        "nickname": user.nickname,
        "avatar": user.avatar,
        "phone": user.phone,
        "role": user.role,
        "is_admin": user.is_admin,
    }


@router.post("/me/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """上传头像，返回可直连的 URL。

    文件按 UUID 重命名后落盘，**绝不用客户端给的文件名** ——
    那个名字可以写成 ``../../app/core/config.py``。
    """
    user = await db.scalar(select(User).where(User.external_id == user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    ext = Path(file.filename or "").suffix.lower()
    if ext not in AVATAR_EXTS:
        raise HTTPException(
            status_code=400,
            detail=f"仅支持 {', '.join(sorted(AVATAR_EXTS))} 格式",
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="文件为空")
    if len(content) > AVATAR_MAX_BYTES:
        raise HTTPException(status_code=400, detail="头像不能超过 2MB")

    name = f"{uuid.uuid4()}{ext}"
    path = _avatar_dir() / name
    path.write_bytes(content)

    # 新文件先落盘成功，再换引用、删旧文件 —— 反过来的话写盘失败会把人家的
    # 头像搞丢。
    old = user.avatar
    user.avatar = f"/static/avatars/{name}"
    await db.commit()
    _remove_avatar_file(old)

    return {"avatar": user.avatar}


@router.delete("/me/avatar")
async def delete_avatar(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """删回默认头像（数据库引用与文件一起清）。"""
    user = await db.scalar(select(User).where(User.external_id == user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    old = user.avatar
    user.avatar = None
    await db.commit()
    _remove_avatar_file(old)

    return {"avatar": None}
