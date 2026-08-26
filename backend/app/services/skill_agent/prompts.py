"""Skill 系统提示。"""

from __future__ import annotations

from typing import Any

from app.services.skill_agent.protocol import schema_hint


def catalog_block(skill_name: str, skill_id: str, description: str, tools: list[dict[str, Any]]) -> str:
    lines = [
        f"当前已激活 Skill：{skill_name}（id={skill_id}）。",
        f"一句话能力：{(description or '').strip()[:400]}",
        "工具一览：",
    ]
    for t in tools:
        lines.append(f"- {t['name']}: {t.get('description') or ''}")
    return "\n".join(lines)


def agent_system_prompt(
    *,
    skill_name: str,
    skill_id: str,
    description: str,
    tools: list[dict[str, Any]],
    skill_body: str = "",
    recommended_tools: list[str] | None = None,
    extra_rules: str = "",
) -> str:
    tool_detail = []
    for t in tools:
        schema = t.get("parameters") or {}
        tool_detail.append(f"### {t['name']}\n{t.get('description') or ''}\n参数: {schema}")
    body = (skill_body or "").strip()
    body_part = ""
    if body:
        body_part = "\n\n## SKILL.md（按需已展开，勿再 read_skill）\n" + body[:8000]
    recs = [r for r in (recommended_tools or []) if r]
    rec_line = ""
    if recs:
        rec_line = "- 必须按清单逐个调用：" + " → ".join(f"`{r}`" for r in recs) + "。未完成禁止 finish。\n"
    extra = (extra_rules or "").strip()
    extra_part = ("\n" + extra + "\n") if extra else ""
    return (
        "你是主 Agent：只使用当前已激活的这一个 Skill，禁止改用、调用或推荐其它 Skill。"
        "把用户请求拆成子任务，逐个调用当前 Skill 的工具。"
        "一次请求里有多件事（再画、并且、1. 2.）就必须多次 call_tool。"
        "禁止只做第一件就 finish；禁止用文案假装已经生成未调用的结果。\n\n"
        + catalog_block(skill_name, skill_id, description, tools)
        + "\n\n"
        + schema_hint()
        + "\n规则：\n"
        + rec_line
        + "- 用户点名的每一种产出（图/文件/转换）都必须有对应工具成功记录。\n"
        "- 工具成功后若清单仍有未完成项，继续 call_tool。\n"
        "- 全部完成后 action=finish；说明必须与实际产出一致。不要贴 png 文件名。\n"
        "- 不要让用户改参数或重跑。\n"
        + extra_part
        + "\n## 工具参数\n"
        + "\n".join(tool_detail)
        + body_part
    )


EXCEL_RULES = (
    "- 先看产出类型：表格文件 vs 图。两者不是同一个工具。\n"
    "- 要 xls/xlsx/表格文件/导出、且话里没有「图/柱状/折线/饼」→ 只调 export_workbook。\n"
    "- 禁止 query_sql。单价、公式写进 constraints.prices（如 {\"铅笔\":1,\"钢笔\":10}），"
    "总销售金额由系统按 数量×单价 计算，不要让模型手算或写 SQL。\n"
    "- 「柱状图」再「生成一个总销售金额折线」是两张图：chart_grouped_bar + chart_line，不要组合成一张。\n"
    "- 「增加一列总销量」且同时要图 → export_workbook（写列）+ 柱状图（图里不要再塞金额列）。\n"
    "- 「占比/饼图」→ chart_pie，不能用柱状组合图冒充。\n"
    "- 柱状图和饼图同时出现：两个工具都要调。\n"
    "- 表格已预览则不必 parse_table。禁止把未生成的文件写进回复。"
)

PIPELINE_RULES = (
    "- 用 execute 完成本 Skill 能力；多步时 focus 填尚未完成的那一句。\n"
    "- 系统若已自动 execute，核对结果后 finish，不要假装没跑过。\n"
    "- 不要把「会做」写成已经做完。"
)


def plan_system_prompt(
    *,
    skill_name: str,
    skill_id: str,
    description: str,
    tools: list[dict[str, Any]],
    extra_rules: str = "",
) -> str:
    from app.services.skill_agent.protocol import plan_schema_hint

    names = "、".join(t["name"] for t in tools)
    extra = (extra_rules or "").strip()
    return (
        "你只负责整理当前已激活 Skill 的任务需求，不要执行、不要写给用户的完成说明。\n"
        f"{catalog_block(skill_name, skill_id, description, tools)}\n"
        f"可用工具名：{names}\n"
        + (extra + "\n" if extra else "")
        + "规则：只使用上列工具；你整理需求，不执行计算、不写 SQL。"
        "用户给的标题、单价、页码、文件顺序必须写进 summary 与 constraints；"
        "不要用「销量情况」等套话当标题，除非用户原文就是销量。\n"
        + plan_schema_hint()
    )


def final_system_prompt(*, skill_name: str, skill_id: str) -> str:
    return (
        f"你是「{skill_name}」（{skill_id}）的终稿助手。"
        "根据已经执行的工具结果用简体中文回复用户。"
        "只陈述实际发生的事：生成了哪些文件/图、算了哪一列、检索到什么。"
        "stdout 里若有「总销售金额」表，必须把各月数字写进回复，不要只说「已计算」。"
        "禁止编造未出现在工具结果里的数字、会议名、下载。"
        "禁止套用无关模板（不要无故写「销量情况」）。"
        "不要输出 JSON，不要贴 png 文件名。"
        "xlsx 请用 Markdown 链接 [下载 Excel](url)；图由下方卡片展示。"
        "工具失败就直说失败原因，不要假装已完成。"
    )
