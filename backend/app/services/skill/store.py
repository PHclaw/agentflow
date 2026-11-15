"""Filesystem Skill store: skills/<slug>/SKILL.md (+ optional scripts/)."""
from __future__ import annotations

import json
import os
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

#: 平台侧元数据的旁挂文件：``skills/<slug>/agentflow.json``。
#:
#: 为什么不把平台字段直接写进 SKILL.md：**第三方技能会校验自己 SKILL.md 的
#: 原始字节**。``ppt-master`` 的 ``scripts/attribution_guard.py`` 用逐字符
#: 正则核对 frontmatter（``^  copyright\s*:\s*"…"\s*$`` —— 恰好两个空格、
#: 键名不带引号），并要求 LICENSE 的 sha256 一字不差。
#:
#: 早先导入时把 YAML frontmatter 统一重写成 JSON，正则全部落空，那个技能
#: 退出码 78、当场自我中止（「完整性校验未通过」）—— **而导入流程报的是成功**。
#:
#: 所以约定改成：**导入不修改 SKILL.md 的任何一个字节**。平台需要的字段
#: （id / authorId / 广场描述 / systemPrompt 覆盖）写在这个旁挂文件里，
#: 加载时合并、旁挂优先。这样第三方技能永远保持官方分发的原始形态。
SIDECAR_FILENAME = "agentflow.json"

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


#: frontmatter 头部**看起来像** YAML 映射的最低标准：至少一行顶格的 ``key:``。
#: 见 ``_parse_yaml_frontmatter`` —— 少了这道检查，YAML 兜底会变成「什么都收」。
_YAML_MAPPING_RE = re.compile(r"(?m)^[A-Za-z_][A-Za-z0-9_-]*\s*:")


def _split_skill_md(text: str) -> tuple[dict[str, Any], str]:
    """SKILL.md = optional frontmatter between --- fences + markdown body.

    frontmatter **JSON 优先、YAML 兜底**。AgentFlow 自己写的全是 JSON，但从
    Claude Code 生态导入的技能用的是 YAML（``name:`` / ``description: >`` /
    嵌套 ``metadata:``）；那些技能必须原样保留（见 ``SIDECAR_FILENAME``），
    于是加载路径也得能读。
    """
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
        # 两边都不行时要把**这条**消息抛出去：运维在管理后台看到的
        # 「技能加载失败」原因里带着文件名和字段信息，比裸的
        # JSONDecodeError（"Expecting property name ..."）可行动得多。
        return _parse_yaml_frontmatter(
            head, f"SKILL.md frontmatter 不是合法 JSON: {exc}"
        ), body.strip()
    if not isinstance(meta, dict):
        raise ValueError("SKILL.md frontmatter 必须是 JSON 对象")
    return meta, body.strip()


def _parse_yaml_frontmatter(head: str, json_error: str) -> dict[str, Any]:
    """YAML 兜底。解析不出「像 frontmatter 的东西」就把 JSON 那条错误抛回去。

    为什么要多一道 ``_YAML_MAPPING_RE`` 的形似检查：``yaml.safe_load`` 几乎
    什么都收（``"{ 坏 JSON }"`` 会变成 ``{"坏 JSON": None}``）。只用它兜底，
    那些**本来会被跳过的坏 SKILL.md** 就会带着一堆乱码元数据被加载进来 ——
    「静默加载一个坏技能」比「跳过它」难发现得多。至少得有一行顶格的
    ``key:`` 才算数。
    """
    if not _YAML_MAPPING_RE.search(head):
        raise ValueError(json_error)
    try:
        import yaml
    except ImportError:
        logger.warning("SKILL.md 用的是 YAML frontmatter，但没装 pyyaml，无法加载")
        raise ValueError(json_error) from None
    try:
        meta = yaml.safe_load(head)
    except Exception:  # noqa: BLE001 - 报 JSON 那条错指向性更强
        raise ValueError(json_error) from None
    if not isinstance(meta, dict):
        raise ValueError(json_error)
    return meta


def _read_sidecar(folder: Path) -> dict[str, Any]:
    """读平台旁挂元数据。

    不存在、读坏、不是对象 —— 一律返回空 dict 并留一条日志。**不能让它挡住
    技能加载**：旁挂只是平台侧的补充信息，SKILL.md 才是技能的本体。
    """
    path = folder / SIDECAR_FILENAME
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("旁挂元数据损坏，已忽略：%s（%s）", path, exc)
        return {}
    if not isinstance(data, dict):
        logger.warning("旁挂元数据不是 JSON 对象，已忽略：%s", path)
        return {}
    return data


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
    # 平台旁挂元数据盖在包里的 frontmatter 之上，且必须在这里合并：下面每一处
    # 都从 meta 取值，合一次就够。旁挂优先 —— 它是管理员在导入/编辑时明确
    # 定下的那几项，而 SKILL.md 里的原值可能根本不符合 AgentFlow 的字段约定。
    meta = {**meta, **_read_sidecar(folder)}
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


