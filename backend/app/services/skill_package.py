"""技能包（zip）导入。

**两种包布局都接受**：

1. 扁平包（自己打的）::

       <slug>/
         SKILL.md        # 必需：frontmatter + Markdown
         scripts/        # 可选：可执行脚本

2. 仓库整包（GitHub ``Download ZIP``）::

       <repo>-main/
         .github/  README.md  docs/assets/…    # ← 这些不会被导入
         skills/<name>/
           SKILL.md
           scripts/  references/  templates/…

   第 2 种会自动**下钻**到 ``SKILL.md`` 所在的目录，只导入那个目录下的
   文件。不下钻的话，``ppt-master-main.zip``（54MB、一万三千条）会直接撞
   在体积和条目上限上，而它真正的技能只有 37MB；下钻还顺带避免把 ``docs/``
   里 19MB 的演示 gif 和 CI 配置搬进技能目录。

   包里含多个 ``SKILL.md``（很多仓库一次放几十个技能）时**不猜**：报错并
   列出候选，由调用方用 ``skill_path`` 指定。猜错会导进来一个内容完全不对
   的技能，而且看起来是成功的 —— 那种故障比直接报错难查得多。

**frontmatter 兼容 JSON 与 YAML**：AgentFlow 自己写的是 JSON，但 Claude
Code 生态的技能用 YAML（``name:`` / ``description: >``）。两者都读成 dict
后**只用来解析和预览**。

**导入不修改 SKILL.md 的任何一个字节**：平台需要的字段（id / authorId /
广场描述 / systemPrompt 覆盖）写到旁挂文件 ``agentflow.json``，加载时合并。
这条是硬的 —— 第三方技能常拿文本比对自己分发的文件，重写 frontmatter 会让
它们当场失效且不报错。详见 ``store.SIDECAR_FILENAME``。

来源通常是 GitHub 仓库整包下载 —— 本仓库 ``skills/`` 下的
``html-ppt-skill-main``、``frontend-slides-main`` 就是这么来的。

**为什么值得单独一个模块而不是在 API 里解压**：zip 是不可信输入，
有四种典型的攻击面，漏一个就能被拿捏：

1. **路径穿越** —— 条目名写成 ``../../app/core/config.py``，解压时会写到
   skills_root 之外；
2. **符号链接** —— zip 里可以存一个指向 ``/etc/passwd`` 的软链，
   解压后再往里写文件就中招了；
3. **zip bomb** —— 几十 KB 的包解压出几十 GB；
4. **覆盖既有技能** —— 同名 slug 直接盖掉线上技能。

这几条都在这里拦掉，API 层只负责鉴权。
"""
from __future__ import annotations

import io
import json
import shutil
import time
import zipfile
from dataclasses import dataclass, field, replace
from pathlib import Path, PurePosixPath

from app.core.logging import get_logger
from app.services.skill.store import (
    HIDDEN_SLUGS,
    PLATFORM_AUTHOR_ID,
    SIDECAR_FILENAME,
    SKILL_FILENAME,
    SkillWriteError,
    _extract_section,
    _split_skill_md,
    check_slug_shape,
    invalidate_cache,
    normalize_slug,
    skill_dir,
    skills_root,
)

logger = get_logger("skillpackage")

