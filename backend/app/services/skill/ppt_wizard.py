"""PPT 多轮向导：问卷 → 三套风格预览 → 再出完整 HTML/PPTX。"""
from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any

from app.services.skill.ppt_html import (
    DEFAULT_PREVIEWS,
    render_deck_html,
    resolve_theme,
    write_html,
)

ROOT = Path(__file__).resolve().parents[4]
WIZARD_DIR = ROOT / "static" / "generated" / "ppt-wizard"
GENERATED_DIR = ROOT / "static" / "generated"

SKIP_WIZARD_RE = re.compile(r"(直接生成|直接出稿|跳过问卷|不用问|马上生成|立刻生成)")
NEW_DECK_RE = re.compile(r"(生成|做|制作|创建).{0,12}(ppt|pptx|演示|幻灯片)", re.I)
STYLE_PICK_RE = re.compile(
    r"(style\s*[-_]?\s*([abc])|风格\s*([abc])|选\s*([abc])|纸与墨|极夜|复古编辑)",
    re.I,
)

OPTION_FOOTER = "请按题号回复，例如 `1b 2a 3a 4b`（第1题选b、第2题选a…）。也可以写成 `1B 2A`。材料可直接贴在同一条后面。"

PURPOSE_Q = """**1. 用途**
- a. 分享 / 推介
- b. 内部演示
- c. 教学 / 讲解
- d. 会议演讲"""

LENGTH_Q = """**2. 页数**
- a. 短 5–10 张
- b. 中 10–20 张
- c. 长 20+ 张"""

CONTENT_STATUS_Q = """**3. 内容准备到哪一步**
- a. 材料已经准备好（下一条粘贴大纲/数据）
- b. 只有粗略笔记（下一条粘贴笔记）
- c. 只有主题，请按主题策划（请顺手写主题）"""

DENSITY_Q = """**4. 密度**
- a. 低密度 / 演讲导向（少字、大标题）
- b. 高密度 / 阅读导向（表格、对比更完整）"""

CONTENT_BODY_Q = """**3. 请提供正文**
- a. 下一条 / 这条里粘贴完整大纲或数据
- b. 这条里粘贴粗略笔记
- c. 只有主题，请策划（请写主题，如「大模型评测对比」）
- d. 用刚才对话里的材料"""

BRIEF_OUTPUT = f"""先确认这 4 项。材料齐了再选主题，选完主题才生成。

{PURPOSE_Q}

{LENGTH_Q}

{CONTENT_STATUS_Q}

{DENSITY_Q}

{OPTION_FOOTER}
"""

CONTENT_OUTPUT = f"""还缺可做页的正文，不会用上一轮旧主题凑稿。

{CONTENT_BODY_Q}

回复例如 `3a`，然后把大纲贴上；或回复 `3d` 表示用刚才对话里的材料。
"""

GAP_BLOCKS = {
    "purpose": PURPOSE_Q,
    "length": LENGTH_Q,
    "density": DENSITY_Q,
    "content": CONTENT_BODY_Q,
}

USE_PRIOR_RE = re.compile(r"用刚才|用上文|用之前|沿用(刚才|上文|之前)|用对话里")
NUMBERED_CHOICE_RE = re.compile(r"([1-4])\s*[:.、\-]?\s*([a-dA-D])")
PRIOR_CHOICE_RE = re.compile(r"(?:^|[\s,，])(?:3\s*[:.、\-]?\s*)?[dD]\b")

STYLE_OUTPUT = """接下来选视觉风格。也可以先看三套封面再决定。

**1. 怎么选风格**
- a. 给我看看选项（推荐）
- b. 我知道要什么（直接说主题名，如 `tokyo-night` / 纸与墨 / 商务）

**2. 希望观众看完后的感觉（可选，可写多项如 `2a 2d`）**
- a. 专业、冷静
- b. 酷炫、兴奋
- c. 温暖、文艺
- d. 信任、有说服力

回复例如：`1a 2a` 或 `1b` 加上主题名。
"""


def _wizard_path(key: str) -> Path:
    WIZARD_DIR.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "-", (key or "anon"))[:80]
    return WIZARD_DIR / f"{safe}.json"


def load_state(key: str) -> dict[str, Any]:
    path = _wizard_path(key)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def save_state(key: str, state: dict[str, Any]) -> None:
    path = _wizard_path(key)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def wizard_in_progress(conversation_id: str | None) -> bool:
    if not conversation_id:
        return False
    phase = str(load_state(conversation_id).get("phase") or "")
    return phase in {"brief", "content", "style", "preview"}


def _current(text: str) -> str:
    t = text or ""
    if "## 当前用户" in t:
        t = t.split("## 当前用户", 1)[-1]
    return t.strip()


def wants_prior_material(text: str) -> bool:
    return bool(USE_PRIOR_RE.search(text or ""))


def has_real_content(text: str) -> bool:
    t = _current(text)
    if is_detailed_spec(t):
        return True
    rest = re.sub(
        r"(生成|做|制作|创建).{0,12}(ppt|pptx|演示文稿|幻灯片)",
        "",
        t,
        flags=re.I,
    ).strip()
    if len(rest) >= 80:
        return True
    if re.search(r"标题[：:]|第\s*\d+\s*页|大纲|副标题", t):
        return True
    return False


