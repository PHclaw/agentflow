"""Skill 选型：召回 + 可选小模型重排。"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.logging_setup import get_logger
from app.services.json_task import run_json_task
from app.services.skill.lexical import lexical_score, normalize_confidences
from app.services.skill.store import FileSkill, list_skills

logger = get_logger("skill.resolve")


@dataclass
class ScoredSkill:
    agent: FileSkill
    lexical: float
    confidence: float
    reason: str


async def list_resolvable_agents(db: AsyncSession, user_id: str) -> list[FileSkill]:
    """可调用 Skill：默认仅平台精选（与广场一致）。"""
    _ = db, user_id
    return [
        s
        for s in list_skills(curated_only=True, statuses={"published"})
        if s.visibility in {"team", "public"}
    ]


async def _llm_rerank(
    db: AsyncSession,
    user_id: str,
    query: str,
    candidates: list[ScoredSkill],
) -> list[ScoredSkill] | None:
    if not candidates:
        return None

    lines = []
    for i, c in enumerate(candidates, 1):
        a = c.agent
        triggers = ", ".join(str(t) for t in (getattr(a, "triggers", None) or [])[:6])
        lines.append(
            f"{i}. id={a.id}\n"
            f"   specialty={a.specialty or ''}\n"
            f"   name={a.name}\n"
            f"   routerBlurb={(getattr(a, 'router_blurb', None) or '')[:120]}\n"
            f"   triggers={triggers}\n"
            f"   description={(a.description or '')[:120]}\n"
            f"   lexical={c.lexical:.3f}"
        )
    catalog = "\n".join(lines)
    system = (
        "你是 Skill 路由器。根据用户任务，从候选专业 Skill 中选出最合适的，按匹配度排序。\n"
        "只输出一个 JSON 对象，不要 Markdown 围栏：\n"
        '{"ranked":[{"id":"技能id","score":0.0到1.0,"reason":"一句话"}]}\n'
        "硬性要求：id 必须来自候选；score 为置信度；更贴合专业方向的排前面；"
        "若都不合适，仍返回全部但 score 都偏低。"
    )
    user = f"【用户任务】\n{query}\n\n【候选 Skill】\n{catalog}\n"
    try:
        task = await run_json_task(
            db,
            user_id=user_id,
            system=system,
            user=user,
            temperature=0.1,
            max_tokens=1024,
        )
        ranked = task.data.get("ranked")
        if not isinstance(ranked, list) or not ranked:
            return None
        by_id = {c.agent.id: c for c in candidates}
        out: list[ScoredSkill] = []
        seen: set[str] = set()
        for item in ranked:
            if not isinstance(item, dict):
                continue
            sid = str(item.get("id") or "").strip()
            if sid not in by_id or sid in seen:
                continue
            seen.add(sid)
            base = by_id[sid]
            try:
                conf = float(item.get("score"))
            except (TypeError, ValueError):
                conf = base.confidence
            conf = max(0.0, min(1.0, conf))
            reason = str(item.get("reason") or base.reason)[:200]
            out.append(
                ScoredSkill(
                    agent=base.agent,
                    lexical=base.lexical,
                    confidence=conf,
                    reason=reason,
                )
            )
        for c in candidates:
            if c.agent.id not in seen:
                out.append(c)
        return out or None
    except Exception:  # noqa: BLE001
        return None


async def resolve_skills(
    db: AsyncSession,
    *,
    user_id: str,
    query: str,
    top_k: int = 3,
    recall_k: int = 8,
    rerank: bool = True,
) -> list[dict]:
    """输入任务文本 → 返回按置信度排序的 Skill 列表。"""
    q = (query or "").strip()
    if not q:
        raise ValueError("query 不能为空")
    top_k = max(1, min(int(top_k), 10))
    recall_k = max(top_k, min(int(recall_k), 20))

    agents = await list_resolvable_agents(db, user_id)
    if not agents:
        return []

    scored: list[ScoredSkill] = []
    for agent in agents:
        lex, reason = lexical_score(q, agent)
        scored.append(ScoredSkill(agent=agent, lexical=lex, confidence=0.0, reason=reason))

    scored.sort(key=lambda x: x.lexical, reverse=True)
    strong = [
        s
        for s in scored
        if s.lexical >= 0.15 or "specialty" in s.reason or "name" in s.reason
    ]
    if strong:
        pool = strong[:recall_k]
        confs = normalize_confidences([s.lexical for s in pool])
    elif rerank:
        pool = scored[:recall_k]
        confs = normalize_confidences([max(s.lexical, 0.01) for s in pool])
    else:
        return []

    for s, c in zip(pool, confs):
        s.confidence = c

    final = pool
    if rerank and len(pool) >= 1:
        reranked = await _llm_rerank(db, user_id, q, pool)
        if reranked:
            final = reranked

    final = final[:top_k]
    items = [
        {
            "skillId": s.agent.id,
            "name": s.agent.name,
            "specialty": s.agent.specialty or "",
            "confidence": round(float(s.confidence), 4),
            "reason": s.reason,
            "version": s.agent.version,
            "lexicalScore": round(float(s.lexical), 4),
        }
        for s in final
    ]
    top = items[0] if items else None
    logger.info(
        "resolve user=%s rerank=%s candidates=%s top=%s conf=%s reason=%s qChars=%s",
        user_id,
        rerank,
        len(pool),
        (top or {}).get("skillId"),
        (top or {}).get("confidence"),
        (top or {}).get("reason"),
        len(q),
    )
    return items
