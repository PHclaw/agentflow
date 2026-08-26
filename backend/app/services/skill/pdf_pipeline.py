"""PDF Skill：对已上传 PDF 做白名单操作（合并 / 拆分 / 抽文本 / 表单探测 / 水印）。"""
from __future__ import annotations

import io
import json
import re
import uuid
from pathlib import Path
from typing import Any

from app.logging_setup import get_logger

logger = get_logger("pdf")

from app.core.paths import generated_root

GENERATED_DIR = generated_root()
_WM_FONT: str | None = None
_CJK_FONT_CANDIDATES = (
    Path(r"C:\Windows\Fonts\msyh.ttc"),
    Path(r"C:\Windows\Fonts\msyhbd.ttc"),
    Path(r"C:\Windows\Fonts\simhei.ttf"),
    Path(r"C:\Windows\Fonts\simsun.ttc"),
    Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
    Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
)


def _watermark_font(text: str) -> str:
    """Helvetica 不含中文；有 CJK 时注册系统字体。"""
    global _WM_FONT
    if not re.search(r"[\u4e00-\u9fff]", text or ""):
        return "Helvetica-Bold"
    if _WM_FONT:
        return _WM_FONT
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    for path in _CJK_FONT_CANDIDATES:
        if not path.is_file():
            continue
        try:
            kwargs = {"subfontIndex": 0} if path.suffix.lower() == ".ttc" else {}
            pdfmetrics.registerFont(TTFont("CjkWm", str(path), **kwargs))
            _WM_FONT = "CjkWm"
            return _WM_FONT
        except Exception as exc:  # noqa: BLE001
            logger.warning("register watermark font fail path=%s err=%s", path, exc)
    _WM_FONT = "Helvetica-Bold"
    return _WM_FONT


def is_pdf_skill(agent) -> bool:
    wf = getattr(agent, "workflow", None) or {}
    if isinstance(wf, dict) and wf.get("kind") == "pdf":
        return True
    if (getattr(agent, "id", None) or "") == "pdf":
        return True
    specialty = getattr(agent, "specialty", None) or ""
    name = getattr(agent, "name", None) or ""
    return specialty == "PDF处理" or "PDF" in name


def _pdf_files(uploaded: list[dict] | None) -> list[dict]:
    out: list[dict] = []
    for f in uploaded or []:
        name = str(f.get("name") or "")
        path = str(f.get("path") or "")
        if name.lower().endswith(".pdf") and path and Path(path).is_file():
            out.append(f)
    return out


def _parseable_files(uploaded: list[dict] | None) -> list[dict]:
    from app.services.skill.doc_parser import PARSEABLE_SUFFIX

    out: list[dict] = []
    for f in uploaded or []:
        name = str(f.get("name") or "")
        path = str(f.get("path") or "")
        if Path(name).suffix.lower() in PARSEABLE_SUFFIX and path and Path(path).is_file():
            out.append(f)
    return out


def _is_followup_request(text: str) -> bool:
    current = prefer_current_user_text(text)
    if any(k in current for k in ("上文", "上面", "上述", "刚才", "刚刚", "之前的", "先前")):
        return True
    return "## 先前对话" in (text or "")


def prefer_current_user_text(text: str) -> str:
    """多轮会话会把历史拼进 input；意图只看「当前用户」段。"""
    t = text or ""
    marker = "## 当前用户"
    if marker in t:
        return t.split(marker, 1)[-1].strip()
    return t.strip()


_CONVERT_VERB_RE = re.compile(
    r"(转化|转换|转为|转成|转换成?|导出为?|保存为?|变成|化为|做成|改成)"
)
# 中文「doc文件」里 doc 后不是 ASCII 词边界，不能用 \b
_DOCX_TOKEN_RE = re.compile(
    r"docx|\.docx|(?<![a-z])word(?:文档|文件|格式)?(?![a-z])",
    re.I,
)
_DOC_TOKEN_RE = re.compile(
    r"\.doc(?!x)|doc(?:文件|格式|文档)(?![a-z])|(?<![a-z.])doc(?![a-z])",
    re.I,
)
_XLSX_TOKEN_RE = re.compile(r"xlsx|\.xlsx|(?<![a-z])excel(?![a-z])|\.csv|csv文件", re.I)
_MD_TOKEN_RE = re.compile(r"markdown|\.md|(?<![a-z])md(?:文件|格式)?(?![a-z])", re.I)
_IMG_TOKEN_RE = re.compile(r"图片|图像|\.png|\.jpe?g|png文件", re.I)


def _compact_intent_text(text: str) -> str:
    return re.sub(r"\s+", "", prefer_current_user_text(text).lower())


def _route_format_intent(text: str) -> str | None:
    """有「转化/转成/导出…」+ 目标格式时，直接走对应工具，不依赖模型猜。"""
    c = _compact_intent_text(text)
    converting = bool(_CONVERT_VERB_RE.search(c)) or c in {
        "docx",
        "doc",
        "word",
        "doc文件",
        "docx文件",
        "word文件",
    }
    if not converting:
        return None
    if _DOCX_TOKEN_RE.search(c):
        return "to_docx"
    if _DOC_TOKEN_RE.search(c):
        return "to_doc"
    if _XLSX_TOKEN_RE.search(c):
        return "extract_tables"
    if _MD_TOKEN_RE.search(c):
        return "parse"
    if _IMG_TOKEN_RE.search(c):
        return "extract_images"
    return None