def body_ready(state: dict[str, Any]) -> bool:
    outline = str(state.get("raw_outline") or "").strip()
    if has_real_content(outline):
        return True
    if str(state.get("content_mode") or "") == "topic":
        rest = re.sub(
            r"(生成|做|制作|创建).{0,12}(ppt|pptx|演示文稿|幻灯片)",
            "",
            outline or str(state.get("topic") or ""),
            flags=re.I,
        ).strip()
        return len(rest) >= 8
    return False


def missing_slots(state: dict[str, Any]) -> list[tuple[str, str]]:
    gaps: list[tuple[str, str]] = []
    if not state.get("purpose"):
        gaps.append(("purpose", "用途"))
    if not state.get("slide_count"):
        gaps.append(("length", "页数"))
    if not state.get("density"):
        gaps.append(("density", "密度"))
    if not body_ready(state):
        gaps.append(("content", "正文材料"))
    return gaps


def _ask_gaps(key: str, state: dict[str, Any], gaps: list[tuple[str, str]]) -> dict[str, Any]:
    kinds = {g[0] for g in gaps}
    qnum = {"purpose": 1, "length": 2, "content": 3, "density": 4}
    lines = [
        "材料还没齐。请按**原题号**回复（例如还缺第 3、4 题就写 `3a 4b`）；选完主题才会生成。",
        "",
        "还缺：",
    ]
    for key_name, label in gaps:
        lines.append(f"{qnum.get(key_name, '?')}. {label}")
    lines.append("")
    for key_name, _ in gaps:
        block = GAP_BLOCKS.get(key_name)
        if block:
            lines.append(block)
            lines.append("")
    lines.append(OPTION_FOOTER)
    if "content" in kinds and not (kinds - {"content"}):
        state["phase"] = "content"
        intent = "content-ask"
    else:
        state["phase"] = "brief"
        intent = "brief"
    save_state(key, state)
    return _trace(
        intent=intent,
        output="\n".join(lines).strip(),
        note="信息未齐，禁止生成完整稿。",
    )


def absorb_current(state: dict[str, Any], current: str) -> dict[str, Any]:
    state = dict(state)
    purpose, length, content_mode, density = _parse_brief_combo(current)
    if purpose:
        state["purpose"] = purpose
    if length:
        state["slide_count"] = length
    if content_mode:
        state["content_mode"] = content_mode
    if density:
        state["density"] = density
    if has_real_content(current):
        state["raw_outline"] = current
        state["content_mode"] = state.get("content_mode") or "ready"
        n = parse_page_count(current)
        if n:
            state["slide_count"] = state.get("slide_count") or n
        if re.search(r"报告|评测|对比|论文", current):
            state["density"] = state.get("density") or "high"
            state["purpose"] = state.get("purpose") or "internal"
        theme = infer_theme_from_text(current)
        if theme:
            state["hint_theme"] = theme
    return state


def is_detailed_spec(text: str) -> bool:
    t = text or ""
    pages = len(re.findall(r"第\s*\d+\s*页", t))
    if pages >= 2:
        return True
    if len(t) >= 180 and re.search(r"(封面页|标题[：:]|副标题[：:]|风格[：:])", t):
        return True
    return False


def infer_theme_from_text(text: str) -> str | None:
    t = text or ""
    if re.search(r"深色|纯黑|极夜|tokyo-night|dark", t, re.I):
        return "tokyo-night"
    if re.search(r"蓝灰|商务|科研|简约|浅色|白底|企业|对比(分析)?报告", t):
        return "corporate-clean"
    if re.search(r"学术|论文|答辩", t):
        return "academic-paper"
    if re.search(r"纸与墨|文艺", t):
        return "editorial-serif"
    if re.search(r"小红书", t):
        return "xiaohongshu-white"
    return None


def parse_page_count(text: str) -> int | None:
    m = re.search(r"共\s*(\d{1,2})\s*页", text or "")
    if m:
        return max(3, min(24, int(m.group(1))))
    pages = [int(x) for x in re.findall(r"第\s*(\d+)\s*页", text or "")]
    return max(pages) if pages else None


def _parse_table_from_block(block: str) -> dict[str, Any] | None:
    rows: list[list[str]] = []
    for ln in (block or "").splitlines():
        s = ln.strip().lstrip("-*·").strip()
        if not s:
            continue
        if re.search(r"deepseek|qwen|gpt|gemini|模型", s, re.I) and re.search(r"\d\.\d+", s):
            parts = re.split(r"[|｜\t,，]\s*|\s{2,}", s)
            parts = [p.strip() for p in parts if p.strip() and p.strip() not in {"排名", "名"}]
            name_m = re.search(
                r"(deepseek-[\w.]+|qwen[\w.]+|gpt[\w.]+|gemini[\w.]+)", s, re.I
            )
            name = name_m.group(1) if name_m else (parts[0] if parts else s)
            rest = s[name_m.end() :] if name_m else s
            nums = re.findall(r"0\.\d{2,}", rest)
            if len(nums) >= 3:
                rows.append([name, *nums[:4]])
    if not rows:
        return None
    width = max(len(r) for r in rows)
    headers = ["模型", "Recall", "F1", "BLEU-4", "综合"][:width]
    if width == 6:
        headers = ["模型", "Recall", "F1", "BLEU-4", "综合", "备注"]
    return {"headers": headers, "rows": [r + [""] * (width - len(r)) for r in rows]}


