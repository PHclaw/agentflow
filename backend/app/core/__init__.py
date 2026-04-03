"""
定时任务 - Celery
"""
from celery import Celery
from celery.schedules import crontab

from .core.config import settings

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
    """清理过期的会话"""
    from .core.database import SessionLocal
    from datetime import datetime, timedelta
    
    db = SessionLocal()
    try:
        # 清理30天前的会话
        threshold = datetime.utcnow() - timedelta(days=30)
        # TODO: 实现清理逻辑
    finally:
        db.close()


@celery_app.task
def generate_daily_report():
    """生成每日报告"""
    # TODO: 实现报告生成
    pass


@celery_app.task
def process_document_upload(file_path: str, agent_id: str):
    """处理文档上传"""
    # TODO: 实现文档处理（OCR、文本提取、分块等）
    pass
