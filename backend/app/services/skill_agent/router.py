"""Excel 仅导出工作簿时的直接出表路径。"""
from __future__ import annotations

from typing import Any

from app.logging_setup import get_logger
from app.services.skill_agent.checklist import Checklist, excel_goals
from app.services.skill_agent.excel_tools import ExcelToolSession

logger = get_logger("skill-agent-router")


def excel_workbook_only(user_text: str) -> bool:
    from app.services.skill.excel_engine import wants_chart_output, wants_workbook_output

    return wants_workbook_output(user_text) and not wants_chart_output(user_text)


def export_user_reply(
    download_url: str | None,
    download_name: str | None,
    *,
    has_total: bool = True,
) -> str:
    name = download_name or "结果.xlsx"
    url = download_url or ""
    col = "「总销量」列" if has_total else "数据"
    if url:
        return (
            f"已生成 Excel 文件，并写入{col}。请点击下方卡片下载。\n\n"
            f"[下载 {name}]({url})"
        )
    return f"已生成 Excel 文件，并写入{col}。请使用回复下方的下载卡片。"


def try_excel_workbook_direct(
    user_text: str,
    uploaded_files: list[dict] | None,
) -> Any | None:
    """只要表格文件、不要图：直接 export_workbook，不进模型循环、不二次解读。"""
    from app.services.skill_agent.runtime import SkillAgentResult

    if not excel_workbook_only(user_text):
        return None
    session = ExcelToolSession(user_text, uploaded_files)
    session.allow_charts = False
    loaded = session.load_if_possible()
    if not loaded.get("ok"):
        logger.info("excel direct export skip, load fail: %s", loaded.get("error"))
        return None
    out = session.export_workbook({})
    if not out.get("ok"):
        logger.info("excel direct export fail: %s", out.get("error"))
        return None
    checklist = Checklist(goals=excel_goals(user_text))
    checklist.mark("export_workbook", out)
    trace = session.to_tool_trace()
    steps = [
        {
            "step": "direct-0",
            "action": "call_tool",
            "name": "export_workbook",
            "ok": True,
            "auto": True,
        }
    ]
    trace["agentSteps"] = steps
    trace["checklist"] = checklist.summary()
    return SkillAgentResult(
        tool_trace=trace,
        output=export_user_reply(out.get("downloadUrl"), out.get("downloadName")),
        latency_ms=0,
        steps=steps,
    )


def sanitize_export_trace(trace: dict[str, Any] | None) -> dict[str, Any] | None:
    if not trace:
        return trace
    urls = [str(u) for u in (trace.get("downloadUrls") or []) if u]
    if trace.get("downloadUrl"):
        urls.insert(0, str(trace["downloadUrl"]))
    sheets = [u for u in dict.fromkeys(urls) if _is_sheet(u)]
    name = (trace.get("downloadName") if sheets else None) or (
        sheets[-1].rsplit("/", 1)[-1] if sheets else None
    )
    return {
        **trace,
        "intent": "export",
        "downloadUrl": sheets[-1] if sheets else None,
        "downloadName": name,
        "downloadUrls": sheets[-1:] if sheets else [],
        "imageUrl": None,
    }


def export_trace_has_sheet(trace: dict[str, Any] | None) -> bool:
    if not trace:
        return False
    urls = [str(u) for u in (trace.get("downloadUrls") or []) if u]
    if trace.get("downloadUrl"):
        urls.insert(0, str(trace["downloadUrl"]))
    return any(_is_sheet(u) for u in urls)


def _is_sheet(url: str) -> bool:
    import re

    return bool(re.search(r"\.(xlsx|xls|csv)(\?|$)", str(url), re.I))
