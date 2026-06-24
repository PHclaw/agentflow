"""
Agent 模型
"""
from sqlalchemy import Column, String, Text, DateTime, Boolean, Integer, JSON, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid

from app.core.base import Base


class Agent(Base):
    """Agent 表"""
    __tablename__ = "agents"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.external_id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    
    # 工作流定义
    workflow_definition = Column(JSON, nullable=False, default=dict)
    
    # 模型配置
    model_config = Column(JSON, nullable=False, default=dict)
    
    # 模板名称（关联 WorkflowTemplate）
    template = Column(String(100), nullable=True)
    
    # 知识库 ID
    knowledge_base_id = Column(String(36), nullable=True, index=True)
    
    # 设置
    settings = Column(JSON, nullable=True)
    
    # 状态
    is_active = Column(Boolean, default=True)
    
    # 统计
    message_count = Column(Integer, default=0)
    
    # 时间戳
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # 关系
    user = relationship("User", back_populates="agents", foreign_keys=[user_id])


class WorkflowTemplate(Base):
    """工作流模板"""
    __tablename__ = "workflow_templates"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)
    category = Column(String(50), nullable=False)  # customer_service, sales, hr, finance
    description = Column(Text)
    
    # 前端展示
    icon = Column(String(50), default="template")  # emoji 或图标名
    color = Column(String(50), default="from-blue-500 to-indigo-600")  # Tailwind gradient
    features = Column(JSON, default=list)  # ["功能1", "功能2"]
    
    # 模板定义
    workflow_definition = Column(JSON, nullable=False)
    
    # 预览
    preview_image = Column(String(500))
    
    # 统计
    use_count = Column(Integer, default=0)
    is_public = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ChatSession(Base):
    """对话会话"""
    __tablename__ = "chat_sessions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    
    # 消息历史
    messages = Column(JSON, default=list)
    
    # 元数据
    session_metadata = Column(JSON)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class KnowledgeBase(Base):
    """知识库"""
    __tablename__ = "knowledge_bases"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String(36), nullable=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    
    # 配置
    config = Column(JSON)
    
    # 统计
    documents_count = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
