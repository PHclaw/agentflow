"""
知识库 API - 内存存储版本
"""
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import uuid

from .auth import get_current_user_id

router = APIRouter(prefix="/api/v1/knowledge", tags=["知识库"])


class CreateKBRequest(BaseModel):
    name: str
    description: str = ""


class SearchRequest(BaseModel):
    query: str
    kb_ids: Optional[List[str]] = None
    top_k: int = 5


# ===== 内存存储 =====
_kb_storage = {}  # kb_id -> {id, name, description, user_id, documents, created_at}
_doc_storage = {}  # doc_id -> {id, kb_id, filename, content, file_type, chunk_count, status, created_at}


# ===== 知识库管理 =====

@router.get("")
async def list_knowledge_bases(user_id: str = None):
    """列出所有知识库"""
    try:
        user_id = get_current_user_id()
    except:
        user_id = "default"
    
    kbs = [kb for kb in _kb_storage.values() if kb["user_id"] == user_id]
    
    return [{
        "id": kb["id"],
        "name": kb["name"],
        "description": kb["description"],
        "document_count": len(kb["documents"]),
        "created_at": kb["created_at"],
    } for kb in sorted(kbs, key=lambda x: x["created_at"], reverse=True)]


@router.post("")
async def create_knowledge_base(
    data: CreateKBRequest,
    user_id: str = None
):
    """创建知识库"""
    try:
        user_id = get_current_user_id()
    except:
        user_id = "default"
    
    kb_id = str(uuid.uuid4())[:8]
    kb = {
        "id": kb_id,
        "user_id": user_id,
        "name": data.name,
        "description": data.description,
        "documents": [],
        "created_at": datetime.now().isoformat(),
    }
    _kb_storage[kb_id] = kb
    
    return {
        "id": kb_id,
        "name": data.name,
        "description": data.description,
        "message": "创建成功"
    }


@router.get("/{kb_id}")
async def get_knowledge_base(kb_id: str):
    """获取知识库详情"""
    if kb_id not in _kb_storage:
        raise HTTPException(404, "知识库不存在")
    
    kb = _kb_storage[kb_id]
    docs = [doc for doc in _doc_storage.values() if doc["kb_id"] == kb_id]
    
    return {
        "id": kb["id"],
        "name": kb["name"],
        "description": kb["description"],
        "documents": [{
            "id": doc["id"],
            "filename": doc["filename"],
            "file_type": doc["file_type"],
            "file_size": len(doc["content"]) if doc.get("content") else 0,
            "chunk_count": doc["chunk_count"],
            "status": doc["status"],
            "created_at": doc["created_at"],
        } for doc in docs],
    }


@router.delete("/{kb_id}")
async def delete_knowledge_base(kb_id: str):
    """删除知识库"""
    if kb_id not in _kb_storage:
        raise HTTPException(404, "知识库不存在")
    
    # 删除关联文档
    doc_ids_to_delete = [doc_id for doc_id, doc in _doc_storage.items() if doc["kb_id"] == kb_id]
    for doc_id in doc_ids_to_delete:
        del _doc_storage[doc_id]
    
    del _kb_storage[kb_id]
    
    return {"message": "删除成功"}


# ===== 文档管理 =====

