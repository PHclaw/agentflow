"""数据库迁移"""
from alembic.config import Config
from alembic import command
import os

def init_migrations():
    """初始化迁移"""
    alembic_cfg = Config("alembic.ini")
    command.init(alembic_cfg, "migrations")

def generate_migration(message: str):
    """生成迁移"""
    alembic_cfg = Config("alembic.ini")
    command.revision(alembic_cfg, autogenerate=True, message=message)

def apply_migrations():
    """应用迁移"""
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")
