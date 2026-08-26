"""Skill 运行时日志桥接。"""
from __future__ import annotations

import logging
from typing import Optional

from app.core.logging import logger as _root_logger

_LOGGER_NAME = "agentflow.skills"


def get_logger(name: Optional[str] = None) -> logging.Logger:
    if name:
        prefix = _LOGGER_NAME if not name.startswith(_LOGGER_NAME) else ""
        return logging.getLogger(f"{prefix}.{name}" if prefix else name)
    return _root_logger
