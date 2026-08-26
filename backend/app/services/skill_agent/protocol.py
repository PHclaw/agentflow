"""解析模型输出的 JSON 动作。"""
from __future__ import annotations

import json
import re
from typing import Any

ALLOWED_ACTIONS = {"call_tool", "finish"}

_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.S)


class ActionParseError(ValueError):
    pass


def _extract_object(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if not raw:
        raise ActionParseError("空输出")
    m = _FENCE_RE.search(raw)
    blob = m.group(1) if m else None
    if blob is None:
        start = raw.find("{")
        if start < 0:
            raise ActionParseError("未找到 JSON 对象")
        depth = 0
        end = -1
        in_str = False
        esc = False
        for i, ch in enumerate(raw[start:], start):
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i
                    break
        if end < 0:
            raise ActionParseError("JSON 括号不完整")
        blob = raw[start : end + 1]
    try:
        data = json.loads(blob)
    except json.JSONDecodeError as exc:
        raise ActionParseError(f"JSON 无法解析: {exc}") from exc
    if not isinstance(data, dict):
        raise ActionParseError("根节点必须是对象")
    return data


def parse_action(text: str) -> dict[str, Any]:
    """解析一轮模型输出为 {action, name?, args?, reply?}。"""
    data = _extract_object(text)
    action = str(data.get("action") or "").strip()
    if not action:
        if data.get("tool") or data.get("name"):
            action = "call_tool"
        elif "reply" in data or "finish" in data:
            action = "finish"
    if action not in ALLOWED_ACTIONS:
        raise ActionParseError(
            f"action 必须是 call_tool 或 finish，收到 {action or type(data)!r}"
        )
    if action == "call_tool":
        name = str(data.get("name") or data.get("tool") or "").strip()
        if not name:
            raise ActionParseError("call_tool 需要 name")
        args = data.get("args") or data.get("arguments") or data.get("spec") or {}
        if data.get("spec") is not None and name == "render_chart" and "spec" not in (
            data.get("args") or {}
        ):
            if isinstance(args, dict) and "kind" in args:
                pass
            elif isinstance(data.get("spec"), dict):
                args = {"spec": data["spec"]}
        if not isinstance(args, dict):
            raise ActionParseError("args 必须是对象")
        return {"action": "call_tool", "name": name, "args": args}
    reply = data.get("reply")
    if reply is None:
        reply = data.get("output") or data.get("finish") or ""
    return {"action": "finish", "reply": str(reply)}


def schema_hint() -> str:
    return (
        "每轮只输出一个 JSON 对象，不要 markdown 解释。两种合法形状：\n"
        '{"action":"call_tool","name":"<工具名>","args":{...}}\n'
        '{"action":"finish","reply":"<给用户的中文说明；不要贴文件名>"}\n'
    )


def parse_task_plan(text: str) -> dict[str, Any]:
    """解析任务规划 JSON（mode / summary / tools / constraints）。"""
    data = _extract_object(text)
    mode = str(data.get("mode") or data.get("intent") or "task").strip().lower()
    if mode not in {"intro", "task"}:
        mode = "task"
    tools: list[dict[str, Any]] = []
    raw_tools = data.get("tools")
    if isinstance(raw_tools, list):
        for item in raw_tools:
            if isinstance(item, str) and item.strip():
                tools.append({"name": item.strip(), "args": {}})
            elif isinstance(item, dict):
                name = str(item.get("name") or item.get("tool") or "").strip()
                if not name:
                    continue
                args = item.get("args") or item.get("arguments") or {}
                if not isinstance(args, dict):
                    args = {}
                tools.append({"name": name, "args": args})
    constraints = data.get("constraints")
    if not isinstance(constraints, dict):
        constraints = {}
    deliverables = data.get("deliverables")
    if not isinstance(deliverables, list):
        deliverables = []
    return {
        "mode": mode,
        "summary": str(data.get("summary") or data.get("task") or "")[:800],
        "deliverables": [str(d) for d in deliverables[:12]],
        "tools": tools[:12],
        "constraints": {str(k): v for k, v in list(constraints.items())[:20]},
    }


def plan_schema_hint() -> str:
    return (
        "只输出一个 JSON 对象，不要 Markdown 解释：\n"
        '{"mode":"intro或task","summary":"实际要做的事（含标题/单价/页码/顺序）",'
        '"deliverables":["xlsx","bar"],'
        '"tools":[{"name":"工具名","args":{}}],'
        '"constraints":{"title":"图题或空","prices":{"铅笔":1}}}\n'
        "mode=intro：问好或问能力，tools 必须是 []。\n"
        "mode=task：tools 的 name 必须来自下面工具表；标题、单价写进 constraints，不要 query_sql。"
    )