def route_intent(text: str) -> str:
    t = prefer_current_user_text(text).lower()
    fmt_intent = _route_format_intent(text)
    if fmt_intent:
        return fmt_intent
    if any(
        k in t
        for k in (
            "水印",
            "watermark",
            "盖章文字",
            "机密标记",
        )
    ):
        return "watermark"
    if any(k in t for k in ("合并", "merge", "合成", "拼成", "合成一个")):
        return "merge"
    if any(
        k in t
        for k in (
            "拆分",
            "分割",
            "切分",
            "split",
            "按页",
            "拆开",
            "单独抽",
            "抽出第",
            "只要第",
        )
    ) or re.search(r"第\s*[一二三四五六七八九十\d]+\s*页", t):
        return "split"
    if any(
        k in t
        for k in (
            "表单结构",
            "字段探测",
            "探测表单",
            "表单探测",
            "可填字段",
            "form structure",
            "form field",
            "extract_form",
            "字段坐标",
            "探测字段",
        )
    ):
        return "form_probe"
    if any(
        k in t
        for k in (
            "表格",
            "抽表",
            "extract table",
            "extract_tables",
            "导出csv",
            "导出 excel",
            "导出excel",
            "导出xlsx",
            "to csv",
            "to excel",
        )
    ):
        return "extract_tables"
    if any(
        k in t
        for k in (
            "提取图片",
            "提取图像",
            "导出图片",
            "导出图像",
            "内嵌图",
            "抽图",
            "提取附件",
            "提取文件",
            "图片提取",
            "图像提取",
        )
    ) or (
        any(k in t for k in ("图片", "图像", "插图", "附图"))
        and any(k in t for k in ("提取", "导出", "抽出", "抽取", "拿出"))
    ):
        return "extract_images"
    if any(
        k in t
        for k in (
            "markdown",
            "转md",
            "转成md",
            "转成 markdown",
            "解析成",
            "文档解析",
            "解析文档",
            "转 markdown",
            "转成markdown",
        )
    ):
        return "parse"
    if "解析" in t and "表单" not in t:
        return "parse"
    if any(
        k in t
        for k in (
            "提取文字",
            "抽取文字",
            "extract text",
            "ocr",
        )
    ):
        return "extract"
    # 问文档写了什么 / 默认：走文档解析 JAR，再交给模型回答
    return "parse"


def _public_url(filename: str) -> str:
    return f"/static/generated/{filename}"


def _safe_name(name: str, *, default: str, suffix: str) -> str:
    fname = name or default
    fname = re.sub(r"[^\w.\-一-龥]+", "_", fname)
    if not fname.lower().endswith(suffix):
        fname += suffix
    return fname


_CN_ORD = {
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}


def _ordinal_rank(token: str) -> int | None:
    t = (token or "").strip()
    if not t:
        return None
    if t in {"最后", "最后一个", "最后一", "末尾", "末", "最后面"}:
        return 10_000
    if t in {"首先", "第一", "第一个", "最前", "最前面"}:
        return 1
    m = re.match(r"^第([一二三四五六七八九十]+)个?$", t)
    if m:
        raw = m.group(1)
        if raw in _CN_ORD:
            return _CN_ORD[raw]
        if raw == "十":
            return 10
    m = re.match(r"^第(\d+)个?$", t)
    if m:
        return int(m.group(1))
    m = re.match(r"^(\d+)$", t)
    if m:
        return int(m.group(1))
    return None


def _match_uploaded_pdf(token: str, files: list[dict]) -> dict | None:
    raw = (token or "").strip().strip("「」\"'【】[]()（）")
    if not raw:
        return None
    key = raw.lower()
    stem_key = Path(raw).stem.lower()
    exact: list[dict] = []
    stems: list[dict] = []
    for f in files:
        name = str(f.get("name") or "")
        nlow = name.lower()
        if nlow == key or nlow == f"{stem_key}.pdf":
            exact.append(f)
        elif Path(name).stem.lower() == stem_key:
            stems.append(f)
    if len(exact) == 1:
        return exact[0]
    if len(stems) == 1:
        return stems[0]
    return None


def _mentions_in_text(text: str, files: list[dict]) -> list[dict]:
    """按用户原文出现顺序收集已上传 PDF（长文件名优先，避免 1 误伤 10.pdf）。"""
    labels: list[tuple[str, dict]] = []
    seen_label = set()
    for f in files:
        name = str(f.get("name") or "")
        stem = Path(name).stem
        for lab in (name, f"{stem}.pdf", stem):
            k = lab.lower()
            if k in seen_label:
                continue
            seen_label.add(k)
            labels.append((lab, f))
    labels.sort(key=lambda x: len(x[0]), reverse=True)

    hits: list[tuple[int, dict]] = []
    occupied: list[tuple[int, int]] = []
    for lab, f in labels:
        if len(lab) <= 1 and not lab.lower().endswith(".pdf"):
            # 单字符 stem 必须紧贴「为/是/第/.pdf」才算点名，避免误伤
            pat = re.compile(re.escape(lab) + r"(?=\.pdf|为|是|作为|当)", re.I)
        else:
            pat = re.compile(re.escape(lab), re.I)
        for m in pat.finditer(text or ""):
            span = (m.start(), m.end())
            if any(span[0] < b and span[1] > a for a, b in occupied):
                continue
            occupied.append(span)
            hits.append((m.start(), f))
    hits.sort(key=lambda x: x[0])
    ordered: list[dict] = []
    seen_id = set()
    for _, f in hits:
        ident = id(f)
        if ident in seen_id:
            continue
        seen_id.add(ident)
        ordered.append(f)
    return ordered


