"""
支付模型
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Enum
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum


class PlanType(str, enum.Enum):
    FREE = "free"
    PRO = "pro"
    TEAM = "team"


class Subscription(Base):
    """用户订阅"""
    __tablename__ = "subscriptions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    plan = Column(String(20), default=PlanType.FREE.value)
    
    # Stripe 相关
    stripe_customer_id = Column(String(100))
    stripe_subscription_id = Column(String(100))
    stripe_price_id = Column(String(100))
    
    # 状态
    status = Column(String(20), default="active")  # active, canceled, past_due
    current_period_start = Column(DateTime)
    current_period_end = Column(DateTime)
    cancel_at_period_end = Column(Boolean, default=False)
    
    # 使用统计
    agents_used = Column(Integer, default=0)
    messages_used = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    user = relationship("User", back_populates="subscription")
    
    @property
    def is_pro(self) -> bool:
        return self.plan in [PlanType.PRO.value, PlanType.TEAM.value] and self.status == "active"
    
    def can_create_agent(self, settings) -> bool:
        limit = settings.PRO_AGENTS if self.is_pro else settings.FREE_AGENTS
        return self.agents_used < limit
    
    def can_send_message(self, settings) -> bool:
        limit = settings.PRO_MESSAGES if self.is_pro else settings.FREE_MESSAGES
        return self.messages_used < limit
