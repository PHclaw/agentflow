"""多步任务清单。"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Goal:
    id: str
    label: str
    tools: tuple[str, ...] = ()
    note_needles: tuple[str, ...] = ()
    done: bool = False


@dataclass
class Checklist:
    goals: list[Goal] = field(default_factory=list)

    def pending(self) -> list[Goal]:
        return [g for g in self.goals if not g.done]

    def mark(self, tool: str, obs: dict[str, Any] | None) -> None:
        blob = ""
        try:
            blob = json.dumps(obs or {}, ensure_ascii=False, default=str)
        except TypeError:
            blob = str(obs or "")
        applied = (obs or {}).get("appliedSpec") or {}
        kind = str(applied.get("kind") or "")
        line_mode = str(applied.get("line_mode") or "")
        note = str((obs or {}).get("note") or "")
        hay = f"{blob} {kind} {line_mode} {note} {tool}"
        for g in self.goals:
            if g.done:
                continue
            if tool and tool in g.tools:
                g.done = True
                continue
            if any(n and n in hay for n in g.note_needles):
                g.done = True

    def summary(self) -> str:
        if not self.goals:
            return "（无拆解子任务）"
        lines = []
        for g in self.goals:
            flag = "已完成" if g.done else "未完成"
            lines.append(f"- [{flag}] {g.label}（id={g.id}）")
        return "\n".join(lines)

    def missing_artifacts(self, urls: list[str] | None) -> str:
        """清单标完成但下载列表对不上时，禁止 finish。"""
        blob = " ".join(str(u) for u in (urls or []))
        for g in self.goals:
            if g.id == "workbook" and not re.search(r"\.(xlsx|xls)(\?|$)", blob, re.I):
                return "尚未生成可下载的 Excel 文件，请调用 export_workbook"
            if g.id in {"combo-total", "bar-total-col", "combo-each", "pie"} and g.done:
                if not re.search(r"\.(png|jpe?g|gif|webp)(\?|$)", blob, re.I):
                    return f"任务 {g.label} 没有图片产出，请改用对应 chart_* 工具"
        return ""


def goals_from_clauses(text: str) -> list[Goal]:
    """按「再/另外/并且/1. 2.」切开，供任意 Skill 使用。"""
    t = (text or "").strip()
    t = re.split(r"\n## (?:当前上传|上传文件|先前对话)", t, maxsplit=1)[0]
    parts = re.split(
        r"[;；]|"
        r"再(?:画|做|生成|导出|绘制|转)|"
        r"另外|同时|并且|以及|还要|然后|"
        r"\n\s*[（(]?\d+[)）、.]",
        t,
    )
    chunks = [re.sub(r"\s+", " ", p).strip(" 。，,") for p in parts]
    chunks = [c for c in chunks if len(c) >= 4]
    if len(chunks) <= 1:
        return []
    return [
        Goal(
            id=f"clause-{i}",
            label=c[:48],
            tools=("execute", "run_pipeline"),
            note_needles=(c[:6],),
        )
        for i, c in enumerate(chunks[:8])
    ]


def excel_goals(text: str) -> list[Goal]:
    from app.services.skill.excel_engine import (
        wants_chart_output,
        wants_combo_chart,
        wants_combo_total_line,
        wants_pie_chart,
        wants_total_as_extra_series,
        wants_workbook_output,
    )
    from app.services.skill.excel_pipeline import prefer_current_user_text

    t = prefer_current_user_text(text)
    goals: list[Goal] = []
    chart = wants_chart_output(t)
    if wants_workbook_output(t):
        goals.append(
            Goal(
                id="workbook",
                label="生成带数据的 Excel 文件（xlsx）",
                tools=("export_workbook", "add_computed_column", "export_xlsx"),
                note_needles=(".xlsx", ".xls", "downloadUrl"),
            )
        )
    if chart and wants_combo_total_line(t):
        goals.append(
            Goal(
                id="combo-total",
                label="各品类柱状 + 总销量变化折线",
                tools=("chart_combo_bar_with_total_line",),
                note_needles=("combo_line=total", "合计变化"),
            )
        )
    elif chart and wants_total_as_extra_series(t) and not wants_workbook_output(t):
        goals.append(
            Goal(
                id="bar-total-col",
                label="分组柱状并增加总销量列",
                tools=("chart_grouped_bar_with_total_column",),
                note_needles=("含总销量", "include_total"),
            )
        )
    elif chart and wants_combo_chart(t):
        goals.append(
            Goal(
                id="combo-each",
                label="柱状+折线组合图",
                tools=("chart_combo_bar_with_each_line", "chart_combo_bar_with_total_line"),
                note_needles=("combo_line=",),
            )
        )
    if chart and wants_pie_chart(t):
        goals.append(
            Goal(
                id="pie",
                label="销量占比饼图",
                tools=("chart_pie",),
                note_needles=("chart=pie", "饼图", "占比"),
            )
        )
    extra = goals_from_clauses(t)
    seen = {g.id for g in goals}
    for g in extra:
        if g.id not in seen:
            goals.append(g)
    return goals
