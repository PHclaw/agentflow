"""
定时任务 - Celery
"""
from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "agentflow",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
)

# 定时任务
celery_app.conf.beat_schedule = {
    "cleanup-expired-sessions": {
        "task": "app.celery_app.cleanup_expired_sessions",
        "schedule": crontab(minute="*/30"),  # 每30分钟
    },
    "generate-daily-report": {
        "task": "app.celery_app.generate_daily_report",
        "schedule": crontab(hour="1", minute="0"),  # 每天凌晨1点
    },
}


@celery_app.task
def cleanup_expired_sessions():
    """清理过期的会话（30天未更新的）"""
    import asyncio
    from datetime import datetime, timedelta, timezone

    async def _cleanup():
        from app.core.database import get_async_session_factory
        from sqlalchemy import delete, select
        from app.models.agent import ChatSession

        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        factory = get_async_session_factory()

        async with factory() as session:
            result = await session.execute(
                delete(ChatSession).where(ChatSession.updated_at < cutoff)
            )
            await session.commit()
            return result.rowcount

    try:
        deleted = asyncio.run(_cleanup())
        print(f"[Celery] Cleaned up {deleted} expired sessions")
        return {"deleted": deleted}
    except Exception as e:
        print(f"[Celery] Cleanup error: {e}")
        return {"error": str(e)}


@celery_app.task
def generate_daily_report():
    """生成每日报告"""
    import asyncio
    from datetime import datetime, timedelta, timezone

    async def _report():
        from app.core.database import get_async_session_factory
        from sqlalchemy import select, func
        from app.models.agent import Agent, ChatSession
        from app.models.user import User

        factory = get_async_session_factory()
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)

        async with factory() as session:
            # 统计
            total_agents = await session.scalar(select(func.count(Agent.id))) or 0
            total_users = await session.scalar(select(func.count(User.id))) or 0
            yesterday_sessions = await session.scalar(
                select(func.count(ChatSession.id)).where(
                    ChatSession.created_at >= yesterday
                )
            ) or 0

            report = {
                "date": yesterday.strftime("%Y-%m-%d"),
                "total_agents": total_agents,
                "total_users": total_users,
                "new_sessions_24h": yesterday_sessions,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
            print(f"[Celery] Daily report: {report}")
            return report

    try:
        return asyncio.run(_report())
    except Exception as e:
        print(f"[Celery] Report error: {e}")
        return {"error": str(e)}


@celery_app.task
def process_document_upload(file_path: str, kb_id: str):
    """异步处理文档上传（文本提取 + 分块 + 向量化）"""
    import asyncio

    async def _process():
        from app.core.database import get_async_session_factory
        from app.services.knowledge import KnowledgeService
        from pathlib import Path

        factory = get_async_session_factory()
        path = Path(file_path)

        # 读取文件内容
        content = path.read_text(errors="ignore")

        async with factory() as session:
            service = KnowledgeService(session, kb_id)
            doc = await service.add_document(
                kb_id=kb_id,
                filename=path.name,
                content=content,
                file_type=path.suffix.lstrip("."),
            )
            return {
                "doc_id": doc.id,
                "status": doc.status,
                "chunk_count": doc.chunk_count,
            }

    try:
        return asyncio.run(_process())
    except Exception as e:
        print(f"[Celery] Document processing error: {e}")
        return {"error": str(e)}