#: 上传体积上限。
#:
#: 早先是 20MB，理由是「技能包就是几个 md 和 py」—— 那个假设只对自己打的
#: 扁平包成立。GitHub 整包下载动辄几十上百 MB（ppt-master-main 就是 54MB）。
#: 真正防 zip bomb 的是下面两条「解压后」的上限，压缩包本身多大只关系到
#: 上传耗时，不该是准入条件。
MAX_ZIP_BYTES = 256 * 1024 * 1024
#: 解压后总量上限。作用在**真正会落盘的那部分**（下钻后的技能目录），
#: 不是整个压缩包 —— 仓库整包里的 docs/ 截图不该吃掉技能的体积额度。
MAX_TOTAL_BYTES = 256 * 1024 * 1024
#: 落盘文件数上限。同上，只算技能目录内的。500 对「几个 md 加一个
#: scripts/」够用，但真实的 PPT/图表类技能带一两万个模板文件是正常的。
MAX_ENTRIES = 50_000
#: 中央目录条目总数上限（含不导入的那些）。便宜的第一道闸：
#: 解析 central directory 不落盘，先把病态压缩包挡在外面。
MAX_SCAN_ENTRIES = 200_000
#: 单个条目解压后的字节上限。用于在流式读取时兜住
#: 「声明的 file_size 与实际不符」这种 zip bomb 变体。
MAX_ENTRY_BYTES = 64 * 1024 * 1024
#: 正文被当作 systemPrompt 使用所需的最短长度。
#:
#: 第三方包（尤其 Claude Code 生态）常常没有 systemPrompt，只有一大段
#: SKILL.md 正文 —— 那段正文本来就是写给模型看的指令，直接拿来当
#: systemPrompt 是合理的。但过短的内容是占位符（比如正文只有一个「正文」
#: 二字），拿它当提示词只会得到一个能加载、能调用、产出垃圾的空壳。
#: 宁可让它失败，也别让它静默地坏着。
MIN_BODY_PROMPT_CHARS = 40
#: 预览响应里回传的文件名个数上限。真实仓库包有一万多个文件，
#: 全塞进预览 JSON 是一兆多的无用载荷。
PREVIEW_FILE_SAMPLE = 200
#: 暂存目录闲置多久算「死掉的导入」。见 ``cleanup_stale_staging``。
STALE_STAGING_SECONDS = 3600


class PackageError(Exception):
    """技能包不合法。message 直接给用户看。"""


@dataclass
class PackagePreview:
    """解压前的检查结果，给管理界面做确认用。"""

    slug: str
    name: str
    description: str = ""
    #: 技能目录内的文件相对路径，**最多只保留 ``PREVIEW_FILE_SAMPLE`` 个**
    files: list[str] = field(default_factory=list)
    #: 技能目录内的文件总数（可能大于 ``len(files)``）
    file_count: int = 0
    total_bytes: int = 0
    has_scripts: bool = False
    #: 不致命但值得提示的问题（例如缺 description）
    warnings: list[str] = field(default_factory=list)
    #: 该 slug 是否已存在（导入会撞车）
    exists: bool = False
    #: 定位到的技能目录（包内相对路径，空串表示 SKILL.md 就在根上）
    skill_path: str = ""
    #: 包里所有含 SKILL.md 的目录。多于一个时只导入 ``skill_path``
    skill_candidates: list[str] = field(default_factory=list)
    #: 因为不在技能目录内而被跳过的文件数（仓库整包里的 docs/、.github/ 等）
    ignored_files: int = 0


def _normalize_entry(name: str) -> str:
    """zip 条目名统一成 posix 风格，并拒绝任何越界写法。"""
    # Windows 打的包可能用反斜杠
    raw = name.replace("\\", "/")
    if not raw or raw.startswith("/"):
        raise PackageError(f"包含非法的文件路径：{name}")
    parts = PurePosixPath(raw).parts
    if any(p in ("..",) for p in parts):
        raise PackageError(f"包含路径穿越的文件：{name}")
    if any(":" in p for p in parts):  # C: 盘符之类
        raise PackageError(f"包含非法的文件路径：{name}")
    return "/".join(parts)