def order_pdfs_for_merge(files: list[dict], user_text: str) -> list[dict]:
    """按当前用户指定的顺序重排；未点名的文件保持原相对顺序接到后面。"""
    if len(files) < 2:
        return list(files)
    current = prefer_current_user_text(user_text)
    slots: dict[int, dict] = {}

    name_then_ord = re.compile(
        r"(?P<name>[^\s，,。；;]+?\.pdf)\s*(?:为|是|作为|当)?\s*"
        r"(?P<ord>第[一二三四五六七八九十\d]+个?|最后(?:一个)?|末尾|首先)",
        re.I,
    )
    ord_then_name = re.compile(
        r"(?P<ord>第[一二三四五六七八九十\d]+个?|首先|第一|最后(?:一个)?|末尾)\s*"
        r"(?:为|是|：|:)?\s*(?P<name>[^\s，,。；;]+?\.pdf)",
        re.I,
    )
    for rx in (name_then_ord, ord_then_name):
        for m in rx.finditer(current):
            rank = _ordinal_rank(m.group("ord"))
            hit = _match_uploaded_pdf(m.group("name"), files)
            if rank is None or hit is None:
                continue
            slots.setdefault(rank, hit)

    if slots:
        used = {id(f) for f in slots.values()}
        ordered = [slots[k] for k in sorted(slots)]
        for f in files:
            if id(f) not in used:
                ordered.append(f)
        if len(ordered) == len(files):
            return ordered

    mentioned = _mentions_in_text(current, files)
    if len(mentioned) >= 2:
        used = {id(f) for f in mentioned}
        return mentioned + [f for f in files if id(f) not in used]
    return list(files)


def merge_pdfs(files: list[dict], *, out_name: str | None = None) -> dict[str, Any]:
    from pypdf import PdfReader, PdfWriter

    if len(files) < 2:
        return {
            "intent": "merge",
            "exitCode": 1,
            "note": "合并至少需要 2 个已上传的 PDF。",
            "stdout": "",
            "stderr": "",
        }
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    writer = PdfWriter()
    page_total = 0
    names: list[str] = []
    for f in files:
        path = Path(str(f["path"]))
        reader = PdfReader(str(path))
        for page in reader.pages:
            writer.add_page(page)
            page_total += 1
        names.append(str(f.get("name") or path.name))

    fname = _safe_name(out_name or f"merged-{uuid.uuid4().hex[:10]}.pdf", default="merged.pdf", suffix=".pdf")
    out_path = GENERATED_DIR / fname
    with out_path.open("wb") as fp:
        writer.write(fp)

    url = _public_url(fname)
    stdout = (
        f"merged={fname}\n"
        f"pages={page_total}\n"
        f"sources={', '.join(names)}\n"
        f"downloadUrl={url}\n"
        f"path={out_path.resolve()}"
    )
    logger.info("pdf merge ok files=%s pages=%s out=%s", len(files), page_total, fname)
    return {
        "intent": "merge",
        "script": "pypdf.PdfWriter",
        "exitCode": 0,
        "stdout": stdout,
        "stderr": "",
        "note": f"已按此顺序合并：{' → '.join(names)}",
        "downloadUrl": url,
        "downloadName": fname,
        "pageCount": page_total,
        "sources": names,
    }


def extract_text_bundle(files: list[dict]) -> dict[str, Any]:
    from pypdf import PdfReader

    if not files:
        return {
            "intent": "extract",
            "exitCode": 1,
            "note": "未找到已上传的 PDF。",
            "stdout": "",
            "stderr": "",
        }
    parts: list[str] = []
    for f in files:
        path = Path(str(f["path"]))
        reader = PdfReader(str(path))
        parts.append(f"# {f.get('name') or path.name} （{len(reader.pages)} 页）")
        for i, page in enumerate(reader.pages[:12]):
            text = (page.extract_text() or "").strip()
            parts.append(f"## 第 {i + 1} 页\n{text or '（无文本，可能为扫描件）'}")
    stdout = "\n\n".join(parts)[:120_000]
    return {
        "intent": "extract",
        "script": "pypdf.extract_text",
        "exitCode": 0,
        "stdout": stdout,
        "stderr": "",
        "note": "已抽取上传 PDF 文本",
    }


