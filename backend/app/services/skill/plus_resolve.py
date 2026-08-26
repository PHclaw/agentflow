"""解析广场输入中的 \\+skillname / +skillname，并匹配精选 Skill。"""
from __future__ import annotations

import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.skill.store import FileSkill, list_skills

_PLUS_RE = re.compile(r"^\s*\\?\+([^\s\\]+)\s*(?:\n|$)")


def strip_plus_directive(text: str) -> tuple[str | None, str]:
    """返回 (token, remainder)。无前缀则 token=None。"""
    raw = text or ""
    m = _PLUS_RE.match(raw)
    if not m:
        return None, raw
    token = m.group(1).strip()
    rest = raw[m.end() :]
    return token, rest


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "").strip().lower()).strip("-")


def match_agent_by_token(agents: list[FileSkill], token: str) -> FileSkill | None:
    if not token:
        return None
    t = token.strip()
    tl = t.lower()
    ts = _slug(t)

    for a in agents:
        if (a.id or "").strip().lower() == tl or _slug(a.id or "") == ts:
            return a
    for a in agents:
        if (a.name or "").strip().lower() == tl:
            return a
    for a in agents:
        if (a.specialty or "").strip().lower() == tl:
            return a
    for a in agents:
        for trig in a.triggers or []:
            if str(trig).strip().lower() == tl or _slug(str(trig)) == ts:
                return a
    for a in agents:
        if _slug(a.name or "") == ts or _slug(a.specialty or "") == ts:
            return a
    return None


async def resolve_plus_agent(db: AsyncSession, token: str) -> FileSkill | None:
    _ = db
    rows = [
        s
        for s in list_skills(curated_only=True, statuses={"published"})
        if s.visibility in {"team", "public"}
    ]
    return match_agent_by_token(rows, token)


def apply_plus_to_variables(variables: dict[str, Any]) -> tuple[str | None, dict[str, str]]:
    """从 variables['input'] 剥离 \\+token，返回 (token, new_variables)。"""
    out = {str(k): str(v) for k, v in (variables or {}).items()}
    token, rest = strip_plus_directive(out.get("input") or "")
    if token is not None:
        out["input"] = rest
    return token, out
