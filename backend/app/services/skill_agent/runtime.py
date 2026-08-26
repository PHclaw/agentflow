"""Skill 工具循环与 Excel / 管线分发。"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.logging_setup import get_logger
from app.services.adapters.base import ChatResult
from app.services.model_runtime import run_chat_messages
from app.services.skill.excel_pipeline import run_excel_tools
from app.services.skill.store import FileSkill
from app.services.skill_agent.checklist import Checklist, Goal, excel_goals, goals_from_clauses
from app.services.skill_agent.excel_tools import (
    ExcelToolSession,
    excel_tool_defs,
    recommend_excel_tool,
    recommend_excel_tools,
)
from app.services.skill_agent.pipeline_pack import PipelineToolSession, pipeline_tool_defs
from app.services.skill_agent.prompts import EXCEL_RULES, PIPELINE_RULES, agent_system_prompt
from app.services.skill_agent.protocol import ActionParseError, parse_action, schema_hint

logger = get_logger("skill-agent")

ChatMessagesFn = Callable[..., Awaitable[ChatResult]]

MAX_STEPS = 8


def _strip_chart_embeds(reply: str, urls: list[str]) -> str:
    """图由前端按 toolTrace 渲染；去掉回复里重复的 markdown 图和裸 png 文件名。保留 xlsx 下载链接。"""
    text = reply or ""
    images = [
        str(u or "").strip()
        for u in (urls or [])
        if re.search(r"\.(png|jpe?g|gif|webp)(\?|$)", str(u or ""), re.I)
    ]
    for u in images:
        if not u:
            continue
        name = u.rsplit("/", 1)[-1]
        text = re.sub(rf"!\[[^\]]*\]\({re.escape(u)}\)", "", text)
        text = re.sub(rf"\[(?:下载图表|下载)\]\({re.escape(u)}\)", "", text)
        if name:
            text = re.sub(rf"!\[[^\]]*\]\([^)]*{re.escape(name)}\)", "", text)
            text = re.sub(rf"`{re.escape(name)}`", "", text)
            text = re.sub(rf"(?m)^\s*{re.escape(name)}\s*$", "", text)
            text = text.replace(u, "")
            text = text.replace(name, "")
    return re.sub(r"\n{3,}", "\n\n", text).strip()


@dataclass
class SkillAgentResult:
    tool_trace: dict[str, Any]
    output: str | None = None
    latency_ms: int = 0
    steps: list[dict[str, Any]] = field(default_factory=list)
    fallback: bool = False


TOOL_ALIASES = {
    "grouped_bar": "chart_grouped_bar",
    "bar": "chart_grouped_bar",
    "combo_total": "chart_combo_bar_with_total_line",
    "combo_total_line": "chart_combo_bar_with_total_line",
    "chart_combo_total": "chart_combo_bar_with_total_line",
    "combo_each": "chart_combo_bar_with_each_line",
    "pie": "chart_pie",
    "export": "export_workbook",
    "export_xlsx": "export_workbook",
    "run_pipeline": "execute",
}


def _excel_dispatch(session: ExcelToolSession, name: str, args: dict[str, Any]) -> dict[str, Any]:
    name = TOOL_ALIASES.get(name, name)
    chart_names = {
        "render_chart",
        "chart_grouped_bar",
        "chart_grouped_bar_with_total_column",
        "chart_combo_bar_with_total_line",
        "chart_combo_bar_with_each_line",
        "chart_line",
        "chart_pie",
    }
    if name in chart_names and not getattr(session, "allow_charts", True):
        return {
            "ok": False,
            "error": "当前请求只要表格文件，不出图。请调用 export_workbook。",
        }
    fn = {
        "read_skill": session.read_skill,
        "parse_table": session.parse_table,
        "preview_frame": session.preview_frame,
        "add_computed_column": session.add_computed_column,
        "query_sql": session.query_sql,
        "render_chart": session.render_chart,
        "chart_grouped_bar": session.chart_grouped_bar,
        "chart_grouped_bar_with_total_column": session.chart_grouped_bar_with_total_column,
        "chart_combo_bar_with_total_line": session.chart_combo_bar_with_total_line,
        "chart_combo_bar_with_each_line": session.chart_combo_bar_with_each_line,
        "chart_line": session.chart_line,
        "chart_pie": session.chart_pie,
        "export_xlsx": session.export_xlsx,
        "export_workbook": session.export_workbook,
        "summarize": session.summarize,
    }.get(name)
    if not fn:
        rec = recommend_excel_tool(session.current)
        return {"ok": False, "error": f"未知工具 {name}。请改用 {rec} 或 render_chart。"}
    return fn(args or {})


def _pipeline_dispatch(session: PipelineToolSession, name: str, args: dict[str, Any]) -> dict[str, Any]:
    name = TOOL_ALIASES.get(name, name)
    fn = {
        "read_skill": session.read_skill,
        "execute": session.execute,
        "run_pipeline": session.execute,
    }.get(name)
    if not fn:
        return {"ok": False, "error": f"未知工具 {name}。请使用 execute。"}
    return fn(args or {})


def _observe_text(obs: dict[str, Any]) -> str:
    try:
        return json.dumps(obs, ensure_ascii=False, default=str)[:6000]
    except TypeError:
        return str(obs)[:6000]


def _finish_reply(session: Any, checklist: Checklist) -> str:
    urls = list(getattr(session, "download_urls", None) or [])
    sheets = [u for u in urls if re.search(r"\.(xlsx|xls|csv)(\?|$)", str(u), re.I)]
    name = getattr(session, "download_name", None) or "结果.xlsx"
    ids = {g.id for g in checklist.goals}
    if "workbook" in ids and sheets:
        return (
            "已生成 Excel 文件，并写入「总销量」列。请点击下方卡片下载。\n\n"
            f"[下载 {name}]({sheets[0]})"
        )
    if sheets:
        return f"已生成文件，请点击下方卡片下载。\n\n[下载 {name}]({sheets[0]})"
    return "已完成本次处理。"


async def _agent_loop(
    db: AsyncSession | None,
    agent: FileSkill,
    *,
    user_text: str,
    model: str,
    temperature: float,
    max_tokens: int,
    caller_id: str,
    chat: ChatMessagesFn,
    session: Any,
    tools: list[dict[str, Any]],
    dispatch: Callable[[Any, str, dict[str, Any]], dict[str, Any]],
    checklist: Checklist,
    recommended: list[str],
    extra_rules: str,
    bootstrap: str,
    fallback_fn: Callable[[], dict[str, Any]],
    auto_tools: list[str] | None = None,
    skip_model_if_done: bool = False,
) -> SkillAgentResult:
    system = agent_system_prompt(
        skill_name=agent.name or agent.id,
        skill_id=agent.id,
        description=agent.description or agent.router_blurb or "",
        tools=tools,
        skill_body="",
        recommended_tools=recommended,
        extra_rules=extra_rules,
    )
    user_parts = [
        "用户请求：\n" + (user_text or ""),
        schema_hint(),
        "任务清单（全部完成后才能 finish）：\n" + checklist.summary(),
        bootstrap,
    ]
    messages: list[dict[str, str]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": "\n\n".join(p for p in user_parts if p)},
    ]
    steps: list[dict[str, Any]] = []
    latency = 0
    parse_fails = 0
    finish_blocks = 0

    for i, name in enumerate(auto_tools or []):
        obs = dispatch(session, name, {})
        resolved = TOOL_ALIASES.get(name, name)
        if obs.get("ok"):
            checklist.mark(resolved, obs)
        steps.append(
            {
                "step": f"auto-{i}",
                "action": "call_tool",
                "name": resolved,
                "ok": bool(obs.get("ok")),
                "auto": True,
            }
        )
        messages.append(
            {
                "role": "user",
                "content": f"系统已自动调用 `{resolved}`：\n" + _observe_text(obs),
            }
        )
    if auto_tools:
        pending0 = checklist.pending()
        if pending0:
            nxt = pending0[0].tools[0] if pending0[0].tools else (recommended[0] if recommended else "execute")
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "预执行后清单仍有未完成项，请 call_tool "
                        f"`{nxt}`。\n" + checklist.summary()
                    ),
                }
            )
        else:
            messages.append(
                {
                    "role": "user",
                    "content": "推荐工具已自动执行，清单已完成。请只输出 finish JSON。说明与实际产出一致，不要贴文件名。",
                }
            )
        gap = checklist.missing_artifacts(getattr(session, "download_urls", None))
        urls_now = getattr(session, "download_urls", None) or []
        if auto_tools and not checklist.pending() and not gap and (
            skip_model_if_done or urls_now
        ):
            trace = session.to_tool_trace()
            trace["agentSteps"] = steps
            trace["checklist"] = checklist.summary()
            return SkillAgentResult(
                tool_trace=trace,
                output=_finish_reply(session, checklist),
                latency_ms=latency,
                steps=steps,
            )

    for step in range(MAX_STEPS):
        try:
            res = await chat(
                db,
                user_id=getattr(agent, "author_id", None),
                model=model,
                messages=messages,
                temperature=min(temperature, 0.35),
                max_tokens=max_tokens,
                scene="skill-agent",
                log_extra={
                    "skillId": agent.id,
                    "skill": agent.name or "",
                    "caller": caller_id,
                    "agentStep": str(step),
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("skill agent chat fail step=%s err=%s", step, exc)
            break
        latency += int(res.latency_ms or 0)
        raw = res.output or ""
        messages.append({"role": "assistant", "content": raw})
        try:
            action = parse_action(raw)
        except ActionParseError as exc:
            parse_fails += 1
            steps.append({"step": step, "parseError": str(exc), "rawPreview": raw[:400]})
            messages.append(
                {
                    "role": "user",
                    "content": f"解析失败：{exc}。{schema_hint()}只输出 JSON。",
                }
            )
            if parse_fails >= 2:
                break
            continue
        if action["action"] == "finish":
            pending = checklist.pending()
            gap = checklist.missing_artifacts(getattr(session, "download_urls", None))
            if (pending or gap) and finish_blocks < 2:
                finish_blocks += 1
                labels = "；".join(g.label for g in pending) if pending else gap
                rec = (
                    pending[0].tools[0]
                    if pending and pending[0].tools
                    else (recommended[0] if recommended else "execute")
                )
                if gap and "export_workbook" in (recommended or []) and not pending:
                    rec = "export_workbook"
                steps.append(
                    {
                        "step": step,
                        "action": "finish-blocked",
                        "pending": [g.id for g in pending],
                        "artifactGap": gap or None,
                    }
                )
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            f"禁止 finish：{labels}。\n"
                            f"请 call_tool `{rec}`（或清单中的下一个工具）。\n"
                            + checklist.summary()
                        ),
                    }
                )
                continue
            reply = (action.get("reply") or "").strip()
            steps.append({"step": step, "action": "finish"})
            trace = session.to_tool_trace()
            trace["agentSteps"] = steps
            trace["checklist"] = checklist.summary()
            if not reply:
                reply = None
            else:
                urls = [str(u) for u in (trace.get("downloadUrls") or []) if u]
                reply = _strip_chart_embeds(reply, urls) or None
            return SkillAgentResult(
                tool_trace=trace,
                output=reply,
                latency_ms=latency,
                steps=steps,
            )
        name = action["name"]
        args = action.get("args") or {}
        obs = dispatch(session, name, args)
        resolved = TOOL_ALIASES.get(name, name)
        if obs.get("ok"):
            checklist.mark(resolved, obs)
        steps.append(
            {
                "step": step,
                "action": "call_tool",
                "name": resolved,
                "ok": bool(obs.get("ok")),
            }
        )
        pending = checklist.pending()
        if pending:
            nxt = pending[0].tools[0] if pending[0].tools else "execute"
            follow = (
                f"\n清单未完成，下一步调用 `{nxt}`（focus/args 对准：{pending[0].label}）。禁止 finish。\n"
                + checklist.summary()
            )
        else:
            follow = "\n清单已全部完成，请 action=finish。不要贴 png 文件名。"
        messages.append(
            {
                "role": "user",
                "content": "工具结果：\n" + _observe_text(obs) + follow,
            }
        )

    logger.info(
        "skill agent loop end skillId=%s steps=%s parseFails=%s pending=%s",
        agent.id,
        len(steps),
        parse_fails,
        [g.id for g in checklist.pending()],
    )
    urls = getattr(session, "download_urls", None) or []
    prior = getattr(session, "_trace", None) or {}
    if urls or prior.get("stdout") or prior.get("note") or prior.get("exitCode") is not None:
        trace = session.to_tool_trace()
        trace["agentSteps"] = steps
        trace["checklist"] = checklist.summary()
        return SkillAgentResult(
            tool_trace=trace,
            output=None,
            latency_ms=latency,
            steps=steps,
            fallback=False,
        )
    try:
        trace = fallback_fn()
    except Exception as exc:  # noqa: BLE001
        logger.warning("skill agent fallback fail skillId=%s err=%s", agent.id, exc)
        trace = {
            "intent": "task",
            "script": "pipeline_fallback",
            "exitCode": 1,
            "note": "工具执行失败",
            "stdout": "",
            "stderr": str(exc),
        }
    trace["script"] = trace.get("script") or "pipeline_fallback"
    trace["agentSteps"] = steps
    return SkillAgentResult(
        tool_trace=trace,
        output=None,
        latency_ms=latency,
        steps=steps,
        fallback=True,
    )


async def run_excel_skill_agent(
    db: AsyncSession | None,
    agent: FileSkill,
    *,
    user_text: str,
    uploaded_files: list[dict] | None,
    model: str,
    temperature: float = 0.2,
    max_tokens: int = 2048,
    caller_id: str = "",
    chat_messages: ChatMessagesFn | None = None,
) -> SkillAgentResult:
    from app.services.skill_agent.orchestrator import run_skill_orchestrator

    pack = await run_skill_orchestrator(
        db,
        agent,
        user_text=user_text,
        uploaded_files=uploaded_files,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        caller_id=caller_id,
        chat=chat_messages,
    )
    if pack is None:
        raise RuntimeError("excel skill orchestrator returned None")
    return pack


async def run_pipeline_skill_agent(
    db: AsyncSession | None,
    agent: FileSkill,
    *,
    user_text: str,
    uploaded_files: list[dict] | None,
    model: str,
    temperature: float = 0.2,
    max_tokens: int = 2048,
    caller_id: str = "",
    runner: Callable[..., dict[str, Any]],
    runner_kwargs: dict[str, Any] | None = None,
    chat_messages: ChatMessagesFn | None = None,
) -> SkillAgentResult:
    chat = chat_messages or run_chat_messages
    session = PipelineToolSession(
        user_text,
        uploaded_files,
        skill_body=(getattr(agent, "md_doc", None) or "")[:8000],
        runner=runner,
        runner_kwargs=runner_kwargs,
    )
    clauses = goals_from_clauses(user_text)
    if not clauses:
        clauses = [Goal(id="main", label="完成用户请求", tools=("execute",), note_needles=())]
    checklist = Checklist(goals=clauses)
    return await _agent_loop(
        db,
        agent,
        user_text=user_text,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        caller_id=caller_id,
        chat=chat,
        session=session,
        tools=pipeline_tool_defs(),
        dispatch=_pipeline_dispatch,
        checklist=checklist,
        recommended=["execute"],
        extra_rules=PIPELINE_RULES,
        bootstrap="请先 execute。多步时下一次 execute 的 focus 填未完成子句。",
        fallback_fn=lambda: runner(user_text, **(runner_kwargs or {})),
        auto_tools=["execute"],
    )


async def run_skill_agent_for(
    db: AsyncSession | None,
    agent: FileSkill,
    *,
    user_text: str,
    uploaded_files: list[dict] | None,
    model: str,
    temperature: float = 0.2,
    max_tokens: int = 2048,
    caller_id: str = "",
    conversation_id: str | None = None,
) -> SkillAgentResult | None:
    """带工具 Skill：规划 → 自动执行 → 终稿；纯提示词 Skill 返回 None。"""
    from app.services.skill_agent.orchestrator import run_skill_orchestrator

    return await run_skill_orchestrator(
        db,
        agent,
        user_text=user_text,
        uploaded_files=uploaded_files,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        caller_id=caller_id,
        conversation_id=conversation_id,
    )
