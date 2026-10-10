"""
知识库 API - 文档管理和向量搜索
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
import json
import aiofiles
from pathlib import Path

from ..core.config import settings
from ..core.database import get_db
from ..core.paths import uploads_root
from ..models.agent import KnowledgeBase
from ..models.document import Document, DocumentChunk
from ..services.knowledge import EmbeddingNotConfiguredError, KnowledgeService
from app.api.auth import get_current_user_id

import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/knowledge",
    tags=["知识库"],
    dependencies=[Depends(get_current_user_id)],
)

UPLOAD_DIR = uploads_root()


class CreateKBRequest(BaseModel):
    name: str
    description: str = ""


class SearchRequest(BaseModel):
    query: str
    kb_ids: Optional[List[str]] = None
    top_k: int = 5
    #: 相关度下限。此前这个字段根本不存在，客户端传 threshold 会被静默丢弃、
    #: 一律按默认阈值过滤，表现为「明明有文档却一条都搜不到」。
    #:
    #: 默认值按实测标定：不同嵌入模型的相关度分布差异极大。例如
    #: shaw/dmeta-embedding-zh 下相关问题只有 0.26~0.40、不相关约 0.25，
    #: 分数被压缩在很窄的区间（原先默认 0.7，等于把结果几乎全挡掉）。
    #: 想按业务调召回，把这个值显式传进来即可。
    threshold: float = 0.25


async def _load_owned_kb(db: AsyncSession, kb_id: str, user_id: str) -> KnowledgeBase:
    """取知识库并校验归属。

    此前这个文件里所有接口都只校验「已登录」，任何登录用户都能看到、
    下载、删除别人的知识库。
    """
    from sqlalchemy import select

    stmt = select(KnowledgeBase).where(
        KnowledgeBase.id == kb_id,
        KnowledgeBase.user_id == user_id,
    )
    kb = (await db.execute(stmt)).scalar_one_or_none()
    if not kb:
        raise HTTPException(404, "知识库不存在")
    return kb


async def _filter_owned_kb_ids(
    db: AsyncSession, kb_ids: Optional[List[str]], user_id: str
) -> List[str]:
    """把请求里的知识库 id 过滤成当前用户拥有的那些"""
    from sqlalchemy import select

    stmt = select(KnowledgeBase.id).where(KnowledgeBase.user_id == user_id)
    if kb_ids:
        stmt = stmt.where(KnowledgeBase.id.in_(kb_ids))
    return list((await db.execute(stmt)).scalars().all())


# ===== 知识库管理 =====

@router.get("")
async def list_knowledge_bases(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """列出当前用户的知识库"""
    from sqlalchemy import select, func
    stmt = (
        select(KnowledgeBase)
        .where(KnowledgeBase.user_id == user_id)
        .order_by(KnowledgeBase.created_at.desc())
    )
    result = await db.execute(stmt)
    kbs = result.scalars().all()

    # 统计每个知识库的文档数量
    kb_list = []
    for kb in kbs:
        doc_count = await db.scalar(
            select(func.count(Document.id)).where(Document.kb_id == kb.id)
        ) or 0
        # 知识块数：此前列表接口不返回它，前端只能显示「0 个知识块」
        chunk_count = await db.scalar(
            select(func.coalesce(func.sum(Document.chunk_count), 0)).where(
                Document.kb_id == kb.id
            )
        ) or 0
        kb_list.append({
            "id": kb.id,
            "name": kb.name,
            "description": kb.description,
            "document_count": doc_count,
            "chunk_count": chunk_count,
            # 空知识库没有可索引内容，不应该永远显示「索引中」
            "status": "ready" if doc_count > 0 else "empty",
            "created_at": kb.created_at.isoformat() if kb.created_at else None,
            "updated_at": kb.updated_at.isoformat() if kb.updated_at else None,
        })

    return {"knowledge_bases": kb_list}


@router.post("")
async def create_knowledge_base(
    data: CreateKBRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """创建知识库"""
    service = KnowledgeService(db)
    kb = await service.create_knowledge_base(
        name=data.name,
        description=data.description,
        user_id=user_id,
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
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """获取知识库详情"""
    kb = await _load_owned_kb(db, kb_id, user_id)

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
            "error_message": doc.error_message,
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
        } for doc in docs],
    }


@router.delete("/{kb_id}")
async def delete_knowledge_base(
    kb_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """删除知识库（连同其文档与向量数据）"""
    from sqlalchemy import delete, select

    kb = await _load_owned_kb(db, kb_id, user_id)

    # 先删文档与分块，再删知识库本身，避免留下孤儿数据
    chunk_ids = select(DocumentChunk.document_id).where(DocumentChunk.kb_id == kb.id)
    await db.execute(delete(DocumentChunk).where(DocumentChunk.document_id.in_(chunk_ids)))
    await db.execute(delete(Document).where(Document.kb_id == kb.id))
    await db.execute(delete(KnowledgeBase).where(KnowledgeBase.id == kb.id))
    await db.commit()

    # 向量目录一并清掉，否则会残留一份孤儿索引
    try:
        import shutil

        shutil.rmtree(KnowledgeService(db, kb.id)._get_vector_store_path(kb.id), ignore_errors=True)
    except Exception as e:  # noqa: BLE001 - 清理失败不影响删除结果
        logger.warning("清理向量目录失败 kb=%s: %s", kb.id, e)

    return {"message": "删除成功"}


# ===== 文档管理 =====

@router.post("/{kb_id}/documents")
async def upload_document(
    kb_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """上传文档到知识库"""
    # 知识库必须先存在且属于当前用户
    kb = await _load_owned_kb(db, kb_id, user_id)

    # 文档入库要生成向量，缺凭证时提前给出可操作的提示。
    # 判断依据是「实际能否拿到凭证」（含设置页里配置的），
    # 而不是只看 .env —— 此前用户在设置页配好了密钥，这里仍判定为未配置。
    service = KnowledgeService(db, kb.id)
    try:
        service._get_embeddings()
    except EmbeddingNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

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
    if not content:
        raise HTTPException(400, "文件内容为空")
    if len(content) > settings.MAX_FILE_SIZE:
        raise HTTPException(400, f"文件过大，最大支持 {settings.MAX_FILE_SIZE // 1024 // 1024}MB")

    # 先提取文本，解析不了就直接报错，不要把二进制当文本存进向量库
    try:
        text_content = await extract_text(content, file_type, file.filename)
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc))

    if not text_content.strip():
        raise HTTPException(400, "文件里没有可索引的文字内容")

    # 保存原始文件（供下载）
    file_id = str(uuid.uuid4())
    stored_name = f"{file_id}_{file.filename}"
    file_path = UPLOAD_DIR / stored_name

    async with aiofiles.open(file_path, 'wb') as f:
        await f.write(content)

    # 入库并建立向量索引
    try:
        doc = await service.add_document(
            kb_id=kb.id,
            filename=file.filename,
            content=text_content,
            file_type=file_type,
            stored_path=stored_name,
        )
    except EmbeddingNotConfiguredError as exc:
        _cleanup_upload(file_path)
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:  # noqa: BLE001 - 统一成可读提示，细节记日志
        logger.exception("文档索引失败 kb=%s file=%s", kb_id, file.filename)
        _cleanup_upload(file_path)
        raise HTTPException(status_code=502, detail=f"文档索引失败：{_readable_index_error(exc)}")

    return {
        "id": doc.id,
        "filename": doc.filename,
        "file_type": doc.file_type,
        "chunk_count": doc.chunk_count,
        "status": doc.status,
        "message": "上传成功，已处理完成"
    }


def _cleanup_upload(file_path: Path) -> None:
    """索引失败时清掉已落盘的原文件，避免留下垃圾"""
    try:
        file_path.unlink(missing_ok=True)
    except OSError:  # pragma: no cover - 清理失败不影响主流程
        pass


def _readable_index_error(exc: Exception) -> str:
    """把向量库/嵌入接口的异常翻译成用户能行动的一句话"""
    text = f"{exc}".lower()
    if "401" in text or "unauthorized" in text or "invalid api key" in text:
        return "向量服务认证失败，请检查「设置 → 模型配置」里的 API Key"
    if "404" in text or "model" in text and "not found" in text:
        return "向量模型不可用，请检查模型名是否正确"
    if "connection" in text or "timeout" in text or "timed out" in text:
        return "无法连接向量服务，请检查 Base URL 是否可访问"
    if "dimension" in text or "embedding" in text:
        return "向量维度不匹配：更换向量模型后需要重新上传文档"
    return f"{exc}"[:200]


async def extract_text(content: bytes, file_type: str, filename: str) -> str:
    """提取文件文本内容。

    解析失败必须显式报错：此前 PDF 走的是未安装的 PyPDF2，
    异常被 except 吞掉后 return content.decode(...) —— 相当于把 PDF 二进制
    当 UTF-8 解出来存进向量库，检索出来全是乱码却没有任何提示。
    """
    if file_type in ("txt", "md"):
        return content.decode("utf-8", errors="ignore")

    if file_type == "pdf":
        try:
            import io
            from pypdf import PdfReader
        except ImportError as exc:  # pragma: no cover - 依赖缺失
            raise ValueError(f"PDF 解析依赖缺失：{exc}") from exc

        try:
            reader = PdfReader(io.BytesIO(content))
        except Exception as exc:
            raise ValueError(f"PDF 文件无法读取（可能已损坏）：{exc}") from exc

        text_parts = []
        for page in reader.pages:
            try:
                text = page.extract_text()
            except Exception:  # noqa: BLE001 - 单页失败不影响其余页
                continue
            if text:
                text_parts.append(text)

        text = "\n\n".join(text_parts).strip()
        if not text:
            raise ValueError(
                "这份 PDF 没有可提取的文字（可能是扫描件/图片型 PDF），"
                "请改用 txt/md，或先用工具做 OCR"
            )
        return text

    if file_type == "docx":
        try:
            import io
            from docx import Document as DocxDocument
        except ImportError as exc:  # pragma: no cover - 依赖缺失
            raise ValueError(f"Word 解析依赖缺失：{exc}") from exc

        try:
            doc = DocxDocument(io.BytesIO(content))
        except Exception as exc:
            raise ValueError(f"Word 文件无法读取（可能已损坏）：{exc}") from exc

        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        text = "\n\n".join(paragraphs).strip()
        if not text:
            raise ValueError("这份 Word 文档没有可提取的文字")
        return text

    return content.decode("utf-8", errors="ignore")


@router.get("/{kb_id}/documents")
async def list_documents(
    kb_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """列出知识库中的文档"""
    kb = await _load_owned_kb(db, kb_id, user_id)
    service = KnowledgeService(db, kb.id)
    docs = await service.get_documents(kb.id)
    
    return [{
        "id": doc.id,
        "filename": doc.filename,
        "file_type": doc.file_type,
        "file_size": doc.file_size,
        "chunk_count": doc.chunk_count,
        "status": doc.status,
        # 索引失败时把原因带出来，否则用户只看到「失败」两个字无从排查
        "error_message": doc.error_message,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
    } for doc in docs]


@router.get("/{kb_id}/documents/{doc_id}/download")
async def download_document(
    kb_id: str,
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """下载文档的原始文件"""
    kb = await _load_owned_kb(db, kb_id, user_id)

    doc = await db.get(Document, doc_id)
    if not doc or doc.kb_id != kb.id:
        raise HTTPException(404, "文档不存在")

    if not doc.stored_path:
        raise HTTPException(404, "该文档未保留原始文件（可能是早期上传的数据）")

    # 只解析 UPLOAD_DIR 下的文件，并对文件名做净化，避免路径穿越
    stored_name = Path(doc.stored_path).name
    file_path = (UPLOAD_DIR / stored_name).resolve()
    if file_path.parent != UPLOAD_DIR.resolve() or not file_path.is_file():
        raise HTTPException(404, "原始文件已丢失，请重新上传")

    return FileResponse(
        file_path,
        filename=doc.filename,
        media_type="application/octet-stream",
    )


@router.delete("/{kb_id}/documents/{doc_id}")
async def delete_document(
    kb_id: str,
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """删除文档"""
    kb = await _load_owned_kb(db, kb_id, user_id)
    service = KnowledgeService(db, kb.id)
    await service.delete_document(doc_id)

    return {"message": "删除成功"}


# ===== 向量搜索 =====

@router.post("/search")
async def search_knowledge(
    data: SearchRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """语义搜索"""
    # 只能搜自己的知识库
    kb_ids = await _filter_owned_kb_ids(db, data.kb_ids, user_id)

    service = KnowledgeService(db)
    try:
        results = await service.search(
            query=data.query,
            kb_ids=kb_ids or None,
            top_k=data.top_k,
            threshold=data.threshold,
        )
    except EmbeddingNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:  # noqa: BLE001 - 检索失败要能看出原因
        logger.exception("知识库检索失败")
        raise HTTPException(status_code=502, detail=f"检索失败：{_readable_index_error(exc)}")

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


# ===== LangChain RAG 链 =====

class RAGRequest(BaseModel):
    query: str
    kb_ids: Optional[List[str]] = None
    system_prompt: Optional[str] = None
    model: Optional[str] = "gpt-4o-mini"
    temperature: float = 0.7


class ChatHistoryRequest(BaseModel):
    query: str
    chat_history: List[Dict[str, str]] = []
    kb_ids: Optional[List[str]] = None
    system_prompt: Optional[str] = None


@router.post("/rag")
async def rag_query(
    data: RAGRequest,
    db: AsyncSession = Depends(get_db)
):
    """RAG 查询 - 检索 + 生成"""
    service = KnowledgeService(db)
    result = await service.rag_chain(
        query=data.query,
        kb_ids=data.kb_ids,
        system_prompt=data.system_prompt,
        model=data.model,
        temperature=data.temperature,
    )
    
    return {
        "query": data.query,
        "answer": result,
    }


@router.post("/rag/stream")
async def rag_query_stream(
    data: RAGRequest,
    db: AsyncSession = Depends(get_db)
):
    """RAG 查询 - 流式输出"""
    service = KnowledgeService(db)
    
    async def generate():
        async for chunk in service.rag_chain_stream(
            query=data.query,
            kb_ids=data.kb_ids,
            system_prompt=data.system_prompt,
            model=data.model,
            temperature=data.temperature,
        ):
            yield f"data: {json.dumps({'content': chunk})}\n\n"
        yield "data: [DONE]\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.post("/rag/chat")
async def rag_chat_with_history(
    data: ChatHistoryRequest,
    db: AsyncSession = Depends(get_db)
):
    """带历史记录的 RAG 问答"""
    service = KnowledgeService(db)
    result = await service.query_with_history(
        query=data.query,
        chat_history=data.chat_history,
        kb_ids=data.kb_ids,
        system_prompt=data.system_prompt,
    )
    
    return {
        "query": data.query,
        "answer": result,
        "sources": await service.search(data.query, data.kb_ids, top_k=3),
    }


@router.get("/{kb_id}/stats")
async def get_kb_stats(
    kb_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """获取知识库统计信息"""
    kb = await _load_owned_kb(db, kb_id, user_id)
    service = KnowledgeService(db, kb.id)
    stats = await service.get_kb_stats(kb.id)
    return stats


class RerankRequest(BaseModel):
    query: str
    results: List[dict] = []
    top_n: int = 5


@router.post("/rerank")
async def rerank_results(
    data: RerankRequest,
):
    """对搜索结果进行重排序"""
    if not data.results:
        return {"results": []}

    try:
        from langchain_community.cross_encoders import HuggingFaceCrossEncoder

        model = HuggingFaceCrossEncoder(model_name="BAAI/bge-reranker-base")

        contents = [r.get("content", "") for r in data.results]
        scores = model.predict([(data.query, c) for c in contents])

        # 排序
        ranked = list(zip(data.results, scores))
        ranked.sort(key=lambda x: x[1], reverse=True)

        return {
            "results": [
                {**r, "rerank_score": float(s)}
                for r, s in ranked[:data.top_n]
            ]
        }
    except Exception as e:
        # 降级：按原始顺序返回
        return {"results": data.results[:data.top_n], "fallback": True, "error": str(e)}