def _parse_page_numbers(text: str, page_count: int) -> list[int]:
    """从「第二页 / 第2页 / 第2-4页」解析 1-based 页码。空列表表示整本按页拆。"""
    t = prefer_current_user_text(text)
    pages: list[int] = []

    def _num(token: str) -> int | None:
        token = (token or "").strip()
        if token.isdigit():
            return int(token)
        return _CN_ORD.get(token)

    for a, b in re.findall(
        r"第\s*([一二三四五六七八九十\d]+)\s*[-~到至]\s*([一二三四五六七八九十\d]+)\s*页",
        t,
    ):
        lo, hi = _num(a), _num(b)
        if lo and hi:
            for i in range(min(lo, hi), max(lo, hi) + 1):
                pages.append(i)
    for raw in re.findall(r"第\s*([一二三四五六七八九十\d]+)\s*页", t):
        n = _num(raw)
        if n:
            pages.append(n)
    for raw in re.findall(r"page\s*(\d+)", t, re.I):
        pages.append(int(raw))
    out: list[int] = []
    seen: set[int] = set()
    for p in pages:
        if 1 <= p <= page_count and p not in seen:
            seen.add(p)
            out.append(p)
    return out


def split_first_pdf(files: list[dict], user_text: str = "") -> dict[str, Any]:
    from pypdf import PdfReader, PdfWriter

    if not files:
        return {
            "intent": "split",
            "exitCode": 1,
            "note": "未找到已上传的 PDF。",
            "stdout": "",
            "stderr": "",
        }
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    src = files[0]
    path = Path(str(src["path"]))
    reader = PdfReader(str(path))
    total = len(reader.pages)
    stem = Path(str(src.get("name") or path.name)).stem
    wanted = _parse_page_numbers(user_text, total)
    urls: list[str] = []
    if wanted:
        writer = PdfWriter()
        for p in wanted:
            writer.add_page(reader.pages[p - 1])
        label = "-".join(str(p) for p in wanted[:8])
        fname = f"{stem}-p{label}-{uuid.uuid4().hex[:6]}.pdf"
        out = GENERATED_DIR / fname
        with out.open("wb") as fp:
            writer.write(fp)
        url = _public_url(fname)
        urls = [url]
        note = f"已抽出第 {','.join(str(p) for p in wanted)} 页，共 {len(wanted)} 页"
        stdout = f"pages={wanted}\ndownloadUrl={url}"
        return {
            "intent": "split",
            "script": "pypdf.extract_pages",
            "exitCode": 0,
            "stdout": stdout,
            "stderr": "",
            "note": note,
            "downloadUrl": url,
            "downloadName": fname,
            "downloadUrls": urls,
        }
    for i, page in enumerate(reader.pages[:30]):
        writer = PdfWriter()
        writer.add_page(page)
        fname = f"{stem}-p{i + 1}-{uuid.uuid4().hex[:6]}.pdf"
        out = GENERATED_DIR / fname
        with out.open("wb") as fp:
            writer.write(fp)
        urls.append(_public_url(fname))
    stdout = "\n".join(f"page={i + 1} downloadUrl={u}" for i, u in enumerate(urls))
    return {
        "intent": "split",
        "script": "pypdf.split",
        "exitCode": 0,
        "stdout": stdout,
        "stderr": "",
        "note": f"已拆分前 {len(urls)} 页（最多 30 页）",
        "downloadUrl": urls[0] if urls else None,
        "downloadName": urls[0].rsplit("/", 1)[-1] if urls else None,
        "downloadUrls": urls,
    }


def _fillable_fields(pdf_path: Path) -> list[dict[str, Any]]:
    """简化版可填字段探测（不依赖 scripts 路径）。"""
    from pypdf import PdfReader
    from pypdf.generic import ArrayObject

    reader = PdfReader(str(pdf_path))
    fields = reader.get_fields() or {}
    if not fields:
        return []

    # page → annot mapping for rect/page
    page_annots: dict[int, list] = {}
    for page_index, page in enumerate(reader.pages):
        annots = page.get("/Annots")
        if not annots:
            continue
        try:
            annots = annots.get_object()
        except Exception:  # noqa: BLE001
            pass
        if not isinstance(annots, (list, ArrayObject)):
            continue
        for annot_ref in annots:
            try:
                annot = annot_ref.get_object()
            except Exception:  # noqa: BLE001
                continue
            page_annots.setdefault(id(annot), []).append(page_index)

    out: list[dict[str, Any]] = []
    for name, info in fields.items():
        if not isinstance(info, dict):
            continue
        field_type = str(info.get("/FT") or info.get("ft") or "")
        kids = info.get("/Kids")
        rect = None
        page_num = None
        try:
            if kids:
                kid0 = kids[0].get_object() if hasattr(kids[0], "get_object") else kids[0]
                rect = list(kid0.get("/Rect") or [])
                for page_index, page in enumerate(reader.pages):
                    annots = page.get("/Annots") or []
                    try:
                        annots = annots.get_object() if hasattr(annots, "get_object") else annots
                    except Exception:  # noqa: BLE001
                        continue
                    for a in annots or []:
                        try:
                            obj = a.get_object() if hasattr(a, "get_object") else a
                        except Exception:  # noqa: BLE001
                            continue
                        if obj is kid0 or obj.get("/T") == name:
                            page_num = page_index + 1
                            rect = list(obj.get("/Rect") or rect or [])
                            break
                    if page_num:
                        break
            else:
                rect = list(info.get("/Rect") or []) if info.get("/Rect") else None
        except Exception:  # noqa: BLE001
            rect = None

        item: dict[str, Any] = {
            "field_id": str(name),
            "type": {
                "/Tx": "text",
                "/Btn": "button",
                "/Ch": "choice",
                "/Sig": "signature",
            }.get(field_type, field_type or "unknown"),
            "value": str(info.get("/V") or "") if info.get("/V") is not None else "",
        }
        if page_num:
            item["page"] = page_num
        if rect:
            item["rect"] = [float(x) for x in rect[:4]]
        out.append(item)
    return out