# ---------------------------------------------------------------------------
# 写入（管理后台用）
#
# 技能广场原本只有读路径：加技能靠运维手工建目录写文件。这里补上对称的写
# 路径，让管理后台能增删改。三个约束不能松：
#
# 1. **slug 是拼进文件系统路径的**，必须收得非常紧；
# 2. **原子写** —— SKILL.md 写坏一半，``load_skill_from_dir`` 会抛异常，
#    整个技能被扫盘跳过，用户看到的就是「技能凭空消失」；
# 3. **写完必须失效缓存**，否则要等下一次 mtime 变化才刷新。
# ---------------------------------------------------------------------------

#: 广场不可见的目录。见 ``list_skills`` 里的排除逻辑。
#: 这些是从 GitHub 整包拉下来的 ``-main`` 目录，内容格式与 AgentFlow 的
#: frontmatter 约定不一定对得上，所以不展示。
HIDDEN_SLUGS = frozenset({
    "html-ppt-skill-main",
    "frontend-slides-main",
    "xlsx",
    "data-analysis",
    "chart-visualization",
})

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")

#: frontmatter 里必须有的字段。缺了 ``systemPrompt`` 技能能加载但一调用就
#: 产出空内容，所以在写入时就拦掉。
REQUIRED_FIELDS = ("name", "systemPrompt")

#: 平台预置技能的 author_id。
#: ``list_skills(curated_only=True)`` 用它筛「平台预置」，而
#: ``GET /skills/plaza`` 正是这么调的 —— 管理后台建的技能必须落到这个值上，
#: 否则建完在广场上根本看不到（而且不报错，只是凭空不出现）。
PLATFORM_AUTHOR_ID = "platform-preset"


class SkillWriteError(Exception):
    """技能写入失败（slug 非法 / 被占用 / 命中保留名单 / 缺必填字段）。"""


def check_slug_shape(raw: str) -> str:
    """只校验字符集与长度，**不查保留名单**。

    拆出来是给技能包预览用的：预览阶段要能拿到保留名然后**警告**
    （「这个 slug 导进去广场也看不到」），而不是直接报错。
    写入侧仍然走 ``normalize_slug``，那里会连保留名单一起拦。
    """
    slug = (raw or "").strip().lower()
    if not _SLUG_RE.match(slug):
        raise SkillWriteError(
            "slug 只能包含小写字母、数字和连字符，且以字母或数字开头，长度 1-64"
        )
    return slug


def normalize_slug(raw: str) -> str:
    """校验并归一化 slug。

    目录名会直接拼进文件系统路径，因此只允许小写字母、数字和连字符，
    首字符必须是字母或数字。中文名、空格、斜杠、``..``、超长一律拒绝。
    """
    slug = check_slug_shape(raw)
    if slug in HIDDEN_SLUGS:
        raise SkillWriteError(
            f"「{slug}」是平台保留目录（预置但未接入广场），不能通过后台创建"
        )
    return slug


def skill_dir(slug: str) -> Path:
    """slug 对应的目录，并确保它确实落在 skills_root 之内。

    即使 ``normalize_slug`` 被绕过，这一层也要拦住 —— 双保险。
    """
    root = skills_root().resolve()
    path = (root / slug).resolve()
    if path != root and root not in path.parents:
        raise SkillWriteError("非法路径")
    return path


def resolve_slug(raw: str) -> str:
    """**读取**用的 slug 归一化：只做路径安全检查，不改写大小写。

    ``normalize_slug`` 是写入用的严格校验，会把大写折叠成小写。读取已有
    目录时不能折叠 —— 盘上叫什么就得找什么，否则明明存在的技能会报 404。
    """
    slug = (raw or "").strip()
    if not slug:
        raise SkillWriteError("slug 不能为空")
    skill_dir(slug)  # 只借它做「仍在 skills_root 之内」的路径检查
    return slug


