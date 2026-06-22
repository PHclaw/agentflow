"""模板 API"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.agent import WorkflowTemplate

router = APIRouter()


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
        return {"error": "模板不存在"}, 404

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