def _visual_structure(pdf_path: Path, *, max_pages: int = 8) -> dict[str, Any]:
    import pdfplumber

    structure: dict[str, Any] = {
        "pages": [],
        "labels": [],
        "lines": [],
        "checkboxes": [],
        "row_boundaries": [],
    }
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page_num, page in enumerate(pdf.pages[:max_pages], 1):
            structure["pages"].append(
                {
                    "page_number": page_num,
                    "width": float(page.width),
                    "height": float(page.height),
                }
            )
            words = page.extract_words() or []
            # 控制体积：每页最多 400 个 label
            for word in words[:400]:
                structure["labels"].append(
                    {
                        "page": page_num,
                        "text": word["text"],
                        "x0": round(float(word["x0"]), 1),
                        "top": round(float(word["top"]), 1),
                        "x1": round(float(word["x1"]), 1),
                        "bottom": round(float(word["bottom"]), 1),
                    }
                )
            for line in page.lines or []:
                if abs(float(line["x1"]) - float(line["x0"])) > page.width * 0.5:
                    structure["lines"].append(
                        {
                            "page": page_num,
                            "y": round(float(line["top"]), 1),
                            "x0": round(float(line["x0"]), 1),
                            "x1": round(float(line["x1"]), 1),
                        }
                    )
            for rect in page.rects or []:
                width = float(rect["x1"]) - float(rect["x0"])
                height = float(rect["bottom"]) - float(rect["top"])
                if 5 <= width <= 15 and 5 <= height <= 15 and abs(width - height) < 2:
                    structure["checkboxes"].append(
                        {
                            "page": page_num,
                            "x0": round(float(rect["x0"]), 1),
                            "top": round(float(rect["top"]), 1),
                            "x1": round(float(rect["x1"]), 1),
                            "bottom": round(float(rect["bottom"]), 1),
                            "center_x": round((float(rect["x0"]) + float(rect["x1"])) / 2, 1),
                            "center_y": round((float(rect["top"]) + float(rect["bottom"])) / 2, 1),
                        }
                    )

    lines_by_page: dict[int, list[float]] = {}
    for line in structure["lines"]:
        lines_by_page.setdefault(int(line["page"]), []).append(float(line["y"]))
    for page, y_coords in lines_by_page.items():
        ys = sorted(set(y_coords))
        for i in range(len(ys) - 1):
            structure["row_boundaries"].append(
                {"page": page, "top": ys[i], "bottom": ys[i + 1]}
            )
    return structure


def probe_form_structure(files: list[dict]) -> dict[str, Any]:
    if not files:
        return {
            "intent": "form_probe",
            "exitCode": 1,
            "note": "未找到已上传的 PDF。",
            "stdout": "",
            "stderr": "",
        }
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    src = files[0]
    path = Path(str(src["path"]))
    fillable = _fillable_fields(path)
    visual = _visual_structure(path)
    payload = {
        "source": str(src.get("name") or path.name),
        "fillable_fields": fillable,
        "fillable_count": len(fillable),
        "visual_structure": {
            "page_count": len(visual.get("pages") or []),
            "label_count": len(visual.get("labels") or []),
            "line_count": len(visual.get("lines") or []),
            "checkbox_count": len(visual.get("checkboxes") or []),
            "row_boundary_count": len(visual.get("row_boundaries") or []),
            "pages": visual.get("pages") or [],
            "labels": (visual.get("labels") or [])[:800],
            "lines": visual.get("lines") or [],
            "checkboxes": visual.get("checkboxes") or [],
            "row_boundaries": visual.get("row_boundaries") or [],
        },
        "mode": "fillable" if fillable else "non_fillable_visual",
    }
    fname = f"form-probe-{uuid.uuid4().hex[:10]}.json"
    out_path = GENERATED_DIR / fname
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    url = _public_url(fname)
    summary_lines = [
        f"source={payload['source']}",
        f"mode={payload['mode']}",
        f"fillable_count={payload['fillable_count']}",
        f"labels={payload['visual_structure']['label_count']}",
        f"lines={payload['visual_structure']['line_count']}",
        f"checkboxes={payload['visual_structure']['checkbox_count']}",
        f"downloadUrl={url}",
    ]
    if fillable:
        summary_lines.append("fillable_preview:")
        for item in fillable[:40]:
            summary_lines.append(
                f"  - id={item.get('field_id')} type={item.get('type')} page={item.get('page')} value={item.get('value')!r}"
            )
    else:
        labels = payload["visual_structure"]["labels"][:30]
        summary_lines.append("label_preview:")
        for lb in labels:
            summary_lines.append(f"  - p{lb['page']} {lb['text']!r} @({lb['x0']},{lb['top']})")

    return {
        "intent": "form_probe",
        "script": "pdfplumber+pypdf.form_probe",
        "exitCode": 0,
        "stdout": "\n".join(summary_lines),
        "stderr": "",
        "note": "已完成表单结构探测，JSON 可下载",
        "downloadUrl": url,
        "downloadName": fname,
        "fillableCount": payload["fillable_count"],
        "mode": payload["mode"],
    }


