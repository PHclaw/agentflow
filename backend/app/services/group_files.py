"""群聊文件存储。

为什么单独建一层，而不是复用 Agent 工作区
------------------------------------------
用户上传文件时，**还不知道会由哪个成员接手**——路由发生在发送消息那一刻。
所以文件必须先落在「群」这一级，等选中了 agent 再复制进它的工作区。

目录结构::

    uploads/group_files/{group_id}/{stored_name}

``stored_name`` 是落盘用的安全名（净化过、冲突时加序号），
消息里另外记一份用户看到的原始文件名——两者分开，改名不动作业系统上的文件。

安全边界
--------
- 所有入口都要 ``ensure_group_dir`` 校验群归属，杜绝跨群访问
- 扩展名走白名单，不靠 MIME（浏览器上报的 Content-Type 不可信）
- 落盘名去掉路径分隔符与控制字符，且用 ``O_CREAT|O_EXCL`` 原子创建，
  并发上传同名文件不会互相覆盖
"""
import mimetypes
import os
import re
import shutil
import uuid
from pathlib import Path
from typing import Any, Iterable

from app.core.config import settings

#: 单个文件上限。与 Agent 工作区上传保持一致，避免用户在两处遇到不同限制。
MAX_FILE_BYTES = 10 * 1024 * 1024

#: 一条消息最多携带几个文件
MAX_FILES_PER_MESSAGE = 5

#: 单个群占用的总容量上限，防止一个群把磁盘写满
MAX_GROUP_BYTES = 500 * 1024 * 1024

#: 扩展名白名单（正向列举）。
#: 刻意不含 exe/dll/bat/sh/ps1：这些文件在 PiAgent 于宿主机执行时风险过高，
#: 而群聊并不需要分发可执行程序。
ALLOWED_EXTENSIONS = frozenset({
    # 文档
    ".pdf", ".doc", ".docx", ".txt", ".md", ".rtf",
    ".ppt", ".pptx", ".xls", ".xlsx", ".csv", ".tsv",
    # 图片
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg",
    # 数据与配置
    ".json", ".yaml", ".yml", ".xml", ".toml", ".ini",
    # 代码（PiAgent 的工作场景需要）
    ".py", ".js", ".ts", ".tsx", ".jsx", ".sql", ".html", ".css",
    # 压缩
    ".zip",
})

#: 图片类扩展名，前端据此决定是否渲染缩略图
IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"})


class GroupFileError(ValueError):
    """文件相关的可预期错误，路由层转成 4xx。"""


def uploads_root() -> Path:
    root = Path(settings.UPLOAD_DIR or "./uploads")
    if not root.is_absolute():
        root = Path.cwd() / root
    return root


def group_dir(group_id: str) -> Path:
    """群的存储目录。group_id 由服务端生成（uuid），不是用户输入，
    但仍然做一次净化，避免有人拿构造的 id 越权。"""
    safe = re.sub(r"[^A-Za-z0-9._-]", "", group_id or "")
    if not safe:
        raise GroupFileError("群标识非法")
    return uploads_root() / "group_files" / safe


