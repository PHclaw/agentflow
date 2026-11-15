"""用户模型"""
import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.orm import relationship

from app.core.base import Base


class UserRole(str, enum.Enum):
    """用户角色。

    只有两档：普通用户、管理员。没有再细分（运营 / 客服 / 只读）。
    真要做细粒度权限时应该换成独立的角色-权限表，而不是在这个枚举上继续加。
    """

    USER = "user"
    ADMIN = "admin"


class User(Base):
    """用户表"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    # 保留 UUID 作为外部 ID
    external_id = Column(String(36), unique=True, default=lambda: str(uuid.uuid4()))
    
    email = Column(String(255), unique=True, index=True, nullable=True)
    phone = Column(String(20), unique=True, index=True, nullable=True)
    password_hash = Column(String(255), nullable=False)
    
    # 用户信息
    nickname = Column(String(50), nullable=True)
    avatar = Column(String(500), nullable=True)
    
    # 状态
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    # 角色。默认普通用户；管理员由 ADMIN_EMAILS 配置在登录时授予。
    # server_default 保证已有数据行在迁移时也能拿到 'user' 而不是 NULL。
    role = Column(String(20), nullable=False, default=UserRole.USER.value,
                  server_default=UserRole.USER.value)

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN.value
    
    
    # 时间戳
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    last_login_at = Column(DateTime, nullable=True)
    # 最近一次修改密码的时间。token 里会带上签发时的这个值，
    # 校验时比对：token 早于本次改密即失效。
    # 少了它，「改密码」拦得住下一次登录，拦不住已经发出去的那些 token ——
    # 而 token 有效期是 7 天，等于账号被盗后改密码也踢不掉人。
    password_changed_at = Column(DateTime, nullable=True)
    
    # 关系
    subscription = relationship("Subscription", back_populates="user", uselist=False)
    agents = relationship("Agent", back_populates="user", foreign_keys="Agent.user_id")
