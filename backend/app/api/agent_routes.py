"""Agent 增强路由 - 版本控制、统计、模板"""
from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
import json

from app.core.logging import get_logger
from app.core.cache import cache, generate_cache_key

router = APIRouter()
logger = get_logger("agent_routes")


# ===== 请求/响应模型 =====

class AgentStatsResponse(BaseModel):
    """Agent 统计响应"""
    agent_id: str
    total_conversations: int
    total_messages: int
    total_tokens: int
    avg_response_time_ms: float
    last_used: Optional[str]
    created_at: str
    success_rate: float


class AgentVersionResponse(BaseModel):
    """Agent 版本响应"""
    versions: List[dict]
    current_version: str


class AgentDuplicateRequest(BaseModel):
    """复制 Agent 请求"""
    name: str
    description: Optional[str] = None


class AgentExportResponse(BaseModel):
    """导出 Agent 请求"""
    include_knowledge: bool = True
    include_conversations: bool = False


# ===== Agent 统计 API =====

@router.get("/{agent_id}/stats", response_model=AgentStatsResponse)
async def get_agent_stats(agent_id: str):
    """
    获取 Agent 使用统计
    """
    # 模拟统计数据（生产环境应从数据库查询）
    return AgentStatsResponse(
        agent_id=agent_id,
        total_conversations=156,
        total_messages=2847,
        total_tokens=1250000,
        avg_response_time_ms=850.5,
        last_used=datetime.utcnow().isoformat(),
        created_at=datetime.utcnow().isoformat(),
        success_rate=0.95
    )


@router.get("/{agent_id}/versions", response_model=AgentVersionResponse)
async def get_agent_versions(agent_id: str):
    """
    获取 Agent 版本历史
    """
    # 模拟版本历史
    return AgentVersionResponse(
        versions=[
            {
                "version": "v2.1.0",
                "created_at": datetime.utcnow().isoformat(),
                "changes": ["优化知识库检索逻辑", "添加新的响应模板"],
                "is_current": True
            },
            {
                "version": "v2.0.0",
                "created_at": datetime.utcnow().isoformat(),
                "changes": ["全新工作流引擎", "支持 WebSocket"],
                "is_current": False
            },
            {
                "version": "v1.0.0",
                "created_at": datetime.utcnow().isoformat(),
                "changes": ["初始版本"],
                "is_current": False
            }
        ],
        current_version="v2.1.0"
    )


@router.post("/{agent_id}/versions/{version}/rollback")
async def rollback_agent_version(agent_id: str, version: str):
    """
    回滚到指定版本
    """
    logger.info(f"Rolling back agent {agent_id} to version {version}")
    return {
        "status": "success",
        "message": f"Agent 已回滚到版本 {version}",
        "new_version": version
    }


@router.post("/{agent_id}/duplicate")
async def duplicate_agent(agent_id: str, request: AgentDuplicateRequest):
    """
    复制 Agent
    """
    logger.info(f"Duplicating agent {agent_id} as '{request.name}'")
    
    # 模拟创建新 Agent
    return {
        "status": "success",
        "agent_id": f"new-agent-{agent_id}",
        "name": request.name,
        "description": request.description or f"{request.name} 的副本",
        "created_at": datetime.utcnow().isoformat()
    }


@router.get("/{agent_id}/export")
async def export_agent(agent_id: str, include_knowledge: bool = True):
    """
    导出 Agent 配置
    """
    # 模拟导出
    export_data = {
        "agent_id": agent_id,
        "exported_at": datetime.utcnow().isoformat(),
        "version": "2.0.0",
        "config": {
            "name": "示例 Agent",
            "model": "gpt-4o-mini",
            "temperature": 0.7,
            "workflow_definition": {}
        },
        "knowledge_bases": [] if not include_knowledge else [
            {"id": "kb-1", "name": "产品文档", "document_count": 25}
        ]
    }
    
    return export_data


@router.post("/{agent_id}/import")
async def import_agent(agent_id: str, data: dict):
    """
    导入 Agent 配置
    """
    logger.info(f"Importing agent data for {agent_id}")
    return {
        "status": "success",
        "agent_id": agent_id,
        "imported_at": datetime.utcnow().isoformat()
    }


