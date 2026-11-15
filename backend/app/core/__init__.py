"""
Core module - Configuration and Database
"""
from app.core.base import Base  # noqa: F401 - needed for metadata
from app.core.config import settings
from app.core.database import async_session, get_db, init_db

__all__ = ["settings", "get_db", "init_db", "async_session"]
