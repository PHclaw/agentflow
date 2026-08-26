"""调用工具前判断 intro / task。"""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.logging_setup import get_logger
from app.services.model_runtime import run_chat
from app.services.skill.capability import (
    build_intent_gate_prompt,
    is_ability_ask,
    is_capability_query,
    parse_intent_gate,
    prefer_current_user_text,
)

logger = get_logger("intent-gate")
GATE_TIMEOUT_SEC = 8.0


@dataclass
class IntentGateResult:
    skip_tools: bool
    latency_ms: int = 0
    model_called: bool = False
    timed_out: bool = False


def _looks_like_tool_task(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    return bool(
        re.search(
            r"生成xls|xlsx|导出|下载表|表格文件|"
            r"拆分|分割|切分|合并|水印|转成\s*word|转docx|"
            r"检索|搜(索|一下)|速读|柱状|折线|饼图|出图",
            t,
            re.I,
        )
    )


def _ppt_wizard_busy(agent: Any, conversation_id: str | None) -> bool:
    if not conversation_id:
        return False
    try:
        from app.services.skill.ppt_pipeline import is_ppt_skill
        from app.services.skill.ppt_wizard import wizard_in_progress

        return bool(is_ppt_skill(agent) and wizard_in_progress(conversation_id))
    except Exception:  # noqa: BLE001
        return False


async def resolve_skip_tools(
    db: AsyncSession,
    agent: Any,
    user_text: str,
    *,
    uploaded_files: list[dict] | None = None,
    conversation_id: str | None = None,
    caller_id: str = "",
    model: str = "",
) -> IntentGateResult:
    if _ppt_wizard_busy(agent, conversation_id):
        return IntentGateResult(skip_tools=False)

    current = prefer_current_user_text(user_text)
    if not uploaded_files and (is_capability_query(user_text) or is_ability_ask(user_text)):
        logger.info(
            "intent gate shortcut intro skillId=%s text=%r",
            getattr(agent, "id", None),
            current[:40],
        )
        return IntentGateResult(skip_tools=True, model_called=False)

    # 已有明确任务或上传文件时跳过意图闸门。
    if uploaded_files or _looks_like_tool_task(current):
        return IntentGateResult(skip_tools=False, model_called=False)

    from app.services.model_validation import resolve_callable_model

    gate_sys, gate_user = build_intent_gate_prompt(
        agent, user_text, uploaded_files=uploaded_files
    )
    try:
        gate_res = await asyncio.wait_for(
            run_chat(
                db,
                user_id=getattr(agent, "author_id", None) or caller_id,
                model=resolve_callable_model(model or getattr(agent, "model_name", None)),
                system=gate_sys,
                user=gate_user,
                variables=None,
                temperature=0.0,
                max_tokens=64,
                scene="skill-intent-gate",
                log_extra={
                    "skillId": getattr(agent, "id", None) or "",
                    "skill": getattr(agent, "name", None) or "",
                    "caller": caller_id,
                    "gate": True,
                },
            ),
            timeout=GATE_TIMEOUT_SEC,
        )
        latency = int(gate_res.latency_ms or 0)
        decided = parse_intent_gate(gate_res.output or "")
        logger.info(
            "intent gate skillId=%s decided=%s raw=%r",
            getattr(agent, "id", None),
            decided,
            (gate_res.output or "")[:80],
        )
        return IntentGateResult(
            skip_tools=decided == "intro",
            latency_ms=latency,
            model_called=True,
        )
    except (TimeoutError, asyncio.TimeoutError, asyncio.CancelledError) as exc:
        logger.warning(
            "intent gate timeout skillId=%s err=%s — 已调用模型但上游未在 %.0fs 内返回",
            getattr(agent, "id", None),
            type(exc).__name__,
            GATE_TIMEOUT_SEC,
        )
        intro = is_capability_query(user_text) or is_ability_ask(user_text)
        return IntentGateResult(
            skip_tools=intro,
            timed_out=True,
            model_called=True,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "intent gate fail skillId=%s err=%s",
            getattr(agent, "id", None),
            type(exc).__name__,
        )
        intro = is_capability_query(user_text) or is_ability_ask(user_text)
        return IntentGateResult(skip_tools=intro, timed_out=True, model_called=True)
