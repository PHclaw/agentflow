"""学术文献检索：多源公开 API 合并去重，按相关度排序并附带可点链接。"""
from __future__ import annotations

import json
import os
import re
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any
from urllib.parse import quote_plus
from pathlib import Path

import httpx

from app.logging_setup import get_logger
from app.core.paths import generated_root

logger = get_logger("academic")

SEARCH_STATE_DIR = generated_root() / "academic-search"

ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV_NS = "{http://arxiv.org/schemas/atom}"
UA = "ModelLab-academic-search/1.0 (mailto:dev@localhost)"
TIMEOUT = 18.0
ARXIV_URL = "https://export.arxiv.org/api/query"
OPENALEX_URL = "https://api.openalex.org/works"
S2_SEARCH = "https://api.semanticscholar.org/graph/v1/paper/search"
CROSSREF_URL = "https://api.crossref.org/works"
DBLP_URL = "https://dblp.org/search/publ/api"
PUBMED_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
NCBI_COMMON = {"tool": "modellab-academic-search", "email": "dev@localhost"}
SOURCES_LABEL = "arXiv / Semantic Scholar / OpenAlex / DBLP / PubMed / Crossref"
_CS_HINTS = (
    "neural",
    "transformer",
    "llm",
    "bert",
    "gpt",
    "nlp",
    "computer vision",
    "graph neural",
    "gnn",
    "reinforcement",
    "vit",
    "vision transformer",
    "diffusion model",
    "attention",
    "deep learning",
    "machine learning",
    "large language",
    "knowledge graph",
    "recommender",
    "multimodal",
    "pretrain",
)
_MED_HINTS = (
    "cancer",
    "clinical",
    "patient",
    "drug",
    "protein",
    "genome",
    "covid",
    "disease",
    "therapy",
    "medical",
    "biomed",
    "patholog",
    "tumor",
    "vaccine",
    "epidemi",
    "dermatolog",
    "skin",
)
_CS_VENUES = (
    "neurips",
    "nips",
    "iclr",
    "icml",
    "kdd",
    "www ",
    "aaai",
    "ijcai",
    "acl",
    "emnlp",
    "cvpr",
    "iccv",
    "eccv",
    "sigir",
    "recsys",
    "wsdm",
    "icde",
    "vldb",
    "sigmod",
    "tpami",
    "jmlr",
    "tnnls",
    "cs.lg",
    "cs.ai",
    "cs.cl",
    "cs.cv",
    "cs.ir",
    "cs.si",
)
_CN_EN_TERMS: tuple[tuple[str, str], ...] = (
    (r"深度强化学习", "deep reinforcement learning"),
    (r"强化学习|增强学习", "reinforcement learning"),
    (r"大语言模型|大模型", "large language model"),
    (r"图神经网络", "graph neural network"),
    (r"知识图谱", "knowledge graph"),
    (r"计算机视觉", "computer vision"),
    (r"自然语言处理", "natural language processing"),
    (r"机器学习", "machine learning"),
    (r"深度学习", "deep learning"),
    (r"(?i)(?<![a-z])vit(?![a-z])|vision\s*transformer|视觉\s*transformer|视觉变换器", "vision transformer"),
    (r"皮肤癌|黑色素瘤", "skin cancer melanoma"),
    (r"皮肤病|皮肤科|皮炎|皮肤镜|皮肤", "dermatology skin disease"),
    (r"医疗决策|临床决策|医学决策", "medical decision making"),
    (r"治疗规划|治疗方案|治疗计划", "treatment planning"),
    (r"医院资源", "hospital resource allocation"),
    (r"医疗领域|医学领域|医疗卫生", "healthcare"),
    (r"脓毒症|败血症", "sepsis"),
    (r"肿瘤学|癌症|肿瘤", "oncology"),
    (r"医疗|医学|临床", "medical"),
    (r"决策", "decision making"),
)

_CONCEPT_GROUPS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (
        ("reinforcement learning", "reinforcement", "强化学习", "增强学习"),
        ("reinforcement learning", "reinforcement", "inverse reinforcement"),
    ),
    (
        ("vision transformer", "视觉变换", "视觉transformer"),
        ("vision transformer", "visual transformer", "vit"),
    ),
    (
        ("dermatology", "skin disease", "皮肤病", "皮肤癌", "皮肤科", "皮炎", "皮肤镜"),
        (
            "dermatolog",
            "skin cancer",
            "skin disease",
            "dermoscopic",
            "melanoma",
            "psoriasis",
            "eczema",
            "cutaneous",
        ),
    ),
    (
        (
            "medical",
            "clinical",
            "healthcare",
            "hospital",
            "sepsis",
            "oncolog",
            "patient",
            "treatment",
            "therapy",
            "diagnos",
            "icu",
            "医疗",
            "医学",
            "临床",
            "医院",
        ),
        (
            "medical",
            "clinical",
            "healthcare",
            "health care",
            "hospital",
            "sepsis",
            "oncolog",
            "patient",
            "treatment",
            "therapy",
            "diagnos",
            "icu",
            "biomed",
        ),
    ),
)

_NON_CS_VENUES = (
    "hep-",
    "nucl-",
    "physics",
    "phys.rev",
    "physical review",
    "nuclear",
    "neutrino",
    "astrophys",
    "hep.ex",
    "hep-ex",
)


def is_academic_search_skill(agent) -> bool:
    wf = getattr(agent, "workflow", None) or {}
    if isinstance(wf, dict) and wf.get("kind") == "academic-search":
        return True
    sid = (getattr(agent, "id", None) or "").strip().lower()
    if sid in {"academic-search", "academic_search"}:
        return True
    name = getattr(agent, "name", None) or ""
    specialty = getattr(agent, "specialty", None) or ""
    return "学术文献检索" in name or specialty == "学术检索"


