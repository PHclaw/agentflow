"""模板 API"""
from fastapi import APIRouter
router = APIRouter()

@router.get("")
async def list_templates():
    return [
        {"id": "1", "name": "客服机器人", "category": "customer_service"},
        {"id": "2", "name": "销售助手", "category": "sales"},
        {"id": "3", "name": "HR 助手", "category": "hr"},
    ]
