"""
Core module - Configuration and Database
"""
from app.core.config import settings
from app.core.base import Base  # noqa: F401 - needed for metadata
from app.core.database import get_db, init_db, async_session

__all__ = ["settings", "get_db", "init_db", "async_session"]