@router.get("/{agent_id}/health")
async def check_agent_health(agent_id: str):
    """
    检查 Agent 健康状态
    """
    return {
        "agent_id": agent_id,
        "status": "healthy",
        "checks": {
            "workflow_valid": True,
            "model_available": True,
            "knowledge_bases_accessible": True,
            "webhook_reachable": True
        },
        "last_check": datetime.utcnow().isoformat()
    }


@router.post("/{agent_id}/validate")
async def validate_agent(agent_id: str):
    """
    验证 Agent 配置
    """
    issues = []
    warnings = []
    
    # 模拟验证
    warnings.append({
        "type": "low_temperature",
        "message": "温度设置为 0 可能导致响应过于确定性",
        "severity": "warning"
    })
    
    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "warnings": warnings
    }


@router.get("/{agent_id}/performance/tokens")
async def get_token_usage(agent_id: str, days: int = 7):
    """
    获取 Token 使用统计
    """
    # 模拟数据
    return {
        "agent_id": agent_id,
        "period_days": days,
        "total_tokens": 1250000,
        "by_model": {
            "gpt-4o-mini": {"input": 800000, "output": 450000},
            "gpt-4o": {"input": 0, "output": 0}
        },
        "daily_average": 178571,
        "trend": "up"  # up, down, stable
    }


@router.get("/{agent_id}/performance/latency")
async def get_latency_stats(agent_id: str):
    """
    获取响应延迟统计
    """
    return {
        "agent_id": agent_id,
        "avg_ms": 850,
        "p50_ms": 650,
        "p95_ms": 1500,
        "p99_ms": 2500,
        "by_node": {
            "trigger": {"avg_ms": 10},
            "llm": {"avg_ms": 700},
            "knowledge": {"avg_ms": 120},
            "response": {"avg_ms": 20}
        }
    }


@router.get("/{agent_id}/performance/errors")
async def get_error_stats(agent_id: str, days: int = 7):
    """
    获取错误统计
    """
    return {
        "agent_id": agent_id,
        "period_days": days,
        "total_errors": 45,
        "by_type": {
            "model_timeout": 20,
            "rate_limit": 15,
            "invalid_input": 10
        },
        "error_rate": 0.02,
        "trend": "down"
    }


# ===== Agent 模板 API =====

@router.get("/templates/popular")
async def get_popular_templates():
    """
    获取热门模板
    """
    return {
        "templates": [
            {
                "id": "customer-service",
                "name": "客服助手",
                "description": "基于知识库的智能客服",
                "usage_count": 12500,
                "rating": 4.8,
                "icon": "headset"
            },
            {
                "id": "sales-bot",
                "name": "销售机器人",
                "description": "产品推荐和销售线索收集",
                "usage_count": 8900,
                "rating": 4.7,
                "icon": "shopping-cart"
            },
            {
                "id": "hr-assistant",
                "name": "HR 助手",
                "description": "员工问答和入职指引",
                "usage_count": 5600,
                "rating": 4.6,
                "icon": "users"
            },
            {
                "id": "code-review",
                "name": "代码审查",
                "description": "自动化代码审查和建议",
                "usage_count": 4200,
                "rating": 4.9,
                "icon": "code"
            }
        ]
    }


@router.get("/templates/categories")
async def get_template_categories():
    """
    获取模板分类
    """
    return {
        "categories": [
            {
                "id": "customer-service",
                "name": "客户服务",
                "icon": "headset",
                "count": 45
            },
            {
                "id": "sales",
                "name": "销售营销",
                "icon": "trending-up",
                "count": 38
            },
            {
                "id": "hr",
                "name": "人力资源",
                "icon": "users",
                "count": 22
            },
            {
                "id": "developer",
                "name": "开发工具",
                "icon": "code",
                "count": 56
            },
            {
                "id": "productivity",
                "name": "效率工具",
                "icon": "zap",
                "count": 34
            }
        ]
    }


@router.post("/templates/{template_id}/instantiate")
async def instantiate_template(template_id: str, name: str):
    """
    从模板创建 Agent
    """
    logger.info(f"Creating agent from template {template_id}")
    return {
        "status": "success",
        "agent_id": f"agent-from-{template_id}",
        "name": name,
        "template_id": template_id,
        "created_at": datetime.utcnow().isoformat()
    }