def _clean_watermark_value(val: str) -> str | None:
    text = (val or "").strip().strip("「」\"'【】[]")
    text = re.sub(r"^(文字|内容|内容为|为)\s*", "", text)
    text = re.split(r"[。；;\n]", text, maxsplit=1)[0].strip()
    text = text.strip("：:，, ")
    if not text:
        return None
    low = text.lower()
    if low in {"pdf", "watermark", "水印", "加上水印", "加水印"}:
        return None
    if re.fullmatch(r".+\.pdf", text, flags=re.I):
        return None
    return text[:80]


def _parse_watermark_text(user_text: str) -> str:
    t = prefer_current_user_text(user_text)
    patterns = [
        r"水印[文字内容]*[为是：:\s]+[「「\"'【\[](.+?)[」」\"'】\]]",
        r"加上?[文字]*水印\s*[「「\"'](.+?)[」」\"']",
        r"watermark\s*[:=]\s*[\"']?([^\n\"']+)",
        r"水印[：:]\s*([^\n，,。；;]+)",
        r"加上?水印\s*[：:]*\s+(.+)",
        r"水印(?:文字|内容)?\s*[为是]\s*(.+)",
        r"文字[为是：:]\s*([^\n，,。；;]+)",
    ]
    for pat in patterns:
        m = re.search(pat, t, flags=re.I)
        if m:
            val = _clean_watermark_value(m.group(1))
            if val:
                return val
    compact = re.sub(r"\s+", "", t)
    if "水印" in compact:
        rest = re.sub(r"^.*?(?:加上?水印|水印)", "", compact, count=1)
        rest = rest.strip("：:，,")
        val = _clean_watermark_value(rest)
        if val:
            return val
    return "CONFIDENTIAL"


def add_text_watermark(files: list[dict], *, text: str) -> dict[str, Any]:
    from pypdf import PdfReader, PdfWriter
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import Color

    if not files:
        return {
            "intent": "watermark",
            "exitCode": 1,
            "note": "未找到已上传的 PDF。",
            "stdout": "",
            "stderr": "",
        }
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    src = files[0]
    path = Path(str(src["path"]))
    reader = PdfReader(str(path))
    writer = PdfWriter()
    mark = (text or "CONFIDENTIAL").strip()[:80] or "CONFIDENTIAL"

    for page in reader.pages:
        box = page.mediabox
        width = float(box.width)
        height = float(box.height)
        packet = io.BytesIO()
        c = canvas.Canvas(packet, pagesize=(width, height))
        c.saveState()
        c.setFillColor(Color(0.55, 0.55, 0.55, alpha=0.28))
        c.setFont(_watermark_font(mark), max(28, min(width, height) * 0.08))
        c.translate(width / 2, height / 2)
        c.rotate(35)
        c.drawCentredString(0, 0, mark)
        c.restoreState()
        c.save()
        packet.seek(0)
        overlay = PdfReader(packet).pages[0]
        page.merge_page(overlay)
        writer.add_page(page)

    stem = Path(str(src.get("name") or path.name)).stem
    fname = _safe_name(f"{stem}-wm-{uuid.uuid4().hex[:8]}.pdf", default="watermarked.pdf", suffix=".pdf")
    out_path = GENERATED_DIR / fname
    with out_path.open("wb") as fp:
        writer.write(fp)
    url = _public_url(fname)
    stdout = (
        f"watermarkText={mark}\n"
        f"pages={len(reader.pages)}\n"
        f"source={src.get('name') or path.name}\n"
        f"downloadUrl={url}\n"
    )
    return {
        "intent": "watermark",
        "script": "reportlab+pypdf.watermark",
        "exitCode": 0,
        "stdout": stdout,
        "stderr": "",
        "note": f"已添加文字水印「{mark}」",
        "downloadUrl": url,
        "downloadName": fname,
        "watermarkText": mark,
        "pageCount": len(reader.pages),
    }


def _rows_to_gfm(rows: list[list[str]], *, max_rows: int = 12) -> str:
    if not rows:
        return ""
    width = max((len(r) for r in rows[:max_rows]), default=1)

    def pad(row: list[str]) -> list[str]:
        cells = [("" if c is None else str(c).replace("|", "\\|").replace("\n", " ").strip()) for c in row]
        if len(cells) < width:
            cells.extend([""] * (width - len(cells)))
        return cells[:width]

    header = pad(rows[0])
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    for row in rows[1:max_rows]:
        lines.append("| " + " | ".join(pad(row)) + " |")
    return "\n".join(lines)


def _clean_table_rows(table: list | None) -> list[list[str]]:
    rows: list[list[str]] = []
    for row in table or []:
        cells = [("" if c is None else str(c).replace("\n", " ").strip()) for c in row]
        if any(c for c in cells):
            rows.append(cells)
    return rows


def _tables_from_markdown(md: str) -> list[list[list[str]]]:
    tables: list[list[list[str]]] = []
    current: list[list[str]] = []
    for raw in (md or "").splitlines():
        line = raw.strip()
        if not line.startswith("|"):
            if current:
                tables.append(current)
                current = []
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if cells and all(re.fullmatch(r":?-{3,}:?", c or "") for c in cells):
            continue
        if any(c for c in cells):
            current.append(cells)
    if current:
        tables.append(current)
    return tables


