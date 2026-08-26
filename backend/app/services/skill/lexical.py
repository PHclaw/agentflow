"""Skill 选型：字面/关键词召回打分（含 triggers / routerBlurb）。"""
from __future__ import annotations

import math
import re

from app.services.skill.taxonomy import category_of_agent, infer_category

_TOKEN_RE = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)


def tokens(text: str) -> set[str]:
    raw = (text or "").lower().strip()
    if not raw:
        return set()
    parts = _TOKEN_RE.findall(raw)
    out: set[str] = set()
    for p in parts:
        out.add(p)
        if re.search(r"[\u4e00-\u9fff]", p) and len(p) >= 2:
            for i in range(len(p) - 1):
                out.add(p[i : i + 2])
    return out


def overlap_score(query: str, query_tokens: set[str], field: str, weight: float) -> float:
    if not field:
        return 0.0
    f = field.strip().lower()
    q = (query or "").lower()
    if not f or not q:
        return 0.0
    if len(f) >= 2 and f in q:
        return weight
    field_tokens = tokens(f)
    if not field_tokens or not query_tokens:
        return 0.0
    hit = len(query_tokens & field_tokens)
    if hit == 0:
        grams = 0
        gram_hits = 0
        for i in range(len(f) - 1):
            g = f[i : i + 2]
            if re.search(r"[\u4e00-\u9fff]", g):
                grams += 1
                if g in q:
                    gram_hits += 1
        if grams and gram_hits:
            return weight * (gram_hits / grams) * 0.85
        return 0.0
    return weight * (hit / max(len(query_tokens), 1))


def _trigger_score(query: str, triggers: list[str]) -> float:
    if not triggers:
        return 0.0
    q = (query or "").lower()
    best = 0.0
    for t in triggers:
        t = (t or "").strip().lower()
        if not t:
            continue
        if t in q or q in t:
            best = max(best, 1.2)
            continue
        # 双字重叠
        hit = 0
        total = 0
        for i in range(len(t) - 1):
            g = t[i : i + 2]
            if re.search(r"[\u4e00-\u9fff]", g):
                total += 1
                if g in q:
                    hit += 1
        if total:
            best = max(best, 0.9 * (hit / total))
    return best


def lexical_score(query: str, agent) -> tuple[float, str]:
    q_tokens = tokens(query)
    if not q_tokens:
        return 0.0, "空查询"

    specialty = agent.specialty or ""
    name = agent.name or ""
    desc = agent.description or ""
    tags = " ".join(agent.tags or [])
    blurb = getattr(agent, "router_blurb", None) or ""
    triggers = [str(t) for t in (getattr(agent, "triggers", None) or []) if str(t).strip()]

    # SkillPilot/Soup 思路：triggers 优先，再 specialty / blurb
    trig = _trigger_score(query, triggers)
    core_parts = [
        (trig, "triggers"),
        (overlap_score(query, q_tokens, specialty, 1.0), "specialty"),
        (overlap_score(query, q_tokens, blurb, 0.85), "routerBlurb"),
        (overlap_score(query, q_tokens, name, 0.55), "name"),
    ]
    soft_parts = [
        (overlap_score(query, q_tokens, tags, 0.45), "tags"),
        (overlap_score(query, q_tokens, desc, 0.35), "description"),
    ]
    core = sum(s for s, _ in core_parts)
    soft = sum(s for s, _ in soft_parts)
    score = core + (soft if core > 0 else soft * 0.1)

    q_cat, _ = infer_category(specialty=query, name=query, description=query)
    a_cat, _ = category_of_agent(agent)
    if q_cat != "other" and q_cat == a_cat:
        score += 0.35
        core_parts = core_parts + [(0.35, "category")]
    if core > 0 or (q_cat != "other" and q_cat == a_cat):
        calls = max(int(agent.total_calls or 0), 0)
        score += 0.05 * math.log1p(calls)

    reasons = [n for s, n in core_parts + soft_parts if s > 0]
    reason = "+".join(reasons) if reasons else "弱匹配"
    return score, reason


def normalize_confidences(scores: list[float]) -> list[float]:
    if not scores:
        return []
    top = max(scores)
    if top <= 0:
        n = len(scores)
        return [1.0 / n] * n
    exps = [math.exp((s / top) * 3.0) for s in scores]
    total = sum(exps) or 1.0
    return [e / total for e in exps]
