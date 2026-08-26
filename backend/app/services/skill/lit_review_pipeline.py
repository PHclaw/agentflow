"""文献速读：用检索命中的题名/序号拉取摘要，再交给笔记模型。"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from difflib import SequenceMatcher
from typing import Any

import httpx

from app.logging_setup import get_logger
from app.services.skill.academic_search_pipeline import (
    ARXIV_URL,
    ATOM,
    OPENALEX_URL,
    TIMEOUT,
    load_last_papers,
    _clean_doi,
    _client,
    _get_json_or_text,
    _norm_title,
    _s2_headers,
    _search_arxiv,
    _search_arxiv_by_title,
    _search_crossref,
    _search_openalex,
    _search_s2,
)

logger = get_logger("lit-review")

S2_PAPER = "https://api.semanticscholar.org/graph/v1/paper/{key}"
PUBMED_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
NCBI_COMMON = {"tool": "modellab-lit-review", "email": "dev@localhost"}
MAX_NOTES = 3

_CN_ORD = {
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}

WANTS_SEARCH_NOTES_RE = re.compile(
    r"(速读|解析|精读|笔记|解读).{0,24}(论文|文献|这[些几]|第.+篇|刚才|上面|检索|搜到)|"
    r"(论文|文献).{0,12}(速读|解析|精读|笔记)|"
    r"第[一二三四五六七八九十\d]+\s*篇|"
    r"(?:\\?\+)?lit-review-notes",
    re.I,
)
_LIT_SKILL_TOKEN_RE = re.compile(r"\\?lit-review-notes", re.I)
_ARXIV_VERSION_RE = re.compile(r"v\d+$")


def is_lit_review_skill(agent) -> bool:
    sid = (getattr(agent, "id", None) or "").strip().lower()
    if sid in {"lit-review-notes", "lit_review_notes"}:
        return True
    name = getattr(agent, "name", None) or ""
    specialty = getattr(agent, "specialty", None) or ""
    return "文献速读" in name or specialty == "文献速读"


def wants_search_notes(text: str) -> bool:
    t = text or ""
    if "## 当前用户" in t:
        t = t.split("## 当前用户", 1)[-1]
    return bool(WANTS_SEARCH_NOTES_RE.search(t.strip()))


def _extract_title_query(text: str) -> str:
    t = (text or "").strip()
    if "## 当前用户" in t:
        t = t.split("## 当前用户", 1)[-1].strip()
    quoted = re.search(r"[「『\"“](.+?)[」』\"”]", t)
    if quoted and len(quoted.group(1).strip()) >= 8:
        return quoted.group(1).strip()
    t = re.sub(
        r"^(请|帮我|帮忙)?(做|进行)?(文献)?(速读|解析|精读|总结|笔记|解读|综述)\s*(一下|这篇|这篇论文)?",
        " ",
        t,
    )
    t = _LIT_SKILL_TOKEN_RE.sub(" ", t)
    t = re.sub(
        r"(这篇)?论文(说了什么|讲了什么|讲的是什么|是什么意思|总结一下|速读一下).*$",
        " ",
        t,
    )
    t = re.sub(r"(说了什么|讲了什么|是什么意思)\s*$", " ", t)
    t = re.sub(r"(这篇)?(论文|文献)(标题)?[:：]?", " ", t)
    t = re.sub(r"标题[:：]", " ", t)
    t = re.sub(r"\s+", " ", t).strip(" ，。、")
    return t


def _has_paper_body(text: str) -> bool:
    t = (text or "").strip()
    if "## 当前用户" in t:
        t = t.split("## 当前用户", 1)[-1].strip()
    if len(t) >= 800:
        return True
    hits = sum(
        1
        for k in ("方法：", "结果：", "局限：", "abstract", "methods", "results")
        if k in t.lower() or k in t
    )
    return hits >= 2 and len(t) >= 280


def _ord_token(tok: str) -> int | None:
    tok = (tok or "").strip()
    if tok.isdigit():
        return int(tok)
    return _CN_ORD.get(tok)


def _requested_indices(text: str) -> list[int]:
    found: list[int] = []
    for m in re.finditer(r"第\s*([一二三四五六七八九十]|\d+)\s*篇", text or ""):
        n = _ord_token(m.group(1))
        if n:
            found.append(n)
    return found


def _title_score(query: str, title: str) -> float:
    q = _norm_title(query)
    t = _norm_title(title)
    if not q or not t:
        return 0.0
    if q in t or t in q:
        return 0.95
    seq = SequenceMatcher(None, q, t).ratio()
    q_toks = set(re.findall(r"[a-z0-9]{3,}", q))
    t_toks = set(re.findall(r"[a-z0-9]{3,}", t))
    if q_toks:
        overlap = len(q_toks & t_toks) / max(len(q_toks), 1)
        if overlap >= 0.7:
            seq = max(seq, 0.78)
    return seq


def _pick_papers(text: str, pool: list[dict[str, Any]]) -> list[dict[str, Any]]:
    t = text or ""
    if "## 当前用户" in t:
        t = t.split("## 当前用户", 1)[-1].strip()
    if not pool:
        return []
    idxs = _requested_indices(t)
    picked: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(p: dict[str, Any]) -> None:
        key = _norm_title(str(p.get("title") or ""))
        if not key or key in seen:
            return
        seen.add(key)
        picked.append(p)

    for n in idxs:
        if 1 <= n <= len(pool):
            add(pool[n - 1])
    if picked:
        return picked[:MAX_NOTES]
    scored = sorted(
        (( _title_score(t, str(p.get("title") or "")), p) for p in pool),
        key=lambda x: x[0],
        reverse=True,
    )
    if scored and scored[0][0] >= 0.45 and len(t) >= 12:
        add(scored[0][1])
        return picked[:MAX_NOTES]
    if wants_search_notes(t) or len(t) < 80:
        for p in pool[:MAX_NOTES]:
            add(p)
        return picked
    return []


def _uninvert_abstract(idx: dict[str, Any] | None) -> str:
    if not isinstance(idx, dict) or not idx:
        return ""
    try:
        last = max(max(pos) for pos in idx.values() if pos)
    except ValueError:
        return ""
    words = [""] * (last + 1)
    for word, positions in idx.items():
        for p in positions or []:
            if 0 <= int(p) < len(words):
                words[int(p)] = str(word)
    return re.sub(r"\s+", " ", " ".join(words)).strip()


def _fill_abstract(paper: dict[str, Any]) -> dict[str, Any]:
    p = dict(paper)
    if str(p.get("abstract") or "").strip():
        return p
    aid = str(p.get("arxiv_id") or "").replace("abs/", "").strip()
    doi = _clean_doi(p.get("doi"))
    pmid = str(p.get("pmid") or "").strip()
    sid = str(p.get("s2_id") or "").strip()
    try:
        from app.services.skill.academic_search_pipeline import _uninvert_oa_abstract

        if aid:
            try:
                with _client() as client:
                    data = _get_json_or_text(
                        client,
                        f"{OPENALEX_URL}/arxiv:{_ARXIV_VERSION_RE.sub('', aid)}",
                        params={"mailto": "dev@localhost"},
                    )
                abs_t = _uninvert_oa_abstract(data.get("abstract_inverted_index"))
                if abs_t:
                    p["abstract"] = abs_t
                    return p
            except Exception:  # noqa: BLE001
                pass
        if aid:
            url = f"{ARXIV_URL}?id_list={aid}&start=0&max_results=1"
            with _client() as client:
                body = _get_json_or_text(client, url, as_json=False)
            root = ET.fromstring(body)
            summary = root.findtext(f".//{ATOM}summary") or ""
            if summary.strip():
                p["abstract"] = re.sub(r"\s+", " ", summary).strip()
                return p
        if sid or doi:
            key = sid or f"DOI:{doi}"
            params = {"fields": "title,abstract,year,venue,externalIds,url"}
            with httpx.Client(timeout=TIMEOUT, headers=_s2_headers(), follow_redirects=True) as client:
                data = _get_json_or_text(client, S2_PAPER.format(key=key), params=params)
            abs_t = (data.get("abstract") or "").strip()
            if abs_t:
                p["abstract"] = abs_t
                return p
        if doi:
            with _client() as client:
                data = _get_json_or_text(
                    client,
                    f"{OPENALEX_URL}/doi:{doi}",
                    params={"mailto": "dev@localhost"},
                )
            abs_t = _uninvert_abstract(data.get("abstract_inverted_index"))
            if abs_t:
                p["abstract"] = abs_t
                return p
        if pmid:
            params = {
                **NCBI_COMMON,
                "db": "pubmed",
                "id": pmid,
                "rettype": "abstract",
                "retmode": "text",
            }
            with _client() as client:
                body = _get_json_or_text(client, PUBMED_EFETCH, params=params, as_json=False)
            if body and len(body.strip()) > 40:
                p["abstract"] = re.sub(r"\s+", " ", body).strip()[:4000]
                return p
    except Exception as exc:  # noqa: BLE001
        logger.warning("abstract fetch fail title=%r err=%s", p.get("title"), exc)
    return p


def _lookup_by_title(title: str) -> dict[str, Any] | None:
    title = _extract_title_query(title)
    if len(re.sub(r"\s+", "", title)) < 8:
        return None
    hits: list[dict[str, Any]] = []
    from concurrent.futures import ThreadPoolExecutor, as_completed

    with ThreadPoolExecutor(max_workers=3) as pool:
        futs = {
            pool.submit(fn, title, limit=6, year=None): fn
            for fn in (_search_openalex, _search_crossref, _search_s2)
        }
        for fut in as_completed(futs):
            fn = futs[fut]
            try:
                hits.extend(fut.result() or [])
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "title search fail src=%s q=%r err=%s",
                    getattr(fn, "__name__", fn),
                    title,
                    exc,
                )
    if not any(
        _title_score(title, str(h.get("title") or "")) >= 0.5 and str(h.get("abstract") or "").strip()
        for h in hits
    ):
        try:
            hits.extend(_search_arxiv_by_title(title, limit=8) or [])
        except Exception as exc:  # noqa: BLE001
            logger.warning("arxiv title search fail q=%r err=%s", title, exc)
    best = None
    best_key = (-1.0, 0)
    for h in hits:
        s = _title_score(title, str(h.get("title") or ""))
        key = (s, 1 if str(h.get("abstract") or "").strip() else 0)
        if key > best_key:
            best_key = key
            best = h
    best_s = best_key[0]
    if not best or best_s < 0.42:
        logger.info("title lookup miss q=%r best=%s score=%s", title, (best or {}).get("title"), best_s)
        return None
    filled = _fill_abstract(best)
    if not str(filled.get("abstract") or "").strip():
        try:
            extra = _search_s2(str(filled.get("title") or title), limit=3, year=None)
            for h in extra:
                if _title_score(title, str(h.get("title") or "")) >= 0.5:
                    filled = _fill_abstract({**filled, **{k: v for k, v in h.items() if v}})
                    if str(filled.get("abstract") or "").strip():
                        break
        except Exception:  # noqa: BLE001
            pass
    return filled


def _format_material(papers: list[dict[str, Any]], user_text: str) -> str:
    blocks = [
        "请根据平台按标题检索到的题录与摘要写速读笔记，依据仅限下列材料。"
        "禁止编造摘要中没有的数字、会议名和页码；摘要未写的结果放进「待核实」。",
        "",
        f"用户要求：{user_text.strip()}",
        "",
    ]
    for i, p in enumerate(papers, 1):
        authors = p.get("authors") or []
        if isinstance(authors, list):
            au = ", ".join(str(a) for a in authors[:8])
        else:
            au = str(authors)
        abs_t = str(p.get("abstract") or "").strip() or "（未取到摘要，仅有题录）"
        link = p.get("url") or p.get("doi_url") or p.get("arxiv_url") or p.get("pdf_url") or "—"
        blocks.extend(
            [
                f"## 文献 {i}",
                f"- 标题：{p.get('title')}",
                f"- 年份：{p.get('year') or '—'}",
                f"- Venue：{p.get('venue') or '—'}",
                f"- 作者：{au or '—'}",
                f"- DOI：{p.get('doi') or '—'}",
                f"- 链接：{link}",
                f"- 摘要：{abs_t}",
                "",
            ]
        )
    return "\n".join(blocks).strip()


def run_lit_review_prepare(text: str, *, conversation_id: str | None = None) -> dict[str, Any]:
    current = text or ""
    if "## 当前用户" in current:
        current = current.split("## 当前用户", 1)[-1].strip()
    query = _extract_title_query(current)
    if _has_paper_body(current):
        return {
            "intent": "notes",
            "script": "lit-review-notes",
            "exitCode": 0,
            "note": "使用用户粘贴的正文",
            "stdout": current,
            "stderr": "",
        }
    pool = load_last_papers(conversation_id)
    picked = _pick_papers(query, pool) if _requested_indices(query) else []
    if not picked:
        looked = _lookup_by_title(query)
        if looked:
            picked = [looked]
    if not picked:
        return {
            "intent": "notes",
            "script": "lit-review-notes",
            "exitCode": 1,
            "note": "未检索到该标题对应的论文",
            "stdout": "",
            "stderr": f"未找到与标题匹配的论文：{query}",
        }
    filled = [_fill_abstract(p) for p in picked[:MAX_NOTES]]
    if not any(str(p.get("abstract") or "").strip() for p in filled):
        return {
            "intent": "notes",
            "script": "lit-review-notes",
            "exitCode": 1,
            "note": "找到题录但没有摘要，无法写速读",
            "stdout": _format_material(filled, query),
            "stderr": "已匹配到标题，但公开接口未返回摘要。请换一篇或提供 DOI。",
            "papers": filled,
        }
    material = _format_material(filled, query)
    return {
        "intent": "notes",
        "script": "lit-review-notes",
        "exitCode": 0,
        "note": f"已按标题检索并准备 {len(filled)} 篇摘要",
        "stdout": material,
        "stderr": "",
        "papers": filled,
    }


def format_lit_review_tool_result(trace: dict[str, Any] | None) -> str:
    if not trace:
        return "（无脚本结果）"
    parts = [
        f"intent: {trace.get('intent')}",
        f"script: {trace.get('script')}",
        f"exitCode: {trace.get('exitCode')}",
    ]
    if trace.get("note"):
        parts.append(f"note: {trace['note']}")
    if trace.get("stdout"):
        parts.append("stdout:\n" + str(trace["stdout"])[:12000])
        parts.append(
            "重要：stdout 是按用户粘贴的标题检索到的题录与摘要。"
            "只根据这些材料写速读；摘要没有的内容写进「待核实」，禁止编造。"
            "若 exitCode≠0：说明未找到该论文，禁止生成笔记模板。"
        )
    if trace.get("stderr"):
        parts.append("stderr:\n" + str(trace["stderr"]))
    return "\n".join(parts)