def _write_table_files(
    tables: list[dict[str, Any]],
    *,
    stem: str,
) -> tuple[str, str, list[str]]:
    from openpyxl import Workbook

    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    uid = uuid.uuid4().hex[:8]
    wb = Workbook()
    default = wb.active
    wb.remove(default)
    used_names: set[str] = set()
    for i, item in enumerate(tables, 1):
        rows: list[list[str]] = item["rows"]
        sheet = f"p{item.get('page') or i}_t{item.get('index') or i}"
        sheet = re.sub(r"[\\/*?:\[\]]", "_", sheet)[:31] or f"t{i}"
        if sheet in used_names:
            sheet = f"t{i}"[:31]
        used_names.add(sheet)
        ws = wb.create_sheet(sheet)
        for row in rows:
            ws.append(row)
    xlsx_name = _safe_name(f"{stem}-tables-{uid}.xlsx", default="tables.xlsx", suffix=".xlsx")
    xlsx_path = GENERATED_DIR / xlsx_name
    wb.save(str(xlsx_path))
    xlsx_url = _public_url(xlsx_name)
    return xlsx_url, xlsx_name, [xlsx_url]


def extract_tables_bundle(files: list[dict]) -> dict[str, Any]:
    import pdfplumber

    if not files:
        return {
            "intent": "extract_tables",
            "exitCode": 1,
            "note": "未找到已上传的 PDF。",
            "stdout": "",
            "stderr": "",
        }
    src = files[0]
    path = Path(str(src["path"]))
    stem = Path(str(src.get("name") or path.name)).stem
    found: list[dict[str, Any]] = []
    if path.suffix.lower() == ".pdf":
        with pdfplumber.open(str(path)) as pdf:
            for page_num, page in enumerate(pdf.pages[:40], 1):
                for ti, table in enumerate(page.extract_tables() or [], 1):
                    rows = _clean_table_rows(table)
                    if rows:
                        found.append(
                            {"page": page_num, "index": ti, "rows": rows, "source": "pdfplumber"}
                        )

    if not found:
        # 扫描件/图片表：用文档解析 Markdown 里的表格兜底
        from app.services.skill.doc_parser import parse_uploaded

        parsed = parse_uploaded([src], intent="extract_tables")
        md = str(parsed.get("markdown") or parsed.get("stdout") or "")
        for i, rows in enumerate(_tables_from_markdown(md), 1):
            found.append({"page": None, "index": i, "rows": rows, "source": "markdown"})
        if not found:
            return {
                "intent": "extract_tables",
                "script": "pdfplumber.extract_tables",
                "exitCode": 1,
                "stdout": parsed.get("stdout") or "",
                "stderr": parsed.get("stderr") or "",
                "note": "未检测到表格。若是扫描件/图片表，可先说「解析成 markdown」再指定页码。",
                "downloadUrl": parsed.get("downloadUrl"),
                "downloadName": parsed.get("downloadName"),
            }

    xlsx_url, xlsx_name, urls = _write_table_files(found, stem=stem)
    preview_parts: list[str] = [f"tableCount={len(found)}", f"downloadUrl={xlsx_url}"]
    for item in found[:6]:
        loc = f"page={item.get('page')} index={item.get('index')} source={item.get('source')}"
        preview_parts.append(loc)
        preview_parts.append("markdownPreview:")
        preview_parts.append(_rows_to_gfm(item["rows"]))
        preview_parts.append("")
    return {
        "intent": "extract_tables",
        "script": "pdfplumber.extract_tables",
        "exitCode": 0,
        "stdout": "\n".join(preview_parts)[:12_000],
        "stderr": "",
        "note": f"已提取 {len(found)} 张表格，Excel 可下载",
        "downloadUrl": xlsx_url,
        "downloadName": xlsx_name,
        "downloadUrls": urls,
        "tableCount": len(found),
    }