def parse_detailed_spec(text: str) -> dict[str, Any] | None:
    t = text or ""
    chunks = re.split(r"(?=第\s*\d+\s*页)", t)
    slides: list[dict[str, Any]] = []
    deck_title = ""
    for ch in chunks:
        hm = re.search(r"第\s*(\d+)\s*页", ch)
        if not hm:
            title_m = re.search(r"标题[：:]\s*(.+)", ch)
            if title_m and not deck_title:
                deck_title = title_m.group(1).strip()
            continue
        idx = int(hm.group(1))
        kind = ""
        km = re.search(r"【([^】]+)】", ch)
        if km:
            kind = km.group(1)
        title_m = re.search(r"标题[：:]\s*(.+)", ch)
        sub_m = re.search(r"副标题[：:]\s*(.+)", ch)
        note_m = re.search(r"(?:备注|脚注)[：:]\s*(.+)", ch)
        title = (title_m.group(1).strip() if title_m else kind or f"第{idx}页")[:80]
        subtitle = (sub_m.group(1).strip() if sub_m else "")[:160]
        table = _parse_table_from_block(ch)
        points: list[str] = []
        body = ch
        cm = re.search(r"内容[：:]\s*", ch)
        if cm:
            body = ch[cm.end() :]
        for ln in body.splitlines():
            s = ln.strip()
            if not s or re.match(r"^第\s*\d+\s*页", s):
                continue
            if re.match(r"^(标题|副标题|备注|脚注|风格|配色|排版)[：:]", s):
                continue
            s = re.sub(r"^\d+[\.、]\s*", "", s)
            s = s.lstrip("-*· ").strip()
            if table and re.search(r"0\.\d{2,}", s) and re.search(
                r"deepseek|qwen|gpt|gemini", s, re.I
            ):
                continue
            if "|" in s or "｜" in s:
                continue
            if 2 <= len(s) <= 80:
                points.append(s)
        if "封面" in kind:
            stype = "title"
            if not deck_title:
                deck_title = title
        elif "排名" in kind or table:
            stype = "table"
        elif "目录" in kind:
            stype = "toc"
        elif "感谢" in kind or "结尾" in kind:
            stype = "conclusion"
        else:
            stype = "content"
        if note_m and note_m.group(1).strip() not in points:
            points.append(note_m.group(1).strip())
        sl: dict[str, Any] = {
            "slide_number": idx,
            "type": stype,
            "title": title,
            "subtitle": subtitle,
            "key_points": points[:8],
        }
        if table:
            sl["type"] = "table"
            sl["table"] = table
        slides.append(sl)
    if not slides:
        return None
    slides.sort(key=lambda s: int(s.get("slide_number") or 0))
    return {"title": deck_title or str(slides[0].get("title") or "演示文稿"), "slides": slides}


def parse_purpose(text: str) -> str | None:
    t = text or ""
    if re.search(r"会议|演讲|conference|\bD\b", t, re.I) and not re.search(r"内部演示", t):
        if re.search(r"会议|演讲|conference", t, re.I) or re.search(r"(^|[\s,，])D([\s,，]|$)", t, re.I):
            return "conference"
    if re.search(r"教学|讲解|教程", t):
        return "teaching"
    if re.search(r"内部", t):
        return "internal"
    if re.search(r"分享|推介|电影", t):
        return "share"
    return None


def parse_length(text: str) -> int | None:
    t = text or ""
    m = re.search(r"(\d{1,2})\s*张", t)
    if m:
        return max(5, min(24, int(m.group(1))))
    if re.search(r"长|20\s*\+", t):
        return 20
    if re.search(r"中|10\s*[-–—到至]\s*20", t):
        return 12
    if re.search(r"短|5\s*[-–—到至]\s*10", t):
        return 8
    return None


def parse_browser_edit(text: str) -> bool | None:
    t = text or ""
    if re.search(r"不要编辑|不能改|只要下载|不要", t) and not re.search(r"要能编辑|要编辑", t):
        return False
    if re.search(r"要编辑|可以改|浏览器|推荐|是（推荐）|^是$|要能编辑", t):
        return True
    return None


def parse_style_mode(text: str) -> str | None:
    t = text or ""
    if re.search(r"看看选项|给我看", t):
        return "browse"
    if re.search(r"我知道|直接说主题", t):
        return "known"
    return None


def parse_moods(text: str) -> list[str]:
    t = text or ""
    out: list[str] = []
    if re.search(r"专业|冷静|聚焦", t):
        out.append("calm")
    if re.search(r"酷炫|兴奋|科技|暗色", t):
        out.append("excited")
    if re.search(r"温暖|文艺|纸与墨|小红书", t):
        out.append("warm")
    if re.search(r"信任|说服|商务|投资", t):
        out.append("confident")
    return out[:2]


