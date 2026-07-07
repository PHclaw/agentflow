"""
知识库服务 - LangChain RAG 实现
"""
from typing import List, Optional, Dict, Any, AsyncIterator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, text
from sqlalchemy.orm import selectinload
import json
import os
import uuid
import io
from datetime import datetime as dt
from pathlib import Path

from ..models.agent import KnowledgeBase
from ..models.document import Document, DocumentChunk
from ..services.llm import LLMService
from ..core.config import settings

def datetime_now():
    """返回不带时区的 datetime，避免数据库时区冲突"""
    return dt.now()

# LangChain imports
from langchain_core.documents import Document as LCDocument
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.document_loaders import (
    TextLoader,
    UnstructuredWordDocumentLoader,
    UnstructuredHTMLLoader,
    UnstructuredMarkdownLoader,
)
from langchain_community.document_loaders.pdf import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter, MarkdownTextSplitter
from langchain_community.vectorstores import Chroma, FAISS

# 向量存储缓存
_vector_stores: Dict[str, Any] = {}


class KnowledgeService:
    """知识库服务 - 基于 LangChain"""
    
    def __init__(self, db: AsyncSession, kb_id: str = None):
        self.db = db
        self.kb_id = kb_id
        self.llm = LLMService()
        self._vector_store = None
    
    def _get_embeddings(self):
        """获取嵌入模型"""
        return OpenAIEmbeddings(
            api_key=settings.OPENAI_API_KEY,
            model="text-embedding-3-small"
        )
    
    def _get_llm(self, model: str = None, temperature: float = 0.7):
        """获取 LLM 模型"""
        return ChatOpenAI(
            api_key=settings.OPENAI_API_KEY,
            model=model or settings.OPENAI_MODEL,
            temperature=temperature
        )
    
    def _get_vector_store_path(self, kb_id: str) -> Path:
        """获取向量存储路径"""
        return Path(settings.UPLOAD_DIR) / "vectorstore" / kb_id
    
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
            agent_id=None,
        )
        self.db.add(kb)
        await self.db.commit()
        await self.db.refresh(kb)
        
        # 创建向量存储目录
        vs_path = self._get_vector_store_path(kb.id)
        vs_path.mkdir(parents=True, exist_ok=True)
        
        return kb
    
    async def add_document(
        self,
        kb_id: str,
        filename: str,
        content: str,
        file_type: str = "txt",
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ) -> Document:
        """添加文档 - 使用 LangChain 处理"""
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
            # 使用 LangChain 加载文档
            lc_doc = LCDocument(
                page_content=content,
                metadata={
                    "source": filename,
                    "file_type": file_type,
                    "document_id": doc.id,
                }
            )
            
            # 文本分块 - 使用 RecursiveCharacterTextSplitter
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                length_function=len,
                separators=["\n\n", "\n", "。", ". ", " ", ""]
            )
            chunks = text_splitter.split_documents([lc_doc])
            
            # 获取或创建向量存储
            vector_store = await self._get_or_create_vector_store(kb_id)
            
            # 添加到向量存储
            texts = [c.page_content for c in chunks]
            metadatas = [c.metadata for c in chunks]
            vector_store.add_texts(texts=texts, metadatas=metadatas)
            
            # 保存向量存储
            await self._save_vector_store(kb_id, vector_store)
            
            # 保存分块信息到数据库
            for i, chunk_content in enumerate(chunks):
                chunk = DocumentChunk(
                    document_id=doc.id,
                    kb_id=kb_id,
                    chunk_index=i,
                    content=chunk_content,
                    metadata=json.dumps(chunks[i].metadata),
                )
                self.db.add(chunk)
            
            # 更新文档状态
            doc.status = "done"
            doc.chunk_count = len(chunks)
            doc.processed_at = datetime_now()

            await self.db.commit()
            await self.db.refresh(doc)

            return doc

        except Exception as e:
            doc.status = "failed"
            doc.error_message = str(e)
            await self.db.commit()
            raise

    async def process_document(
        self,
        doc_id: int,
        content: str,
        file_path: str = None,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ):
        """处理文档 - 分块和向量化"""
        doc = await self.db.get(Document, doc_id)
        if not doc:
            raise ValueError(f"文档不存在：{doc_id}")

        kb_id = doc.kb_id

        try:
            # 使用 LangChain 加载文档
            from langchain_core.documents import Document as LCDocument
            from langchain_text_splitters import RecursiveCharacterTextSplitter

            lc_doc = LCDocument(
                page_content=content,
                metadata={
                    "source": file_path or doc.filename,
                    "file_type": doc.file_type,
                    "document_id": doc.id,
                }
            )

            # 文本分块
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                length_function=len,
                separators=["\n\n", "\n", "。", ". ", " ", ""]
            )
            chunks = text_splitter.split_documents([lc_doc])

            # 获取或创建向量存储
            vector_store = await self._get_or_create_vector_store(kb_id)

            # 添加到向量存储
            texts = [c.page_content for c in chunks]
            metadatas = [c.metadata for c in chunks]
            vector_store.add_texts(texts=texts, metadatas=metadatas)

            # 保存向量存储
            await self._save_vector_store(kb_id, vector_store)

            # 保存分块信息到数据库
            for i, chunk_content in enumerate(chunks):
                chunk = DocumentChunk(
                    document_id=doc.id,
                    kb_id=kb_id,
                    chunk_index=i,
                    content=chunk_content.page_content,
                    metadata=json.dumps(chunk_content.metadata),
                )
                self.db.add(chunk)

            # 更新文档状态
            doc.status = "done"
            doc.chunk_count = len(chunks)
            doc.processed_at = datetime_now()

            await self.db.commit()
            await self.db.refresh(doc)

            return doc

        except Exception as e:
            doc.status = "failed"
            doc.error_message = str(e)
            await self.db.commit()
            raise

    async def _get_or_create_vector_store(self, kb_id: str):
        """获取或创建向量存储"""
        if kb_id in _vector_stores:
            return _vector_stores[kb_id]

        vs_path = self._get_vector_store_path(kb_id)

        # 检查持久化的向量存储
        if vs_path.exists():
            try:
                vector_store = Chroma(
                    persist_directory=str(vs_path),
                    embedding_function=self._get_embeddings()
                )
                _vector_stores[kb_id] = vector_store
                return vector_store
            except Exception:
                pass

        # 创建新的向量存储
        vector_store = Chroma(
            persist_directory=str(vs_path),
            embedding_function=self._get_embeddings()
        )
        _vector_stores[kb_id] = vector_store
        return vector_store
    
    async def _save_vector_store(self, kb_id: str, vector_store: Chroma):
        """持久化向量存储"""
        try:
            vector_store.persist()
        except Exception:
            pass  # Chroma 会自动持久化

    async def search_in_kb(
        self,
        query: str,
        top_k: int = 5,
        threshold: float = 0.7,
    ) -> List[dict]:
        """在知识库中搜索"""
        if not self.kb_id:
            return []

        return await self.search(
            query=query,
            kb_ids=[self.kb_id],
            top_k=top_k,
            threshold=threshold,
        )

    async def get_documents(self, kb_id: str) -> List[Document]:
        """获取知识库中的所有文档"""
        stmt = select(Document).where(Document.kb_id == kb_id)
        result = await self.db.execute(stmt)
        return result.scalars().all()
    
    async def search(
        self,
        query: str,
        kb_ids: List[str] = None,
        top_k: int = 5,
        threshold: float = 0.7,
        filter_metadata: Dict = None,
    ) -> List[dict]:
        """语义搜索 - LangChain Retriever"""
        kb_id = kb_ids[0] if kb_ids else self.kb_id
        if not kb_id:
            return []
        
        try:
            vector_store = await self._get_or_create_vector_store(kb_id)
            
            # 使用 similarity_search_with_relevance_scores
            results = vector_store.similarity_search_with_relevance_scores(
                query=query,
                k=top_k,
                filter=filter_metadata
            )
            
            search_results = []
            for doc, score in results:
                relevance = 1 - score if score > 0 else score
                if relevance >= threshold:
                    search_results.append({
                        "id": f"{kb_id}_{doc.metadata.get('document_id', 'unknown')}",
                        "content": doc.page_content,
                        "chunk_index": doc.metadata.get("chunk_index", 0),
                        "filename": doc.metadata.get("source", "unknown"),
                        "file_type": doc.metadata.get("file_type", "txt"),
                        "score": relevance,
                        "metadata": doc.metadata,
                    })
            
            return search_results
            
        except Exception as e:
            print(f"Search error: {e}")
            return []
    
    async def similarity_search(
        self,
        query: str,
        kb_ids: List[str] = None,
        top_k: int = 5,
    ) -> List[LCDocument]:
        """纯相似度搜索"""
        kb_id = kb_ids[0] if kb_ids else self.kb_id
        if not kb_id:
            return []
        
        try:
            vector_store = await self._get_or_create_vector_store(kb_id)
            return vector_store.similarity_search(query, k=top_k)
        except Exception:
            return []
    
    async def get_context(
        self,
        query: str,
        kb_ids: List[str] = None,
        max_tokens: int = 2000,
        top_k: int = 10,
    ) -> str:
        """获取 RAG 上下文"""
        results = await self.search(query, kb_ids, top_k=top_k)
        
        context_parts = []
        total_chars = 0
        max_chars = max_tokens * 4
        
        for result in results:
            content = result["content"]
            if total_chars + len(content) > max_chars:
                break
            
            source = f"[{result.get('filename', '未知')}]"
            context_parts.append(f"{source}\n{content}")
            total_chars += len(content)
        
        if not context_parts:
            return ""
        
        return "\n\n---\n\n".join(context_parts)
    
    async def rag_chain(
        self,
        query: str,
        kb_ids: List[str] = None,
        system_prompt: str = None,
        model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """RAG 链 - 检索 + 生成"""
        kb_id = kb_ids[0] if kb_ids else self.kb_id
        if not kb_id:
            return "请先选择知识库"
        
        try:
            vector_store = await self._get_or_create_vector_store(kb_id)
            retriever = vector_store.as_retriever(search_kwargs={"k": 5})
            
            # RAG Prompt
            default_prompt = """你是一个助手，需要根据提供的上下文信息回答用户的问题。
如果上下文中没有相关信息，请如实告知用户你无法从提供的内容中找到答案。

上下文信息:
{context}

用户问题: {question}

请基于上下文信息给出回答:"""
            
            prompt = ChatPromptTemplate.from_template(system_prompt or default_prompt)
            llm = self._get_llm(model, temperature)
            
            # 构建 RAG 链
            def format_docs(docs):
                return "\n\n---\n\n".join([d.page_content for d in docs])
            
            rag_chain = (
                {"context": retriever | format_docs, "question": RunnablePassthrough()}
                | prompt
                | llm
                | StrOutputParser()
            )
            
            result = await rag_chain.ainvoke(query)
            return result
            
        except Exception as e:
            return f"RAG 处理出错: {str(e)}"
    
    async def rag_chain_stream(
        self,
        query: str,
        kb_ids: List[str] = None,
        system_prompt: str = None,
        model: str = None,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """RAG 链 - 流式输出"""
        kb_id = kb_ids[0] if kb_ids else self.kb_id
        if not kb_id:
            yield "请先选择知识库"
            return
        
        try:
            vector_store = await self._get_or_create_vector_store(kb_id)
            retriever = vector_store.as_retriever(search_kwargs={"k": 5})
            
            default_prompt = """你是一个助手，需要根据提供的上下文信息回答用户的问题。
如果上下文中没有相关信息，请如实告知用户你无法从提供的内容中找到答案。

上下文信息:
{context}

用户问题: {question}

请基于上下文信息给出回答:"""
            
            prompt = ChatPromptTemplate.from_template(system_prompt or default_prompt)
            llm = self._get_llm(model, temperature)
            
            def format_docs(docs):
                return "\n\n---\n\n".join([d.page_content for d in docs])
            
            rag_chain = (
                {"context": retriever | format_docs, "question": RunnablePassthrough()}
                | prompt
                | llm
            )
            
            async for chunk in rag_chain.astream(query):
                if chunk.content:
                    yield chunk.content
            
        except Exception as e:
            yield f"RAG 处理出错: {str(e)}"
    
    async def delete_document(self, document_id: int) -> bool:
        """删除文档"""
        # 获取文档信息
        stmt = select(Document).where(Document.id == document_id)
        result = await self.db.execute(stmt)
        doc = result.scalar_one_or_none()
        
        if not doc:
            return False
        
        kb_id = doc.kb_id
        
        # 从数据库删除
        stmt = delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
        await self.db.execute(stmt)
        
        stmt = delete(Document).where(Document.id == document_id)
        await self.db.execute(stmt)
        
        await self.db.commit()
        
        # 重建向量存储（删除该文档的嵌入）
        await self._rebuild_vector_store(kb_id)
        
        return True
    
    async def _rebuild_vector_store(self, kb_id: str):
        """重建向量存储"""
        # 获取所有分块
        stmt = select(DocumentChunk).where(
            DocumentChunk.kb_id == kb_id
        ).join(Document).where(Document.status == "done")
        
        result = await self.db.execute(stmt)
        chunks = result.scalars().all()
        
        if not chunks:
            # 清空向量存储
            if kb_id in _vector_stores:
                del _vector_stores[kb_id]
            
            vs_path = self._get_vector_store_path(kb_id)
            import shutil
            if vs_path.exists():
                shutil.rmtree(vs_path)
            return
        
        # 重建
        vector_store = await self._get_or_create_vector_store(kb_id)
        
        # 删除旧数据并重新添加
        vector_store.delete_collection()
        vector_store = Chroma(
            persist_directory=str(self._get_vector_store_path(kb_id)),
            embedding_function=self._get_embeddings()
        )
        
        texts = [c.content for c in chunks]
        metadatas = [json.loads(c.metadata) if c.metadata else {} for c in chunks]
        
        vector_store.add_texts(texts=texts, metadatas=metadatas)
        await self._save_vector_store(kb_id, vector_store)
        _vector_stores[kb_id] = vector_store
    
    async def get_documents(self, kb_id: str) -> List[Document]:
        """获取知识库中的所有文档"""
        stmt = select(Document).where(Document.kb_id == kb_id).order_by(Document.created_at.desc())
        result = await self.db.execute(stmt)
        return result.scalars().all()
    
    async def get_kb_stats(self, kb_id: str) -> Dict[str, Any]:
        """获取知识库统计信息"""
        # 文档数量
        stmt = select(Document).where(Document.kb_id == kb_id)
        result = await self.db.execute(stmt)
        docs = result.scalars().all()
        
        # 分块数量
        stmt = select(DocumentChunk).where(DocumentChunk.kb_id == kb_id)
        result = await self.db.execute(stmt)
        chunks = result.scalars().all()
        
        return {
            "document_count": len(docs),
            "chunk_count": len(chunks),
            "total_size": sum(d.file_size for d in docs),
            "done_count": len([d for d in docs if d.status == "done"]),
            "failed_count": len([d for d in docs if d.status == "failed"]),
        }
    
    async def query_with_history(
        self,
        query: str,
        chat_history: List[Dict[str, str]],
        kb_ids: List[str] = None,
        system_prompt: str = None,
    ) -> str:
        """带历史记录的问答"""
        kb_id = kb_ids[0] if kb_ids else self.kb_id
        if not kb_id:
            return "请先选择知识库"
        
        try:
            vector_store = await self._get_or_create_vector_store(kb_id)
            retriever = vector_store.as_retriever(search_kwargs={"k": 5})
            
            # 构建历史消息
            history_text = ""
            for msg in chat_history[-5:]:  # 最近5条
                role = "用户" if msg.get("role") == "user" else "助手"
                history_text += f"{role}: {msg.get('content')}\n"
            
            default_prompt = f"""你是一个助手，需要根据提供的上下文信息回答用户的问题。
请结合对话历史来理解用户意图。

对话历史:
{history_text}

上下文信息:
{{context}}

用户问题: {{question}}

请基于上下文信息和对话历史给出回答:"""
            
            prompt = ChatPromptTemplate.from_template(system_prompt or default_prompt)
            llm = self._get_llm()
            
            def format_docs(docs):
                return "\n\n---\n\n".join([d.page_content for d in docs])
            
            rag_chain = (
                {"context": retriever | format_docs, "question": RunnablePassthrough()}
                | prompt
                | llm
                | StrOutputParser()
            )
            
            result = await rag_chain.ainvoke(query)
            return result
            
        except Exception as e:
            return f"处理出错: {str(e)}"


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """余弦相似度"""
    import numpy as np
    a = np.array(a)
    b = np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))
