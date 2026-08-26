"""带工具 Skill：先整理任务规划，再执行工具，最后生成回复。"""
from __future__ import annotations

import json
import re
from typing import Any, Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.logging_setup import get_logger
from app.services.adapters.base import ChatResult
from app.services.model_runtime import run_chat
from app.services.skill.excel_pipeline import prefer_current_user_text
from app.services.skill.store import FileSkill
from app.services.skill_agent.excel_tools import (
    ExcelToolSession,
    excel_tool_defs,
    recommend_excel_tools,
)
from app.services.skill_agent.pipeline_pack import PipelineToolSession, pipeline_tool_defs
from app.services.skill_agent.prompts import (
    EXCEL_RULES,
    PIPELINE_RULES,
    final_system_prompt,
    plan_system_prompt,
)
from app.services.skill_agent.protocol import ActionParseError, parse_task_plan
from app.services.skill_agent.runtime import (
    TOOL_ALIASES,
    SkillAgentResult,
    _excel_dispatch,
    _pipeline_dispatch,
    _strip_chart_embeds,
)

logger = get_logger("skill-orchestrator")

ChatFn = Callable[..., Awaitable[ChatResult]]

SKIP_AUTO_TOOLS = frozenset({"query_sql", "read_skill", "preview_frame", "parse_table"})


def _allowed_names(tools: list[dict[str, Any]]) -> set[str]:
    names = {str(t.get("name") or "") for t in tools}
    names.update(TOOL_ALIASES.keys())
    names.update(TOOL_ALIASES.values())
    return {n for n in names if n}


def _merge_constraints(args: dict[str, Any], constraints: dict[str, Any]) -> dict[str, Any]:
    out = dict(args or {})
    title = constraints.get("title") or constraints.get("chart_title")
    if title and not out.get("title"):
        out["title"] = title
    return out


def _apply_excel_plan_computations(session: Any, user_text: str, constraints: dict[str, Any]) -> None:
    if not getattr(session, "con", None) or not getattr(session, "table_map", None):
        return
    from app.services.skill.excel_engine import apply_unit_price_amount, coerce_price_map

    extra = coerce_price_map(constraints.get("prices"))
    nested = constraints.get("computations")
    if isinstance(nested, dict):
        extra.update(coerce_price_map(nested.get("prices")))
        extra.update(coerce_price_map(nested.get("总销售金额")))
    apply_unit_price_amount(session.con, session.table_map, user_text, extra_prices=extra or None)
    preview = getattr(session, "preview_frame", None)
    if callable(preview):
        got = preview({"limit": 8})
        if isinstance(got, dict) and got.get("markdown"):
            session.table_preview = str(got["markdown"])


def _union_excel_calls(
    required: list[dict[str, Any]],
    planned: list[dict[str, Any]],
    constraints: dict[str, Any],
) -> list[dict[str, Any]]:
    """合并推荐工具与规划结果，规划中的参数优先。"""
    by_plan = {c["name"]: c for c in planned}
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in required:
        name = item["name"]
        if name in seen:
            continue
        src = by_plan.get(name, item)
        out.append({"name": name, "args": _merge_constraints(src.get("args") or {}, constraints)})
        seen.add(name)
    required_charts = {c["name"] for c in required if str(c.get("name") or "").startswith("chart_")}
    for item in planned:
        name = item["name"]
        if name in seen:
            continue
        if required_charts and name.startswith("chart_") and name not in required_charts:
            continue
        seen.add(name)
        out.append(item)
    return out or required or planned


def _heuristic_calls(agent: FileSkill, user_text: str, kind: str) -> list[dict[str, Any]]:
    if kind == "excel":
        return [{"name": n, "args": {}} for n in recommend_excel_tools(user_text)]
    return [{"name": "execute", "args": {"focus": prefer_current_user_text(user_text)}}]