def parse_style_pick(text: str, previews: list[dict[str, Any]]) -> dict[str, Any] | None:
    t = _current(text)
    letter = None
    m_num = re.search(r"(?:^|[\s,，])1\s*[:.、\-]?\s*([a-dA-D])\b", t)
    if m_num:
        ch = m_num.group(1).upper()
        if ch == "D" and previews:
            return previews[-1]
        letter = ch.lower()
    m = STYLE_PICK_RE.search(t)
    if m:
        letter = letter or (m.group(2) or m.group(3) or m.group(4) or "").lower()
        if "纸与墨" in t:
            letter = letter or "c"
        elif "极夜" in t:
            letter = letter or "a"
        elif "复古" in t:
            letter = letter or "b"
    if not letter:
        m2 = re.match(r"\s*([ABCD])\b", t, re.I)
        if m2:
            ch = m2.group(1).upper()
            if ch == "D" and previews:
                return previews[-1]
            letter = ch.lower()
    if letter in {"a", "b", "c"}:
        key = f"style-{letter}"
        for p in previews:
            if p.get("key") == key:
                return p
    low = t.lower()
    for p in previews:
        theme = str(p.get("theme") or "")
        name = str(p.get("name") or "")
        if theme and theme.lower() in low:
            return p
        if any(part in t for part in re.split(r"\s+", name) if len(part) >= 2):
            return p
    return None


def _previews_for_moods(moods: list[str]) -> tuple[tuple[str, str, str, str], ...]:
    if "warm" in moods:
        return (
            ("style-a", "Xiaohongshu 小红书白", "xiaohongshu-white", "轻量、适合图文分享"),
            ("style-b", "Soft Pastel 柔彩", "soft-pastel", "柔和、亲和"),
            ("style-c", "Paper & Ink 纸与墨", "editorial-serif", "暖纸衬线、文艺阅读"),
        )
    if "excited" in moods:
        return (
            ("style-a", "Tokyo Night 极夜", "tokyo-night", "深色技术分享"),
            ("style-b", "Aurora 极光", "aurora", "渐变、发布会"),
            ("style-c", "Cyberpunk 赛博", "cyberpunk-neon", "强对比、酷炫"),
        )
    if "calm" in moods or "confident" in moods:
        return (
            ("style-a", "Corporate Clean 商务", "corporate-clean", "内部汇报、正式"),
            ("style-b", "Swiss Grid 网格", "swiss-grid", "克制、信息密度清晰"),
            ("style-c", "Academic Paper 学术", "academic-paper", "报告、论文答辩"),
        )
    return DEFAULT_PREVIEWS


def _purpose_kicker(purpose: str | None) -> str:
    return {
        "share": "分享 / 推介",
        "internal": "内部演示",
        "teaching": "教学 / 讲解",
        "conference": "会议演讲",
    }.get(purpose or "", "演示")


def parse_content_mode(text: str) -> str | None:
    t = text or ""
    if re.search(r"准备好|现成|全部内容", t):
        return "ready"
    if re.search(r"粗略|笔记|提纲", t):
        return "notes"
    if re.search(r"只有主题|仅主题|帮我策划", t):
        return "topic"
    return None


def parse_density(text: str) -> str | None:
    t = text or ""
    if re.search(r"低密度|演讲|少字", t):
        return "low"
    if re.search(r"高密度|阅读|报告", t):
        return "high"
    return None


def _parse_brief_combo(text: str) -> tuple[str | None, int | None, str | None, str | None]:
    """解析「1b 2a 3a 4b」；短回复也可退回「b a a b」。"""
    t = text or ""
    purpose = length = content_mode = density = None
    pairs = {int(n): let.upper() for n, let in NUMBERED_CHOICE_RE.findall(t)}
    if pairs:
        purpose = {"A": "share", "B": "internal", "C": "teaching", "D": "conference"}.get(pairs.get(1, ""))
        length = {"A": 8, "B": 15, "C": 22, "D": 15}.get(pairs.get(2, ""))
        content_mode = {"A": "ready", "B": "notes", "C": "topic", "D": "prior"}.get(pairs.get(3, ""))
        density = {"A": "low", "B": "high", "C": "high"}.get(pairs.get(4, ""))
    elif len(t.strip()) <= 48 and not has_real_content(t):
        letters = [x.upper() for x in re.findall(r"[A-Da-d]", t)]
        if len(letters) >= 1:
            purpose = {"A": "share", "B": "internal", "C": "teaching", "D": "conference"}.get(letters[0])
        if len(letters) >= 2:
            length = {"A": 8, "B": 15, "C": 22, "D": 15}.get(letters[1])
        if len(letters) >= 3:
            content_mode = {"A": "ready", "B": "notes", "C": "topic", "D": "prior"}.get(letters[2])
        if len(letters) >= 4:
            density = {"A": "low", "B": "high", "C": "high"}.get(letters[3])
    purpose = purpose or parse_purpose(t)
    length = length or parse_length(t)
    content_mode = content_mode or parse_content_mode(t)
    density = density or parse_density(t)
    return purpose, length, content_mode, density


