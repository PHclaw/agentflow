"""
文件上传 API
"""
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import os
import uuid
from pathlib import Path

from ..core.database import get_db
from ..core.config import settings

router = APIRouter(prefix="/upload", tags=["upload"])

ALLOWED_EXTENSIONS = {'.pdf', '.doc', '.docx', '.txt', '.md', '.csv', '.xlsx', '.xls'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


@router.post("/{agent_id}")
async def upload_document(
    agent_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """上传文档到 Agent 知识库"""
    # 检查文件扩展名
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"不支持的文件格式: {ext}")
    
    # 检查文件大小
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(400, "文件大小超过 50MB 限制")
    
    # 生成唯一文件名
    filename = f"{uuid.uuid4()}{ext}"
    filepath = Path(settings.UPLOAD_DIR) / agent_id / filename
    
    # 确保目录存在
    filepath.parent.mkdir(parents=True, exist_ok=True)
    
    # 保存文件
    with open(filepath, "wb") as f:
        f.write(content)
    
    return {
        "filename": filename,
        "original_filename": file.filename,
        "size": len(content),
        "path": str(filepath),
    }


@router.get("/{filename}")
async def get_upload_url(filename: str):
    """获取上传文件的访问 URL"""
    return {
        "url": f"/uploads/{filename}",
    }