def prefer_current_user_text(text: str) -> str:
    t = text or ""
    marker = "## 当前用户"
    if marker in t:
        return t.split(marker, 1)[-1].strip()
    return t.strip()


def parse_search_request(text: str) -> dict[str, Any]:
    raw = prefer_current_user_text(text)
    year = None
    ym = re.search(r"(20\d{2})\s*年(?:以来|之后|以后|起)?", raw)
    if ym:
        year = int(ym.group(1))
    else:
        ny = re.search(r"近\s*(\d)\s*年", raw)
        if ny:
            year = datetime.utcnow().year - int(ny.group(1)) + 1
        else:
            ym = re.search(
                r"(?:since|from|after|starting|>=)\s*(20\d{2})|(20\d{2})\s*(?:-|–|—|to)\b",
                raw,
                re.I,
            )
            if ym:
                year = int(ym.group(1) or ym.group(2))
    limit = 8
    limit_explicit = False
    nm = re.search(r"(?:前|最新|top)\s*(\d{1,2})\s*篇?", raw, re.I)
    if nm:
        limit = min(20, max(3, int(nm.group(1))))
        limit_explicit = True
    else:
        nm = re.search(r"(\d{1,2})\s*篇", raw)
        if nm:
            limit = min(20, max(3, int(nm.group(1))))
            limit_explicit = True
        else:
            cn_num = {
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
            nm = re.search(r"([一二两三四五六七八九十])\s*篇", raw)
            if nm:
                limit = min(20, max(3, cn_num[nm.group(1)]))
                limit_explicit = True
    q = raw
    q = re.sub(r"(20\d{2})\s*年(?:以来|之后|以后|起)?", " ", q)
    q = re.sub(r"近\s*\d\s*年", " ", q)
    q = re.sub(r"(?:since|from|after|starting)\s*20\d{2}", " ", q, flags=re.I)
    q = re.sub(r"以来|之后|以后", " ", q)
    q = re.sub(r"(?:前|最新|top)\s*\d{1,2}\s*篇?", " ", q, flags=re.I)
    q = re.sub(r"用\s*(pubmed|lubmed|arxiv|openalex|semantic\s*scholar|crossref)", " ", q, flags=re.I)
    q = re.sub(
        r"^(请|帮我|帮忙)?(搜索|检索|查找|找一下|搜一下|查一下|找)\s*",
        " ",
        q,
    )
    q = re.sub(r"\d{1,2}\s*篇", " ", q)
    q = re.sub(r"[一二两三四五六七八九十]\s*篇", " ", q)
    q = re.sub(
        r"(论文|文献|顶会论文|顶会|给我|摘要表|列表|检索结果|academic-search|相关|关于)",
        " ",
        q,
        flags=re.I,
    )
    q = re.sub(
        r"\b(search|find|papers?|since|from|after|top|please|give|me|pubmed|lubmed|arxiv)\b",
        " ",
        q,
        flags=re.I,
    )
    q = re.sub(r"\?+", " ", q)
    q = re.sub(r"\b20\d{2}\b", " ", q)
    q = re.sub(
        r"(细化|收窄|缩小范围|我现在|只需要|只要|仅限|限定在|聚焦到|方面的?)",
        " ",
        q,
    )
    q = re.sub(r"\s+", " ", q).strip(" ，。、")
    if not re.search(r"[\w\u4e00-\u9fff]", q):
        q = re.sub(r"[^\x20-\x7e]+", " ", raw)
        q = re.sub(r"\s+", " ", q).strip()
    return {
        "query": q or raw.strip(),
        "limit": limit,
        "limit_explicit": limit_explicit,
        "year": year,
        "raw": raw,
    }


def _uniq(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        key = re.sub(r"\s+", " ", (item or "").strip().lower())
        if len(key) < 3 or key in seen:
            continue
        seen.add(key)
        out.append(re.sub(r"\s+", " ", item.strip()))
    return out


def _alias_in_blob(alias: str, blob: str) -> bool:
    a = (alias or "").lower().strip()
    b = (blob or "").lower()
    if not a or not b:
        return False
    if a in {"vit", "rl", "gnn", "nlp"} or len(a) <= 3:
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(a)}(?![a-z0-9])", b))
    return a in b


def expand_search_plan(query: str) -> dict[str, Any]:
    """中文需求扩成英文检索式，并给出不够时自动复检的优化词。"""
    raw = (query or "").strip()
    mapped: list[str] = []
    rest = raw
    for pat, en in _CN_EN_TERMS:
        if re.search(pat, rest):
            mapped.append(en)
            rest = re.sub(pat, " ", rest)
    rest = re.sub(r"在|的|与|及|及其|方面|领域|应用", " ", rest)
    rest = re.sub(r"[\u4e00-\u9fff]+", " ", rest)
    rest = re.sub(r"\s+", " ", rest).strip(" -")
    primary = " ".join(_uniq([*mapped, rest] if rest else mapped)) or raw
    blob = f"{raw} {primary}".lower()
    groups: list[tuple[str, ...]] = []
    for triggers, aliases in _CONCEPT_GROUPS:
        if any(_alias_in_blob(t, blob) for t in triggers):
            groups.append(aliases)
    variants = [primary]
    joined = " ".join(a for g in groups for a in g)
    if "vision transformer" in primary.lower() and "dermatolog" in joined:
        variants.extend(
            [
                "vision transformer dermatology",
                "vision transformer skin cancer medical",
            ]
        )
    elif "vision transformer" in primary.lower() and "medical" in joined:
        variants.extend(
            [
                "vision transformer medical",
                "vision transformer healthcare",
            ]
        )
    elif len(groups) >= 2 and "reinforcement" in primary.lower() and "medical" in joined:
        variants.extend(
            [
                "reinforcement learning medical decision making",
                "reinforcement learning healthcare clinical",
                "deep reinforcement learning treatment planning",
            ]
        )
    elif primary != raw:
        variants.append(raw)
    return {
        "primary": primary,
        "variants": _uniq(variants)[:4],
        "groups": groups,
        "original": raw,
    }


def _paper_blob(paper: dict[str, Any]) -> str:
    return f"{paper.get('title') or ''} {paper.get('venue') or ''}".lower()


def _hits_concept_groups(paper: dict[str, Any], groups: list[tuple[str, ...]]) -> bool:
    if not groups:
        return True
    blob = _paper_blob(paper)
    return all(any(_alias_in_blob(alias, blob) for alias in group) for group in groups)


def _headers() -> dict[str, str]:
    return {"User-Agent": UA}


def _s2_headers() -> dict[str, str]:
    h = _headers()
    key = ""
    try:
        from app.config import get_settings

        key = (getattr(get_settings(), "semantic_scholar_api_key", None) or "").strip()
    except Exception:  # noqa: BLE001
        key = ""
    if not key:
        key = (os.environ.get("SEMANTIC_SCHOLAR_API_KEY") or "").strip()
    if key:
        h["x-api-key"] = key
    return h


def _client() -> httpx.Client:
    return httpx.Client(timeout=TIMEOUT, headers=_headers(), follow_redirects=True)


def _query_domain(query: str) -> str:
    q = (query or "").lower()
    med = any(h in q for h in _MED_HINTS)
    cs = any(h in q for h in _CS_HINTS)
    if med and not cs:
        return "med"
    if cs and not med:
        return "cs"
    return "general"


def _get_json_or_text(client: httpx.Client, url: str, *, params: dict | None = None, as_json: bool = True):
    last = None
    for i in range(5):
        last = client.get(url, params=params)
        if last.status_code != 429:
            break
        retry_after = last.headers.get("Retry-After")
        try:
            wait = min(8.0, float(retry_after)) if retry_after else 2.2 * (i + 1)
        except ValueError:
            wait = 2.2 * (i + 1)
        if "arxiv.org" in url:
            wait = max(wait, 3.5 * (i + 1))
        time.sleep(min(12.0, wait))
    assert last is not None
    last.raise_for_status()
    return last.json() if as_json else last.text


def _fetch_n(limit: int) -> int:
    return min(20, max(int(limit) * 2, 12))


def _norm_title(title: str) -> str:
    t = re.sub(r"\s+", " ", (title or "").lower()).strip()
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", t)


def _clean_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    d = str(doi).strip()
    d = re.sub(r"^https?://(dx\.)?doi\.org/", "", d, flags=re.I)
    return d or None


def _paper_key(p: dict[str, Any]) -> str:
    doi = _clean_doi(p.get("doi"))
    if doi:
        return "doi:" + doi.lower()
    if p.get("pmid"):
        return "pmid:" + str(p["pmid"]).strip()
    if p.get("arxiv_id"):
        return "arxiv:" + re.sub(r"v\d+$", "", str(p["arxiv_id"]).lower())
    if p.get("s2_id"):
        return "s2:" + str(p["s2_id"]).lower()
    return "t:" + _norm_title(str(p.get("title") or ""))


def _ensure_urls(p: dict[str, Any]) -> dict[str, Any]:
    doi = _clean_doi(p.get("doi"))
    if doi:
        p["doi"] = doi
        p["doi_url"] = f"https://doi.org/{doi}"
    pmid = str(p.get("pmid") or "").strip()
    if pmid:
        p["pubmed_url"] = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
    aid = str(p.get("arxiv_id") or "").strip()
    if aid:
        aid = aid.replace("abs/", "")
        p["arxiv_id"] = aid
        p["arxiv_url"] = f"https://arxiv.org/abs/{aid}"
        if not p.get("pdf_url"):
            p["pdf_url"] = f"https://arxiv.org/pdf/{aid}"
    sid = str(p.get("s2_id") or "").strip()
    if sid and not p.get("s2_url"):
        p["s2_url"] = f"https://www.semanticscholar.org/paper/{sid}"
    if p.get("dblp_url") and not str(p.get("dblp_url")).startswith("http"):
        p["dblp_url"] = f"https://dblp.org/rec/{p['dblp_url']}"
    if not p.get("url"):
        p["url"] = (
            p.get("doi_url")
            or p.get("arxiv_url")
            or p.get("pubmed_url")
            or p.get("s2_url")
            or p.get("dblp_url")
            or p.get("pdf_url")
        )
    return p


def _merge_field(old: dict[str, Any], new: dict[str, Any], key: str) -> None:
    if not old.get(key) and new.get(key):
        old[key] = new[key]


def _merge(papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by: dict[str, dict[str, Any]] = {}
    for p in papers:
        if not p.get("title"):
            continue
        p = _ensure_urls(dict(p))
        key = _paper_key(p)
        old = by.get(key)
        if not old:
            by[key] = p
            continue
        if (p.get("citation_count") or 0) > (old.get("citation_count") or 0):
            old["citation_count"] = p["citation_count"]
        for k in (
            "pdf_url",
            "url",
            "doi",
            "doi_url",
            "arxiv_id",
            "arxiv_url",
            "pmid",
            "pubmed_url",
            "s2_id",
            "s2_url",
            "dblp_url",
            "venue",
            "year",
        ):
            _merge_field(old, p, k)
        src = str(p.get("source") or "")
        if src and src not in str(old.get("source") or ""):
            old["source"] = f"{old.get('source')}+{src}"
        _ensure_urls(old)
    return list(by.values())


def _search_arxiv(query: str, *, limit: int, year: int | None, restrict_cs: bool | None = None) -> list[dict[str, Any]]:
    tokens = _query_tokens(query)[:6] or [query]
    inner = f'(ti:"{query}") OR ({" AND ".join(f"all:{t}" for t in tokens)})'
    domain = _query_domain(query)
    if restrict_cs is None:
        restrict_cs = domain == "cs"
    if restrict_cs:
        inner = f"({inner}) AND cat:cs.*"
    q = quote_plus(inner)
    url = (
        f"{ARXIV_URL}?search_query={q}&start=0&max_results={limit}"
        "&sortBy=relevance&sortOrder=descending"
    )
    with _client() as client:
        body = _get_json_or_text(client, url, as_json=False)
    return _parse_arxiv_atom(body, year=year)


def _search_arxiv_by_title(title: str, *, limit: int = 8) -> list[dict[str, Any]]:
    """按完整标题查 arXiv，不限制 cs.*（eess.IV 等也会命中）。"""
    title = re.sub(r"\s+", " ", (title or "").strip())
    if len(title) < 8:
        return []
    head = title.split(":")[0].strip()
    clauses = [f'ti:"{title}"']
    if 4 <= len(head) <= 90 and head.lower() != title.lower():
        clauses.append(f'ti:"{head}"')
        clauses.append(f'all:"{head}"')
    inner = " OR ".join(clauses)
    url = (
        f"{ARXIV_URL}?search_query={quote_plus(inner)}&start=0&max_results={limit}"
        "&sortBy=relevance&sortOrder=descending"
    )
    with _client() as client:
        body = _get_json_or_text(client, url, as_json=False)
    return _parse_arxiv_atom(body, year=None)


def _parse_arxiv_atom(body: str, *, year: int | None) -> list[dict[str, Any]]:
    root = ET.fromstring(body)
    out: list[dict[str, Any]] = []
    for entry in root.findall(f"{ATOM}entry"):
        title = re.sub(r"\s+", " ", (entry.findtext(f"{ATOM}title") or "").strip())
        published = (entry.findtext(f"{ATOM}published") or "")[:10]
        py = int(published[:4]) if published[:4].isdigit() else None
        if year and py and py < year:
            continue
        authors = [
            (a.findtext(f"{ATOM}name") or "").strip()
            for a in entry.findall(f"{ATOM}author")
        ]
        authors = [a for a in authors if a]
        aid = (entry.findtext(f"{ATOM}id") or "").rsplit("/", 1)[-1]
        aid = aid.replace("abs/", "")
        pdf = ""
        abs_url = ""
        for link in entry.findall(f"{ATOM}link"):
            href = link.attrib.get("href") or ""
            if link.attrib.get("title") == "pdf" or link.attrib.get("type") == "application/pdf":
                pdf = href
            elif link.attrib.get("rel") == "alternate":
                abs_url = href
        cats = [
            c.attrib.get("term") or ""
            for c in entry.findall(f"{ARXIV_NS}primary_category")
        ]
        doi = (entry.findtext(f"{ARXIV_NS}doi") or "").strip()
        summary = re.sub(r"\s+", " ", (entry.findtext(f"{ATOM}summary") or "").strip())
        out.append(
            {
                "title": title,
                "authors": authors[:8],
                "year": py,
                "venue": "arXiv" + (f" [{cats[0]}]" if cats and cats[0] else ""),
                "citation_count": None,
                "pdf_url": pdf or (f"https://arxiv.org/pdf/{aid}" if aid else None),
                "url": abs_url or (f"https://arxiv.org/abs/{aid}" if aid else None),
                "arxiv_id": aid,
                "doi": doi or None,
                "abstract": summary or None,
                "source": "arxiv",
            }
        )
    return out


def _uninvert_oa_abstract(idx: dict | None) -> str | None:
    if not isinstance(idx, dict) or not idx:
        return None
    try:
        last = max(max(pos) for pos in idx.values() if pos)
    except ValueError:
        return None
    words = [""] * (last + 1)
    for word, positions in idx.items():
        for p in positions or []:
            if 0 <= int(p) < len(words):
                words[int(p)] = str(word)
    text = re.sub(r"\s+", " ", " ".join(words)).strip()
    return text or None


def _search_openalex(query: str, *, limit: int, year: int | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    with _client() as client:
        for sort in (None, "cited_by_count:desc"):
            params: dict[str, Any] = {
                "search": query,
                "per_page": limit,
                "mailto": "dev@localhost",
            }
            if year:
                params["filter"] = f"from_publication_date:{year}-01-01"
            if sort:
                params["sort"] = sort
            data = _get_json_or_text(client, OPENALEX_URL, params=params)
            works = data.get("results") or []
            for w in works:
                title = (w.get("display_name") or "").strip()
                if not title:
                    continue
                loc = w.get("primary_location") or {}
                src = loc.get("source") or {}
                pdf = (w.get("open_access") or {}).get("oa_url") or loc.get("pdf_url") or ""
                landing = loc.get("landing_page_url") or ""
                ids = w.get("ids") or {}
                doi = _clean_doi(ids.get("doi") or w.get("doi"))
                pmid = None
                pmid_url = str(ids.get("pmid") or "")
                m = re.search(r"/(\d+)$", pmid_url)
                if m:
                    pmid = m.group(1)
                arxiv = ""
                for loc2 in w.get("locations") or []:
                    page = str((loc2 or {}).get("landing_page_url") or "")
                    if "arxiv.org" in page:
                        arxiv = page.rstrip("/").rsplit("/", 1)[-1]
                        if not pdf:
                            pdf = f"https://arxiv.org/pdf/{arxiv}"
                        if not landing:
                            landing = page
                        break
                authors = []
                for au in w.get("authorships") or []:
                    name = ((au.get("author") or {}).get("display_name") or "").strip()
                    if name:
                        authors.append(name)
                    if len(authors) >= 8:
                        break
                item = {
                    "title": title,
                    "authors": authors,
                    "year": w.get("publication_year"),
                    "venue": (src.get("display_name") or "").strip() or "OpenAlex",
                    "citation_count": w.get("cited_by_count"),
                    "pdf_url": pdf or None,
                    "url": landing or None,
                    "arxiv_id": arxiv or None,
                    "doi": doi,
                    "pmid": pmid,
                    "abstract": _uninvert_oa_abstract(w.get("abstract_inverted_index")),
                    "source": "openalex",
                }
                key = _paper_key(item)
                if key in seen:
                    continue
                seen.add(key)
                out.append(item)
    return out


def _search_s2(query: str, *, limit: int, year: int | None) -> list[dict[str, Any]]:
    params: dict[str, Any] = {
        "query": query,
        "limit": limit,
        "fields": "title,authors,year,citationCount,externalIds,openAccessPdf,url,venue,publicationVenue,abstract",
    }
    if year:
        params["year"] = f"{year}-{datetime.utcnow().year + 1}"
    with httpx.Client(timeout=TIMEOUT, headers=_s2_headers(), follow_redirects=True) as client:
        data = _get_json_or_text(client, S2_SEARCH, params=params)
    out: list[dict[str, Any]] = []
    for w in data.get("data") or []:
        ext = w.get("externalIds") or {}
        pdf = ((w.get("openAccessPdf") or {}) or {}).get("url") or ""
        venue = (w.get("venue") or "") or ((w.get("publicationVenue") or {}) or {}).get("name") or ""
        authors = [a.get("name") for a in (w.get("authors") or []) if a.get("name")]
        out.append(
            {
                "title": (w.get("title") or "").strip(),
                "authors": authors[:8],
                "year": w.get("year"),
                "venue": venue or "Semantic Scholar",
                "citation_count": w.get("citationCount"),
                "pdf_url": pdf or None,
                "url": w.get("url") or None,
                "arxiv_id": ext.get("ArXiv") or ext.get("ARXIV"),
                "doi": _clean_doi(ext.get("DOI")),
                "pmid": str(ext["PubMed"]) if ext.get("PubMed") else None,
                "s2_id": w.get("paperId"),
                "abstract": (w.get("abstract") or "").strip() or None,
                "source": "semanticscholar",
            }
        )
    return out


def _search_crossref(query: str, *, limit: int, year: int | None) -> list[dict[str, Any]]:
    params: dict[str, Any] = {
        "query.title": query,
        "rows": limit,
        "select": "DOI,title,author,published,published-print,published-online,container-title,URL,is-referenced-by-count,link,type",
        "mailto": "dev@localhost",
    }
    if year:
        params["filter"] = f"from-pub-date:{year}-01-01"
    with _client() as client:
        data = _get_json_or_text(client, CROSSREF_URL, params=params)
    items = ((data.get("message") or {}).get("items")) or []
    skip_types = {"peer-review", "component", "grant", "dataset", "posted-content"}
    out: list[dict[str, Any]] = []
    for w in items:
        if str(w.get("type") or "") in skip_types:
            continue
        title = ""
        if isinstance(w.get("title"), list) and w["title"]:
            title = str(w["title"][0]).strip()
        if not title:
            continue
        authors = []
        for au in w.get("author") or []:
            name = " ".join(x for x in (au.get("given"), au.get("family")) if x).strip()
            if name:
                authors.append(name)
            if len(authors) >= 8:
                break
        year_v = None
        for key in ("published-print", "published-online", "published"):
            parts = ((w.get(key) or {}).get("date-parts") or [[]])[0]
            if parts:
                year_v = int(parts[0])
                break
        venue = ""
        if isinstance(w.get("container-title"), list) and w["container-title"]:
            venue = str(w["container-title"][0])
        if venue.strip().lower() == title.strip().lower():
            venue = "Crossref"
        pdf = None
        for lk in w.get("link") or []:
            if "pdf" in str(lk.get("content-type") or "").lower() and lk.get("URL"):
                pdf = lk["URL"]
                break
        out.append(
            {
                "title": title,
                "authors": authors,
                "year": year_v,
                "venue": venue or "Crossref",
                "citation_count": w.get("is-referenced-by-count"),
                "pdf_url": pdf,
                "url": w.get("URL"),
                "doi": _clean_doi(w.get("DOI")),
                "source": "crossref",
            }
        )
    return out


def _search_dblp(query: str, *, limit: int, year: int | None) -> list[dict[str, Any]]:
    params = {"q": query, "format": "json", "h": str(limit)}
    with _client() as client:
        data = _get_json_or_text(client, DBLP_URL, params=params)
    hits = (((data.get("result") or {}).get("hits") or {}).get("hit")) or []
    out: list[dict[str, Any]] = []
    for h in hits:
        info = (h or {}).get("info") or {}
        title = re.sub(r"\s+", " ", str(info.get("title") or "").strip()).rstrip(".")
        if not title:
            continue
        py = info.get("year")
        try:
            py = int(str(py)[:4]) if py else None
        except (TypeError, ValueError):
            py = None
        if year and py and py < year:
            continue
        authors = info.get("authors") or {}
        auths = authors.get("author") or []
        if isinstance(auths, dict):
            auths = [auths]
        names: list[str] = []
        for a in auths:
            if isinstance(a, dict):
                names.append(str(a.get("text") or "").strip())
            elif isinstance(a, str):
                names.append(a.strip())
        doi = _clean_doi(info.get("doi"))
        ee = info.get("ee")
        if isinstance(ee, list):
            ee = ee[0] if ee else ""
        if isinstance(ee, dict):
            ee = ee.get("text") or ee.get("@text") or ""
        ee_url = str(ee or "").strip() or None
        key = str(info.get("key") or "").strip()
        dblp_url = f"https://dblp.org/rec/{key}" if key else None
        out.append(
            {
                "title": title,
                "authors": [n for n in names if n][:8],
                "year": py,
                "venue": str(info.get("venue") or "DBLP"),
                "citation_count": None,
                "pdf_url": ee_url if ee_url and ee_url.lower().endswith(".pdf") else None,
                "url": ee_url or dblp_url,
                "doi": doi,
                "dblp_url": dblp_url,
                "source": "dblp",
            }
        )
    return out


def _search_pubmed(query: str, *, limit: int, year: int | None) -> list[dict[str, Any]]:
    term = query.strip()
    if year:
        term = f"({term}) AND {year}:3000[dp]"
    params = {
        **NCBI_COMMON,
        "db": "pubmed",
        "term": term,
        "retmax": str(limit),
        "retmode": "json",
        "sort": "relevance",
    }
    with _client() as client:
        search_data = _get_json_or_text(client, PUBMED_ESEARCH, params=params)
        ids = (search_data.get("esearchresult") or {}).get("idlist") or []
        if not ids:
            return []
        result = _get_json_or_text(
            client,
            PUBMED_ESUMMARY,
            params={
                **NCBI_COMMON,
                "db": "pubmed",
                "id": ",".join(str(i) for i in ids[:limit]),
                "retmode": "json",
            },
        )
    result = result.get("result") or {}
    out: list[dict[str, Any]] = []
    for pmid in ids[:limit]:
        rec = result.get(str(pmid)) or {}
        if not isinstance(rec, dict):
            continue
        title = re.sub(r"\s+", " ", (rec.get("title") or "").strip())
        if not title:
            continue
        pubdate = str(rec.get("pubdate") or rec.get("epubdate") or "")
        py = int(pubdate[:4]) if pubdate[:4].isdigit() else None
        if year and py and py < year:
            continue
        authors = []
        for au in rec.get("authors") or []:
            name = (au.get("name") or "").strip()
            if name:
                authors.append(name)
            if len(authors) >= 8:
                break
        doi = ""
        pmc = ""
        for aid in rec.get("articleids") or []:
            kind = str(aid.get("idtype") or "").lower()
            val = str(aid.get("value") or "").strip()
            if kind == "doi" and val:
                doi = val
            elif kind == "pmc" and val:
                pmc = val if val.upper().startswith("PMC") else f"PMC{val}"
        pdf = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmc}/pdf/" if pmc else None
        venue = (rec.get("fulljournalname") or rec.get("source") or "PubMed").strip()
        out.append(
            {
                "title": title,
                "authors": authors,
                "year": py,
                "venue": venue,
                "citation_count": None,
                "pdf_url": pdf,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "arxiv_id": None,
                "doi": doi or None,
                "pmid": str(pmid),
                "source": "pubmed",
            }
        )
    return out


def _query_tokens(query: str) -> list[str]:
    stop = {
        "the",
        "and",
        "for",
        "with",
        "from",
        "that",
        "this",
        "综述",
        "最新",
        "相关",
        "using",
        "based",
    }
    toks = re.split(r"[\s+/_,，。]+", (query or "").lower())
    return [t for t in toks if len(t) > 2 and t not in stop]


def _relevance(paper: dict[str, Any], query: str) -> int:
    title = (paper.get("title") or "").lower()
    venue = (paper.get("venue") or "").lower()
    src = str(paper.get("source") or "").lower()
    qn = re.sub(r"\s+", " ", (query or "").lower()).strip()
    toks = _query_tokens(query)
    score = 0
    if qn and qn in title:
        score += 20
    if len(toks) >= 2 and " ".join(toks[:3]) in title:
        score += 10
    if toks:
        hits = sum(1 for t in toks if t in title)
        score += hits * 4
        if hits == len(toks):
            score += 8
        if hits * 2 < len(toks):
            score -= 8
        if hits == 0:
            score -= 12
        score += sum(1 for t in toks if t in venue)
    plan_blob = (query or "").lower()
    groups = [
        aliases
        for triggers, aliases in _CONCEPT_GROUPS
        if any(_alias_in_blob(t, plan_blob) for t in triggers)
    ]
    if groups:
        if _hits_concept_groups(paper, groups):
            score += 12
        else:
            score -= 16
    domain = _query_domain(query)
    if domain == "cs":
        if any(v in venue for v in _CS_VENUES):
            score += 8
        if any(v in venue for v in _NON_CS_VENUES):
            score -= 10
        if "pubmed" in src:
            score -= 6
        if "dblp" in src or "arxiv" in src or "semanticscholar" in src:
            score += 2
    cite = paper.get("citation_count")
    if isinstance(cite, int):
        if cite >= 200:
            score += 4
        elif cite >= 50:
            score += 2
    return score


def _sort_papers(papers: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    now_y = datetime.utcnow().year

    def recency(p: dict[str, Any]) -> int:
        y = p.get("year")
        if not y:
            return 0
        if y >= now_y:
            return 2
        if y >= now_y - 1:
            return 1
        return 0

    def rank_cites(p: dict[str, Any]) -> int:
        c = p.get("citation_count")
        if not isinstance(c, int):
            return -1
        y = p.get("year")
        # OpenAlex 偶发把会议论文引用数标到数千，压掉真实高引综述
        if y and int(y) >= 2023 and c > 1200:
            return 400
        return c

    return sorted(
        papers,
        key=lambda p: (
            _relevance(p, query),
            rank_cites(p),
            recency(p),
            p.get("year") or 0,
        ),
        reverse=True,
    )


def _link_cell(p: dict[str, Any]) -> str:
    bits: list[str] = []
    if p.get("url"):
        bits.append(f"[详情]({p['url']})")
    if p.get("doi_url"):
        bits.append(f"[DOI]({p['doi_url']})")
    if p.get("arxiv_url"):
        bits.append(f"[arXiv]({p['arxiv_url']})")
    if p.get("pubmed_url"):
        bits.append(f"[PubMed]({p['pubmed_url']})")
    if p.get("s2_url"):
        bits.append(f"[S2]({p['s2_url']})")
    if p.get("dblp_url"):
        bits.append(f"[DBLP]({p['dblp_url']})")
    if p.get("pdf_url"):
        bits.append(f"[PDF]({p['pdf_url']})")
    return " · ".join(bits) if bits else "—"


def _table(papers: list[dict[str, Any]]) -> str:
    lines = [
        "| 标题 | 年份 | Venue | 引用 | 链接 |",
        "|------|------|-------|------|------|",
    ]
    now_y = datetime.utcnow().year
    for p in papers:
        title = (p.get("title") or "").replace("|", "/")
        href = p.get("url") or p.get("doi_url") or p.get("pdf_url")
        title_s = f"[{title}]({href})" if href else title
        y = p.get("year") or ""
        if y and int(y) >= now_y:
            y = f"{y} [新]"
        venue = (p.get("venue") or "").replace("|", "/")
        cite = p.get("citation_count")
        cite_s = str(cite) if cite is not None else "—"
        lines.append(f"| {title_s} | {y} | {venue} | {cite_s} | {_link_cell(p)} |")
    return "\n".join(lines)


def format_academic_tool_result(trace: dict[str, Any] | None) -> str:
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
        parts.append("stdout:\n" + str(trace["stdout"]))
        if trace.get("intent") == "intro":
            parts.append("重要：intent=intro。只介绍检索能力，禁止编造论文列表。")
        else:
            parts.append(
                f"重要：以上检索结果来自 {SOURCES_LABEL} 实时接口。"
                "必须原样使用表中的详情/DOI/arXiv/PubMed/DBLP/PDF 链接，禁止编造未出现的论文或 URL。"
                "若已出现「实际使用的检索式」或「已用优化检索词自动复检」，按当前表格作答，"
                "禁止再把同一批检索词当成「下一步可深挖」让用户自己搜。"
                "若出现「上下文策略: refine」，说明已把上一轮主题和本轮约束合并检索，按合并后的主题总结，不要说本轮与上一轮无关。"
                "下一步只可建议更窄场景（如 sepsis / oncology），且不得冒充已检索到的论文。"
                "本 Skill 只给题名与链接，不要写文献速读笔记。"
                "必须告知：平台另有独立 Skill「文献速读笔记」(lit-review-notes)，可以按论文标题检索并写问题/方法/结果/局限速读。"
                "用法：复制本表中的标题，切换到该 Skill，或发送 \\lit-review-notes 加上标题；不要让用户粘贴摘要。"
            )
    if trace.get("stderr"):
        parts.append("stderr:\n" + str(trace["stderr"]))
    return "\n".join(parts)


def _search_all(query: str, *, limit: int, year: int | None) -> tuple[list[dict[str, Any]], list[str]]:
    n = _fetch_n(limit)
    domain = _query_domain(query)
    jobs = {
        "arxiv": lambda: _search_arxiv(query, limit=n, year=year),
        "semanticscholar": lambda: _search_s2(query, limit=n, year=year),
        "openalex": lambda: _search_openalex(query, limit=n, year=year),
        "crossref": lambda: _search_crossref(query, limit=n, year=year),
    }
    if domain != "cs":
        jobs["pubmed"] = lambda: _search_pubmed(query, limit=n, year=year)
    if domain != "med":
        jobs["dblp"] = lambda: _search_dblp(query, limit=n, year=year)
    papers: list[dict[str, Any]] = []
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futs = {pool.submit(fn): name for name, fn in jobs.items()}
        for fut in as_completed(futs):
            name = futs[fut]
            try:
                papers.extend(fut.result() or [])
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{name}: {exc}")
                logger.warning("%s search fail q=%r err=%s", name, query, exc)
    return papers, errors


def _select_papers(
    papers: list[dict[str, Any]],
    *,
    rank_query: str,
    groups: list[tuple[str, ...]],
    limit: int,
    year: int | None,
) -> list[dict[str, Any]]:
    merged = _sort_papers(_merge(papers), rank_query)
    if year:
        merged = [p for p in merged if not p.get("year") or int(p["year"]) >= year]
    tight = [p for p in merged if _hits_concept_groups(p, groups) and _relevance(p, rank_query) >= 4]
    if tight:
        return tight[:limit]
    good = [p for p in merged if _relevance(p, rank_query) >= 6]
    return (good or merged)[:limit]


def _search_state_path(conversation_id: str | None) -> Path | None:
    if not conversation_id:
        return None
    SEARCH_STATE_DIR.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "-", conversation_id)[:80]
    return SEARCH_STATE_DIR / f"{safe}.json"


def _load_search_state(conversation_id: str | None) -> dict[str, Any]:
    path = _search_state_path(conversation_id)
    if not path or not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _save_search_state(conversation_id: str | None, state: dict[str, Any]) -> None:
    path = _search_state_path(conversation_id)
    if not path:
        return
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _last_user_from_history(text: str) -> str:
    if "## 先前对话" not in (text or ""):
        return ""
    block = (text or "").split("## 当前用户", 1)[0]
    found = re.findall(r"^用户[:：]\s*(.+)$", block, re.M)
    return found[-1].strip() if found else ""


def _merge_groups(
    old: list[Any], new: list[tuple[str, ...]]
) -> list[tuple[str, ...]]:
    out: list[tuple[str, ...]] = []
    seen: set[str] = set()
    for group in [*(tuple(g) for g in old or []), *new]:
        key = " ".join(group[:2]).lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(tuple(group))
    return out


def _slim_paper(p: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k in (
        "title",
        "authors",
        "year",
        "venue",
        "citation_count",
        "doi",
        "pmid",
        "arxiv_id",
        "s2_id",
        "url",
        "doi_url",
        "arxiv_url",
        "pubmed_url",
        "s2_url",
        "pdf_url",
        "abstract",
    ):
        if p.get(k) not in (None, "", []):
            out[k] = p[k]
    return out


def load_last_papers(conversation_id: str | None) -> list[dict[str, Any]]:
    papers = _load_search_state(conversation_id).get("papers") or []
    return [p for p in papers if isinstance(p, dict) and p.get("title")]


def run_academic_search(text: str, *, conversation_id: str | None = None) -> dict[str, Any]:
    from app.services.context_intent import decide_context

    current = prefer_current_user_text(text)
    prior_user = _last_user_from_history(text)
    saved = _load_search_state(conversation_id)
    action = decide_context(
        current, has_history=bool(prior_user or saved.get("primary"))
    )
    req = parse_search_request(text)
    plan = expand_search_plan(req["query"])
    query = plan["primary"]
    variants: list[str] = list(plan["variants"])
    groups: list[tuple[str, ...]] = list(plan["groups"])
    limit = req["limit"]
    year = req["year"]
    context_note = ""
    if action == "refine":
        last = dict(saved)
        if not last.get("primary") and prior_user:
            prev = parse_search_request(prior_user)
            prev_plan = expand_search_plan(prev["query"])
            last = {
                "primary": prev_plan["primary"],
                "groups": [list(g) for g in prev_plan["groups"]],
                "limit": prev.get("limit") or 8,
                "year": prev.get("year"),
            }
        if last.get("primary"):
            query = " ".join(_uniq([str(last["primary"]), plan["primary"]]))
            groups = _merge_groups(last.get("groups") or [], plan["groups"])
            extra = [
                query,
                f"{last['primary']} {plan['primary']}".strip(),
                *plan["variants"],
            ]
            variants = _uniq(extra)[:4]
            if not req.get("limit_explicit"):
                limit = int(last.get("limit") or limit)
            if not year:
                year = last.get("year")
            context_note = (
                f"上下文策略: refine（沿用上一轮「{last['primary']}」，加上本轮约束）\n"
            )
        else:
            context_note = "上下文策略: refine（无上一轮检索词，按本轮单独检索）\n"
    else:
        context_note = f"上下文策略: {action}\n"

    papers: list[dict[str, Any]] = []
    errors: list[str] = []
    used: list[str] = []
    selected: list[dict[str, Any]] = []
    for q in variants:
        used.append(q)
        batch, errs = _search_all(q, limit=limit, year=year)
        papers.extend(batch)
        errors.extend(errs)
        selected = _select_papers(
            papers, rank_query=query, groups=groups, limit=limit, year=year
        )
        enough = [p for p in selected if _hits_concept_groups(p, groups)]
        if len(enough) >= limit:
            selected = enough[:limit]
            break
    script = "arxiv+s2+openalex+dblp+pubmed+crossref"
    if not selected:
        return {
            "intent": "search",
            "script": script,
            "exitCode": 1,
            "note": "未检索到论文" + (f"；{'; '.join(errors)}" if errors else ""),
            "stdout": context_note,
            "stderr": "\n".join(errors),
            "query": query,
        }

    _save_search_state(
        conversation_id,
        {
            "primary": query,
            "original": plan["original"],
            "groups": [list(g) for g in groups],
            "limit": limit,
            "year": year,
            "papers": [_slim_paper(p) for p in selected],
        },
    )
    payload = {
        "query": query,
        "originalQuery": plan["original"],
        "usedQueries": used,
        "contextAction": action,
        "yearFrom": year,
        "count": len(selected),
        "papers": selected,
    }
    used_line = "；".join(used)
    auto_retry = len(used) > 1
    stdout = (
        context_note
        + f"原始需求: {plan['original']}\n"
        f"检索词: {query}\n"
        f"实际使用的检索式: {used_line}\n"
        + ("已用优化检索词自动复检，不要再让用户用同一批词自己搜一遍。\n" if auto_retry else "")
        + (f"年份下限: {year}\n" if year else "")
        + f"条数: {len(selected)}\n"
        + f"来源: {SOURCES_LABEL}\n\n"
        + _table(selected)
        + "\n\n## JSON\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )
    logger.info(
        "academic search q=%r action=%s used=%s year=%s n=%s src_err=%s",
        query,
        action,
        used,
        year,
        len(selected),
        len(errors),
    )
    return {
        "intent": "search",
        "script": script,
        "exitCode": 0,
        "note": f"已检索 {len(selected)} 篇"
        + ("；收窄上一轮主题" if action == "refine" else "")
        + ("；已自动复检" if auto_retry else ""),
        "stdout": stdout,
        "stderr": "\n".join(errors),
        "query": query,
        "downloadUrl": None,
    }
