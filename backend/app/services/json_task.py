"""共享：调用优化模型并解析 JSON 对象。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.services.json_extract import extract_json_object
from app.services.model_runtime import run_chat


@dataclass
class JsonTaskResult:
    data: dict[str, Any]
    raw: str
    model: str
    latency_ms: int


async def run_json_task(
    db: AsyncSession | None,
    *,
    user_id: str | None,
    system: str,
    user: str,
    temperature: float = 0.2,
    max_tokens: int = 2048,
    model: str | None = None,
) -> JsonTaskResult:
    """用 OPTIMIZE_MODEL（或指定 model）跑一轮 chat，并 extract_json_object。"""
    settings = get_settings()
    model_name = model or settings.optimize_model or settings.default_model
    if not model_name:
        raise ValueError("未配置可用模型（OPTIMIZE_MODEL / DEFAULT_MODEL）")
    result = await run_chat(
        db,
        user_id=user_id,
        model=model_name,
        system=system,
        user=user,
        temperature=temperature,
        max_tokens=max_tokens,
        scene="optimize",
        log_extra={"caller": user_id or "-"},
    )
    raw = (result.output or "").strip()
    return JsonTaskResult(
        data=extract_json_object(raw),
        raw=raw,
        model=model_name,
        latency_ms=result.latency_ms,
    )
