"""
知识库服务 - RAG + pgvector
"""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
import json
import os
import uuid
from datetime import datetime

from ..models.agent import KnowledgeBase
from ..models.document import Document, DocumentChunk
from ..services.llm import LLMService

# 尝试导入 pgvector
try:
    from pgvector.sqlalchemy import Vector
    from sqlalchemy import text
    HAS_PGVECTOR = True
except ImportError:
    HAS_PGVECTOR = False


class KnowledgeService:
    """知识库服务"""
    
    def __init__(self, db: AsyncSession, kb_id: str = None):
        self.db = db
        self.kb_id = kb_id
        self.llm = LLMService()
    
    async def create_knowledge_base(
        self,
        name: str,
        description: str = "",
        user_id: str = None,
    ) -> KnowledgeBase:
        """创建知识库"""
        kb = KnowledgeBase(
            id=str(uuid.uuid4()),
            name=name,
            description=description,
            agent_id=None,  # 独立知识库
        )
        self.db.add(kb)
        await self.db.commit()
        await self.db.refresh(kb)
        return kb
    
    async def add_document(
        self,
        kb_id: str,
        filename: str,
        content: str,
        file_type: str = "txt",
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ) -> Document:
        """添加文档"""
        # 创建文档记录
        doc = Document(
            kb_id=kb_id,
            filename=filename,
            file_type=file_type,
            file_size=len(content),
            status="processing",
        )
        self.db.add(doc)
        await self.db.commit()
        await self.db.refresh(doc)
        
        try:
            # 分块
            chunks = self._split_text(content, chunk_size, chunk_overlap)
            
            # 为每个分块生成嵌入并保存
            for i, chunk_content in enumerate(chunks):
                # 生成嵌入向量
                embedding = await self.llm.embed(chunk_content)
                
                chunk = DocumentChunk(
                    document_id=doc.id,
                    kb_id=kb_id,
                    chunk_index=i,
                    content=chunk_content,
                    embedding=embedding,
                )
                self.db.add(chunk)
            
            # 更新文档状态
            doc.status = "done"
            doc.chunk_count = len(chunks)
            doc.processed_at = datetime.utcnow()
            
            await self.db.commit()
            await self.db.refresh(doc)
            
            return doc
            
        except Exception as e:
            doc.status = "failed"
            doc.error_message = str(e)
            await self.db.commit()
            raise
    
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
                # 中英文句子边界
                last_period = max(chunk.rfind("。"), chunk.rfind("."), chunk.rfind("!"), chunk.rfind("?"))
                last_newline = chunk.rfind("\n")
                split_point = max(last_period, last_newline)
                
                if split_point > chunk_size * 0.3:
                    chunk = chunk[:split_point + 1]
                    end = start + split_point + 1
            
            chunk = chunk.strip()
            if chunk:
                chunks.append(chunk)
            
            start = end - chunk_overlap if end < len(text) else len(text)
        
        return chunks
    
    async def search(
        self,
        query: str,
        kb_ids: List[str] = None,
        top_k: int = 5,
        threshold: float = 0.7,
    ) -> List[dict]:
        """语义搜索 - pgvector"""
        # 生成查询向量
        query_embedding = await self.llm.embed(query)
        
        if HAS_PGVECTOR:
            # 使用 pgvector 余弦相似度搜索
            results = await self._vector_search(query_embedding, kb_ids, top_k, threshold)
        else:
            # 回退到内存搜索
            results = await self._memory_search(query_embedding, kb_ids, top_k, threshold)
        
        return results
    
    async def _vector_search(
        self,
        query_embedding: List[float],
        kb_ids: List[str],
        top_k: int,
        threshold: float,
    ) -> List[dict]:
        """pgvector 向量搜索"""
        # 将向量转换为字符串格式
        vector_str = f"[{','.join(str(x) for x in query_embedding)}]"
        
        # 构建查询
        query = """
            SELECT 
                dc.id, dc.content, dc.chunk_index, dc.metadata,
                d.filename, d.file_type,
                dc.embedding <=> :embedding::vector as distance
            FROM document_chunks dc
            JOIN documents d ON dc.document_id = d.id
            WHERE d.status = 'done'
        """
        
        params = {"embedding": vector_str}
        
        if kb_ids:
            query += " AND dc.kb_id = ANY(:kb_ids)"
            params["kb_ids"] = kb_ids
        
        query += f" ORDER BY dc.embedding <=> :embedding::vector LIMIT {top_k}"
        
        result = await self.db.execute(text(query), params)
        rows = result.fetchall()
        
        results = []
        for row in rows:
            # 余弦距离转换为相似度: similarity = 1 - distance
            similarity = 1 - row.distance if row.distance else 0
            
            if similarity >= threshold:
                results.append({
                    "id": row.id,
                    "content": row.content,
                    "chunk_index": row.chunk_index,
                    "filename": row.filename,
                    "file_type": row.file_type,
                    "score": similarity,
                })
        
        return results
    
    async def _memory_search(
        self,
        query_embedding: List[float],
        kb_ids: List[str],
        top_k: int,
        threshold: float,
    ) -> List[dict]:
        """内存向量搜索（回退方案）"""
        # 构建查询
        stmt = select(DocumentChunk).options(
            selectinload(DocumentChunk.document)
        )
        
        if kb_ids:
            stmt = stmt.where(DocumentChunk.kb_id.in_(kb_ids))
        
        result = await self.db.execute(stmt)
        chunks = result.scalars().all()
        
        # 计算相似度
        scored_chunks = []
        for chunk in chunks:
            if chunk.embedding:
                sim = cosine_similarity(query_embedding, chunk.embedding)
                if sim >= threshold:
                    scored_chunks.append((sim, chunk))
        
        # 排序并返回 top_k
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        scored_chunks = scored_chunks[:top_k]
        
        results = []
        for score, chunk in scored_chunks:
            results.append({
                "id": chunk.id,
                "content": chunk.content,
                "chunk_index": chunk.chunk_index,
                "filename": chunk.document.filename if chunk.document else None,
                "file_type": chunk.document.file_type if chunk.document else None,
                "score": score,
            })
        
        return results
    
    async def get_context(
        self,
        query: str,
        kb_ids: List[str] = None,
        max_tokens: int = 2000,
    ) -> str:
        """获取 RAG 上下文"""
        results = await self.search(query, kb_ids, top_k=10)
        
        context_parts = []
        total_chars = 0
        max_chars = max_tokens * 4  # 粗略估计
        
        for result in results:
            content = result["content"]
            if total_chars + len(content) > max_chars:
                break
            
            # 添加来源信息
            source = f"[{result.get('filename', '未知')}]"
            context_parts.append(f"{source}\n{content}")
            total_chars += len(content)
        
        if not context_parts:
            return ""
        
        return "\n\n---\n\n".join(context_parts)
    
    async def delete_document(self, document_id: int) -> bool:
        """删除文档"""
        stmt = delete(Document).where(Document.id == document_id)
        await self.db.execute(stmt)
        await self.db.commit()
        return True
    
    async def get_documents(self, kb_id: str) -> List[Document]:
        """获取知识库中的所有文档"""
        stmt = select(Document).where(Document.kb_id == kb_id).order_by(Document.created_at.desc())
        result = await self.db.execute(stmt)
        return result.scalars().all()


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """余弦相似度"""
    import numpy as np
    a = np.array(a)
    b = np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