def expand_plan(plan: dict[str, Any], target: int, *, lock: bool = False) -> dict[str, Any]:
    slides = list(plan.get("slides") or [])
    if not slides:
        return plan
    if lock or any(s.get("table") for s in slides) or plan.get("planned"):
        for i, sl in enumerate(slides[:24], 1):
            sl["slide_number"] = i
            sl.setdefault("key_points", [])
            sl.setdefault("type", "content")
        plan = dict(plan)
        plan["slides"] = slides[:24]
        return plan
    target = max(5, min(24, int(target or len(slides))))
    title_sl = slides[0]
    if str(title_sl.get("type") or "") != "title":
        title_sl = {
            "type": "title",
            "title": plan.get("title") or title_sl.get("title"),
            "subtitle": "",
            "key_points": [],
        }
        slides = [title_sl, *slides]
    rest = [s for s in slides[1:] if str(s.get("type")) not in {"conclusion", "thanks"}]
    thanks = next(
        (s for s in slides if str(s.get("type")) in {"conclusion", "thanks"}),
        {"type": "conclusion", "title": "Thanks", "subtitle": "谢谢", "key_points": []},
    )
    toc = {
        "type": "toc",
        "title": "目录",
        "key_points": [str(s.get("title") or "") for s in rest[:6]],
    }
    body = [toc, *rest] if rest else [toc]
    grown: list[dict[str, Any]] = []
    for s in body:
        pts = [str(p).strip() for p in (s.get("key_points") or []) if str(p).strip()]
        if str(s.get("type")) == "toc" or len(pts) <= 4:
            grown.append(s)
            continue
        grown.append({**s, "key_points": pts[:3]})
        for i in range(3, len(pts), 3):
            grown.append(
                {
                    "type": "content",
                    "title": f"{s.get('title')}（续）",
                    "key_points": pts[i : i + 3],
                }
            )
    while len(grown) + 2 < target:
        grown.append(
            {
                "type": "content",
                "title": f"补充 {len(grown)}",
                "key_points": ["可在浏览器中直接改这段文字", "按主题继续补充要点", "保持一页一个重点"],
            }
        )
    out_slides = [title_sl, *grown[: max(1, target - 2)], thanks]
    for i, sl in enumerate(out_slides, 1):
        sl["slide_number"] = i
        sl.setdefault("key_points", [])
        sl.setdefault("type", "content")
    plan = dict(plan)
    plan["slides"] = out_slides
    return plan


def _trace(*, intent: str, output: str, note: str, **extra: Any) -> dict[str, Any]:
    return {
        "intent": intent,
        "script": "ppt-wizard",
        "exitCode": 0,
        "stdout": output,
        "stderr": "",
        "note": note,
        **extra,
    }


COMPOSE_SYSTEM = (
    "你是资深演示文稿策划，不是大纲搬运工。只输出一个 JSON 对象，不要解释、不要 Markdown。"
    "结构：{\"title\":\"...\",\"slides\":[{\"type\":\"title|toc|content|table|conclusion\","
    "\"title\":\"...\",\"subtitle\":\"\",\"key_points\":[\"短句\"],"
    "\"table\":{\"headers\":[\"...\"],\"rows\":[[\"...\"]]}}]}。"
    "工作方式：先在内部完成叙事规划（封面结论→指标含义→总排名→分指标冠军→启示），再写成可上台的页。"
    "硬性规则："
    "1) 沿用用户标题、模型名、指标名和全部数字，禁止改成技术架构/年度总结等其它主题，禁止编造未给出的数；"
    "2) 标题必须是完整结论或页名，禁止「表格」「第N页」「续」这种空标题；"
    "3) 对比数字必须放进 table.headers/rows，禁止在 key_points 里用 | 或逗号堆原始表格行；"
    "4) 每条 key_points ≤22 字，是给观众看的短句（如「Recall 冠军 deepseek-pro」），不要把整行备注原样粘贴；"
    "5) 一页一个重点；禁止相邻两页标题或要点重复；不要生成空白填充页；"
    "6) 用户若只写了前几页但要求共 N 页：用已给数据规划余下页（指标定义卡、总表+图、分指标冠军、结论），仍不得编造新数字；"
    "7) 封面 type=title，排名/对比 type=table 且带 table，指标说明用 3 张短卡片。"
)


def _pipe_rows(points: list[str]) -> list[list[str]]:
    rows: list[list[str]] = []
    for p in points or []:
        parts = [x.strip() for x in re.split(r"[|｜]", str(p)) if x.strip()]
        if len(parts) >= 3:
            rows.append(parts)
    return rows


def coerce_tables(plan: dict[str, Any]) -> dict[str, Any]:
    slides = []
    for sl in list(plan.get("slides") or []):
        sl = dict(sl)
        pts = [str(p).strip() for p in (sl.get("key_points") or []) if str(p).strip()]
        table = sl.get("table") if isinstance(sl.get("table"), dict) else None
        rows = _pipe_rows(pts)
        if (not table or not (table.get("rows") or table.get("headers"))) and len(rows) >= 2:
            width = max(len(r) for r in rows)
            headers = ["项目", "模型", "得分", "说明"][:width]
            if rows and not re.search(r"\d", rows[0][0] or ""):
                headers = rows[0] + [""] * (width - len(rows[0]))
                data = rows[1:]
            else:
                data = rows
            sl["type"] = "table"
            sl["table"] = {"headers": headers, "rows": [r + [""] * (width - len(r)) for r in data]}
            sl["key_points"] = [p for p in pts if "|" not in p and "｜" not in p][:3]
        elif table:
            sl["key_points"] = [p for p in pts if "|" not in p and "｜" not in p][:4]
        slides.append(sl)
    plan = dict(plan)
    plan["slides"] = slides
    return plan


