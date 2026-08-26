from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.logging_setup import get_logger
from app.services.adapters import ChatResult, get_adapter
from app.services.prompt_utils import render_template
from app.services.time_sync import inject_time_into_messages, inject_time_into_system

logger = get_logger("model")


def resolve_credentials() -> tuple[str | None, str | None]:
    """统一读取服务端 .env 中的 API Key / Base URL（不允许用户自选）。

    优先 CHATZOC_*，否则回退 DASHSCOPE_API_KEY / MODEL_BASE_URL。
    """
    settings = get_settings()
    api_key: str | None = (
        settings.chatzoc_api_key
        or settings.dashscope_api_key
        or None
    )
    base_url: str | None = (
        settings.chatzoc_base_url
        or settings.model_base_url
        or None
    )
    return api_key, base_url


def _agent_type(model: str) -> str:
    settings = get_settings()
    return (settings.chatzoc_agent_type or model or "").strip() or model


def _fmt_extra(extra: dict[str, str] | None) -> str:
    if not extra:
        return ""
    parts = [f"{k}={v}" for k, v in extra.items() if v is not None and str(v) != ""]
    return (" " + " ".join(parts)) if parts else ""


async def run_chat(
    db: AsyncSession | None = None,
    *,
    user_id: str | None = None,
    model: str,
    system: str,
    user: str,
    variables: dict[str, str] | None = None,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    scene: str = "chat",
    log_extra: dict[str, str] | None = None,
) -> ChatResult:
    """统一非流式调用；每次真实上游调用写 mct.model 日志。"""
    _ = db  # 保留形参以兼容既有调用方；凭证不依赖用户/会话
    rendered_user = render_template(user, variables)
    rendered_system = inject_time_into_system(render_template(system, variables))
    api_key, base_url = resolve_credentials()
    adapter = get_adapter(model)
    agent_type = _agent_type(model)
    extra = {
        "user": user_id or "-",
        **(log_extra or {}),
    }
    try:
        result = await adapter.chat(
            model,
            system=rendered_system,
            user=rendered_user,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=api_key,
            base_url=base_url,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "fail scene=%s model=%s agentType=%s sysChars=%s userChars=%s errType=%s err=%r%s",
            scene,
            model,
            agent_type,
            len(rendered_system),
            len(rendered_user),
            type(exc).__name__,
            str(exc).strip() or repr(exc),
            _fmt_extra(extra),
        )
        raise

    logger.info(
        "ok scene=%s model=%s agentType=%s latencyMs=%s tokensIn=%s tokensOut=%s "
        "outChars=%s sysChars=%s userChars=%s%s",
        scene,
        model,
        agent_type,
        result.latency_ms,
        result.tokens_input,
        result.tokens_output,
        len(result.output or ""),
        len(rendered_system),
        len(rendered_user),
        _fmt_extra(extra),
    )
    return result


async def run_chat_messages(
    db: AsyncSession | None = None,
    *,
    user_id: str | None = None,
    model: str,
    messages: list[dict[str, str]],
    temperature: float = 0.7,
    max_tokens: int = 2048,
    scene: str = "conversation",
    log_extra: dict[str, str] | None = None,
) -> ChatResult:
    """多轮非流式调用。"""
    _ = db
    messages = inject_time_into_messages(messages)
    api_key, base_url = resolve_credentials()
    adapter = get_adapter(model)
    agent_type = _agent_type(model)
    extra = {
        "user": user_id or "-",
        **(log_extra or {}),
    }
    msg_chars = sum(len(m.get("content") or "") for m in messages)
    try:
        result = await adapter.chat_messages(
            model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=api_key,
            base_url=base_url,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "fail scene=%s model=%s agentType=%s msgCount=%s msgChars=%s errType=%s err=%r%s",
            scene,
            model,
            agent_type,
            len(messages),
            msg_chars,
            type(exc).__name__,
            str(exc).strip() or repr(exc),
            _fmt_extra(extra),
        )
        raise

    logger.info(
        "ok scene=%s model=%s agentType=%s latencyMs=%s tokensIn=%s tokensOut=%s "
        "outChars=%s msgCount=%s msgChars=%s%s",
        scene,
        model,
        agent_type,
        result.latency_ms,
        result.tokens_input,
        result.tokens_output,
        len(result.output or ""),
        len(messages),
        msg_chars,
        _fmt_extra(extra),
    )
    return result


async def run_stream(
    *,
    model: str,
    system: str,
    user: str,
    variables: dict[str, str] | None = None,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    scene: str = "debug-stream",
    log_extra: dict[str, str] | None = None,
) -> AsyncIterator[str]:
    """统一流式调用：产出 SSE 文本行（data: {...}），done 事件含 tokens。"""
    rendered_user = render_template(user, variables)
    rendered_system = inject_time_into_system(render_template(system, variables))
    api_key, base_url = resolve_credentials()
    adapter = get_adapter(model)
    agent_type = _agent_type(model)
    extra = dict(log_extra or {})
    started = time.perf_counter()
    full: list[str] = []
    tin = 0
    tout = 0
    logger.info(
        "stream-start scene=%s model=%s agentType=%s sysChars=%s userChars=%s%s",
        scene,
        model,
        agent_type,
        len(rendered_system),
        len(rendered_user),
        _fmt_extra(extra),
    )
    try:
        async for chunk in adapter.chat_stream(
            model,
            system=rendered_system,
            user=rendered_user,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=api_key,
            base_url=base_url,
        ):
            if chunk.tokens_input is not None:
                tin = chunk.tokens_input
            if chunk.tokens_output is not None:
                tout = chunk.tokens_output
            if chunk.delta:
                full.append(chunk.delta)
                yield f"data: {json.dumps({'delta': chunk.delta}, ensure_ascii=False)}\n\n"
        latency = int((time.perf_counter() - started) * 1000)
        output = "".join(full)
        logger.info(
            "stream-ok scene=%s model=%s agentType=%s latencyMs=%s tokensIn=%s "
            "tokensOut=%s outChars=%s%s",
            scene,
            model,
            agent_type,
            latency,
            tin,
            tout,
            len(output),
            _fmt_extra(extra),
        )
        done = {
            "done": True,
            "output": output,
            "latencyMs": latency,
            "tokens": {"input": tin, "output": tout},
            "model": model,
        }
        yield f"data: {json.dumps(done, ensure_ascii=False)}\n\n"
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "stream-fail scene=%s model=%s agentType=%s err=%s%s",
            scene,
            model,
            agent_type,
            exc,
            _fmt_extra(extra),
        )
        yield f"data: {json.dumps({'error': str(exc)}, ensure_ascii=False)}\n\n"