@router.post("/{kb_id}/documents")
async def upload_document(kb_id: str, file: UploadFile = File(...)):
    """上传文档到知识库"""
    if kb_id not in _kb_storage:
        raise HTTPException(404, "知识库不存在")
    
    # 验证文件类型
    allowed_extensions = {'.txt', '.md', '.pdf', '.docx'}
    file_ext = '.' + file.filename.split('.')[-1].lower() if '.' in file.filename else ''
    
    if file_ext not in allowed_extensions:
        raise HTTPException(400, "不支持的文件类型，仅支持 txt, md, pdf, docx")
    
    # 读取内容
    content = await file.read()
    
    # 检查文件大小 (限制 10MB)
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(400, "文件过大，最大支持 10MB")
    
    # 创建文档记录
    doc_id = len(_doc_storage) + 1
    text_content = content.decode("utf-8", errors="ignore")
    
    # 简单分块 (每500字符一块)
    chunk_size = 500
    chunks = [text_content[i:i+chunk_size] for i in range(0, len(text_content), chunk_size)]
    
    doc = {
        "id": doc_id,
        "kb_id": kb_id,
        "filename": file.filename,
        "content": text_content,
        "file_type": file_ext[1:],
        "chunk_count": len(chunks),
        "status": "done",
        "created_at": datetime.now().isoformat(),
    }
    _doc_storage[doc_id] = doc
    
    # 更新知识库文档列表
    _kb_storage[kb_id]["documents"].append(doc_id)
    
    return {
        "id": doc_id,
        "filename": file.filename,
        "file_type": file_ext[1:],
        "chunk_count": len(chunks),
        "status": "done",
        "message": "上传成功"
    }


@router.get("/{kb_id}/documents")
async def list_documents(kb_id: str):
    """列出知识库中的文档"""
    if kb_id not in _kb_storage:
        raise HTTPException(404, "知识库不存在")
    
    docs = [doc for doc in _doc_storage.values() if doc["kb_id"] == kb_id]
    
    return [{
        "id": doc["id"],
        "filename": doc["filename"],
        "file_type": doc["file_type"],
        "file_size": len(doc["content"]) if doc.get("content") else 0,
        "chunk_count": doc["chunk_count"],
        "status": doc["status"],
        "created_at": doc["created_at"],
    } for doc in docs]


@router.delete("/{kb_id}/documents/{doc_id}")
async def delete_document(kb_id: str, doc_id: int):
    """删除文档"""
    if kb_id not in _kb_storage:
        raise HTTPException(404, "知识库不存在")
    
    doc_id_str = str(doc_id)
    if doc_id not in _doc_storage:
        raise HTTPException(404, "文档不存在")
    
    # 从知识库中移除
    if doc_id in _kb_storage[kb_id]["documents"]:
        _kb_storage[kb_id]["documents"].remove(doc_id)
    
    del _doc_storage[doc_id]
    
    return {"message": "删除成功"}


# ===== 向量搜索 (简化版 - 关键词匹配) =====

@router.post("/search")
async def search_knowledge(data: SearchRequest):
    """语义搜索"""
    results = []
    
    kb_ids = data.kb_ids or list(_kb_storage.keys())
    
    for kb_id in kb_ids:
        if kb_id not in _kb_storage:
            continue
        
        docs = [doc for doc in _doc_storage.values() if doc["kb_id"] == kb_id]
        
        for doc in docs:
            content = doc.get("content", "")
            query_lower = data.query.lower()
            
            # 简单的关键词匹配
            if query_lower in content.lower():
                # 找到匹配位置
                idx = content.lower().find(query_lower)
                # 提取周围文本
                start = max(0, idx - 100)
                end = min(len(content), idx + len(data.query) + 100)
                snippet = content[start:end]
                
                results.append({
                    "id": doc["id"],
                    "content": snippet,
                    "filename": doc["filename"],
                    "score": 0.8,  # 简化：所有匹配都是0.8分
                })
    
    # 按分数排序
    results = sorted(results, key=lambda x: x["score"], reverse=True)[:data.top_k]
    
    return {
        "query": data.query,
        "results": results,
        "total": len(results),
    }


@router.post("/context")
async def get_rag_context(data: SearchRequest):
    """获取 RAG 上下文"""
    search_results = await search_knowledge(data)
    
    context_parts = []
    for result in search_results["results"]:
        context_parts.append(f"[{result['filename']}]\n{result['content']}")
    
    return {
        "query": data.query,
        "context": "\n\n---\n\n".join(context_parts),
    }