def dedupe_slides(plan: dict[str, Any]) -> dict[str, Any]:
    out = []
    prev = None
    for sl in plan.get("slides") or []:
        pts = tuple(str(p).strip() for p in (sl.get("key_points") or []) if str(p).strip())
        sig = (str(sl.get("title") or "").strip(), pts, json.dumps(sl.get("table") or {}, ensure_ascii=False))
        if sig == prev:
            continue
        if str(sl.get("title") or "").startswith("第") and str(sl.get("title")).endswith("页") and not pts and not sl.get("table"):
            continue
        prev = sig
        out.append(sl)
    plan = dict(plan)
    plan["slides"] = out
    return plan


def merge_parsed_tables(plan: dict[str, Any], parsed: dict[str, Any] | None) -> dict[str, Any]:
    if not parsed:
        return plan
    src = [s for s in (parsed.get("slides") or []) if isinstance(s.get("table"), dict) and s["table"].get("rows")]
    if not src:
        return plan
    slides = []
    used = False
    for sl in plan.get("slides") or []:
        sl = dict(sl)
        title = str(sl.get("title") or "")
        need = any(k in title for k in ("排名", "得分", "对比", "综合")) or sl.get("type") == "table"
        if need and not (isinstance(sl.get("table"), dict) and sl["table"].get("rows")):
            sl["table"] = src[0]["table"]
            sl["type"] = "table"
            used = True
        slides.append(sl)
    if not used:
        # keep parsed ranking page if model omitted numbers
        have = any(isinstance(s.get("table"), dict) and s.get("table", {}).get("rows") for s in slides)
        if not have:
            slides.insert(min(2, len(slides)), src[0])
    plan = dict(plan)
    plan["slides"] = slides
    return plan


def is_off_topic(user_title: str, model_title: str) -> bool:
    mt = model_title or ""
    if re.search(r"技术架构|年度工作|演进汇报", mt):
        return True
    ut = (user_title or "").strip()
    if ut and ut[:4] not in mt and mt[:4] not in ut:
        return True
    return False


def parse_slides_json(text: str) -> dict[str, Any] | None:
    raw = (text or "").strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if fence:
        raw = fence.group(1).strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        obj = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return None
    slides = obj.get("slides") if isinstance(obj, dict) else None
    if not isinstance(slides, list) or not slides:
        return None
    clean = []
    for i, sl in enumerate(slides[:24], 1):
        if not isinstance(sl, dict):
            continue
        pts = sl.get("key_points") or sl.get("points") or []
        if not isinstance(pts, list):
            pts = [str(pts)]
        clean.append(
            {
                "slide_number": i,
                "type": str(sl.get("type") or ("title" if i == 1 else "content")),
                "title": str(sl.get("title") or f"第{i}页")[:80],
                "subtitle": str(sl.get("subtitle") or "")[:160],
                "key_points": [str(p).strip()[:120] for p in pts if str(p).strip()][:10],
            }
        )
        table = sl.get("table")
        if isinstance(table, dict) and (table.get("headers") or table.get("rows")):
            clean[-1]["table"] = {
                "headers": [str(h) for h in (table.get("headers") or [])][:8],
                "rows": [
                    [str(c) for c in (row if isinstance(row, (list, tuple)) else [row])][:8]
                    for row in (table.get("rows") or [])[:16]
                ],
            }
            clean[-1]["type"] = "table"
    if not clean:
        return None
    return {"title": str(obj.get("title") or clean[0]["title"]), "slides": clean}


def compose_trace(
    key: str,
    state: dict[str, Any],
    *,
    theme: str,
    editable: bool,
    picked: dict[str, Any] | None = None,
) -> dict[str, Any]:
    gaps = missing_slots(state)
    if gaps:
        return _ask_gaps(key, state, gaps)
    outline = str(state.get("raw_outline") or "").strip()
    mode = str(state.get("content_mode") or "")
    theme = resolve_theme(theme)
    n = int(state.get("slide_count") or 8)
    picked_name = (picked or {}).get("name") or theme
    density = str(state.get("density") or "high")
    spec = {
        "wizard_key": key,
        "theme": theme,
        "editable": bool(editable),
        "slide_count": n,
        "purpose": state.get("purpose"),
        "raw_outline": outline,
        "picked_name": picked_name,
        "density": density,
        "content_mode": mode,
    }
    state["pending_compose"] = spec
    save_state(key, state)
    kicker = _purpose_kicker(state.get("purpose"))
    dens = "低密度演讲" if density == "low" else "高密度阅读"
    topic_note = (
        "用户只有主题：可策划页结构，但禁止引用未出现在大纲中的机构名/项目/数字。\n"
        if mode == "topic"
        else "只根据「用户大纲」撰写，禁止使用其它会话主题。\n"
    )
    stdout = (
        "请先完成内容规划再写 JSON。结论型标题、短要点、对比数字进 table。"
        "禁止把「A | B | 0.97」贴进卡片。\n\n"
        f"{topic_note}"
        f"目标页数: {n}\n用途: {kicker}\n密度: {dens}\n视觉主题: {theme}（{picked_name}）\n\n"
        f"## 用户大纲\n{outline or '（仅主题，见用途与用户当轮说明）'}\n"
    )
    return _trace(
        intent="compose",
        output=stdout,
        note="向导已收齐内容与风格。请模型撰写幻灯片 JSON，随后由平台渲染 HTML/PPTX。",
        compose=spec,
    )


