"""Excel表格助手：结构探查 / SQL 分析 / 出图 / 生成或导出工作簿。"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.logging_setup import get_logger
from app.services.skill.excel_engine import (
    TABULAR_SUFFIX,
    add_row_and_col_totals,
    auto_sql,
    category_rollup_rows,
    current_user_text,
    describe_tables,
    extract_sql,
    is_numeric_type,
    load_pasted_table,
    load_tables,
    parse_pasted_table,
    render_chart,
    rows_to_markdown,
    run_sql,
    summarize_table,
    wants_category_rollup,
    wants_plain_totals,
    write_xlsx,
    write_xlsx_sheets,
)

logger = get_logger("excel")


def is_excel_skill(agent) -> bool:
    wf = getattr(agent, "workflow", None) or {}
    if isinstance(wf, dict) and wf.get("kind") == "excel":
        return True
    if (getattr(agent, "id", None) or "") == "excel":
        return True
    name = getattr(agent, "name", None) or ""
    return "Excel表格" in name or name == "Excel表格助手"


def prefer_current_user_text(text: str) -> str:
    return current_user_text(text)


def _tabular_files(uploaded: list[dict] | None) -> list[dict]:
    out: list[dict] = []
    for f in uploaded or []:
        name = str(f.get("name") or "")
        path = str(f.get("path") or "")
        if Path(name).suffix.lower() in TABULAR_SUFFIX and path and Path(path).is_file():
            out.append(f)
    return out


def route_intent(text: str) -> str:
    current = prefer_current_user_text(text)
    t = current.lower()
    from app.services.skill.excel_engine import wants_chart_output, wants_workbook_output

    if wants_workbook_output(current) and not wants_chart_output(current):
        return "export"
    if any(k in t for k in ("图", "可视化", "chart", "plot", "饼", "柱状", "折线", "散点", "直方", "雷达")):
        return "chart"
    if extract_sql(prefer_current_user_text(text)):
        return "query"
    if any(k in t for k in ("描述统计", "summary", "均值", "分布怎么样", "统计摘要")):
        return "summary"
    if any(k in t for k in ("结构", "有哪些列", "inspect", "看看表", "字段")):
        return "inspect"
    if any(k in t for k in ("新建", "做一张表", "生成表格", "生成excel", "做成xlsx", "从下面", "贴的表")):
        return "create"
    if any(k in t for k in ("导出", "下载", "另存", "给我excel", "给我xlsx", "转成xlsx", "转成csv")):
        return "export"
    if any(k in t for k in ("汇总", "分组", "筛选", "sql", "join", "top", "最高", "最多", "分析")):
        return "analyze"
    return "analyze"


def run_excel_tools(
    user_text: str,
    *,
    uploaded_files: list[dict] | None = None,
) -> dict[str, Any]:
    files = _tabular_files(uploaded_files)
    intent = route_intent(user_text)
    current = prefer_current_user_text(user_text)
    parsed = parse_pasted_table(current)

    if not files and not parsed:
        return {
            "intent": intent,
            "script": "excel_pipeline",
            "exitCode": 1,
            "stdout": "",
            "stderr": "",
            "note": (
                "没有识别到表格。可以：上传 .xlsx / .xls / .csv / .tsv；"
                "或直接粘贴空格/制表符对齐的文本表、Markdown 表、CSV。"
                "单元格里的「10支」「8块」会自动收成数字。"
            ),
        }

    try:
        if files:
            con, table_map = load_tables(files)
            stem = Path(str(files[0].get("name") or "table")).stem
        else:
            assert parsed is not None
            cols, rows = parsed
            con, table_map = load_pasted_table(cols, rows)
            stem = "pasted-table"
    except Exception as exc:  # noqa: BLE001
        logger.error("load tables fail: %s", exc)
        return {
            "intent": intent,
            "script": "excel_pipeline",
            "exitCode": 1,
            "stdout": "",
            "stderr": str(exc),
            "note": f"无法读取表格: {exc}",
        }
    if not table_map:
        return {
            "intent": intent,
            "script": "excel_pipeline",
            "exitCode": 1,
            "stdout": "",
            "stderr": "",
            "note": "文件里没有可用的数据表（空表或无法解析）。",
        }

    inspect_txt = describe_tables(con, table_map)
    extra_urls: list[str] = []

    from app.services.skill.excel_engine import (
        add_sum_column,
        wants_chart_output,
        wants_workbook_output,
        write_xlsx,
    )

    if wants_workbook_output(current) and not wants_chart_output(current):
        col_name = "总销量" if "总销量" in current else "合计"
        cols, rows, note = add_sum_column(con, table_map, name=col_name)
        url, name = write_xlsx(cols, rows, sheet="数据", stem="sales-summary")
        md = rows_to_markdown(cols, rows)
        return {
            "intent": "export",
            "script": "excel_pipeline",
            "exitCode": 0,
            "stdout": md,
            "stderr": "",
            "note": note,
            "downloadUrl": url,
            "downloadName": name,
            "downloadUrls": [url],
            "imageUrl": None,
        }

    if intent == "create" and parsed and not files and not wants_plain_totals(current):
        src_cols, src_rows = parsed
        url, name = write_xlsx(src_cols, src_rows, sheet="数据", stem="workbook")
        md = rows_to_markdown(src_cols, src_rows)
        return {
            "intent": "create",
            "script": "excel_pipeline",
            "exitCode": 0,
            "stdout": md,
            "stderr": "",
            "note": f"已根据粘贴内容生成 Excel（{len(src_rows)} 行）",
            "downloadUrl": url,
            "downloadName": name,
        }

    if intent == "inspect":
        return {
            "intent": "inspect",
            "script": "excel_pipeline",
            "exitCode": 0,
            "stdout": inspect_txt[:12000],
            "stderr": "",
            "note": f"已探查 {len(table_map)} 张表",
            "tables": list(table_map.keys()),
        }

    if intent == "summary":
        summary = summarize_table(con, table_map, current)
        return {
            "intent": "summary",
            "script": "excel_pipeline",
            "exitCode": 0,
            "stdout": inspect_txt[:4000] + "\n\n" + summary,
            "stderr": "",
            "note": "已生成描述统计",
        }

    if intent == "chart":
        try:
            url, name, cnote, chart_urls = render_chart(
                con, table_map, current, stem=stem
            )
        except Exception as exc:  # noqa: BLE001
            return {
                "intent": "chart",
                "script": "excel_pipeline",
                "exitCode": 1,
                "stdout": inspect_txt[:4000],
                "stderr": str(exc),
                "note": f"出图失败: {exc}",
            }
        chart_urls = chart_urls or [url]
        return {
            "intent": "chart",
            "script": "excel_pipeline",
            "exitCode": 0,
            "stdout": (
                f"{cnote}\n\n--- 表结构 ---\n{inspect_txt[:3500]}\n"
                "重要：作图数据以「作图数据（全部）」为准，有几行就画几点；"
                "禁止说只展示了前 2 行；禁止把 _src_order 当成月份。"
                "downloadUrls 有几条就有几张图，必须全部展示并可下载。"
                "按意图出图：每种/多个/两张折线=按品类分图；每个月/多张饼=按月分饼；"
                "柱状+折线且「只要一张/同时/同图」=组合图画在同一张，禁止拆成两张。"
                "一句话多种图（未要求同图时）必须都生成。禁止让用户改参数。"
            ),
            "stderr": "",
            "note": f"已生成 {len(chart_urls)} 张图表",
            "downloadUrl": url,
            "downloadName": name,
            "imageUrl": url,
            "downloadUrls": chart_urls,
        }

    tbl = next(iter(table_map.values()))
    col_meta = con.execute(f'DESCRIBE "{tbl}"').fetchall()
    col_names = [c[0] for c in col_meta if c[0] != "_src_order"]
    num_cols = [
        c[0]
        for c in col_meta
        if is_numeric_type(str(c[1])) and c[0] != "_src_order"
    ]
    do_rollup = wants_category_rollup(current, col_names, num_cols)

    sql = extract_sql(current)
    err = ""
    rollup_note = ""
    kpi_sheets: list[tuple[str, list[str], list[tuple]]] = []
    if do_rollup and not sql:
        cols, rows, rollup_note = category_rollup_rows(con, table_map)
        sql = "（按类别透视汇总，非单列 GROUP BY）"
    elif wants_plain_totals(current) and not sql:
        cols, rows, rollup_note, kpi_sheets = add_row_and_col_totals(
            con, table_map, current
        )
        sql = "（按用户点名的指标写入工作簿：合计/月均等）"
    else:
        if intent in {"query", "analyze", "export"} and not sql:
            sql = auto_sql(current, con, table_map)
        if not sql:
            sql = auto_sql("分析", con, table_map)
        cols, rows, err = run_sql(con, sql, table_map)
    if err:
        return {
            "intent": "query",
            "script": "excel_pipeline",
            "exitCode": 1,
            "stdout": inspect_txt[:4000],
            "stderr": err,
            "note": "查询失败，请改写 SQL 或说明要按哪一列汇总",
            "sql": sql,
        }

    md = rows_to_markdown(cols, rows)
    want_file = intent == "export" or any(
        k in current.lower() for k in ("导出", "下载", "xlsx", "xls", "excel", "csv", "给我表", "表格文件")
    )
    url = name = None
    if want_file or intent in {"analyze", "query"}:
        sheets: list[tuple[str, list[str], list[tuple]]] = [("结果", cols, rows)]
        if do_rollup and parsed:
            sheets.insert(0, ("明细", list(parsed[0]), list(parsed[1])))
        elif do_rollup:
            raw = con.execute(f'SELECT * FROM "{tbl}"').fetchdf()
            sheets.insert(
                0,
                (
                    "明细",
                    list(raw.columns),
                    [tuple(r) for r in raw.itertuples(index=False, name=None)],
                ),
            )
        sheets.extend(kpi_sheets)
        url, name = write_xlsx_sheets(sheets, stem=stem + "-out")
        extra_urls.append(url)

    summary = ""
    if intent == "analyze":
        summary = "\n\n" + summarize_table(con, table_map)

    stdout = (
        f"sql:\n{sql}\n"
        f"{rollup_note}\n"
        f"rows={len(rows)}\n\n{md}{summary}\n\n--- 表结构 ---\n{inspect_txt[:3500]}"
    )
    return {
        "intent": intent,
        "script": "excel_pipeline",
        "exitCode": 0,
        "stdout": stdout[:14000],
        "stderr": "",
        "note": (rollup_note or f"已执行查询，返回 {len(rows)} 行"),
        "sql": sql,
        "downloadUrl": url,
        "downloadName": name,
        "downloadUrls": extra_urls,
    }


def format_excel_tool_result(trace: dict[str, Any]) -> str:
    if not trace:
        return "（无脚本结果）"
    parts = [
        f"intent: {trace.get('intent')}",
        f"script: {trace.get('script')}",
        f"exitCode: {trace.get('exitCode')}",
    ]
    if trace.get("note"):
        parts.append(f"note: {trace['note']}")
    if trace.get("sql"):
        parts.append(f"sql: {trace['sql']}")
    if trace.get("downloadUrl"):
        parts.append(f"downloadUrl: {trace['downloadUrl']}")
    if trace.get("downloadName"):
        parts.append(f"downloadName: {trace['downloadName']}")
    if trace.get("downloadUrls"):
        parts.append(
            "downloadUrls:\n" + "\n".join(str(u) for u in trace["downloadUrls"])
        )
    if trace.get("imageUrl") and trace.get("intent") == "chart":
        parts.append(f"imageUrl: {trace['imageUrl']}")
        parts.append(
            "请用 Markdown 图片逐张展示 downloadUrls 中的每一张图："
            "![图表](url)。每张图后写可点击链接：[下载图表](url)。"
            "禁止把路径写成纯文本或代码块。"
        )
    if trace.get("stdout"):
        parts.append("stdout:\n" + str(trace["stdout"])[:8000])
    if trace.get("stderr"):
        parts.append("stderr:\n" + str(trace["stderr"])[:2000])
    if trace.get("intent") == "export":
        parts.append(
            "intent=export：只说明已生成 Excel，必须给出 Markdown 下载链接。"
            "禁止提及柱状图/折线图/饼图，禁止插入图片，禁止改用或调用其它 Skill。"
        )
    else:
        parts.append(
            "重要：数字与表结构必须以 stdout 为准，禁止编造列名或统计值。"
            "若有 downloadUrl / downloadUrls，必须写成 Markdown 链接 [下载](url)，禁止只贴路径。"
            "用户点名的指标（月均、合计、最大/最小）必须出现在 xlsx 的「结果」或「指标」表中，禁止只写在回复文字里。"
            "intent=intro 时只介绍能力。"
            "本会话只使用当前已选定的 Excel Skill，禁止改用或调用其它 Skill。"
        )
    return "\n".join(parts)
