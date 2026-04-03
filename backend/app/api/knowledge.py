"""知识库 API"""
from fastapi import APIRouter
router = APIRouter()

@router.get("")
async def list_knowledge():
    return []