def apply_composed_plan(spec: dict[str, Any], plan: dict[str, Any], pptx_builder) -> dict[str, Any]:
    key = str(spec.get("wizard_key") or "anon")
    state = load_state(key)
    n = int(spec.get("slide_count") or 8)
    plan = coerce_tables(plan)
    plan = dedupe_slides(plan)
    plan["planned"] = True
    plan = expand_plan(plan, n, lock=True)
    plan["style"] = str(spec.get("theme") or "corporate-clean")
    return _finalize(
        key,
        state,
        plan,
        theme=str(spec.get("theme") or "corporate-clean"),
        editable=bool(spec.get("editable", True)),
        pptx_builder=pptx_builder,
        picked={"name": spec.get("picked_name")},
    )


def _emit_style_previews(key: str, state: dict[str, Any], *, plan_builder, current: str) -> dict[str, Any]:
    state = absorb_current(state, current)
    gaps = missing_slots(state)
    if gaps:
        return _ask_gaps(key, state, gaps)
    previews_spec = _previews_for_moods(list(state.get("moods") or []))
    deck_id = uuid.uuid4().hex[:10]
    folder = GENERATED_DIR / f"ppt-preview-{deck_id}"
    seed = str(state.get("raw_outline") or current or state.get("topic") or "演示文稿")
    plan = expand_plan(plan_builder(seed), 6, lock=True)
    kicker = _purpose_kicker(state.get("purpose"))
    previews = []
    urls = []
    for key_name, name, theme, blurb in previews_spec:
        html_text = render_deck_html(
            plan,
            theme=theme,
            kicker=kicker,
            editable=True,
            preview_only=True,
        )
        url = write_html(folder / f"{key_name}.html", html_text)
        previews.append(
            {"key": key_name, "name": name, "theme": theme, "blurb": blurb, "url": url}
        )
        urls.append(url)
    state.update({"phase": "preview", "preview_id": deck_id, "previews": previews, "browser_edit": True})
    save_state(key, state)
    lines = [
        "下面三套是 **html-ppt 主题封面**（不是完整稿）。点开 HTML 看 16:9 画布和字体，再选一套。",
        "",
        "## 风格预览",
    ]
    for p in previews:
        lines.append(f"- **{p['key']}** — {p['name']}：{p['blurb']}")
        lines.extend(
            [
                "",
                "请输入题号+选项，例如 `1a`：",
                "- **1a** / `style-a`",
                "- **1b** / `style-b`",
                "- **1c** / `style-c`",
                "- **1d** 混搭",
                "",
                "也可以自己写想要的风格。",
            ]
        )
    return _trace(
        intent="style-preview",
        output="\n".join(lines),
        note="三套风格封面，等待点名后再生成完整稿。",
        downloadUrl=urls[0] if urls else None,
        downloadName="style-a.html",
        downloadUrls=urls,
    )