def run_pdf_tools(
    user_text: str,
    *,
    uploaded_files: list[dict] | None = None,
) -> dict[str, Any]:
    pdfs = _pdf_files(uploaded_files)
    docs = _parseable_files(uploaded_files)
    intent = route_intent(user_text)
    office_only = bool(docs) and not pdfs

    if intent in {"to_docx", "to_doc"}:
        if not pdfs:
            if _is_followup_request(user_text):
                return {
                    "intent": "followup",
                    "exitCode": 0,
                    "script": None,
                    "stdout": "",
                    "stderr": "",
                    "note": (
                        "本次没有新的 PDF。必须根据「先前对话」回答；"
                        "若上一轮已给出 Word 下载链接，直接指引用户下载，不要说未上传。"
                    ),
                }
            return {
                "intent": intent,
                "exitCode": 1,
                "script": None,
                "stdout": "",
                "stderr": "",
                "note": (
                    "尚未上传 PDF，无法转换。"
                    "本助手支持 PDF → Word：说「word」默认生成 .docx；"
                    "只有明确说「转成 doc」才尝试旧版 .doc。"
                    "请先上传 .pdf 再发送「转成 Word」。"
                ),
            }
        from app.services.skill.pdf_word import convert_pdfs_to_word

        return convert_pdfs_to_word(pdfs, fmt="doc" if intent == "to_doc" else "docx")

    # Word/Excel/PPT 等：表格抽取仍可走解析后的 Markdown 表；其余默认解析
    if office_only and intent not in {"parse", "extract_images", "extract_tables"}:
        intent = "parse"

    if intent in {"parse", "extract_images"}:
        if not docs:
            if _is_followup_request(user_text):
                return {
                    "intent": "followup",
                    "exitCode": 0,
                    "script": None,
                    "stdout": "",
                    "stderr": "",
                    "note": (
                        "本次没有新的 PDF/文档。必须根据用户消息中的「先前对话」回答当前问题，"
                        "禁止说未附带文档，禁止要求重新上传。"
                    ),
                }
            return {
                "intent": intent,
                "exitCode": 1,
                "script": None,
                "stdout": "",
                "stderr": "",
                "note": "当前请求未附带可解析文档。请上传 .pdf / .docx / .xlsx 等后再试。",
            }
        from app.services.skill.doc_parser import parse_uploaded

        return parse_uploaded(docs, intent=intent)

    if intent == "extract_tables":
        if pdfs:
            return extract_tables_bundle(pdfs)
        if docs:
            return extract_tables_bundle(docs)
        return {
            "intent": intent,
            "exitCode": 1,
            "script": None,
            "stdout": "",
            "stderr": "",
            "note": "当前请求未附带可解析的 PDF。请上传 .pdf 后再试。",
        }

    if not pdfs:
        return {
            "intent": intent,
            "exitCode": 1,
            "script": None,
            "stdout": "",
            "stderr": "",
            "note": "当前请求未附带可解析的 PDF 文件。请在输入框上传 .pdf 后再试。",
        }
    # 多文件且当前这句话在说合并时才合并；不要被上一轮「表格」等历史带偏
    current = prefer_current_user_text(user_text).lower()
    if len(pdfs) >= 2 and intent == "parse" and any(
        k in current for k in ("合并", "merge", "合成", "拼成")
    ):
        intent = "merge"
    if len(pdfs) >= 2 and intent not in {
        "split",
        "extract",
        "form_probe",
        "watermark",
        "parse",
        "extract_images",
        "extract_tables",
        "to_docx",
        "to_doc",
    }:
        intent = "merge"

    try:
        if intent == "merge":
            return merge_pdfs(order_pdfs_for_merge(pdfs, user_text))
        if intent == "split":
            return split_first_pdf(pdfs, user_text)
        if intent == "form_probe":
            return probe_form_structure(pdfs)
        if intent == "watermark":
            return add_text_watermark(pdfs, text=_parse_watermark_text(user_text))
        if intent == "extract_tables":
            return extract_tables_bundle(pdfs)
        return extract_text_bundle(pdfs)
    except Exception as exc:  # noqa: BLE001
        logger.error("pdf tool fail: %s", exc)
        return {
            "intent": intent,
            "exitCode": 1,
            "script": "pdf_pipeline",
            "stdout": "",
            "stderr": str(exc),
            "note": f"PDF 处理失败: {exc}",
        }


def format_pdf_tool_result(trace: dict[str, Any]) -> str:
    if not trace:
        return "（无脚本结果）"
    parts = [
        f"intent: {trace.get('intent')}",
        f"script: {trace.get('script')}",
        f"exitCode: {trace.get('exitCode')}",
    ]
    if trace.get("note"):
        parts.append(f"note: {trace['note']}")
    if trace.get("sources"):
        parts.append("mergeOrder: " + " -> ".join(str(x) for x in trace["sources"]))
        parts.append("必须按 mergeOrder 报告合并顺序，不要按用户原话臆造。")
    if trace.get("watermarkText"):
        parts.append(f"watermarkText: {trace['watermarkText']}")
        parts.append("必须确认实际水印文字为 watermarkText，不要改口。")
    if trace.get("downloadUrl"):
        parts.append(f"downloadUrl: {trace['downloadUrl']}")
    if trace.get("downloadName"):
        parts.append(f"downloadName: {trace['downloadName']}")
    if trace.get("downloadUrls"):
        parts.append("downloadUrls:\n" + "\n".join(str(u) for u in trace["downloadUrls"]))
    if trace.get("imageCount") is not None:
        parts.append(f"imageCount: {trace.get('imageCount')}")
    if trace.get("tableCount") is not None:
        parts.append(f"tableCount: {trace.get('tableCount')}")
    if trace.get("stdout"):
        parts.append("stdout:\n" + str(trace["stdout"])[:8000])
    if trace.get("stderr"):
        parts.append("stderr:\n" + str(trace["stderr"])[:2000])
    parts.append(
        "重要：若 exitCode=0 且含 downloadUrl，表示平台已生成结果文件；"
        "请在回复中给出可点击的下载链接（相对路径即可），不要声称「未检测到上传文件」。"
        "若 intent=split：只给 PDF 下载链接，禁止插入或描述任何图片。"
        "若 intent=followup：没有新文档，必须根据「先前对话」作答，禁止说未附带文档。"
        "若 intent=intro：只介绍能力与用法，禁止声称已处理文件。"
        "若 intent=to_docx 或 to_doc：这就是转 Word 的结果（script=pdf_word），"
        "不要再说成文档解析/Markdown，也不要提 torchv-document-api 不能转 Word。"
        "禁止把系统提示里的时钟信息整段复制进回复。"
    )
    return "\n".join(parts)
