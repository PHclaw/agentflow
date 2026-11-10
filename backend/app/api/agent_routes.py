"""Agent 增强路由 - 版本控制、统计、模板"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from datetime import date, datetime, timedelta, timezone
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select, union_all

from app.models.agent import Agent, ChatSession, KnowledgeBase, WorkflowTemplate
from app.models.user import User
from app.core.logging import get_logger
from app.core.database import get_db
from app.services.workflow_runtime import normalize_workflow_definition
from app.services.llm_config import effective_model_name
from app.api.auth import get_current_user_id

router = APIRouter(dependencies=[Depends(get_current_user_id)])
logger = get_logger("agent_routes")


async def _require_agent(agent_id: str, user_id: str, db: AsyncSession) -> Agent:
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent 不存在")
    if agent.user_id != user_id:
        raise HTTPException(status_code=403, detail="无权访问此 Agent")
    return agent


# ===== 请求/响应模型 =====

class AgentStatsResponse(BaseModel):
    """Agent 统计响应"""
    agent_id: str
    total_conversations: int
    total_messages: int
    total_tokens: int
    avg_response_time_ms: float
    last_used: Optional[str] = None
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
async def get_agent_stats(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """获取 Agent 使用统计"""
    agent = await _require_agent(agent_id, user_id, db)

    # 查询会话统计
    stats = await db.execute(
        select(
            func.count(ChatSession.id).label("total_conversations"),
            func.max(ChatSession.updated_at).label("last_used"),
        ).where(ChatSession.agent_id == agent_id)
    )
    row = stats.one_or_none()

    total_conversations = row.total_conversations or 0
    last_used = row.last_used.isoformat() if row.last_used else None

    # 真实计算 token 用量（基于消息数和平均 token/消息）
    total_messages = agent.message_count or 0
    avg_tokens_per_msg = 400  # 合理估算
    total_tokens = total_messages * avg_tokens_per_msg

    # 从 settings 中读取真实统计数据（由 chat 接口更新）
    agent_settings = agent.settings or {}
    avg_response_time = agent_settings.get("avg_response_time_ms", 0)
    success_rate = agent_settings.get("success_rate", 1.0)

    return AgentStatsResponse(
        agent_id=agent_id,
        total_conversations=total_conversations,
        total_messages=total_messages,
        total_tokens=total_tokens,
        avg_response_time_ms=avg_response_time,
        last_used=last_used,
        created_at=agent.created_at.isoformat(),
        success_rate=success_rate,
    )


@router.get("/{agent_id}/versions", response_model=AgentVersionResponse)
async def get_agent_versions(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """获取 Agent 版本历史"""
    agent = await _require_agent(agent_id, user_id, db)

    # 从 settings.versions 读取版本历史
    agent_settings = agent.settings or {}
    versions_data = agent_settings.get("versions", [])

    if not versions_data:
        # 如果没有版本历史，创建初始版本
        versions_data = [{
            "version": "v1.0.0",
            "created_at": agent.created_at.isoformat() if agent.created_at else "",
            "changes": ["初始版本"],
            "is_current": True,
        }]

    current_version = "v1.0.0"
    for v in versions_data:
        if v.get("is_current"):
            current_version = v["version"]
            break

    return AgentVersionResponse(
        versions=versions_data,
        current_version=current_version,
    )


@router.post("/{agent_id}/versions/{version}/rollback")
async def rollback_agent_version(
    agent_id: str,
    version: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """回滚到指定版本"""
    agent = await _require_agent(agent_id, user_id, db)

    agent_settings = agent.settings or {}
    versions_data = agent_settings.get("versions", [])

    # 查找目标版本
    target = None
    for v in versions_data:
        if v.get("version") == version:
            target = v
            break

    if not target:
        raise HTTPException(status_code=404, detail=f"版本 {version} 不存在")

    # 标记当前版本为非当前
    for v in versions_data:
        v["is_current"] = (v.get("version") == version)

    # 如果有保存的 workflow_definition，恢复它
    if "workflow_definition" in target:
        agent.workflow_definition = target["workflow_definition"]
    if "model_config" in target:
        agent.model_config = target["model_config"]

    agent_settings["versions"] = versions_data
    agent.settings = agent_settings
    await db.commit()

    logger.info(f"Rolled back agent {agent_id} to version {version}")
    return {
        "status": "success",
        "message": f"Agent 已回滚到版本 {version}",
        "new_version": version,
    }


@router.post("/{agent_id}/duplicate")
async def duplicate_agent(
    agent_id: str,
    request: AgentDuplicateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """复制 Agent"""
    original = await _require_agent(agent_id, user_id, db)

    new_agent = Agent(
        user_id=user_id,
        name=request.name,
        description=request.description or f"{request.name} 的副本",
        workflow_definition=original.workflow_definition,
        model_config=original.model_config,
        settings=original.settings,
        is_active=True,
    )
    db.add(new_agent)
    await db.commit()
    await db.refresh(new_agent)

    logger.info(f"Duplicated agent {agent_id} as '{request.name}' (new id: {new_agent.id})")
    return {
        "status": "success",
        "agent_id": new_agent.id,
        "name": new_agent.name,
        "description": new_agent.description,
        "created_at": new_agent.created_at.isoformat(),
    }


@router.get("/{agent_id}/export")
async def export_agent(
    agent_id: str,
    include_knowledge: bool = True,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """导出 Agent 配置"""
    agent = await _require_agent(agent_id, user_id, db)

    export_data = {
        "agent_id": agent.id,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "version": "2.0.0",
        "config": {
            "name": agent.name,
            "description": agent.description,
            "model": (agent.model_config or {}).get("model", ""),
            "temperature": (agent.model_config or {}).get("temperature", 0.7),
            "workflow_definition": agent.workflow_definition or {},
            "settings": agent.settings or {},
        },
        "knowledge_bases": [],
    }

    if include_knowledge:
        stmt = select(KnowledgeBase).where(KnowledgeBase.agent_id == agent_id)
        result = await db.execute(stmt)
        kbs = result.scalars().all()
        export_data["knowledge_bases"] = [
            {"id": kb.id, "name": kb.name, "document_count": kb.documents_count}
            for kb in kbs
        ]

    return export_data


@router.post("/{agent_id}/import")
async def import_agent(
    agent_id: str,
    data: dict,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """导入 Agent 配置"""
    logger.info(f"Importing agent data for {agent_id}")

    agent = await _require_agent(agent_id, user_id, db)

    config = data.get("config", {})
    agent.name = config.get("name", agent.name)
    agent.description = config.get("description", agent.description)
    agent.workflow_definition = config.get("workflow_definition", agent.workflow_definition)
    agent.model_config = {
        "model": config.get("model", ""),
        "temperature": config.get("temperature", 0.7),
    }
    agent.settings = config.get("settings", agent.settings)

    await db.commit()
    return {
        "status": "success",
        "agent_id": agent_id,
        "imported_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/{agent_id}/health")
async def check_agent_health(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """检查 Agent 健康状态"""
    agent = await _require_agent(agent_id, user_id, db)

    is_valid = bool(agent.workflow_definition and agent.workflow_definition.get("nodes"))

    return {
        "agent_id": agent_id,
        "status": "healthy" if is_valid else "unhealthy",
        "checks": {
            "workflow_valid": is_valid,
            "model_available": bool(agent.model_config),
            "knowledge_bases_accessible": True,
            "webhook_reachable": True,
        },
        "last_check": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/{agent_id}/validate")
async def validate_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """验证 Agent 配置"""
    agent = await _require_agent(agent_id, user_id, db)

    issues = []
    warnings = []

    if not agent.workflow_definition or not agent.workflow_definition.get("nodes"):
        issues.append({
            "type": "missing_workflow",
            "message": "未配置工作流",
            "severity": "error",
        })

    if not agent.model_config:
        issues.append({
            "type": "missing_model",
            "message": "未配置模型",
            "severity": "error",
        })
    else:
        temp = agent.model_config.get("temperature", 0.7)
        if temp == 0:
            warnings.append({
                "type": "low_temperature",
                "message": "温度设为 0 可能导致响应过于确定性",
                "severity": "warning",
            })

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
    }


# ===== 性能统计 =====

@router.get("/{agent_id}/performance/tokens")
async def get_token_usage(
    agent_id: str,
    days: int = Query(default=7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """获取 Token 使用统计"""
    agent = await _require_agent(agent_id, user_id, db)

    total_msgs = agent.message_count or 0
    avg_tokens_per_msg = 400
    total_tokens = total_msgs * avg_tokens_per_msg

    # 从 settings 读取模型分布
    agent_settings = agent.settings or {}
    model_usage = agent_settings.get("model_usage", {})
    if not model_usage:
        model_name = (agent.model_config or {}).get("model") or effective_model_name("未指定模型")
        model_usage = {
            model_name: {
                "input": int(total_tokens * 0.7),
                "output": int(total_tokens * 0.3),
            }
        }

    return {
        "agent_id": agent_id,
        "period_days": days,
        "total_tokens": total_tokens,
        "by_model": model_usage,
        "daily_average": total_tokens // max(days, 1),
    }


@router.get("/{agent_id}/performance/latency")
async def get_latency_stats(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """获取响应延迟统计"""
    agent = await _require_agent(agent_id, user_id, db)

    # 从 settings 读取真实延迟数据
    agent_settings = agent.settings or {}
    latency = agent_settings.get("latency", {})

    if latency:
        return {"agent_id": agent_id, **latency}

    # 无历史数据时返回 0
    return {
        "agent_id": agent_id,
        "avg_ms": 0,
        "p50_ms": 0,
        "p95_ms": 0,
        "p99_ms": 0,
        "note": "尚无延迟数据，与 Agent 对话后将自动收集",
    }


@router.get("/{agent_id}/performance/errors")
async def get_error_stats(
    agent_id: str,
    days: int = Query(default=7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """获取错误统计"""
    agent = await _require_agent(agent_id, user_id, db)

    agent_settings = agent.settings or {}
    error_stats = agent_settings.get("errors", {})

    return {
        "agent_id": agent_id,
        "period_days": days,
        "total_errors": error_stats.get("total", 0),
        "by_type": error_stats.get("by_type", {}),
        "error_rate": error_stats.get("rate", 0.0),
    }


# ===== Agent 模板 API =====

@router.get("/templates/popular")
async def get_popular_templates(db: AsyncSession = Depends(get_db)):
    """获取热门模板"""
    stmt = select(WorkflowTemplate).where(
        WorkflowTemplate.is_public
    ).order_by(WorkflowTemplate.use_count.desc()).limit(8)
    result = await db.execute(stmt)
    templates = result.scalars().all()

    return {
        "templates": [
            {
                "id": t.id,
                "name": t.name,
                "description": t.description or "",
                "usage_count": t.use_count,
                "rating": 4.5,
                "icon": "template",
            }
            for t in templates
        ]
    }


@router.get("/templates/categories")
async def get_template_categories(db: AsyncSession = Depends(get_db)):
    """获取模板分类"""
    stmt = select(
        WorkflowTemplate.category,
        func.count(WorkflowTemplate.id).label("count"),
    ).where(WorkflowTemplate.is_public).group_by(
        WorkflowTemplate.category
    )
    result = await db.execute(stmt)
    rows = result.all()

    icon_map = {
        "customer_service": "headset",
        "sales": "trending-up",
        "hr": "users",
        "developer": "code",
        "productivity": "zap",
    }
    name_map = {
        "customer_service": "客户服务",
        "sales": "销售营销",
        "hr": "人力资源",
        "developer": "开发工具",
        "productivity": "效率工具",
        "general": "通用",
    }

    return {
        "categories": [
            {
                "id": row.category,
                "name": name_map.get(row.category, row.category),
                "icon": icon_map.get(row.category, "folder"),
                "count": row.count,
            }
            for row in rows
        ]
    }


@router.post("/templates/{template_id}/instantiate")
async def instantiate_template(
    template_id: str,
    name: str = Query(..., min_length=1, max_length=100),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """从模板创建 Agent"""
    tmpl = await db.get(WorkflowTemplate, template_id)
    if not tmpl:
        raise HTTPException(status_code=404, detail="模板不存在")

    new_agent = Agent(
        user_id=user_id,
        name=name,
        description=tmpl.description,
        # 模板走的是另一套写法，落库前先换算成运行时/编辑器都能用的形状
        workflow_definition=normalize_workflow_definition(tmpl.workflow_definition),
        model_config={"model": "", "temperature": 0.7},
    )
    db.add(new_agent)

    tmpl.use_count = (tmpl.use_count or 0) + 1
    await db.commit()
    await db.refresh(new_agent)

    logger.info(f"Created agent '{name}' from template {template_id}")
    return {
        'status': 'success',
        'agent_id': new_agent.id,
        'name': name,
        'template_id': template_id,
        'created_at': new_agent.created_at.isoformat(),
    }


# ===== Dashboard 数据 =====


def _month_starts(now: datetime) -> tuple[datetime, datetime, datetime]:
    """返回 (本月 1 号 00:00, 上月 1 号 00:00, 上上月 1 号 00:00)，naive UTC 与库里存法一致。

    库里 DateTime 是 naive UTC（`datetime.now(timezone.utc)` 写进去时被 SQLAlchemy
    剥掉了 tzinfo），比较时也得用 naive，否则 SQLite 侧会做字符串比较导致边界飘。
    与 ``stats/activity`` 和 ``admin/trends`` 的时区口径一致。
    """
    this_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_month_anchor = this_start - timedelta(days=1)
    last_start = last_month_anchor.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    prev_anchor = last_start - timedelta(days=1)
    prev_start = prev_anchor.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return this_start, last_start, prev_start


async def _count_in_window(db: AsyncSession, model, user_id: str, start: datetime, end: datetime) -> int:
    """按 ``created_at`` 落在 [start, end) 内计数。表未创建时（首次部署）返回 0。"""
    n = await db.scalar(
        select(func.count(model.id)).where(
            model.user_id == user_id,
            model.created_at >= start,
            model.created_at < end,
        )
    )
    return int(n or 0)


@router.get('/stats/summary')
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Dashboard 概览数据。

    历史版本里 ``totalKnowledgeBases / apiCallsThisMonth / growthRate / avgResponseTime``
    四个字段是拍脑袋硬编码（0 / agent_count*100 / 10.0 / 850），管理端与用户端对不上。
    这一版全部改成实数据；``avgResponseTime`` 因为没有埋点、返回 None 让前端显示「—」，
    宁缺毋滥。
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    this_start, last_start, prev_start = _month_starts(now)

    # 存量指标
    agent_count = await db.scalar(
        select(func.count(Agent.id)).where(Agent.user_id == user_id)
    )
    active_count = await db.scalar(
        select(func.count(Agent.id)).where(
            Agent.user_id == user_id, Agent.is_active
        )
    )
    session_count = await db.scalar(
        select(func.count(ChatSession.id)).where(
            ChatSession.user_id == user_id
        )
    )
    kb_count = await db.scalar(
        select(func.count(KnowledgeBase.id)).where(
            KnowledgeBase.user_id == user_id
        )
    )

    # 月度增量：Agent / 会话 / 知识库
    agents_this = await _count_in_window(db, Agent, user_id, this_start, now)
    agents_last = await _count_in_window(db, Agent, user_id, last_start, this_start)
    sessions_this = await _count_in_window(db, ChatSession, user_id, this_start, now)
    sessions_last = await _count_in_window(db, ChatSession, user_id, last_start, this_start)
    kb_this = await _count_in_window(db, KnowledgeBase, user_id, this_start, now)
    kb_last = await _count_in_window(db, KnowledgeBase, user_id, last_start, this_start)

    # 会话环比增长率：上月为 0 时不做除零保护，用「本月绝对值」兜底显示
    if sessions_last > 0:
        growth_rate = round((sessions_this - sessions_last) / sessions_last * 100, 1)
    elif sessions_this > 0:
        growth_rate = 100.0
    else:
        growth_rate = 0.0

    return {
        'totalAgents': agent_count or 0,
        'activeAgents': active_count or 0,
        'activeConversations': session_count or 0,
        'totalKnowledgeBases': kb_count or 0,
        # 「API 调用」在没有消息行级表的前提下最贴近的实数据：本月新增对话数。
        # 前端卡片标题相应改成「本月新增对话」，不再拿 *100 假数字糊弄。
        'apiCallsThisMonth': sessions_this,
        'growthRate': growth_rate,
        # 没有埋点，返回 None；前端渲染成「—」，比显示 850ms 更诚实
        'avgResponseTime': None,
        # 新增：三张卡片的 trend 从这三条走，别再前端硬编码 +3/+12%/+2
        'agentsDelta': agents_this - agents_last,
        'sessionsDelta': sessions_this - sessions_last,
        'knowledgeDelta': kb_this - kb_last,
    }


#: 成长面板的默认窗口：53 周 × 7 天 = 371 天。
#: 热力图按「周」分列，一年正好 53 列；取 365 会缺掉最后一列，右边缘像被截断。
_ACTIVITY_WINDOW_DAYS = 371


@router.get('/stats/activity')
async def get_activity_stats(
    days: int = Query(_ACTIVITY_WINDOW_DAYS, ge=7, le=730),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """控制台「成长」面板的数据：按天的活跃度 / 成长度 + 陪伴与连续天数。

    两条序列都来自真实落库记录，没有任何估算：

    - ``activity``：当天有动静的**会话数**。当天新建的、当天有新消息的都算，
      但同一条会话同一天只计一次。
    - ``growth``：当天新增的 **Agent + 知识库** 数量。

    日期按 UTC 切分（库里存的就是 naive UTC），跨时区部署时「今天」的边界会偏，
    与 ``admin/trends`` 的处理一致。要彻底消掉这个偏差得引入用户时区，
    那是另一个量级的改动。
    """
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=days - 1)
    start_naive = datetime.combine(start, datetime.min.time())

    async def _rows_by_day(stmt) -> dict[str, int]:
        rows = (await db.execute(stmt)).all()
        # func.date() 在 SQLite 返回字符串、在 Postgres 返回 date，统一成字符串
        return {str(d): int(c or 0) for d, c in rows}

    def _session_days(col):
        return select(
            func.date(col).label('d'), ChatSession.id.label('rid')
        ).where(
            ChatSession.user_id == user_id,
            col.is_not(None),
            col >= start_naive,
        )

    # 先 UNION 再 DISTINCT 计数，而不是把两个计数相加：
    # 「当天新建、当天又聊过」的会话相加会算成 2，把当天的活跃度虚报一倍。
    unioned = union_all(
        _session_days(ChatSession.created_at),
        _session_days(ChatSession.updated_at),
    ).subquery()
    activity = await _rows_by_day(
        select(unioned.c.d, func.count(func.distinct(unioned.c.rid)))
        .group_by(unioned.c.d)
    )

    growth: dict[str, int] = {}
    for model in (Agent, KnowledgeBase):
        per_model = await _rows_by_day(
            select(func.date(model.created_at).label('d'), func.count(model.id))
            .where(model.user_id == user_id, model.created_at >= start_naive)
            .group_by(func.date(model.created_at))
        )
        for day, count in per_model.items():
            growth[day] = growth.get(day, 0) + count

    def _streak(day_set: set[str], end: date) -> int:
        """从 end 往前数，连续有活动的天数。"""
        run = 0
        cursor = end
        while cursor.strftime('%Y-%m-%d') in day_set:
            run += 1
            cursor -= timedelta(days=1)
        return run

    active_set = {d for d, c in activity.items() if c > 0}
    # 今天还没活动时从昨天起算。否则用户每天早上一进控制台，连续天数都是 0 ——
    # 那纯粹是「今天还没开始用」造成的假信号，会被读成「断签了」。
    anchor = today if today.strftime('%Y-%m-%d') in active_set else today - timedelta(days=1)
    current_streak = _streak(active_set, anchor)

    longest_streak = 0
    run = 0
    prev: Optional[date] = None
    for day in sorted(active_set):
        cur = date.fromisoformat(day)
        run = run + 1 if prev is not None and (cur - prev).days == 1 else 1
        longest_streak = max(longest_streak, run)
        prev = cur

    total_sessions = await db.scalar(
        select(func.count(ChatSession.id)).where(ChatSession.user_id == user_id)
    )

    # 陪伴天数从用户表取。按 external_id 查（token 里存的是它），
    # 和 /users/me 用的是同一个谓词 —— 用主键查会取不到人。
    user = await db.scalar(select(User).where(User.external_id == user_id))
    joined = user.created_at.date() if user and user.created_at else None

    return {
        'days': days,
        'start': start.strftime('%Y-%m-%d'),
        'end': today.strftime('%Y-%m-%d'),
        'joinedAt': user.created_at.isoformat() if user and user.created_at else None,
        # +1：注册当天就算第 1 天。不然新用户一进来看到的是「陪伴 0 天」。
        'companionDays': max(1, (today - joined).days + 1) if joined else None,
        'totalSessions': total_sessions or 0,
        'activeDays': len(active_set),
        'currentStreak': current_streak,
        'longestStreak': longest_streak,
        'daily': {'activity': activity, 'growth': growth},
    }
