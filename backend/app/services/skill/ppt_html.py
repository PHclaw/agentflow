"""用 html-ppt 主题/版式生成可在浏览器演示的 HTML 幻灯片。"""
from __future__ import annotations

import html
import re
import shutil
from pathlib import Path
from typing import Any

from app.logging_setup import get_logger

logger = get_logger("ppt.html")

ROOT = Path(__file__).resolve().parents[4]
SRC_ASSETS = ROOT / "skills" / "html-ppt-skill-main" / "assets"
STATIC_ASSETS = ROOT / "static" / "html-ppt"
GENERATED_DIR = ROOT / "static" / "generated"

THEME_ALIAS = {
    "keynote": "corporate-clean",
    "dark-premium": "catppuccin-mocha",
    "glassmorphism": "glassmorphism",
    "gradient-modern": "aurora",
    "editorial": "editorial-serif",
    "business": "corporate-clean",
    "academic": "academic-paper",
    "minimal-swiss": "swiss-grid",
    "minimal": "minimal-white",
    "creative": "aurora",
    "neo-brutalist": "neo-brutalism",
    "纸与墨": "editorial-serif",
    "paper": "editorial-serif",
    "小红书": "xiaohongshu-white",
    "商务": "corporate-clean",
    "科研": "corporate-clean",
    "蓝灰": "corporate-clean",
    "简约": "corporate-clean",
}

DEFAULT_PREVIEWS = (
    ("style-a", "Corporate Clean 商务科研", "corporate-clean", "白底蓝灰、适合评测与汇报"),
    ("style-b", "Swiss Grid 网格", "swiss-grid", "克制、信息密度清晰"),
    ("style-c", "Academic Paper 学术", "academic-paper", "浅底、适合论文与科研"),
)


def ensure_html_ppt_assets() -> Path:
    STATIC_ASSETS.mkdir(parents=True, exist_ok=True)
    if not SRC_ASSETS.is_dir():
        raise FileNotFoundError("未找到 skills/html-ppt-skill-main/assets")
    mapping = {
        "fonts.css": SRC_ASSETS / "fonts.css",
        "base.css": SRC_ASSETS / "base.css",
        "runtime.js": SRC_ASSETS / "runtime.js",
        "animations.css": SRC_ASSETS / "animations" / "animations.css",
    }
    for name, src in mapping.items():
        dest = STATIC_ASSETS / name
        if src.is_file() and (not dest.is_file() or src.stat().st_mtime > dest.stat().st_mtime):
            shutil.copy2(src, dest)
    theme_src = SRC_ASSETS / "themes"
    theme_dest = STATIC_ASSETS / "themes"
    if theme_src.is_dir():
        theme_dest.mkdir(parents=True, exist_ok=True)
        for css in theme_src.glob("*.css"):
            dest = theme_dest / css.name
            if not dest.is_file() or css.stat().st_mtime > dest.stat().st_mtime:
                shutil.copy2(css, dest)
    decks = ROOT / "skills" / "html-ppt-skill-main" / "templates" / "full-decks"
    dest_decks = STATIC_ASSETS / "decks"
    dest_decks.mkdir(parents=True, exist_ok=True)
    for name in ("weekly-report", "tech-sharing"):
        src = decks / name / "style.css"
        if src.is_file():
            shutil.copy2(src, dest_decks / f"{name}.css")
    vp = ROOT / "skills" / "frontend-slides-main" / "viewport-base.css"
    if vp.is_file():
        shutil.copy2(vp, STATIC_ASSETS / "viewport-base.css")
    return STATIC_ASSETS


def resolve_theme(style: str | None) -> str:
    raw = (style or "").strip()
    key = raw.lower()
    if raw in THEME_ALIAS:
        return THEME_ALIAS[raw]
    if key in THEME_ALIAS:
        return THEME_ALIAS[key]
    dest = STATIC_ASSETS / "themes" / f"{raw}.css"
    if dest.is_file() or (SRC_ASSETS / "themes" / f"{raw}.css").is_file():
        return raw
    return "corporate-clean"


def _esc(text: Any) -> str:
    return html.escape(str(text or "").strip(), quote=True)