def ensure_group_dir(group_id: str) -> Path:
    d = group_dir(group_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def sanitize_name(raw: str) -> str:
    """把用户给的文件名净化成安全的落盘名。

    只取 basename（挡掉 ``../``）、去掉控制字符与路径分隔符、限长。
    """
    name = Path(raw or "").name.strip() or "upload.bin"
    name = re.sub(r'[\x00-\x1f<>:"/\\|?*]', "_", name)
    return name[:120] or "upload.bin"


def validate_extension(name: str) -> str:
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise GroupFileError(
            f"不支持的文件类型：{ext or '（无扩展名）'}。"
            "支持文档、表格、图片、数据、代码与 zip"
        )
    return ext


def classify(name: str) -> str:
    """给前端一个粗略分类，用于选图标 / 决定是否预览。"""
    ext = Path(name).suffix.lower()
    if ext in IMAGE_EXTENSIONS:
        return "image"
    if ext in {".xls", ".xlsx", ".csv", ".tsv"}:
        return "sheet"
    if ext in {".ppt", ".pptx"}:
        return "slide"
    if ext == ".pdf":
        return "pdf"
    if ext in {".zip"}:
        return "archive"
    if ext in {".py", ".js", ".ts", ".tsx", ".jsx", ".sql", ".html", ".css"}:
        return "code"
    return "doc"


def group_usage(group_id: str) -> int:
    d = group_dir(group_id)
    if not d.exists():
        return 0
    total = 0
    for p in d.iterdir():
        if p.is_file():
            try:
                total += p.stat().st_size
            except OSError:
                continue
    return total


def save_bytes(group_id: str, raw_name: str, content: bytes) -> dict[str, Any]:
    """把上传内容落到群目录，返回给前端和消息 meta 用的描述对象。"""
    if not content:
        raise GroupFileError("文件内容为空")
    if len(content) > MAX_FILE_BYTES:
        raise GroupFileError(
            f"{sanitize_name(raw_name)} 超过 {MAX_FILE_BYTES // (1024 * 1024)}MB 上限"
        )

    safe_name = sanitize_name(raw_name)
    validate_extension(safe_name)

    used = group_usage(group_id)
    if used + len(content) > MAX_GROUP_BYTES:
        raise GroupFileError(
            f"这个群的文件总量已达上限（{MAX_GROUP_BYTES // (1024 * 1024)}MB），"
            "请先清理旧文件"
        )

    d = ensure_group_dir(group_id)
    stem, suffix = Path(safe_name).stem, Path(safe_name).suffix

    # 同名冲突时加序号。用 O_EXCL 原子创建：并发上传同名文件时，
    # 抢输的一方会拿到 FileExistsError 并自动换下一个序号，不会互相覆盖。
    for i in range(0, 200):
        candidate = safe_name if i == 0 else f"{stem}({i}){suffix}"
        target = d / candidate
        try:
            fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        except FileExistsError:
            continue
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(content)
        except Exception:
            # 写了一半就失败：把残缺文件删掉，别留个 0 字节的坑
            target.unlink(missing_ok=True)
            raise
        return describe(group_id, target.name, original_name=raw_name)

    raise GroupFileError("同名文件过多，请改名后重试")


def describe(group_id: str, stored_name: str, *, original_name: str | None = None) -> dict[str, Any]:
    """生成文件描述对象（落库到消息 meta 的就是这个结构）。"""
    path = group_dir(group_id) / stored_name
    size = 0
    try:
        size = path.stat().st_size
    except OSError:
        pass
    ext = Path(stored_name).suffix.lower()
    mime = mimetypes.guess_type(stored_name)[0] or "application/octet-stream"
    return {
        "name": original_name or stored_name,
        "stored_name": stored_name,
        "size": size,
        "ext": ext,
        "kind": classify(stored_name),
        "mime": mime,
        "url": f"/api/v1/groups/{group_id}/files/{stored_name}",
    }


def resolve_file(group_id: str, stored_name: str) -> Path:
    """把消息里记的文件名解析成磁盘路径，并挡掉路径穿越。"""
    d = group_dir(group_id).resolve()
    target = (d / Path(stored_name).name).resolve()
    if d not in target.parents and target != d:
        raise GroupFileError("文件路径非法")
    if not target.is_file():
        raise GroupFileError("文件不存在或已被清理")
    return target


def check_owned_by_group(group_id: str, stored_names: Iterable[str]) -> list[str]:
    """校验待引用文件都真实存在于本群，返回存在的那些。

    发消息时用它挡掉「构造一个别的群的文件名塞进 meta」这种越权引用。
    """
    ok: list[str] = []
    for name in stored_names:
        try:
            resolve_file(group_id, name)
        except GroupFileError:
            continue
        ok.append(Path(name).name)
    return ok


def copy_to_workspace(group_id: str, stored_names: Iterable[str], workspace: Path) -> list[str]:
    """把群文件复制进某个 agent 的工作区。

    PiAgent 的 cwd 是自己的工作区，读不到群目录；执行前必须搬过去一份。
    返回实际复制成功的文件名。
    """
    workspace.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for name in stored_names:
        try:
            src = resolve_file(group_id, name)
        except GroupFileError:
            continue
        dst = workspace / src.name
        # 工作区里已有同名文件时不覆盖——那可能是上一轮生成的产物
        if dst.exists():
            stem, suffix = dst.stem, dst.suffix
            for i in range(1, 100):
                candidate = workspace / f"{stem}({i}){suffix}"
                if not candidate.exists():
                    dst = candidate
                    break
        try:
            shutil.copy2(src, dst)
        except OSError:
            continue
        copied.append(dst.name)
    return copied


def purge_group_dir(group_id: str) -> None:
    """删群时清掉它的文件目录。

    不清理的话磁盘上会留下再也没人访问的孤儿文件——
    数据库记录没了，用户也没有入口去删，只能靠运维手工翻目录。
    """
    import shutil

    try:
        d = group_dir(group_id)
    except GroupFileError:
        return
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)


def new_batch_id() -> str:
    return uuid.uuid4().hex


def summarize_for_prompt(files: Iterable[dict[str, Any]]) -> str:
    """附件清单，拼进发给 agent 的任务描述。

    带附件时调用方会自动切到 PiAgent 执行（只有它能真正读文件内容），
    所以这里可以直接要求「读文件后直接给结果」，不需要教模型怎么解释限制。
    """
    items = list(files or [])
    if not items:
        return ""
    names = "、".join(
        f"{f.get('name')}（{max(1, int((f.get('size') or 0) / 1024))} KB）" for f in items
    )
    return (
        f"附件：{names}\n"
        "文件已就位，可直接读取。读完直接给结论，不要复述文件名，"
        "也不要让用户重新提供文件。"
    )
