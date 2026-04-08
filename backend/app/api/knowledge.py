"""
知识库 API - 文档管理和向量搜索
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
import os
import uuid
import aiofiles
from pathlib import Path

from ..core.config import settings
from ..core.database import get_db
from ..models.agent import KnowledgeBase
from ..models.document import Document, DocumentChunk
from ..services.knowledge import KnowledgeService

router = APIRouter(prefix="/api/v1/knowledge", tags=["知识库"])

UPLOAD_DIR = Path(settings.UPLOAD_DIR)
UPLOAD_DIR.mkdir(exist_ok=True)


class CreateKBRequest(BaseModel):
    name: str
    description: str = ""


class SearchRequest(BaseModel):
    query: str
    kb_ids: Optional[List[str]] = None
    top_k: int = 5


# ===== 知识库管理 =====

@router.get("")
async def list_knowledge_bases(db: AsyncSession = Depends(get_db)):
    """列出所有知识库"""
    from sqlalchemy import select
    stmt = select(KnowledgeBase).order_by(KnowledgeBase.created_at.desc())
    result = await db.execute(stmt)
    kbs = result.scalars().all()
    
    return [{
        "id": kb.id,
        "name": kb.name,
        "description": kb.description,
        "document_count": len(kb.documents) if hasattr(kb, 'documents') else 0,
        "created_at": kb.created_at.isoformat() if kb.created_at else None,
    } for kb in kbs]


@router.post("")
async def create_knowledge_base(
    data: CreateKBRequest,
    db: AsyncSession = Depends(get_db)
):
    """创建知识库"""
    service = KnowledgeService(db)
    kb = await service.create_knowledge_base(
        name=data.name,
        description=data.description,
    )
    
    return {
        "id": kb.id,
        "name": kb.name,
        "description": kb.description,
        "message": "创建成功"
    }


@router.get("/{kb_id}")
async def get_knowledge_base(
    kb_id: str,
    db: AsyncSession = Depends(get_db)
):
    """获取知识库详情"""
    from sqlalchemy import select
    
    stmt = select(KnowledgeBase).where(KnowledgeBase.id == kb_id)
    result = await db.execute(stmt)
    kb = result.scalar_one_or_none()
    
    if not kb:
        raise HTTPException(404, "知识库不存在")
    
    # 获取文档列表
    service = KnowledgeService(db, kb_id)
    docs = await service.get_documents(kb_id)
    
    return {
        "id": kb.id,
        "name": kb.name,
        "description": kb.description,
        "documents": [{
            "id": doc.id,
            "filename": doc.filename,
            "file_type": doc.file_type,
            "file_size": doc.file_size,
            "chunk_count": doc.chunk_count,
            "status": doc.status,
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
        } for doc in docs],
    }


@router.delete("/{kb_id}")
async def delete_knowledge_base(
    kb_id: str,
    db: AsyncSession = Depends(get_db)
):
    """删除知识库"""
    from sqlalchemy import delete
    
    stmt = delete(KnowledgeBase).where(KnowledgeBase.id == kb_id)
    await db.execute(stmt)
    await db.commit()
    
    return {"message": "删除成功"}


# ===== 文档管理 =====

@router.post("/{kb_id}/documents")
async def upload_document(
    kb_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """上传文档到知识库"""
    # 验证文件类型
    allowed_types = {
        "text/plain": "txt",
        "text/markdown": "md",
        "application/pdf": "pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    }
    
    file_type = allowed_types.get(file.content_type, "txt")
    
    if file.content_type not in allowed_types and not file.filename.endswith(('.txt', '.md', '.pdf', '.docx')):
        raise HTTPException(400, "不支持的文件类型，仅支持 txt, md, pdf, docx")
    
    # 检查文件大小
    content = await file.read()
    if len(content) > settings.MAX_FILE_SIZE:
        raise HTTPException(400, f"文件过大，最大支持 {settings.MAX_FILE_SIZE // 1024 // 1024}MB")
    
    # 保存文件
    file_id = str(uuid.uuid4())
    file_path = UPLOAD_DIR / f"{file_id}_{file.filename}"
    
    async with aiofiles.open(file_path, 'wb') as f:
        await f.write(content)
    
    # 提取文本内容
    text_content = await extract_text(content, file_type, file.filename)
    
    # 添加到知识库
    service = KnowledgeService(db, kb_id)
    doc = await service.add_document(
        kb_id=kb_id,
        filename=file.filename,
        content=text_content,
        file_type=file_type,
    )
    
    return {
        "id": doc.id,
        "filename": doc.filename,
        "file_type": doc.file_type,
        "chunk_count": doc.chunk_count,
        "status": doc.status,
        "message": "上传成功，已处理完成"
    }


async def extract_text(content: bytes, file_type: str, filename: str) -> str:
    """提取文件文本内容"""
    if file_type == "txt" or file_type == "md":
        return content.decode("utf-8", errors="ignore")
    
    elif file_type == "pdf":
        # PDF 文本提取
        try:
            import io
            from PyPDF2 import PdfReader
            
            reader = PdfReader(io.BytesIO(content))
            text_parts = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
            
            return "\n\n".join(text_parts)
        except Exception as e:
            # 回退到简单文本
            return content.decode("utf-8", errors="ignore")
    
    elif file_type == "docx":
        # Word 文档提取
        try:
            import io
            from docx import Document as DocxDocument
            
            doc = DocxDocument(io.BytesIO(content))
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            
            return "\n\n".join(paragraphs)
        except Exception as e:
            return content.decode("utf-8", errors="ignore")
    
    return content.decode("utf-8", errors="ignore")


@router.get("/{kb_id}/documents")
async def list_documents(
    kb_id: str,
    db: AsyncSession = Depends(get_db)
):
    """列出知识库中的文档"""
    service = KnowledgeService(db, kb_id)
    docs = await service.get_documents(kb_id)
    
    return [{
        "id": doc.id,
        "filename": doc.filename,
        "file_type": doc.file_type,
        "file_size": doc.file_size,
        "chunk_count": doc.chunk_count,
        "status": doc.status,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
    } for doc in docs]


@router.delete("/{kb_id}/documents/{doc_id}")
async def delete_document(
    kb_id: str,
    doc_id: int,
    db: AsyncSession = Depends(get_db)
):
    """删除文档"""
    service = KnowledgeService(db, kb_id)
    await service.delete_document(doc_id)
    
    return {"message": "删除成功"}


# ===== 向量搜索 =====

@router.post("/search")
async def search_knowledge(
    data: SearchRequest,
    db: AsyncSession = Depends(get_db)
):
    """语义搜索"""
    service = KnowledgeService(db)
    results = await service.search(
        query=data.query,
        kb_ids=data.kb_ids,
        top_k=data.top_k,
    )
    
    return {
        "query": data.query,
        "results": results,
        "total": len(results),
    }


@router.post("/context")
async def get_rag_context(
    data: SearchRequest,
    db: AsyncSession = Depends(get_db)
):
    """获取 RAG 上下文"""
    service = KnowledgeService(db)
    context = await service.get_context(
        query=data.query,
        kb_ids=data.kb_ids,
    )
    
    return {
        "query": data.query,
        "context": context,
    }