def _filter_calls(
    planned: list[dict[str, Any]],
    allowed: set[str],
    constraints: dict[str, Any],
    *,
    fallback: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in planned:
        raw = str(item.get("name") or "")
        name = TOOL_ALIASES.get(raw, raw)
        if name not in allowed and raw not in allowed:
            continue
        name = TOOL_ALIASES.get(name, name)
        if name in seen or name in SKIP_AUTO_TOOLS:
            continue
        seen.add(name)
        out.append({"name": name, "args": _merge_constraints(item.get("args") or {}, constraints)})
    return out or fallback


def _excel_output_appendix(session: Any, trace: dict[str, Any]) -> str:
    bits: list[str] = []
    md = str(getattr(session, "table_preview", "") or trace.get("stdout") or "")
    if "总销售金额" in md:
        bits.append("计算得到的「总销售金额」列如下：\n\n" + md.strip())
    urls = [str(u) for u in (trace.get("downloadUrls") or []) if u]
    sheets = [u for u in urls if re.search(r"\.(xlsx|xls)(\?|$)", u, re.I)]
    if sheets:
        name = trace.get("downloadName") or sheets[0].rsplit("/", 1)[-1]
        bits.append(f"[下载 {name}]({sheets[0]})")
    return "\n\n".join(bits)


def _digest(trace: dict[str, Any], steps: list[dict[str, Any]]) -> str:
    blob = {
        "note": trace.get("note"),
        "stdout": str(trace.get("stdout") or "")[:4000],
        "stderr": str(trace.get("stderr") or "")[:800],
        "downloadUrl": trace.get("downloadUrl"),
        "downloadName": trace.get("downloadName"),
        "downloadUrls": (trace.get("downloadUrls") or [])[:8],
        "intent": trace.get("intent"),
        "exitCode": trace.get("exitCode"),
        "steps": steps[:16],
    }
    try:
        return json.dumps(blob, ensure_ascii=False, default=str)
    except TypeError:
        return str(blob)


def _kind_and_pack(agent: FileSkill, user_text: str, uploaded_files: list[dict] | None, conversation_id: str | None):
    from app.services.skill.academic_search_pipeline import (
        is_academic_search_skill,
        run_academic_search,
    )
    from app.services.skill.excel_pipeline import is_excel_skill
    from app.services.skill.lit_review_pipeline import is_lit_review_skill, run_lit_review_prepare
    from app.services.skill.pdf_pipeline import is_pdf_skill, run_pdf_tools
    from app.services.skill.ppt_pipeline import is_ppt_skill, run_ppt_tools
    from app.services.skill.stat_pipeline import is_statistical_skill, run_statistical_tools

    if is_excel_skill(agent):
        session = ExcelToolSession(
            user_text, uploaded_files, skill_body=(getattr(agent, "md_doc", None) or "")[:8000]
        )
        from app.services.skill.excel_engine import wants_chart_output, wants_workbook_output

        include_charts = wants_chart_output(user_text) or not wants_workbook_output(user_text)
        session.allow_charts = include_charts
        session.load_if_possible()
        tools = [t for t in excel_tool_defs(include_charts=include_charts) if t.get("name") != "query_sql"]
        return "excel", session, tools, _excel_dispatch, EXCEL_RULES
    runner = None
    runner_kwargs: dict[str, Any] = {}
    if is_pdf_skill(agent):
        runner, runner_kwargs = run_pdf_tools, {"uploaded_files": uploaded_files}
    elif is_statistical_skill(agent):
        runner, runner_kwargs = run_statistical_tools, {
            "uploaded_files": uploaded_files,
            "scripts_dir": getattr(agent, "scripts_dir", None),
        }
    elif is_ppt_skill(agent):
        runner, runner_kwargs = run_ppt_tools, {
            "uploaded_files": uploaded_files,
            "conversation_id": conversation_id,
        }
    elif is_academic_search_skill(agent):
        runner, runner_kwargs = run_academic_search, {"conversation_id": conversation_id}
    elif is_lit_review_skill(agent):
        runner, runner_kwargs = run_lit_review_prepare, {"conversation_id": conversation_id}
    if runner is None:
        return None, None, None, None, None
    session = PipelineToolSession(
        user_text,
        uploaded_files,
        skill_body=(getattr(agent, "md_doc", None) or "")[:8000],
        runner=runner,
        runner_kwargs=runner_kwargs,
    )
    return "pipeline", session, pipeline_tool_defs(), _pipeline_dispatch, PIPELINE_RULES


async def run_skill_orchestrator(
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
    chat: ChatFn | None = None,
    intro_only: bool = False,
) -> SkillAgentResult | None:
    """带工具 Skill 走规划→执行→终稿；纯提示词 Skill 返回 None。"""
    kind, session, tools, dispatch, extra_rules = _kind_and_pack(
        agent, user_text, uploaded_files, conversation_id
    )
    if session is None or tools is None or dispatch is None:
        return None

    chat_fn = chat or run_chat
    allowed = _allowed_names(tools)
    fallback = _heuristic_calls(agent, user_text, kind or "pipeline")
    latency = 0
    steps: list[dict[str, Any]] = []
    plan: dict[str, Any] = {
        "mode": "intro" if intro_only else "task",
        "summary": prefer_current_user_text(user_text),
        "deliverables": [],
        "tools": [],
        "constraints": {},
    }

    if not intro_only:
        plan_sys = plan_system_prompt(
            skill_name=agent.name or agent.id,
            skill_id=agent.id,
            description=agent.description or agent.router_blurb or "",
            tools=tools,
            extra_rules=extra_rules or "",
        )
        files = [str(f.get("name") or "") for f in (uploaded_files or []) if f.get("name")]
        plan_user = (
            f"用户请求：\n{user_text or ''}\n\n"
            f"上传文件：{files or '无'}\n"
            "请整理需求 JSON。"
        )
        try:
            plan_res = await chat_fn(
                db,
                user_id=getattr(agent, "author_id", None) or caller_id,
                model=model,
                system=plan_sys,
                user=plan_user,
                variables=None,
                temperature=min(float(temperature), 0.2),
                max_tokens=min(int(max_tokens), 512),
                scene="skill-plan",
                log_extra={
                    "skillId": agent.id,
                    "skill": agent.name or "",
                    "caller": caller_id,
                    "phase": "plan",
                },
            )
            latency += int(plan_res.latency_ms or 0)
            plan = parse_task_plan(plan_res.output or "")
        except (ActionParseError, Exception) as exc:  # noqa: BLE001
            logger.warning("skill plan fail skillId=%s err=%s", agent.id, exc)
            steps.append({"step": "plan", "ok": False, "error": str(exc)[:200]})

        if plan.get("mode") == "intro" and not uploaded_files:
            intro_only = True

    calls: list[dict[str, Any]] = []
    if not intro_only:
        if kind == "excel":
            _apply_excel_plan_computations(session, user_text, plan.get("constraints") or {})
        calls = _filter_calls(plan.get("tools") or [], allowed, plan.get("constraints") or {}, fallback=fallback)
        if kind == "excel":
            calls = _union_excel_calls(fallback, calls, plan.get("constraints") or {})
        for i, call in enumerate(calls):
            name = call["name"]
            args = call.get("args") or {}
            if name == "execute" and not str(args.get("focus") or "").strip():
                args = {**args, "focus": plan.get("summary") or prefer_current_user_text(user_text)}
            obs = dispatch(session, name, args)
            steps.append(
                {
                    "step": f"auto-{i}",
                    "action": "call_tool",
                    "name": name,
                    "ok": bool(obs.get("ok")),
                    "auto": True,
                    "error": None if obs.get("ok") else str(obs.get("error") or "")[:200],
                }
            )
            if not obs.get("ok"):
                logger.info("orchestrator tool fail name=%s err=%s", name, obs.get("error"))
        if kind == "excel":
            from app.services.skill.excel_engine import wants_sales_amount

            urls_now = list(getattr(session, "download_urls", None) or [])
            has_xlsx = any(re.search(r"\.(xlsx|xls)(\?|$)", str(u), re.I) for u in urls_now)
            if wants_sales_amount(user_text) and not has_xlsx:
                obs = dispatch(session, "export_workbook", {})
                steps.append(
                    {
                        "step": "auto-export",
                        "action": "call_tool",
                        "name": "export_workbook",
                        "ok": bool(obs.get("ok")),
                        "auto": True,
                        "error": None if obs.get("ok") else str(obs.get("error") or "")[:200],
                    }
                )

    trace = session.to_tool_trace()
    if intro_only:
        from app.services.skill.capability import intro_trace

        trace = intro_trace(agent)
        trace["intent"] = "intro"

    skip_final = bool(trace.get("intent") == "compose")
    output: str | None = None
    if not skip_final:
        from app.services.skill.capability import INTRO_SYSTEM_ADDENDUM, format_intro_tool_result

        extra = ""
        if not intro_only and "文献速读" in (agent.name or ""):
            extra = (
                "\n若工具给出了摘要材料，输出结构化速读："
                "研究问题、方法、关键结果、局限、可引用表述、待核实。"
                "禁止编造摘要中没有的数字。"
            )
        final_sys = final_system_prompt(skill_name=agent.name or agent.id, skill_id=agent.id) + extra
        if intro_only:
            final_sys = final_sys + "\n\n" + INTRO_SYSTEM_ADDENDUM
            digest = format_intro_tool_result(trace)
        else:
            digest = _digest(trace, steps)
        final_user = (
            f"需求摘要：{plan.get('summary') or prefer_current_user_text(user_text)}\n\n"
            f"工具结果：\n{digest}\n\n"
            f"原始用户话：\n{prefer_current_user_text(user_text)}"
        )
        try:
            final_res = await chat_fn(
                db,
                user_id=getattr(agent, "author_id", None) or caller_id,
                model=model,
                system=final_sys,
                user=final_user,
                variables=None,
                temperature=min(float(temperature), 0.4),
                max_tokens=int(max_tokens),
                scene="skill-final",
                log_extra={
                    "skillId": agent.id,
                    "skill": agent.name or "",
                    "caller": caller_id,
                    "phase": "final",
                },
            )
            latency += int(final_res.latency_ms or 0)
            output = (final_res.output or "").strip() or None
        except Exception as exc:  # noqa: BLE001
            logger.warning("skill final fail skillId=%s err=%s", agent.id, exc)
            output = (trace.get("note") or "") or None

    if output or kind == "excel":
        urls = [str(u) for u in (trace.get("downloadUrls") or []) if u]
        if output:
            output = _strip_chart_embeds(output, urls) or output
        extra = _excel_output_appendix(session, trace) if kind == "excel" else ""
        if extra and extra not in (output or ""):
            output = ((output or "").rstrip() + "\n\n" + extra).strip()

    trace["agentSteps"] = steps
    trace["planSummary"] = plan.get("summary")
    return SkillAgentResult(
        tool_trace=trace,
        output=output,
        latency_ms=latency,
        steps=steps,
        fallback=not bool(plan.get("tools")) and not intro_only,
    )
