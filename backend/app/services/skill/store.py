"""Filesystem Skill store: skills/<slug>/SKILL.md (+ optional scripts/)."""
from __future__ import annotations

import json
import re
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from app.services.prompt_utils import extract_variables
from app.logging_setup import get_logger

logger = get_logger("skillstore")

from app.core.paths import skills_root as _skills_root_path

SKILL_FILENAME = "SKILL.md"

_CACHE: dict[str, tuple[float, "FileSkill"]] = {}
_LIST_CACHE: tuple[tuple[str, ...], float, list["FileSkill"]] | None = None

# 预置中文名 → 稳定英文 slug（迁移与展示用）
PRESET_SLUGS: dict[str, str] = {
    "会议纪要助手": "meeting-minutes",
    "临床病例报告": "clinical-case-report",
    "文献速读笔记": "lit-review-notes",
    "统计分析助手": "statistical-analyst",
    "PDF处理助手": "pdf",
    "PPT生成助手": "ppt-generation",
    "PPT助手": "ppt-generation",
    "学术文献检索": "academic-search",
    "Excel表格助手": "excel",
}


@dataclass
class FileSkill:
    """Duck-compatible with Agent for serializers / call paths."""

    id: str
    name: str
    description: str = ""
    specialty: str = ""
    router_blurb: str = ""
    triggers: list[Any] = field(default_factory=list)
    tags: list[Any] = field(default_factory=list)
    model_name: str = "chatzoc_9b_B"
    model_params: dict[str, Any] = field(default_factory=dict)
    system_prompt_enc: str = ""  # plaintext on disk
    user_prompt_template: str = "{{input}}"
    variables: list[Any] = field(default_factory=list)
    author_id: str = "platform-preset"
    author_name: str = "平台预置"
    version: str = "v1.0.0"
    changelog: str = ""
    status: str = "published"
    visibility: str = "public"
    md_doc: str = ""
    workflow: dict[str, Any] = field(default_factory=dict)
    examples: list[Any] = field(default_factory=list)
    total_calls: int = 0
    avg_rating: float = 0.0
    published_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    root: Path | None = None

    @property
    def scripts_dir(self) -> Path | None:
        if not self.root:
            return None
        p = self.root / "scripts"
        return p if p.is_dir() else None


def skills_root() -> Path:
    root = _skills_root_path()
    root.mkdir(parents=True, exist_ok=True)
    return root



def slugify(name: str, *, fallback: str = "skill") -> str:
    preset = PRESET_SLUGS.get((name or "").strip())
    if preset:
        return preset
    s = (name or "").strip().lower()
    s = re.sub(r"[^\w\u4e00-\u9fff]+", "-", s, flags=re.UNICODE)
    s = re.sub(r"-+", "-", s).strip("-")
    if not s:
        s = fallback
    # Prefer ASCII folder names
    if re.search(r"[\u4e00-\u9fff]", s):
        digest = abs(hash(name)) % 10_000_000
        s = f"{fallback}-{digest}"
    return s[:64]


def _parse_dt(raw: Any) -> datetime | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, datetime):
        return raw
    text = str(raw).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _split_skill_md(text: str) -> tuple[dict[str, Any], str]:
    """SKILL.md = optional JSON frontmatter between --- fences + markdown body."""
    raw = text.lstrip("\ufeff")
    if not raw.startswith("---"):
        return {}, raw.strip()
    rest = raw[3:].lstrip("\r\n")
    end = rest.find("\n---")
    if end < 0:
        return {}, raw.strip()
    head = rest[:end].strip()
    body = rest[end + 4 :].lstrip("\r\n")
    if not head:
        return {}, body.strip()
    try:
        meta = json.loads(head)
    except json.JSONDecodeError as exc:
        raise ValueError(f"SKILL.md frontmatter 不是合法 JSON: {exc}") from exc
    if not isinstance(meta, dict):
        raise ValueError("SKILL.md frontmatter 必须是 JSON 对象")
    return meta, body.strip()


def _extract_section(md: str, heading: str) -> str:
    """Pull fenced or plain block under ### Heading."""
    pattern = rf"(?im)^###\s+{re.escape(heading)}\s*\n+(.*?)(?=^###\s+|\Z)"
    m = re.search(pattern, md or "", flags=re.S)
    if not m:
        return ""
    block = m.group(1).strip()
    fence = re.match(r"^```(?:\w+)?\s*\n(.*)\n```\s*$", block, flags=re.S)
    if fence:
        return fence.group(1).strip()
    return block


def _skill_path(slug: str) -> Path:
    return skills_root() / slug / SKILL_FILENAME