def _render_md(frontmatter: dict[str, Any], body: str) -> str:
    """序列化为 SKILL.md，与 ``_split_skill_md`` 严格对称。

    注意别和下面的 ``render_skill_md(skill: FileSkill)`` 搞混：那个是平台
    侧的序列化入口（吃 FileSkill），这个只服务管理后台的「前端直接给
    frontmatter + body」场景，所以做成私有。

    结尾的换行要留：``_split_skill_md`` 用 ``find("\\n---")`` 定位结束围栏，
    少了换行就找不着。
    """
    return (
        "---\n"
        + json.dumps(frontmatter, ensure_ascii=False, indent=2)
        + "\n---\n\n"
        + (body or "").strip()
        + "\n"
    )


def read_skill_md(slug: str) -> tuple[dict[str, Any], str]:
    """读回 SKILL.md，拆成 frontmatter 与正文。

    **返回的是合并后的有效配置**（包里的 frontmatter + 平台旁挂元数据），
    因为管理后台拿它当编辑表单的数据源 —— 显示实际生效的值，才是他改之前
    该看到的东西。

    文件不存在或 frontmatter 两边都解析不了时抛 ``SkillWriteError`` ——
    统一成一种异常，调用方不必同时 catch ValueError。
    """
    path = skill_dir(slug) / SKILL_FILENAME
    if not path.is_file():
        raise SkillWriteError(f"技能 {slug} 不存在")
    try:
        meta, body = _split_skill_md(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise SkillWriteError(str(exc)) from exc
    return {**meta, **_read_sidecar(path.parent)}, body


def write_sidecar(slug: str, meta: dict[str, Any]) -> Path:
    """写平台旁挂元数据，**不碰 SKILL.md**。

    ``authorId`` 强制为 ``PLATFORM_AUTHOR_ID``：广场走 curated_only 过滤，
    只认这一个值。留个可填的口子就等于留一个「改完技能从广场消失」的陷阱，
    而且它不报错，只是不见了。
    """
    slug = normalize_slug(slug)
    folder = skill_dir(slug)
    if not (folder / SKILL_FILENAME).is_file():
        raise SkillWriteError(f"技能 {slug} 不存在")

    payload = {k: v for k, v in meta.items() if v not in (None, "", [], {})}
    payload["id"] = slug
    payload["authorId"] = PLATFORM_AUTHOR_ID
    path = folder / SIDECAR_FILENAME
    _atomic_write(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return path


def _replace_body(path: Path, body: str) -> None:
    """只替换 SKILL.md 的正文，frontmatter **逐字节**保留。

    用正则切出「开头到结束围栏那一行为止」作为前缀、再拼新正文，而不是
    拆成对象再重新序列化 —— 重排会改掉缩进、引号和换行风格，而那正是
    第三方自检比对的东西（见 ``SIDECAR_FILENAME``）。
    """
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^(\ufeff?---.*?\n---[^\n]*\n)", text, flags=re.S)
    prefix = m.group(1) if m else ""
    _atomic_write(path, prefix + "\n" + (body or "").strip() + "\n")


def _atomic_write(path: Path, text: str) -> None:
    """先写临时文件再替换，避免半截文件被扫盘读到。

    **走 bytes 而不是 ``write_text``**：后者按平台默认翻译换行，Windows 上
    会把 ``\\n`` 写成 ``\\r\\n``，于是同一个技能在 Windows 建的、和在 Linux
    建的落盘字节不同。第三方自检是逐字节比对的（见 ``SIDECAR_FILENAME``），
    这种「平台相关的格式漂移」正是那类故障的温床。
    """
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(text.encode("utf-8"))
    os.replace(tmp, path)


def _validate_frontmatter(frontmatter: dict[str, Any]) -> None:
    if not isinstance(frontmatter, dict):
        raise SkillWriteError("frontmatter 必须是 JSON 对象")
    missing = [f for f in REQUIRED_FIELDS if not str(frontmatter.get(f) or "").strip()]
    if missing:
        raise SkillWriteError(f"缺少必填字段：{'、'.join(missing)}")


def create_skill(slug: str, frontmatter: dict[str, Any], body: str) -> Path:
    """新建技能。slug 已存在时拒绝 —— 想改内容请走 update。"""
    slug = normalize_slug(slug)
    _validate_frontmatter(frontmatter)

    folder = skill_dir(slug)
    if (folder / SKILL_FILENAME).is_file():
        raise SkillWriteError(f"技能 {slug} 已存在，请改用更新")

    meta = dict(frontmatter)
    meta["id"] = slug          # id 必须与目录名一致，否则 get_skill 要走兜底扫描
    # authorId **强制**覆盖而不是 setdefault：广场用 curated_only 过滤，
    # 只认 platform-preset。留一个可填的口子，就等于留一个「建完却看不到」
    # 的陷阱 —— 而它不报错，只是凭空不出现。
    meta["authorId"] = PLATFORM_AUTHOR_ID
    meta.setdefault("authorName", "平台预置")
    meta.setdefault("visibility", "public")
    meta.setdefault("status", "published")

    folder.mkdir(parents=True, exist_ok=True)
    _atomic_write(folder / SKILL_FILENAME, _render_md(meta, body))
    invalidate_cache()
    logger.info("技能已创建 slug=%s", slug)
    return folder / SKILL_FILENAME


def update_skill(slug: str, frontmatter: dict[str, Any], body: str) -> Path:
    """覆盖已有技能的配置与正文。

    **有旁挂元数据的技能（导入来的）改写旁挂，不动 SKILL.md 的 frontmatter。**
    直接重写会把第三方的字节级自检打掉 —— 技能随即在自己的完整性闸门上
    自我中止，而「保存」这个动作看起来是成功的（见 ``SIDECAR_FILENAME``）。

    正文仍然写回 SKILL.md（只换正文段，原 frontmatter 原样保留）：那是技能
    本体的一部分，管理员改说明本来就该改它。
    """
    slug = normalize_slug(slug)
    _validate_frontmatter(frontmatter)

    path = skill_dir(slug) / SKILL_FILENAME
    if not path.is_file():
        raise SkillWriteError(f"技能 {slug} 不存在，请先创建")

    meta = dict(frontmatter)
    meta["id"] = slug

    if (path.parent / SIDECAR_FILENAME).is_file():
        write_sidecar(slug, meta)
        _replace_body(path, body)
        where = "旁挂元数据 + 正文"
    else:
        _atomic_write(path, _render_md(meta, body))
        where = "SKILL.md"

    invalidate_cache(slug)
    invalidate_cache()
    logger.info("技能已更新 slug=%s（%s）", slug, where)
    return path


def remove_skill_dir(slug: str) -> None:
    """**物理删除**整个技能目录（含 scripts/）。

    和 ``delete_skill(skill_id, purge=...)`` 分开：那个的默认行为是软删除
    （把 status 改成 deprecated），是给用户侧「下架我的技能」用的；
    管理后台要的是真的清掉，语义不同，名字也必须不同，否则迟早有人调错。
    """
    slug = normalize_slug(slug)
    folder = skill_dir(slug)
    if not folder.is_dir():
        raise SkillWriteError(f"技能 {slug} 不存在")
    # 双保险：绝不允许删到 skills_root 本身
    if folder.resolve() == skills_root().resolve():
        raise SkillWriteError("不能删除技能根目录")
    shutil.rmtree(folder)
    invalidate_cache()
    logger.info("技能已删除 slug=%s", slug)


def _skills_dir_stamp(root: Path) -> tuple[tuple[str, ...], float]:
    """目录名集合 + 最新 mtime。只看 mtime 时，删掉某个 Skill 文件夹不会失效缓存。"""
    names: list[str] = []
    mtimes: list[float] = []
    for p in root.iterdir():
        if not p.is_dir() or p.name.startswith("."):
            continue
        names.append(p.name)
        mtimes.append(_dir_mtime(p / SKILL_FILENAME))
        # 旁挂元数据也要看：只改 SKILL.md 之外那份时，否则缓存不会失效，
        # 表现是「改了广场描述，界面上要等一会儿才变」。
        mtimes.append(_dir_mtime(p / SIDECAR_FILENAME))
    names.sort()
    return (tuple(names), max(mtimes, default=0.0))


def invalidate_cache(slug: str | None = None) -> None:
    global _LIST_CACHE
    _LIST_CACHE = None
    if slug is None:
        _CACHE.clear()
    else:
        _CACHE.pop(slug, None)


def _is_valid_skill_id(sid: str) -> bool:
    if not sid:
        return False
    if ".." in sid or "/" in sid or "\\" in sid or "\x00" in sid:
        return False
    return True


def get_skill(skill_id: str) -> FileSkill | None:
    """Load by folder slug (= id)."""
    sid = (skill_id or "").strip()
    if not _is_valid_skill_id(sid):
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
            if folder.name in HIDDEN_SLUGS:
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
    # 走 _atomic_write 而不是 write_text：既要原子（写坏一半会被扫盘跳过，
    # 用户看到技能凭空消失），也要字节稳定（write_text 在 Windows 上会把
    # 换行翻成 CRLF）。
    _atomic_write(path, render_skill_md(skill))
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
