"""
数据库声明基类 — 独立模块，避免循环导入
"""
from sqlalchemy.orm import declarative_base

Base = declarative_base()