def _dir_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def load_skill_from_dir(folder: Path) -> FileSkill | None:
    md_path = folder / SKILL_FILENAME
    if not md_path.is_file():
        return None
    text = md_path.read_text(encoding="utf-8")
    meta, body = _split_skill_md(text)
    slug = folder.name
    skill_id = str(meta.get("id") or slug).strip() or slug
    name = str(meta.get("name") or slug).strip()
    system = str(meta.get("systemPrompt") or meta.get("system_prompt") or "").strip()
    user = str(meta.get("userPrompt") or meta.get("user_prompt") or "").strip()
    if not system:
        system = _extract_section(body, "System")
    if not user:
        user = _extract_section(body, "User") or "{{input}}"

    params = meta.get("params") or meta.get("modelParams") or {}
    if not isinstance(params, dict):
        params = {}
    # normalize keys
    model_params = {
        "temperature": float(params.get("temperature", 0.4)),
        "maxTokens": int(params.get("maxTokens") or params.get("max_tokens") or 2048),
    }

    workflow = meta.get("workflow") if isinstance(meta.get("workflow"), dict) else {}
    workflow = dict(workflow or {})
    kind = str(meta.get("workflowKind") or workflow.get("kind") or "").strip()
    if kind:
        workflow["kind"] = kind
    source = str(meta.get("source") or workflow.get("presetSource") or "").strip()
    if source:
        workflow["presetSource"] = source

    md_doc = str(meta.get("mdDoc") or meta.get("md_doc") or "").strip() or body
    variables = meta.get("variables")
    if not isinstance(variables, list) or not variables:
        variables = [{"name": v, "type": "string"} for v in extract_variables(user)]

    published = _parse_dt(meta.get("publishedAt") or meta.get("published_at"))
    created = _parse_dt(meta.get("createdAt") or meta.get("created_at")) or published
    updated = _parse_dt(meta.get("updatedAt") or meta.get("updated_at")) or created
    now = datetime.utcnow()

    return FileSkill(
        id=skill_id,
        name=name,
        description=str(meta.get("description") or ""),
        specialty=str(meta.get("specialty") or "")[:64],
        router_blurb=str(meta.get("routerBlurb") or meta.get("router_blurb") or "")[:256],
        triggers=list(meta.get("triggers") or [])[:16],
        tags=list(meta.get("tags") or []),
        model_name=str(meta.get("model") or meta.get("modelName") or "chatzoc_9b_B"),
        model_params=model_params,
        system_prompt_enc=system,
        user_prompt_template=user,
        variables=variables,
        author_id=str(meta.get("authorId") or meta.get("author_id") or "platform-preset"),
        author_name=str(meta.get("authorName") or meta.get("author_name") or "平台预置"),
        version=str(meta.get("version") or "v1.0.0"),
        changelog=str(meta.get("changelog") or ""),
        status=str(meta.get("status") or "published"),
        visibility=str(meta.get("visibility") or "public"),
        md_doc=md_doc,
        workflow=workflow,
        examples=list(meta.get("examples") or []),
        total_calls=int(meta.get("totalCalls") or meta.get("total_calls") or 0),
        avg_rating=float(meta.get("avgRating") or meta.get("avg_rating") or 0.0),
        published_at=published or (now if (meta.get("status") or "published") == "published" else None),
        created_at=created or now,
        updated_at=updated or now,
        root=folder.resolve(),
    )


def _skills_dir_stamp(root: Path) -> tuple[tuple[str, ...], float]:
    """目录名集合 + 最新 mtime。只看 mtime 时，删掉某个 Skill 文件夹不会失效缓存。"""
    names: list[str] = []
    mtimes: list[float] = []
    for p in root.iterdir():
        if not p.is_dir() or p.name.startswith("."):
            continue
        names.append(p.name)
        mtimes.append(_dir_mtime(p / SKILL_FILENAME))
    names.sort()
    return (tuple(names), max(mtimes, default=0.0))


def invalidate_cache(slug: str | None = None) -> None:
    global _LIST_CACHE
    _LIST_CACHE = None
    if slug is None:
        _CACHE.clear()
    else:
        _CACHE.pop(slug, None)


def get_skill(skill_id: str) -> FileSkill | None:
    """Load by folder slug (= id)."""
    sid = (skill_id or "").strip()
    if not sid:
        return None
    folder = skills_root() / sid
    md_path = folder / SKILL_FILENAME
    if not md_path.is_file():
        # allow id field mismatch: scan once
        for s in list_skills(include_deprecated=True):
            if s.id == sid:
                return s
        return None
    mtime = _dir_mtime(md_path)
    cached = _CACHE.get(sid)
    if cached and cached[0] == mtime:
        return cached[1]
    skill = load_skill_from_dir(folder)
    if skill:
        _CACHE[sid] = (mtime, skill)
    return skill