def _iter_infos(zf: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    """过一遍中央目录：安全校验 + 总数闸。

    **不在这里判体积和落盘条目数** —— 那时候还不知道技能目录是哪个，
    拿整个仓库的量去卡会把正常的整包也挡掉。
    """
    infos = zf.infolist()
    if len(infos) > MAX_SCAN_ENTRIES:
        raise PackageError(
            f"压缩包条目过多（{len(infos)} > {MAX_SCAN_ENTRIES}），已拒绝"
        )

    out: list[zipfile.ZipInfo] = []
    for info in infos:
        if info.is_dir():
            continue
        _normalize_entry(info.filename)  # 先校验，不合法直接抛

        # 符号链接 / 硬链接 / 设备文件一律拒绝。
        # zip 的 Unix 模式在高 16 位里。
        mode = (info.external_attr >> 16) & 0o170000
        if mode == 0o120000:
            raise PackageError(f"包含符号链接，已拒绝：{info.filename}")
        if mode not in (0, 0o100000):
            raise PackageError(f"包含非常规文件类型，已拒绝：{info.filename}")

        out.append(info)
    return out


def _scope_infos(infos: list[zipfile.ZipInfo], root: str) -> list[zipfile.ZipInfo]:
    """只留技能目录下的文件，并在**这个范围上**判体积与条目数。

    仓库整包里 ``docs/`` 有几十兆截图，不圈定范围的话它们会和技能本体
    抢同一份额度 —— 结果是「技能本身很小却被拒绝导入」。
    """
    if not root:
        scoped = list(infos)
    else:
        prefix = root + "/"
        scoped = [i for i in infos if _normalize_entry(i.filename).startswith(prefix)]
        if not scoped:
            raise PackageError(f"技能目录 {root} 下没有任何文件")

    if len(scoped) > MAX_ENTRIES:
        raise PackageError(f"技能目录内文件过多（{len(scoped)} > {MAX_ENTRIES}），已拒绝")
    total = sum(i.file_size for i in scoped)
    if total > MAX_TOTAL_BYTES:
        raise PackageError(
            f"技能目录解压后超过上限（{MAX_TOTAL_BYTES // 1024 // 1024}MB），已拒绝"
        )
    return scoped


def _read_entry(
    zf: zipfile.ZipFile, info: zipfile.ZipInfo, budget: list[int]
) -> bytes:
    """流式读一个条目，按**实际**解压量记账。

    不能只信 ``info.file_size``：那是压缩包自己声明的值，可以撒谎。以前直接
    ``zf.read(info)``、靠声明的体积求和来判断 zip bomb，伪造声明就能让一次
    read 把内存吃满。这里分块读，每块都记进跨条目的总预算。
    """
    chunks: list[bytes] = []
    got = 0
    with zf.open(info) as src:
        while True:
            block = src.read(1 << 20)
            if not block:
                break
            got += len(block)
            if got > MAX_ENTRY_BYTES:
                raise PackageError(f"条目解压后超过单文件上限：{info.filename}")
            budget[0] += len(block)
            if budget[0] > MAX_TOTAL_BYTES:
                raise PackageError(
                    f"解压后体积超过上限（{MAX_TOTAL_BYTES // 1024 // 1024}MB），已拒绝"
                )
            chunks.append(block)
    return b"".join(chunks)


def _skill_roots(names: list[str]) -> list[str]:
    """包里所有「含 SKILL.md 的目录」。空串表示 SKILL.md 直接躺在根上。"""
    roots: set[str] = set()
    suffix = "/" + SKILL_FILENAME
    for name in names:
        if name == SKILL_FILENAME:
            roots.add("")
        elif name.endswith(suffix):
            roots.add(name[: -len(suffix)])
    return sorted(roots)


def _locate_skill_root(names: list[str], skill_path: str | None = None) -> str:
    """定位真正的技能目录（仓库整包需要下钻）。

    多个候选时只接受「唯一最浅」的那一个；同深度有多个就是**不猜**，
    报错并列出候选。猜错的代价是导进来一个内容完全不对的技能，而且从
    表面上看起来是成功的。
    """
    roots = _skill_roots(names)

    if skill_path is not None and skill_path.strip().strip("/"):
        want = skill_path.strip().strip("/")
        if want not in roots:
            raise PackageError(
                f"包内没有 {want}/{SKILL_FILENAME}。可选："
                + ("、".join(r or "(根目录)" for r in roots) or "无")
            )
        return want

    if not roots:
        raise PackageError(f"压缩包里找不到 {SKILL_FILENAME}")
    if len(roots) == 1:
        return roots[0]

    shallowest = min(r.count("/") for r in roots)
    top = [r for r in roots if r.count("/") == shallowest]
    if len(top) == 1:
        return top[0]
    raise PackageError(
        "压缩包里包含多个技能（"
        + "、".join(r or "(根目录)" for r in top)
        + "），一次只能导入一个；请用 skill_path 指定要导入哪个"
    )


def _split_fences(text: str) -> tuple[str, str] | None:
    """与 ``store._split_skill_md`` 同样的围栏切分，只是不解析内容。"""
    raw = text.lstrip("\ufeff")
    if not raw.startswith("---"):
        return None
    rest = raw[3:].lstrip("\r\n")
    end = rest.find("\n---")
    if end < 0:
        return None
    return rest[:end].strip(), rest[end + 4 :].lstrip("\r\n")


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """拆 frontmatter：JSON 优先，YAML 兜底。

    刻意**不动 ``store._split_skill_md``**：那条是加载路径，给它加 YAML
    兜底会让「本来会被跳过的坏 SKILL.md」变成「带着一堆乱码元数据被加载」，
    静默降级比直接跳过更难发现。导入是一次性的、有管理员盯着结果的，
    宽容才有意义；而且导入时就会重写成 JSON，加载路径永远走不到 YAML。
    """
    try:
        return _split_skill_md(text)
    except ValueError as exc:
        json_exc = exc

    parts = _split_fences(text)
    if parts is None:
        raise json_exc
    head, body = parts

    try:
        import yaml
    except ImportError:  # 没装 pyyaml 就退回 JSON-only
        raise json_exc from None

    try:
        meta = yaml.safe_load(head) if head else {}
    except Exception:  # noqa: BLE001 - YAML 也不行，报原来的 JSON 错误
        raise json_exc from None
    if not isinstance(meta, dict):
        raise json_exc from None
    return meta, body.strip()


#: 导入确认框里可以覆盖的 frontmatter 字段。
#: ``id`` / ``authorId`` 不在此列 —— 它们由导入流程强制，见 ``import_zip``。
OVERRIDABLE_FIELDS = (
    "name",
    "description",
    "specialty",
    "routerBlurb",
    "systemPrompt",
    "userPrompt",
    "tags",
    "triggers",
    "version",
)


def _apply_overrides(meta: dict, overrides: dict | None) -> dict:
    """把管理员在确认框里填的值合进 frontmatter。

    空白值一律忽略 —— 表单里没填的字段会以空串传上来，那意思是「用包里的
    值」，不是「把它清空」。否则一次导入会把 name / description 抹掉。
    """
    out = dict(meta)
    for key in OVERRIDABLE_FIELDS:
        value = (overrides or {}).get(key)
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        out[key] = value
    return out


def _resolve_system_prompt(meta: dict, body: str) -> tuple[str, str | None]:
    """定出 systemPrompt，返回 (值, 警告或 None)。

    前两层与 ``store.load_skill_from_dir`` 完全一致（frontmatter →
    正文 ``### System`` 代码块），只在最后多一层「正文兜底」—— 那是专门
    给没有 systemPrompt 的第三方包准备的，见 ``MIN_BODY_PROMPT_CHARS``。
    """
    explicit = str(meta.get("systemPrompt") or meta.get("system_prompt") or "").strip()
    if explicit:
        return explicit, None

    section = _extract_section(body, "System").strip()
    if section:
        return section, None

    stripped = (body or "").strip()
    if len(stripped) >= MIN_BODY_PROMPT_CHARS:
        return stripped, (
            f"该包没有 systemPrompt，已用 SKILL.md 正文（{len(stripped)} 字）"
            "作为系统提示词，建议导入后在编辑页改写"
        )
    return "", None


def _detect_slug(root: str, meta: dict) -> str:
    """推断 slug。

    优先技能目录名（``ppt-master-main/skills/ppt-master`` → ``ppt-master``，
    比整个仓库名 ``ppt-master-main`` 贴切得多），其次 frontmatter 的 ``id``。

    刻意**不退回「唯一的顶层目录名」**：扁平包的顶层目录可能是 ``scripts``，
    拿它当 slug 会建出一个叫 ``scripts`` 的技能目录。推断不出来就让管理员在
    确认框里填，比默默生成一个荒谬的名字好。

    ``SkillWriteError`` 在这里统一转成 ``PackageError``：slug 非法 / 撞保留名
    本质上都是「这个包有问题」，调用方不该去 catch 两种异常。
    """
    candidates: list[tuple[str, str]] = []
    if root:
        candidates.append((PurePosixPath(root).name, "技能目录名"))
    if meta.get("id"):
        candidates.append((str(meta["id"]), "frontmatter.id"))

    problems: list[str] = []
    for value, label in candidates:
        if not str(value).strip():
            continue
        try:
            # 只查字符集，不查保留名单 —— 保留名要留给 import_zip 报错，
            # 让 preview 有机会先警告一句「这个 slug 广场看不到」。
            return check_slug_shape(str(value))
        except SkillWriteError as exc:
            problems.append(f"{label}「{value}」不可用（{exc}）")

    raise PackageError(
        "无法推断 slug："
        + ("；".join(problems) if problems else "包里没有可用作 slug 的目录名或 id")
    )


def cleanup_stale_staging(root: Path | None = None) -> int:
    """清掉上次**被强杀**留下的 ``.import-*`` 暂存目录，返回清掉几个。

    正常路径下 ``import_zip`` 的 ``except`` 自己会清，但进程被 kill 时那段
    代码根本没机会跑 —— 于是整个技能目录的副本就那么留在盘上
    （ppt-master 那个是 37MB）。``list_skills`` 会跳过点开头的目录，所以
    广场上看不出任何异常，只是磁盘在被慢慢吃掉。

    留一小时的宽限期：正在进行的导入不能被误删。解压过程中目录 mtime 一直
    在更新，所以真正在跑的导入不会被判定为过期。
    """
    root = root or skills_root()
    try:
        entries = list(root.iterdir())
    except OSError:
        return 0

    cutoff = time.time() - STALE_STAGING_SECONDS
    removed = 0
    for path in entries:
        if not path.is_dir() or not path.name.startswith(".import-"):
            continue
        try:
            if path.stat().st_mtime > cutoff:
                continue
            shutil.rmtree(path, ignore_errors=True)
        except OSError:
            continue
        if not path.exists():
            removed += 1
            logger.warning("清理残留的技能导入暂存目录：%s", path.name)
    return removed


def inspect_zip(
    data: bytes,
    *,
    overrides: dict | None = None,
    skill_path: str | None = None,
) -> tuple[PackagePreview, dict]:
    """检查 zip，返回预览与 frontmatter。不写任何文件。"""
    if len(data) > MAX_ZIP_BYTES:
        raise PackageError(
            f"压缩包超过 {MAX_ZIP_BYTES // 1024 // 1024}MB，请压缩后重试"
        )

    # 顺手回收上次异常退出留下的暂存目录。放在这里是因为预览和导入都会
    # 走这个函数 —— 有一条路径漏掉，残留就会一直攒着。
    cleanup_stale_staging()

    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise PackageError(f"不是有效的 zip 文件：{exc}") from exc

    with zf:
        infos = _iter_infos(zf)
        names = [_normalize_entry(i.filename) for i in infos]

        root = _locate_skill_root(names, skill_path)
        scoped = _scope_infos(infos, root)
        prefix = len(root) + 1 if root else 0
        scoped_names = [_normalize_entry(i.filename)[prefix:] for i in scoped]

        # SKILL.md 必须读**定位到的那一个**。仓库整包里可能同时存在多个，
        # 靠「第一个 basename 叫 SKILL.md 的条目」会读到别的技能。
        md_entry = (root + "/" if root else "") + SKILL_FILENAME
        info_by_name = {_normalize_entry(i.filename): i for i in infos}
        md_info = info_by_name.get(md_entry)
        if md_info is None:
            raise PackageError(f"压缩包里找不到 {md_entry}")

        try:
            raw_meta, body = _parse_frontmatter(
                _read_entry(zf, md_info, [0]).decode("utf-8", errors="replace")
            )
        except ValueError as exc:
            raise PackageError(f"{SKILL_FILENAME} 解析失败：{exc}") from exc

        meta = _apply_overrides(raw_meta, overrides)

        system, prompt_warning = _resolve_system_prompt(meta, body)
        if not system:
            raise PackageError(
                f"{SKILL_FILENAME} 缺少 systemPrompt，正文也短于 "
                f"{MIN_BODY_PROMPT_CHARS} 字 —— 这样的技能能加载但产出空内容"
            )
        meta = dict(meta)
        meta["systemPrompt"] = system

        if not str(meta.get("name") or "").strip():
            raise PackageError(f"{SKILL_FILENAME} 缺少 name 字段")

        slug = _detect_slug(root, meta)
        # 按路径分量判断，别用子串匹配 scoped_names 是**去掉前缀后的相对
        # 路径**（``scripts/run.py``），``"/scripts/"`` 这种带前导斜杠的
        # 写法一个都匹配不上，结果所有带脚本的技能都被标成「纯 Prompt 技能」。
        has_scripts = any("scripts" in PurePosixPath(n).parts for n in scoped_names)

        warnings: list[str] = []
        if prompt_warning:
            warnings.append(prompt_warning)
        if not str(meta.get("description") or "").strip():
            warnings.append("缺少 description，广场上会显示为空描述")
        if slug in HIDDEN_SLUGS:
            warnings.append(f"「{slug}」是平台保留目录名，导入后广场不可见")
        if not has_scripts:
            warnings.append("没有 scripts/ 目录，这是个纯 Prompt 技能")

        candidates = _skill_roots(names)
        if len(candidates) > 1:
            warnings.append(
                "包里含多个技能（"
                + "、".join(r or "(根目录)" for r in candidates)
                + f"），本次只导入 {root or '(根目录)'}"
            )

        preview = PackagePreview(
            slug=slug,
            name=str(meta.get("name") or slug),
            description=str(meta.get("description") or ""),
            files=scoped_names[:PREVIEW_FILE_SAMPLE],
            file_count=len(scoped_names),
            total_bytes=sum(i.file_size for i in scoped),
            has_scripts=has_scripts,
            warnings=warnings,
            exists=(skill_dir(slug) / SKILL_FILENAME).is_file(),
            skill_path=root,
            skill_candidates=candidates,
            ignored_files=len(infos) - len(scoped),
        )
    return preview, meta


def import_zip(
    data: bytes,
    *,
    slug_override: str | None = None,
    overwrite: bool = False,
    overrides: dict | None = None,
    skill_path: str | None = None,
) -> PackagePreview:
    """把 zip 导入为技能。返回最终生效的预览。

    ``overrides`` 是管理员在确认框里填的值（描述 / 名称 / 系统提示词等），
    空白项会被忽略、沿用包里的值。
    """
    preview, meta = inspect_zip(data, overrides=overrides, skill_path=skill_path)
    try:
        slug = normalize_slug(slug_override) if slug_override else preview.slug
    except SkillWriteError as exc:
        raise PackageError(str(exc)) from exc

    if slug in HIDDEN_SLUGS:
        raise PackageError(
            f"「{slug}」是平台保留目录名（预置但未接入广场），不能导入"
        )

    target = skill_dir(slug)
    if (target / SKILL_FILENAME).is_file() and not overwrite:
        raise PackageError(f"技能 {slug} 已存在；确认要覆盖请显式传 overwrite")

    # 先解到临时目录，全部校验通过后再整体搬过去。
    # 直接往 skills/ 下解的话，中途失败会留下半个技能目录，
    # 而 load_skill_from_dir 遇到坏包只会跳过 —— 用户看到技能凭空消失。
    root = preview.skill_path
    staging = skills_root() / f".import-{slug}"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
        with zf:
            scoped = _scope_infos(_iter_infos(zf), root)
            prefix = len(root) + 1 if root else 0
            # 跨条目共享同一份预算，且按**实际**解压量扣 —— 见 _read_entry
            budget = [0]
            for info in scoped:
                # 剥掉技能目录前缀，让内容直接落在 <slug>/ 下
                rel = _normalize_entry(info.filename)[prefix:]
                if not rel:
                    continue
                dest = (staging / rel).resolve()
                if staging.resolve() not in dest.parents and dest != staging.resolve():
                    raise PackageError(f"非法解压路径：{info.filename}")
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(_read_entry(zf, info, budget))

        if not (staging / SKILL_FILENAME).is_file():
            raise PackageError(f"解压后找不到 {SKILL_FILENAME}")

        # **SKILL.md 一个字节都不改。**
        #
        # 这是这次修复的核心。早先这里把 frontmatter 重新序列化成 JSON 落盘，
        # 于是 ppt-master 的 `scripts/attribution_guard.py` 逐字符正则全部落空、
        # 退出码 78，技能在自己的完整性闸门上当场自我中止 —— 而导入流程
        # 报的是「成功」。凡是第三方技能拿文本比对自己分发的，都会被这类
        # 「规范化」打坏，而且坏得没有任何征兆。
        #
        # 平台需要的字段改写到旁挂文件 `agentflow.json`，加载时合并（旁挂优先）。
        # 只放**导入时定下来的那几项**，不复制整份 frontmatter —— 复制会让
        # 以后改 SKILL.md 的描述失效（旁挂优先），现场看着像「改了没反应」。
        sidecar: dict = {
            # id 必须与目录名一致，否则 get_skill 要走兜底全表扫描。
            "id": slug,
            # authorId **强制**覆盖：广场走 curated_only 过滤，只认
            # platform-preset。这里原先写的是 "platform-admin"，于是通过技能包
            # 导入的技能**从来不会出现在广场上** —— 而且不报错，只是不见了。
            "authorId": PLATFORM_AUTHOR_ID,
        }
        for key in ("name", "description", "systemPrompt"):
            value = meta.get(key)
            if isinstance(value, str) and value.strip():
                sidecar[key] = value
        sidecar.setdefault("authorName", "平台预置")
        sidecar.setdefault("visibility", "public")
        sidecar.setdefault("status", "published")

        # 同样走 bytes：write_text 在 Windows 上会写成 CRLF，让旁挂文件也
        # 变成平台相关的东西（不该发生的事，就别开这个头）。
        (staging / SIDECAR_FILENAME).write_bytes(
            (json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        )

        if target.exists():
            shutil.rmtree(target)
        shutil.move(str(staging), str(target))
    except Exception:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        raise

    invalidate_cache()
    logger.info(
        "技能包已导入 slug=%s 文件数=%d 跳过=%d",
        slug,
        preview.file_count,
        preview.ignored_files,
    )
    return replace(
        preview,
        slug=slug,
        # 用旁挂里那份（若管理员没填 name，则沿用包里的 SKILL.md）
        name=str(sidecar.get("name") or meta.get("name") or slug),
        description=str(sidecar.get("description") or meta.get("description") or ""),
        exists=True,
    )
