"""Excel 工具：加载表格、导出工作簿、出图。"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable

from app.logging_setup import get_logger
from app.services.skill.excel_engine import (
    TABULAR_SUFFIX,
    add_sum_column,
    combo_line_mode,
    correct_chart_spec,
    expand_chart_spec,
    describe_tables,
    extract_chart_title,
    resolve_chart_title,
    extract_sql,
    is_numeric_type,
    load_pasted_table,
    load_tables,
    parse_pasted_table,
    render_chart,
    render_from_spec,
    rows_to_markdown,
    run_sql,
    summarize_table,
    wants_chart_output,
    wants_amount_line_chart,
    wants_combo_chart,
    wants_combo_total_line,
    wants_pie_chart,
    wants_sales_amount,
    wants_added_column,
    wants_total_as_extra_series,
    wants_workbook_output,
    write_xlsx,
)
from app.services.skill.excel_pipeline import prefer_current_user_text

logger = get_logger("skill-agent-excel")

ToolFn = Callable[[dict[str, Any]], dict[str, Any]]


def _tabular_files(uploaded: list[dict] | None) -> list[dict]:
    out: list[dict] = []
    for f in uploaded or []:
        name = str(f.get("name") or "")
        path = str(f.get("path") or "")
        if Path(name).suffix.lower() in TABULAR_SUFFIX and path and Path(path).is_file():
            out.append(f)
    return out


class ExcelToolSession:
    def __init__(self, user_text: str, uploaded_files: list[dict] | None, skill_body: str = ""):
        self.user_text = user_text or ""
        self.current = prefer_current_user_text(self.user_text)
        self.uploaded = uploaded_files or []
        self.skill_body = skill_body or ""
        self.con = None
        self.table_map: dict[str, str] = {}
        self.stem = "table"
        self.download_urls: list[str] = []
        self.download_name = ""
        self.last_note = ""
        self.last_stdout = ""
        self.skill_loaded = False
        self.last_spec: dict[str, Any] = {}
        self.allow_charts = True
        self.table_preview = ""

    def load_if_possible(self) -> dict[str, Any]:
        files = _tabular_files(self.uploaded)
        parsed = parse_pasted_table(self.current)
        if not files and not parsed:
            return {
                "ok": False,
                "error": "没有识别到表格。请上传 xlsx/csv 或粘贴文本表。",
            }
        try:
            if files:
                self.con, self.table_map = load_tables(files)
                self.stem = Path(str(files[0].get("name") or "table")).stem
            else:
                assert parsed is not None
                cols, rows = parsed
                self.con, self.table_map = load_pasted_table(cols, rows)
                self.stem = "pasted-table"
        except Exception as exc:  # noqa: BLE001
            logger.error("excel session load fail: %s", exc)
            return {"ok": False, "error": f"无法读取表格: {exc}"}
        self._apply_derived_columns()
        inspect = describe_tables(self.con, self.table_map)
        self.last_stdout = inspect
        preview = self.preview_frame({"limit": 8})
        self.table_preview = str(preview.get("markdown") or "")
        return {
            "ok": True,
            "tables": list(self.table_map.keys()),
            "inspect": inspect[:4000],
            "preview": preview.get("markdown", ""),
            "columns": preview.get("columns") or [],
            "numeric_columns": preview.get("numeric_columns") or [],
        }

    def _apply_derived_columns(self, extra_prices: dict[str, float] | None = None) -> None:
        from app.services.skill.excel_engine import apply_unit_price_amount

        apply_unit_price_amount(self.con, self.table_map, self.current, extra_prices=extra_prices)
        preview = self.preview_frame({"limit": 8})
        if preview.get("ok"):
            self.table_preview = str(preview.get("markdown") or "") or self.table_preview

    def _need_table(self) -> dict[str, Any] | None:
        if self.con is None or not self.table_map:
            return {"ok": False, "error": "尚未加载表格，请先 parse_table"}
        return None

    def parse_table(self, _args: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.load_if_possible()

    def preview_frame(self, args: dict[str, Any] | None = None) -> dict[str, Any]:
        err = self._need_table()
        if err:
            return err
        limit = 12
        if args and args.get("limit") is not None:
            try:
                limit = max(1, min(int(args["limit"]), 40))
            except (TypeError, ValueError):
                limit = 12
        tbl = next(iter(self.table_map.values()))
        meta = self.con.execute(f'DESCRIBE "{tbl}"').fetchall()
        names = [c[0] for c in meta if c[0] != "_src_order"]
        nums = [
            c[0]
            for c in meta
            if is_numeric_type(str(c[1])) and c[0] != "_src_order"
        ]
        df = self.con.execute(f'SELECT * FROM "{tbl}" LIMIT {limit}').fetchdf()
        if "_src_order" in df.columns:
            df = df.drop(columns=["_src_order"])
        rows = [tuple(r) for r in df.itertuples(index=False, name=None)]
        md = rows_to_markdown(list(df.columns), rows, cap=limit)
        return {
            "ok": True,
            "columns": names,
            "numeric_columns": nums,
            "markdown": md,
            "row_preview": len(rows),
        }

    def _keep_latest_xlsx(self, url: str, fname: str) -> None:
        self.download_urls = [
            u
            for u in self.download_urls
            if not re.search(r"\.(xlsx|xls|csv)(\?|$)", str(u), re.I)
        ]
        self.download_urls.append(url)
        self.download_name = fname

    def add_computed_column(self, args: dict[str, Any] | None = None) -> dict[str, Any]:
        err = self._need_table()
        if err:
            return err
        args = args or {}
        name = str(args.get("name") or "总销量").strip() or "总销量"
        cols, rows, note = add_sum_column(self.con, self.table_map, name=name)
        url, fname = write_xlsx(cols, rows, sheet="数据", stem="sales-summary")
        self._keep_latest_xlsx(url, fname)
        self.last_note = note
        md = rows_to_markdown(cols, rows)
        self.last_stdout = md
        self.table_preview = md
        return {
            "ok": True,
            "note": note,
            "markdown": md[:6000],
            "downloadUrl": url,
            "downloadName": fname,
            "downloadUrls": [url],
            "artifact": "xlsx",
            "columns": cols,
        }

    def query_sql(self, args: dict[str, Any] | None = None) -> dict[str, Any]:
        err = self._need_table()
        if err:
            return err
        args = args or {}
        sql = str(args.get("sql") or "").strip() or extract_sql(self.current) or ""
        if not sql:
            return {"ok": False, "error": "需要 sql 参数"}
        cols, rows, qerr = run_sql(self.con, sql, self.table_map)
        if qerr:
            return {"ok": False, "error": qerr, "sql": sql}
        md = rows_to_markdown(cols, rows)
        self.last_stdout = md
        return {"ok": True, "sql": sql, "markdown": md[:8000], "rows": len(rows)}

    def _draw(self, spec: dict[str, Any]) -> dict[str, Any]:
        err = self._need_table()
        if err:
            return err
        if wants_workbook_output(self.current) and not wants_chart_output(self.current):
            return {
                "ok": False,
                "error": "用户要的是 Excel 表格文件，不是图。请调用 export_workbook。",
            }
        spec = expand_chart_spec(spec, self.current)
        spec = dict(spec)
        resolved = resolve_chart_title(
            self.current,
            spec.get("title"),
            kind=str(spec.get("kind") or "bar"),
        )
        if resolved:
            spec["title"] = resolved
        else:
            spec.pop("title", None)
        self.last_spec = spec
        try:
            url, name, cnote, chart_urls = render_from_spec(
                self.con,
                self.table_map,
                spec,
                stem=self.stem,
                user_text=self.current,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("render_from_spec fail, regex fallback: %s", exc)
            try:
                url, name, cnote, chart_urls = render_chart(
                    self.con, self.table_map, self.current, stem=self.stem
                )
            except Exception as exc2:  # noqa: BLE001
                return {"ok": False, "error": f"出图失败: {exc2}"}
        chart_urls = chart_urls or [url]
        self.download_urls.extend(chart_urls)
        if not re.search(r"\.(xlsx|xls)(\?|$)", str(self.download_name or ""), re.I):
            self.download_name = name
        self.last_note = cnote
        if not self.table_preview:
            self.last_stdout = cnote
        return {
            "ok": True,
            "note": cnote[:4000],
            "downloadUrl": url,
            "downloadName": name,
            "downloadUrls": chart_urls,
            "imageUrl": url,
            "appliedSpec": {
                "kind": spec.get("kind"),
                "line_mode": spec.get("line_mode"),
                "include_total_as_series": spec.get("include_total_as_series"),
                "total_only": spec.get("total_only"),
            },
        }

    def render_chart(self, args: dict[str, Any] | None = None) -> dict[str, Any]:
        args = args or {}
        spec = args.get("spec") if isinstance(args.get("spec"), dict) else args
        if not isinstance(spec, dict) or not spec:
            rec = recommend_excel_tool(self.current)
            return {
                "ok": False,
                "error": f"render_chart 需要 spec。更常见的请求请直接调用 {rec}，参数可空。",
            }
        return self._draw(spec)

    def chart_grouped_bar(self, args: dict[str, Any] | None = None) -> dict[str, Any]:
        args = args or {}
        return self._draw(
            {
                "kind": "bar",
                "title": args.get("title"),
                "include_total_as_series": bool(args.get("include_total_as_series")),
            }
        )

    def chart_grouped_bar_with_total_column(self, args: dict[str, Any] | None = None) -> dict[str, Any]:
        args = args or {}
        return self._draw(
            {
                "kind": "bar",
                "title": args.get("title"),
                "include_total_as_series": True,
                "total_only": False,
            }
        )

    def chart_combo_bar_with_total_line(self, args: dict[str, Any] | None = None) -> dict[str, Any]:
        args = args or {}
        return self._draw(
            {
                "kind": "combo",
                "line_mode": "total",
                "title": args.get("title"),
            }
        )

    def chart_combo_bar_with_each_line(self, args: dict[str, Any] | None = None) -> dict[str, Any]:
        args = args or {}
        return self._draw(
            {
                "kind": "combo",
                "line_mode": "each",
                "title": args.get("title"),
            }
        )

    def chart_line(self, args: dict[str, Any] | None = None) -> dict[str, Any]:
        args = args or {}
        series = args.get("series")
        if not isinstance(series, list) or not series:
            series = ["总销售金额"] if wants_sales_amount(self.current) else None
        spec: dict[str, Any] = {
            "kind": "line",
            "title": args.get("title") or ("总销售金额变化" if wants_sales_amount(self.current) else None),
        }
        if series:
            spec["series"] = series
        return self._draw(spec)

    def chart_pie(self, args: dict[str, Any] | None = None) -> dict[str, Any]:
        args = args or {}
        return self._draw(
            {
                "kind": "pie",
                "title": args.get("title"),
                "facet": bool(args.get("facet")),
            }
        )

    def export_xlsx(self, args: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.export_workbook(args)

    def export_workbook(self, args: dict[str, Any] | None = None) -> dict[str, Any]:
        """只产出一份 xlsx；要总销量列时写入该列。"""
        args = args or {}
        add_total = args.get("add_total_column")
        if add_total is None:
            if wants_sales_amount(self.current):
                add_total = False
            else:
                add_total = wants_total_as_extra_series(self.current) or bool(
                    re.search(r"总销量|合计", self.current or "")
                )
        if add_total:
            col = str(args.get("name") or "").strip()
            if not col:
                col = "总销量" if "总销量" in (self.current or "") else "合计"
            return self.add_computed_column({"name": col})
        err = self._need_table()
        if err:
            return err
        tbl = next(iter(self.table_map.values()))
        df = self.con.execute(f'SELECT * FROM "{tbl}"').fetchdf()
        if "_src_order" in df.columns:
            df = df.drop(columns=["_src_order"])
        cols = list(df.columns)
        rows = [tuple(r) for r in df.itertuples(index=False, name=None)]
        url, name = write_xlsx(cols, rows, sheet="数据", stem="sales-summary")
        self._keep_latest_xlsx(url, name)
        md = rows_to_markdown(cols, rows)
        self.last_stdout = md
        self.table_preview = md
        self.last_note = "已生成 Excel，并写入当前表格列（含已计算列）。"
        return {
            "ok": True,
            "downloadUrl": url,
            "downloadName": name,
            "downloadUrls": [url],
            "rows": len(rows),
            "artifact": "xlsx",
            "markdown": md[:6000],
        }

    def summarize(self, _args: dict[str, Any] | None = None) -> dict[str, Any]:
        err = self._need_table()
        if err:
            return err
        text = summarize_table(self.con, self.table_map, self.current)
        self.last_stdout = text
        return {"ok": True, "summary": text[:8000]}

    def read_skill(self, _args: dict[str, Any] | None = None) -> dict[str, Any]:
        self.skill_loaded = True
        body = (self.skill_body or "").strip()
        if not body:
            return {"ok": True, "body": "（该 Skill 没有额外 SKILL.md 正文）"}
        return {"ok": True, "body": body[:8000]}

    def to_tool_trace(self, *, intent: str = "task", exit_code: int = 0) -> dict[str, Any]:
        urls = list(dict.fromkeys(self.download_urls))
        images = [u for u in urls if re.search(r"\.(png|jpe?g|gif|webp)(\?|$)", str(u), re.I)]
        sheets = [u for u in urls if re.search(r"\.(xlsx|xls|csv)(\?|$)", str(u), re.I)]
        if sheets and not wants_chart_output(self.current):
            urls = sheets
            images = []
            intent = "export"
        elif sheets and not images:
            intent = "export"
        elif images:
            intent = "chart"
        elif sheets:
            intent = "export"
        primary = sheets or images or urls
        parts = [self.table_preview, self.last_stdout, self.last_note]
        seen: list[str] = []
        for p in parts:
            t = str(p or "").strip()
            if t and t not in seen:
                seen.append(t)
        stdout = "\n\n".join(seen)[:14000]
        return {
            "intent": intent,
            "script": "skill_agent",
            "exitCode": exit_code,
            "stdout": stdout,
            "stderr": "",
            "note": self.last_note or "Skill Agent 已执行工具",
            "downloadUrl": primary[0] if primary else None,
            "downloadName": self.download_name or None,
            "downloadUrls": urls,
            "imageUrl": images[0] if images else None,
        }


def recommend_excel_tools(text: str) -> list[str]:
    """先分产出类型（表格 vs 图），再列工具。"""
    t = prefer_current_user_text(text)
    out: list[str] = []
    if wants_workbook_output(t) or wants_added_column(t) or wants_sales_amount(t):
        out.append("export_workbook")
    if wants_chart_output(t):
        if wants_combo_total_line(t) and not wants_amount_line_chart(t):
            out.append("chart_combo_bar_with_total_line")
        elif wants_total_as_extra_series(t) and "export_workbook" not in out:
            out.append("chart_grouped_bar_with_total_column")
        elif wants_combo_chart(t) and combo_line_mode(t) == "each":
            out.append("chart_combo_bar_with_each_line")
        elif re.search(r"柱状|柱形|条形|bar", t, re.I):
            out.append("chart_grouped_bar")
        if wants_amount_line_chart(t) or (
            re.search(r"折线|line", t, re.I)
            and wants_sales_amount(t)
            and not wants_combo_chart(t)
        ):
            out.append("chart_line")
        if wants_pie_chart(t):
            out.append("chart_pie")
    if not out:
        out.append("summarize")
    return out


def recommend_excel_tool(text: str) -> str:
    recs = recommend_excel_tools(text)
    return recs[0] if recs else "render_chart"


def excel_tool_defs(*, include_charts: bool = True) -> list[dict[str, Any]]:
    title_param = {
        "type": "object",
        "properties": {"title": {"type": "string", "description": "可选图题"}},
    }
    tools = [
        {
            "name": "read_skill",
            "description": "读取当前 Excel Skill 的 SKILL.md 正文（需要细则时调用）。",
            "parameters": {"type": "object", "properties": {}},
        },
        {
            "name": "parse_table",
            "description": "从上传文件或粘贴文本加载表格。",
            "parameters": {"type": "object", "properties": {}},
        },
        {
            "name": "preview_frame",
            "description": "预览列名与前几行。",
            "parameters": {
                "type": "object",
                "properties": {"limit": {"type": "integer"}},
            },
        },
        {
            "name": "add_computed_column",
            "description": "不要单独调用。需要合计列时用 export_workbook。",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
            },
        },
        {
            "name": "query_sql",
            "description": "禁止在规划阶段使用。计算列由系统按单价落地，不要写 SQL。",
            "parameters": {
                "type": "object",
                "properties": {"sql": {"type": "string"}},
                "required": ["sql"],
            },
        },
        {
            "name": "export_workbook",
            "description": "生成可下载的 Excel 工作簿（xlsx，不是图）。"
            "用户说生成xls/xlsx/表格文件/导出/下载表时必须用这个。"
            "「加入一列总销量」且不要图时也用这个。禁止用任何 chart_* 代替。",
            "parameters": {
                "type": "object",
                "properties": {
                    "add_total_column": {"type": "boolean"},
                    "name": {"type": "string"},
                },
            },
        },
        {
            "name": "chart_grouped_bar",
            "description": "分组柱状图（各类商品）。不要用来画总销量折线。"
            "用户只要表格文件、不要图时禁止调用。",
            "parameters": title_param,
        },
        {
            "name": "chart_grouped_bar_with_total_column",
            "description": "仅当用户要「图」且要在图上增加总销量柱时使用。"
            "用户要 xls/xlsx/表格文件而不是图时禁止调用，改用 export_workbook。",
            "parameters": title_param,
        },
        {
            "name": "chart_combo_bar_with_total_line",
            "description": "各品类柱状 + 仅一条总销量/合计变化折线。"
            "用于「柱状图增加总销量的变化折线」。禁止对每类再画折线。",
            "parameters": title_param,
        },
        {
            "name": "chart_combo_bar_with_each_line",
            "description": "各品类柱状 + 每类一条折线。仅当用户要各类商品走势时用。",
            "parameters": title_param,
        },
        {
            "name": "chart_line",
            "description": "单独折线图。用户要「总销售金额变化折线」且柱状是另一张图时用这个，不要用组合图。",
            "parameters": title_param,
        },
        {
            "name": "chart_pie",
            "description": "销量占比饼图。用户同时要柱状图和饼图时必须另外调用本工具"
            "（或 render_chart.charts 含 pie），禁止只用组合图冒充占比。",
            "parameters": title_param,
        },
        {
            "name": "render_chart",
            "description": "多图一次出：spec.charts 可含 combo 与 pie。"
            "单种柱状/组合/饼优先用 chart_* 专用工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "spec": {
                        "type": "object",
                        "properties": {
                            "kind": {"type": "string", "enum": ["bar", "line", "pie", "combo"]},
                            "title": {"type": "string"},
                            "series": {"type": "array", "items": {"type": "string"}},
                            "include_total_as_series": {"type": "boolean"},
                            "total_only": {"type": "boolean"},
                            "line_mode": {"type": "string", "enum": ["each", "total"]},
                            "split": {"type": "boolean"},
                            "charts": {"type": "array"},
                        },
                    }
                },
            },
        },
        {
            "name": "export_xlsx",
            "description": "把当前表原样导出为 xlsx。需要合计列时用 export_workbook。",
            "parameters": {"type": "object", "properties": {}},
        },
        {
            "name": "summarize",
            "description": "数值列描述统计。不要用它代替导出或出图。",
            "parameters": {"type": "object", "properties": {}},
        },
    ]
    overlap = {"export_xlsx", "add_computed_column"}
    tools = [t for t in tools if t["name"] not in overlap]
    if not include_charts:
        hide = {
            "chart_grouped_bar",
            "chart_grouped_bar_with_total_column",
            "chart_combo_bar_with_total_line",
            "chart_combo_bar_with_each_line",
            "chart_line",
            "chart_pie",
            "render_chart",
        }
        tools = [t for t in tools if t["name"] not in hide]
    return tools
