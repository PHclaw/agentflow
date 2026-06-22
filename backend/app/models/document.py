"""
文档向量模型 - pgvector
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index, JSON
from sqlalchemy.orm import relationship
from datetime import datetime

# pgvector 扩展
try:
    from pgvector.sqlalchemy import Vector
    HAS_PGVECTOR = True
except ImportError:
    HAS_PGVECTOR = False
    # Fallback: 使用 JSON 存储向量
    from sqlalchemy import JSON
    def Vector(dim):
        return JSON

from ..core.database import Base


class Document(Base):
    """文档表"""
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    kb_id = Column(String(36), ForeignKey("knowledge_bases.id"), index=True)
    
    # 文档信息
    filename = Column(String(255))
    file_type = Column(String(50))  # pdf, docx, txt, md
    file_size = Column(Integer)
    
    # 处理状态
    status = Column(String(20), default="pending")  # pending, processing, done, failed
    chunk_count = Column(Integer, default=0)
    error_message = Column(Text)
    
    # 元数据
    doc_metadata = Column(JSON, default=dict)
    
    # 时间戳
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    processed_at = Column(DateTime)
    
    # 关系
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    """文档分块表"""
    __tablename__ = "document_chunks"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    kb_id = Column(String(36), ForeignKey("knowledge_bases.id"), index=True)
    
    # 分块信息
    chunk_index = Column(Integer)
    content = Column(Text, nullable=False)
    
    # 向量嵌入 (1536 维 for OpenAI, 384 for sentence-transformers)
    embedding = Column(Vector(1536))
    
    # 元数据
    chunk_metadata = Column(JSON, default=dict)
    
    # 时间戳
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    # 关系
    document = relationship("Document", back_populates="chunks")
    
    # 向量索引（如果 pgvector 可用）
    if HAS_PGVECTOR:
        __table_args__ = (
            Index('ix_document_chunks_embedding', embedding, postgresql_using='ivfflat',
                  postgresql_with={'lists': 100},
                  postgresql_ops={'embedding': 'vector_cosine_ops'}),
        )