def run_wizard(
    user_text: str,
    *,
    conversation_id: str,
    plan_builder,
    pptx_builder,
) -> dict[str, Any]:
    key = (conversation_id or "").strip() or "anon"
    current = _current(user_text)
    state = load_state(key)
    phase = str(state.get("phase") or "")

    if is_detailed_spec(current) and phase not in {"brief", "content", "style", "preview"}:
        parsed = parse_detailed_spec(current)
        n = parse_page_count(current) or (
            len(parsed["slides"]) if parsed and parsed.get("slides") else 8
        )
        state = absorb_current(
            {
                "raw_outline": current,
                "slide_count": n,
                "browser_edit": True,
                "content_mode": "ready",
                "topic": current[:200],
            },
            current,
        )
        gaps = missing_slots(state)
        if gaps:
            return _ask_gaps(key, state, gaps)
        return _emit_style_previews(key, state, plan_builder=plan_builder, current=current)

    if SKIP_WIZARD_RE.search(current):
        state = absorb_current({"browser_edit": True}, current)
        gaps = missing_slots(state)
        if gaps:
            return _ask_gaps(key, state, gaps)
        return _emit_style_previews(key, state, plan_builder=plan_builder, current=current)

    starting_new = bool(NEW_DECK_RE.search(current) and not parse_style_pick(current, state.get("previews") or []))
    if phase in {"done", ""} and starting_new and not has_real_content(current):
        state = {}
        phase = ""
    elif phase == "done" and starting_new:
        state = {}
        phase = ""

    if not phase:
        outline = current if has_real_content(current) else ""
        state = {
            "phase": "brief",
            "topic": current[:200],
            "raw_outline": outline,
            "browser_edit": True,
        }
        save_state(key, state)
        return _trace(
            intent="brief",
            output=BRIEF_OUTPUT,
            note="向导第 1 步：用途 / 页数 / 内容 / 密度。禁止现在生成文件。",
        )

    if phase == "brief":
        state = absorb_current(state, current)
        if wants_prior_material(current) or PRIOR_CHOICE_RE.search(current):
            prior = ""
            if "## 先前对话" in user_text:
                prior = user_text.split("## 当前用户", 1)[0]
            if len(prior) >= 80:
                state["raw_outline"] = prior
                state["content_mode"] = "ready"
        gaps = missing_slots(state)
        if gaps:
            return _ask_gaps(key, state, gaps)
        return _emit_style_previews(key, state, plan_builder=plan_builder, current=current)

    if phase == "content":
        state = absorb_current(state, current)
        if wants_prior_material(current) or PRIOR_CHOICE_RE.search(current):
            prior = ""
            if "## 先前对话" in user_text:
                prior = user_text.split("## 当前用户", 1)[0]
            if len(prior) < 80:
                return _ask_gaps(key, state, [("content", "正文材料")])
            state["raw_outline"] = prior
            state["content_mode"] = "ready"
        gaps = missing_slots(state)
        if gaps:
            return _ask_gaps(key, state, gaps)
        return _emit_style_previews(key, state, plan_builder=plan_builder, current=current)

    if phase == "style":
        return _emit_style_previews(key, state, plan_builder=plan_builder, current=current)

    if phase == "preview":
        picked = parse_style_pick(current, state.get("previews") or [])
        if not picked:
            if "混搭" in current or "mix" in current.lower():
                picked = (state.get("previews") or [None])[-1]
            if not picked:
                return _trace(
                    intent="style-preview",
                    output="请输入封面选项（也可以自己描述想要的风格）：\n"
                    "- **1a** / `style-a`\n- **1b** / `style-b`\n- **1c** / `style-c`\n- **1d** 混搭上面几种\n",
                    note="等待选择风格，禁止生成完整稿。",
                    downloadUrls=[
                        p.get("url") for p in (state.get("previews") or []) if p.get("url")
                    ],
                )
        return compose_trace(
            key,
            state,
            theme=str(picked.get("theme") or "tokyo-night"),
            editable=bool(state.get("browser_edit", True)),
            picked=picked,
        )

    state = absorb_current(state, current)
    gaps = missing_slots(state)
    if gaps:
        return _ask_gaps(key, state, gaps)
    return compose_trace(
        key,
        state,
        theme=str(state.get("theme") or state.get("hint_theme") or "corporate-clean"),
        editable=bool(state.get("browser_edit", True)),
    )


def _finalize(
    key: str,
    state: dict[str, Any],
    plan: dict[str, Any],
    *,
    theme: str,
    editable: bool,
    pptx_builder,
    picked: dict[str, Any] | None = None,
) -> dict[str, Any]:
    theme = resolve_theme(theme)
    deck_id = uuid.uuid4().hex[:10]
    folder = GENERATED_DIR / f"ppt-{deck_id}"
    kicker = _purpose_kicker(state.get("purpose"))
    html_text = render_deck_html(plan, theme=theme, kicker=kicker, editable=editable)
    html_url = write_html(folder / "index.html", html_text)
    plan = dict(plan)
    plan["style"] = theme
    pptx_trace = pptx_builder(plan)
    pptx_url = pptx_trace.get("downloadUrl")
    state.update({"phase": "done", "theme": theme, "deck_id": deck_id})
    save_state(key, state)
    style_name = (picked or {}).get("name") or theme
    n = len(plan.get("slides") or [])
    lines = [
        "## 结果",
        f"已按 **{style_name}** 生成 {n} 页 HTML 演示稿（{kicker}），并附可编辑 PPTX。",
        "在浏览器打开 HTML：← → 翻页，T 换主题，F 全屏"
        + ("，点击文字可直接改。" if editable else "。"),
        "",
        "## 下载",
        f"- [在浏览器打开演示稿]({html_url})",
    ]
    if pptx_url:
        lines.append(f"- [Office PPTX]({pptx_url})")
    lines.extend(["", "## 说明", "这是完整稿。若要换风格，直接说「重新做一份」。"])
    output = "\n".join(lines)
    urls = [u for u in [html_url, pptx_url] if u]
    return {
        "intent": "generate",
        "script": "html-ppt+python-pptx",
        "exitCode": 0,
        "stdout": output,
        "stderr": "",
        "note": f"HTML 使用 html-ppt {theme} + {('tech-sharing' if theme in {'tokyo-night','catppuccin-mocha','dracula'} else 'weekly-report')} 全稿模板；PPTX 为可编辑原生表格/图表",
        "downloadUrl": html_url,
        "downloadName": "index.html",
        "downloadUrls": urls,
        "slideCount": n,
        "title": plan.get("title"),
        "style": theme,
    }
