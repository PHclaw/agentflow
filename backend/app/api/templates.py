"""模板 API"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.agent import WorkflowTemplate

router = APIRouter()


# ===== 模型列表 API（必须在 /{template_id} 之前注册）=====

SUPPORTED_MODELS = [
    # OpenAI
    {"id": "gpt-4o", "name": "GPT-4o", "provider": "openai", "tier": "pro"},
    {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "provider": "openai", "tier": "free"},
    {"id": "gpt-4.1", "name": "GPT-4.1", "provider": "openai", "tier": "pro"},
    {"id": "gpt-4.1-mini", "name": "GPT-4.1 Mini", "provider": "openai", "tier": "free"},
    {"id": "o3", "name": "o3", "provider": "openai", "tier": "pro"},
    {"id": "o4-mini", "name": "o4-mini", "provider": "openai", "tier": "pro"},
    # Anthropic
    {"id": "claude-sonnet-4-20250514", "name": "Claude Sonnet 4", "provider": "anthropic", "tier": "pro"},
    {"id": "claude-3-5-haiku-20241022", "name": "Claude 3.5 Haiku", "provider": "anthropic", "tier": "free"},
    # DeepSeek
    {"id": "deepseek-chat", "name": "DeepSeek V3", "provider": "deepseek", "tier": "free"},
    {"id": "deepseek-reasoner", "name": "DeepSeek R1", "provider": "deepseek", "tier": "pro"},
]


@router.get("/models/list")
async def list_models():
    """获取支持的模型列表"""
    return {"models": SUPPORTED_MODELS}


# ===== 模板 API =====

@router.get("")
async def list_templates(db: AsyncSession = Depends(get_db)):
    """获取公开模板列表"""
    result = await db.execute(
        select(WorkflowTemplate).where(WorkflowTemplate.is_public == True)
    )
    templates = result.scalars().all()
    return [
        {
            "id": t.id,
            "name": t.name,
            "category": t.category,
            "description": t.description or "",
            "icon": t.icon or "template",
            "color": t.color or "from-blue-500 to-indigo-600",
            "features": t.features or [],
            "use_count": t.use_count or 0,
        }
        for t in templates
    ]


@router.get("/{template_id}")
async def get_template(template_id: str, db: AsyncSession = Depends(get_db)):
    """获取模板详情（含工作流定义）"""
    result = await db.execute(
        select(WorkflowTemplate).where(
            WorkflowTemplate.id == template_id,
            WorkflowTemplate.is_public == True,
        )
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")

    return {
        "id": template.id,
        "name": template.name,
        "category": template.category,
        "description": template.description or "",
        "icon": template.icon or "template",
        "color": template.color or "from-blue-500 to-indigo-600",
        "features": template.features or [],
        "workflow_definition": template.workflow_definition,
        "preview_image": template.preview_image or "",
        "use_count": template.use_count or 0,
    }
