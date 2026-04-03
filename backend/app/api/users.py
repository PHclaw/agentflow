"""用户 API"""
from fastapi import APIRouter, Depends
router = APIRouter()

@router.get("/me")
async def get_me():
    return {"id": "demo", "email": "demo@example.com"}
