"""用户模型"""
from sqlalchemy import Column, String, DateTime, Boolean, JSON, Integer, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from ..core.database import Base


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
    
    # 时间戳
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    last_login_at = Column(DateTime, nullable=True)
    
    # 关系
    subscription = relationship("Subscription", back_populates="user", uselist=False)
    agents = relationship("Agent", back_populates="user", foreign_keys="Agent.user_id")