def _split_point(pt: str) -> tuple[str, str]:
    s = (pt or "").strip()
    if "|" in s or "｜" in s:
        parts = [x.strip() for x in re.split(r"[|｜]", s) if x.strip()]
        return (parts[0], "  ".join(parts[1:])) if parts else (s, "")
    m = re.split(r"[：:]\s*", s, maxsplit=1)
    if len(m) == 2 and 1 <= len(m[0]) <= 24:
        return m[0].strip(), m[1].strip()
    return s, ""


def _looks_kpi(points: list[str]) -> bool:
    if not points:
        return False
    hit = 0
    for p in points:
        if re.search(r"\d", p) and re.search(r"(%|万|亿|pp|倍|人|单|¥|\$)", p):
            hit += 1
    return hit >= max(2, len(points) // 2)


def _cover_inner(plan: dict[str, Any], sl: dict[str, Any], *, kicker: str) -> str:
    title = _esc(sl.get("title") or plan.get("title") or "演示文稿")
    subtitle = _esc(sl.get("subtitle") or "")
    points = [str(p).strip() for p in (sl.get("key_points") or []) if str(p).strip()]
    pills = "".join(f'<span class="pill">{_esc(p)}</span>' for p in points[:4])
    chip = _esc(points[0] if points else kicker)
    lede = subtitle or "基于多指标的横向对比"
    return f"""
    <div class="cover-head">
      <div class="logo">{title[:12]}</div>
      <div class="week-chip">{chip}</div>
    </div>
    <p class="kicker">EVALUATION REPORT · {_esc(kicker)}</p>
    <h1 class="h1 mt-s anim-fade-up" data-anim="fade-up">{title}</h1>
    <p class="lede mt-m">{_esc(lede)}</p>
    <div class="row wrap mt-l">{pills}</div>
    """


def _toc_inner(plan: dict[str, Any], slides: list[dict[str, Any]]) -> str:
    items = []
    contents = [
        s
        for s in slides
        if str(s.get("type") or "content") not in {"title", "conclusion"}
    ]
    for i, s in enumerate(contents[:6], 1):
        title = _esc(s.get("title") or f"第{i}部分")
        pts = [str(p).strip() for p in (s.get("key_points") or []) if str(p).strip()]
        dim = _esc(pts[0] if pts else "")
        items.append(
            f'<div class="card"><div class="row"><div class="h3 dim2" style="width:56px">'
            f"{i:02d}</div><div><h4>{title}</h4><p class=\"dim\">{dim}</p></div></div></div>"
        )
    return f"""
    <p class="kicker">Agenda · 目录</p>
    <h2 class="h2">今天要讲的事</h2>
    <div class="grid g2 mt-l anim-stagger-list" data-anim-target>
      {"".join(items)}
    </div>
    """


def _table_inner(sl: dict[str, Any], kicker: str) -> str:
    title = _esc(sl.get("title") or "")
    table = sl.get("table") if isinstance(sl.get("table"), dict) else {}
    headers = [str(h) for h in (table.get("headers") or [])]
    rows = table.get("rows") or []
    thead = "".join(f"<th>{_esc(h)}</th>" for h in headers)
    body_rows = []
    for row in rows[:12]:
        cells = row if isinstance(row, (list, tuple)) else [row]
        tds = "".join(
            f'<td class="num">{_esc(c)}</td>'
            if re.search(r"^[\d.]+$", str(c).strip())
            else f"<td>{_esc(c)}</td>"
            for c in cells
        )
        body_rows.append(f"<tr>{tds}</tr>")
    extra = "".join(
        f'<p class="dim mt-s">{_esc(p)}</p>'
        for p in (sl.get("key_points") or [])[:3]
        if str(p).strip()
    )
    bars = []
    for row in rows[:8]:
        cells = row if isinstance(row, (list, tuple)) else [row]
        name = str(cells[0]) if cells else ""
        nums = []
        for c in cells[1:]:
            try:
                nums.append(float(c))
            except (TypeError, ValueError):
                continue
        if not nums:
            continue
        overall = nums[-1]
        h = max(8, min(92, int(overall * 100)))
        bars.append(
            f'<div class="col"><div class="b" data-v="{overall:.3f}" style="height:{h}%"></div>'
            f'<div class="lbl">{_esc(name)}</div></div>'
        )
    chart = ""
    if bars:
        chart = f'<div class="chart mt-l"><div class="chart-bars">{"".join(bars)}</div></div>'
    return f"""
    <p class="kicker">{_esc(kicker)}</p>
    <h2 class="h2">{title}</h2>
    <div class="grid g2 mt-l" style="align-items:start">
      <div class="card" style="padding:4px 12px;overflow:auto">
        <table class="t">
          <thead><tr>{thead}</tr></thead>
          <tbody>{"".join(body_rows)}</tbody>
        </table>
      </div>
      {chart or extra}
    </div>
    """


def _cards_inner(sl: dict[str, Any], kicker: str) -> str:
    if isinstance(sl.get("table"), dict) and (sl["table"].get("rows") or sl["table"].get("headers")):
        return _table_inner(sl, kicker)
    title = _esc(sl.get("title") or "")
    points = [str(p).strip() for p in (sl.get("key_points") or []) if str(p).strip()][:6]
    pipe_rows = []
    for p in points:
        parts = [x.strip() for x in re.split(r"[|｜]", p) if x.strip()]
        if len(parts) >= 3:
            pipe_rows.append(parts)
    if len(pipe_rows) >= 2:
        width = max(len(r) for r in pipe_rows)
        sl = {
            **sl,
            "table": {
                "headers": ["项目", "模型", "得分", "说明"][:width],
                "rows": [r + [""] * (width - len(r)) for r in pipe_rows],
            },
            "key_points": [p for p in points if "|" not in p and "｜" not in p],
        }
        return _table_inner(sl, kicker)
    if 2 <= len(points) <= 4:
        cards = []
        for p in points:
            head, rest = _split_point(p)
            cards.append(
                f'<div class="kpi"><div class="label">{_esc(head)}</div>'
                f'<div class="value" style="font-size:22px;line-height:1.35">{_esc((rest or head)[:48])}</div></div>'
            )
        g = "g4" if len(cards) >= 4 else "g3" if len(cards) == 3 else "g2"
        return f"""
        <p class="kicker">{_esc(kicker)}</p>
        <h2 class="h2">{title}</h2>
        <div class="grid {g} mt-l anim-stagger-list" data-anim-target>{"".join(cards)}</div>
        """
    cards = []
    for i, p in enumerate(points or ["（本页可继续补充要点）"], 1):
        head, rest = _split_point(p)
        cards.append(
            f'<li class="card card-accent"><h4>{i:02d} · {_esc(head)}</h4>'
            f'<p class="dim">{_esc(rest)}</p></li>'
        )
    g = "g3" if len(cards) >= 3 else "g2" if len(cards) == 2 else "g1"
    return f"""
    <p class="kicker">{_esc(kicker)}</p>
    <h2 class="h2">{title}</h2>
    <ul class="grid {g} anim-stagger-list" style="list-style:none;padding:0;margin:32px 0 0;gap:14px" data-anim-target>
      {"".join(cards)}
    </ul>
    """


def _thanks_inner(sl: dict[str, Any]) -> str:
    title = _esc(sl.get("title") or "Thanks")
    sub = _esc(sl.get("subtitle") or "谢谢")
    return f"""
    <div>
      <h1 class="h1" style="font-size:120px;line-height:1"><span class="gradient-text">{title}</span></h1>
      <p class="lede" style="margin:18px auto 0">{sub}</p>
    </div>
    """


def _slide_html(
    *,
    index: int,
    total: int,
    inner: str,
    title: str,
    active: bool,
    thanks: bool,
    editable: bool,
) -> str:
    cls = "slide is-active" if active else "slide"
    if thanks:
        cls += " center tc"
    edit = ' contenteditable="true"' if editable else ""
    return f"""
  <section class="{cls}" data-title="{_esc(title)}"{edit}>
    {inner}
    <div class="deck-footer"><span class="dim2">PPT助手 · HTML</span>
      <span class="slide-number" data-current="{index}" data-total="{total}"></span></div>
  </section>
"""


def render_deck_html(
    plan: dict[str, Any],
    *,
    theme: str,
    kicker: str = "",
    editable: bool = True,
    preview_only: bool = False,
) -> str:
    ensure_html_ppt_assets()
    theme = resolve_theme(theme)
    title = str(plan.get("title") or "演示文稿")
    kicker = kicker or str(plan.get("style") or "演示")
    slides = list(plan.get("slides") or [])
    if preview_only:
        cover = slides[0] if slides else {"type": "title", "title": title, "key_points": []}
        inner = _cover_inner(plan, cover, kicker=kicker)
        body = _slide_html(
            index=1,
            total=1,
            inner=inner,
            title=str(cover.get("title") or title),
            active=True,
            thanks=False,
            editable=editable,
        )
    else:
        parts: list[str] = []
        total = len(slides)
        for i, sl in enumerate(slides, 1):
            st = str(sl.get("type") or "content")
            if st in {"conclusion", "thanks"}:
                inner = _thanks_inner(sl)
                thanks = True
            elif st == "title" or (i == 1 and st not in {"content", "table", "toc"}):
                inner = _cover_inner(plan, sl, kicker=kicker)
                thanks = False
            elif st == "toc":
                inner = _toc_inner(plan, slides)
                thanks = False
            elif st == "table" or sl.get("table"):
                inner = _table_inner(sl, kicker)
                thanks = False
            else:
                inner = _cards_inner(sl, kicker)
                thanks = False
            parts.append(
                _slide_html(
                    index=i,
                    total=total,
                    inner=inner,
                    title=str(sl.get("title") or f"第{i}页"),
                    active=i == 1,
                    thanks=thanks,
                    editable=editable,
                )
            )
        body = "".join(parts)
    themes = "tokyo-night,editorial-serif,corporate-clean,aurora,xiaohongshu-white,swiss-grid,academic-paper,magazine-bold"
    deck_css = "tech-sharing" if theme in {"tokyo-night", "catppuccin-mocha", "dracula"} else "weekly-report"
    tpl = "tpl-tech-sharing" if deck_css == "tech-sharing" else "tpl-weekly-report"
    return f"""<!DOCTYPE html>
<html lang="zh-CN" data-theme="{_esc(theme)}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_esc(title)}</title>
<link rel="stylesheet" href="/static/html-ppt/viewport-base.css">
<link rel="stylesheet" href="/static/html-ppt/fonts.css">
<link rel="stylesheet" href="/static/html-ppt/base.css">
<link rel="stylesheet" href="/static/html-ppt/animations.css">
<link rel="stylesheet" id="theme-link" href="/static/html-ppt/themes/{_esc(theme)}.css">
<link rel="stylesheet" href="/static/html-ppt/decks/{deck_css}.css">
<style>
.deck-viewport{{background:var(--bg,#fff)}}
.deck-stage{{width:1920px;height:1080px;background:var(--bg);overflow:hidden}}
.deck-stage .deck{{width:1920px;height:1080px}}
.deck-stage .slide{{width:1920px;height:1080px;visibility:visible}}
.t{{width:100%;border-collapse:collapse;font-size:15px}}
.t th,.t td{{padding:10px 12px;text-align:left;border-bottom:1px solid var(--border)}}
.t th{{font-size:12px;letter-spacing:.08em;color:var(--text-3);font-weight:600}}
.t td.num{{font-variant-numeric:tabular-nums;text-align:right}}
.t thead th{{background:var(--accent);color:#fff}}
</style>
</head>
<body class="{tpl}" data-themes="{themes}" data-theme-base="/static/html-ppt/themes/" style="background:var(--bg)">
<div class="deck-viewport">
<main class="deck-stage" id="deckStage">
<div class="deck">
{body}
</div>
</main>
</div>
<script src="/static/html-ppt/runtime.js"></script>
<script>
(function(){{
  var stage=document.getElementById('deckStage');
  if(!stage) return;
  function fit(){{
    var s=Math.min(window.innerWidth/1920, window.innerHeight/1080);
    var x=(window.innerWidth-1920*s)/2, y=(window.innerHeight-1080*s)/2;
    stage.style.transform='translate('+x+'px,'+y+'px) scale('+s+')';
  }}
  fit();
  addEventListener('resize', fit);
}})();
</script>
</body>
</html>
"""


def write_html(path: Path, html_text: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html_text, encoding="utf-8")
    rel = path.relative_to(ROOT / "static")
    return "/static/" + str(rel).replace("\\", "/")