def list_skills(
    *,
    curated_only: bool = False,
    include_deprecated: bool = False,
    specialty: str | None = None,
    author_id: str | None = None,
    statuses: set[str] | None = None,
) -> list[FileSkill]:
    global _LIST_CACHE
    root = skills_root()
    names, mtime = _skills_dir_stamp(root)
    if _LIST_CACHE and _LIST_CACHE[0] == names and _LIST_CACHE[1] == mtime:
        skills = list(_LIST_CACHE[2])
    else:
        skills = []
        for folder in sorted(root.iterdir(), key=lambda p: p.name):
            if not folder.is_dir():
                continue
            if folder.name.startswith("."):
                continue
            if folder.name in {
                "html-ppt-skill-main",
                "frontend-slides-main",
                "xlsx",
                "data-analysis",
                "chart-visualization",
            }:
                continue
            try:
                skill = load_skill_from_dir(folder)
            except Exception as exc:  # noqa: BLE001
                logger.warning("skip skill dir=%s err=%s", folder.name, exc)
                continue
            if skill:
                _CACHE[folder.name] = (_dir_mtime(folder / SKILL_FILENAME), skill)
                skills.append(skill)
        stale = [k for k in _CACHE if k not in names]
        for k in stale:
            _CACHE.pop(k, None)
        _LIST_CACHE = (names, mtime, list(skills))

    out = skills
    if not include_deprecated:
        out = [s for s in out if s.status != "deprecated"]
    if curated_only:
        out = [s for s in out if s.author_id == "platform-preset"]
    if author_id:
        out = [s for s in out if s.author_id == author_id]
    if statuses:
        out = [s for s in out if s.status in statuses]
    q = (specialty or "").strip()
    if q:
        out = [s for s in out if q in (s.specialty or "")]
    out.sort(key=lambda s: (s.published_at or s.updated_at or datetime.min), reverse=True)
    return out


def _meta_from_skill(skill: FileSkill) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "id": skill.id,
        "name": skill.name,
        "description": skill.description,
        "specialty": skill.specialty,
        "routerBlurb": skill.router_blurb,
        "triggers": skill.triggers,
        "tags": skill.tags,
        "version": skill.version,
        "model": skill.model_name,
        "params": skill.model_params,
        "authorId": skill.author_id,
        "authorName": skill.author_name,
        "visibility": skill.visibility,
        "status": skill.status,
        "changelog": skill.changelog,
        "systemPrompt": skill.system_prompt_enc,
        "userPrompt": skill.user_prompt_template,
        "variables": skill.variables,
        "examples": skill.examples,
        "workflow": skill.workflow,
        "totalCalls": skill.total_calls,
        "avgRating": skill.avg_rating,
    }
    if skill.published_at:
        meta["publishedAt"] = skill.published_at.isoformat(timespec="seconds")
    if skill.created_at:
        meta["createdAt"] = skill.created_at.isoformat(timespec="seconds")
    if skill.updated_at:
        meta["updatedAt"] = skill.updated_at.isoformat(timespec="seconds")
    source = (skill.workflow or {}).get("presetSource")
    if source:
        meta["source"] = source
    kind = (skill.workflow or {}).get("kind")
    if kind:
        meta["workflowKind"] = kind
    return meta


def render_skill_md(skill: FileSkill) -> str:
    meta = _meta_from_skill(skill)
    body = (skill.md_doc or "").strip()
    # Avoid duplicating huge system into body if body already has it
    return f"---\n{json.dumps(meta, ensure_ascii=False, indent=2)}\n---\n\n{body}\n"


def save_skill(skill: FileSkill) -> FileSkill:
    slug = (skill.id or "").strip()
    if not slug:
        raise ValueError("skill id (slug) 不能为空")
    folder = skills_root() / slug
    folder.mkdir(parents=True, exist_ok=True)
    skill.root = folder.resolve()
    skill.updated_at = datetime.utcnow()
    if not skill.created_at:
        skill.created_at = skill.updated_at
    path = folder / SKILL_FILENAME
    path.write_text(render_skill_md(skill), encoding="utf-8")
    invalidate_cache(slug)
    return skill


def delete_skill(skill_id: str, *, purge: bool = False) -> bool:
    skill = get_skill(skill_id)
    if not skill:
        return False
    if purge and skill.root and skill.root.is_dir():
        shutil.rmtree(skill.root)
        invalidate_cache(skill_id)
        return True
    skill.status = "deprecated"
    skill.updated_at = datetime.utcnow()
    save_skill(skill)
    return True


def allocate_slug(name: str, *, prefer: str | None = None) -> str:
    base = (prefer or "").strip() or slugify(name)
    if not (skills_root() / base).exists():
        return base
    for i in range(2, 50):
        cand = f"{base}-{i}"
        if not (skills_root() / cand).exists():
            return cand
    raise ValueError(f"无法为 {name!r} 分配 slug")


def skill_to_dict(skill: FileSkill) -> dict[str, Any]:
    d = asdict(skill)
    d.pop("root", None)
    return d
