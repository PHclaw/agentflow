"""
知识库服务 - RAG
"""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json
import numpy as np

from ..models.agent import KnowledgeBase
from ..services.llm import LLMService


class KnowledgeService:
    """知识库服务"""
    
    def __init__(self, db: AsyncSession, kb_id: str):
        self.db = db
        self.kb_id = kb_id
        self.llm = LLMService()
    
    async def add_document(
        self,
        content: str,
        metadata: dict = None,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ):
        """添加文档"""
        # 分块
        chunks = self._split_text(content, chunk_size, chunk_overlap)
        
        # 生成嵌入
        documents = []
        for i, chunk in enumerate(chunks):
            embedding = await self.llm.embed(chunk)
            documents.append({
                "kb_id": self.kb_id,
                "chunk_index": i,
                "content": chunk,
                "embedding": embedding,
                "metadata": metadata or {},
            })
        
        # 存储（简化实现）
        return documents
    
    def _split_text(
        self,
        text: str,
        chunk_size: int,
        chunk_overlap: int,
    ) -> List[str]:
        """文本分块"""
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            
            # 尝试在句子边界分割
            if end < len(text):
                last_period = chunk.rfind("。")
                last_newline = chunk.rfind("\n")
                split_point = max(last_period, last_newline)
                
                if split_point > chunk_size * 0.5:
                    chunk = chunk[:split_point + 1]
                    end = start + split_point + 1
            
            chunks.append(chunk.strip())
            start = end - chunk_overlap
        
        return [c for c in chunks if c]
    
    async def search(
        self,
        query: str,
        top_k: int = 5,
        threshold: float = 0.7,
    ) -> List[dict]:
        """语义搜索"""
        # 生成查询向量
        query_embedding = await self.llm.embed(query)
        
        # 搜索（简化实现，实际应使用 pgvector）
        # TODO: 实现向量搜索
        
        return []
    
    async def get_context(
        self,
        query: str,
        max_tokens: int = 2000,
    ) -> str:
        """获取上下文用于 RAG"""
        results = await self.search(query, top_k=5)
        
        context_parts = []
        total_tokens = 0
        
        for result in results:
            content = result["content"]
            # 简单估算 token 数
            tokens = len(content) // 4
            
            if total_tokens + tokens > max_tokens:
                break
            
            context_parts.append(content)
            total_tokens += tokens
        
        return "\n\n---\n\n".join(context_parts)


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """余弦相似度"""
    a = np.array(a)
    b = np.array(b)
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
