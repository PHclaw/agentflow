from __future__ import annotations

import re
from typing import Any

VAR_PATTERN = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


def extract_variables(template: str) -> list[str]:
    return list(dict.fromkeys(VAR_PATTERN.findall(template or "")))


def render_template(template: str, variables: dict[str, Any] | None = None) -> str:
    variables = variables or {}

    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in variables:
            return match.group(0)
        return str(variables[key])

    return VAR_PATTERN.sub(repl, template or "")


_COMMON_INPUT_KEYS = ("input", "query", "question", "text", "q", "content", "message")


def align_variables_to_template(
    template: str, variables: dict[str, Any] | None
) -> dict[str, str]:
    """把调用方变量对齐到模板占位符（解决 UI 传 input、模板用 question 等错位）。"""
    raw = {str(k): "" if v is None else str(v) for k, v in (variables or {}).items()}
    placeholders = extract_variables(template)
    if not placeholders:
        return raw

    aligned = dict(raw)
    for ph in placeholders:
        if aligned.get(ph, "").strip():
            continue
        for alt in _COMMON_INPUT_KEYS:
            if alt != ph and aligned.get(alt, "").strip():
                aligned[ph] = aligned[alt]
                break
    if len(placeholders) == 1:
        ph = placeholders[0]
        if not aligned.get(ph, "").strip():
            for k, v in aligned.items():
                if k != ph and v.strip():
                    aligned[ph] = v
                    break
    return aligned


def build_executable_user(template: str, variables: dict[str, Any] | None) -> str:
    """渲染 User；若变量值未进入正文，强制追加，避免模型「未收到问题」。"""
    tpl = (template or "").strip() or "{{input}}"
    aligned = align_variables_to_template(tpl, variables)
    rendered = render_template(tpl, aligned).strip()

    values = [v.strip() for v in aligned.values() if v and v.strip()]
    if values and not any(v in rendered for v in values):
        if len(values) == 1:
            block = values[0]
        else:
            block = "\n".join(
                f"{k}: {v.strip()}" for k, v in aligned.items() if v and v.strip()
            )
        rendered = f"{rendered}\n\n{block}".strip() if rendered else block

    if not rendered and values:
        rendered = values[0]
    return rendered or tpl


_SYSTEM_FENCE_RE = re.compile(
    r"###\s*System\s*\n\s*```(?:text)?\s*\n([\s\S]*?)```",
    re.IGNORECASE,
)


def extract_system_from_spec_md(md: str) -> str:
    """从 Executable Spec MD 中抽出真正的 System 正文。"""
    m = _SYSTEM_FENCE_RE.search(md or "")
    return (m.group(1).strip() if m else "")


def looks_like_spec_md(text: str) -> bool:
    t = (text or "").lstrip()
    return t.startswith("#") and ("Executable Spec" in t or "## 调用 Prompt" in t or "## 专业方向" in t)


def expand_variable_combinations(
    variables: dict[str, list[str]] | None,
) -> list[dict[str, str]]:
    """将 variables: {input: [a,b], lang: [en]} 展开为笛卡尔积列表。

    若为空，返回 [{}] 表示无变量单次执行。
    若只有一个主变量列表，也支持简写场景。
    """
    if not variables:
        return [{}]

    keys = list(variables.keys())
    lists = [variables[k] or [""] for k in keys]

    combos: list[dict[str, str]] = [{}]
    for key, values in zip(keys, lists):
        next_combos: list[dict[str, str]] = []
        for base in combos:
            for value in values:
                item = dict(base)
                item[key] = value
                next_combos.append(item)
        combos = next_combos
    return combos


def primary_variable(var_map: dict[str, str]) -> tuple[str, str]:
    if not var_map:
        return "", ""
    key = next(iter(var_map))
    return key, var_map[key]
