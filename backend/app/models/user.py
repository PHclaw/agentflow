"""用户模型"""
from sqlalchemy import Column, String, DateTime, Boolean, JSON
from datetime import datetime
import uuid

from ..core.database import Base


class User(Base):
    """用户表"""
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, index=True, nullable=True)
    phone = Column(String(20), unique=True, index=True, nullable=True)
    password_hash = Column(String(255), nullable=False)
    
    # 用户信息
    nickname = Column(String(50), nullable=True)
    avatar = Column(String(500), nullable=True)
    
    # 订阅信息
    subscription_tier = Column(String(20), default="free")  # free / pro / enterprise
    subscription_expires_at = Column(DateTime, nullable=True)
    
    # 使用统计
    usage = Column(JSON, default=dict)  # {agents_count, messages_count, ...}
    
    # 状态
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login_at = Column(DateTime, nullable=True)
