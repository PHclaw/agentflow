"""生成品牌标识 PNG（静态资源）。

为什么不直接用 SVG
----------------
邮件里不能用内联 ``<svg>``：Outlook 桌面版是 Word 排版引擎，完全不认 SVG；
Gmail 会把它整段丢掉。而 ``data:`` base64 图��� Outlook 默认也不显示
（Windows 版只加载 http/https 来源）。所以邮件里唯一的可靠做法是
**引用一个绝对 HTTPS 地址上的 PNG**。

前端 ``Logo.tsx`` 用的是同一套几何的内联 SVG（网页端没有这些限制），
两边的坐标必须同步改：那边改了这边没改，logo 就会对不上。

用法::

    python scripts/gen_brand_mark.py

产物写到 ``static/brand/``，由后端挂在 ``/static`` 下。
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

# ---- 与 frontend/src/components/layout/Logo.tsx 的 viewBox 一致 ------------
VIEW_W, VIEW_H = 68, 50

NAVY = (9, 27, 77, 255)      # #091B4D
CYAN = (0, 191, 239, 255)    # #00BFEF

STROKE = 5.5                 # 走线宽度
PAD_R = 4.6                  # 焊盘半径
PAD_W = 3.2                  # 焊盘环宽
PAD_REACH = 5.8              # 走线必须停在外沿之外，否则圆头线帽会戳进环心

# 4 倍超采样再缩小，得到抗锯齿边缘（直接按目标尺寸画会有明显锯齿）
SUPERSAMPLE = 4


def _stroke(draw: ImageDraw.ImageDraw, pts, color, width) -> None:
    """带圆头线帽的粗线。PIL 的 line() 只有平头，圆头要自己补两个端点圆。"""
    xy = [(x, y) for x, y in pts]
    draw.line(xy, fill=color, width=int(round(width)), joint="curve")
    r = width / 2
    for x, y in (xy[0], xy[-1]):
        draw.ellipse([x - r, y - r, x + r, y + r], fill=color)


def _pad(draw: ImageDraw.ImageDraw, cx: float, cy: float, color) -> None:
    draw.ellipse(
        [cx - PAD_R, cy - PAD_R, cx + PAD_R, cy + PAD_R],
        outline=color,
        width=int(round(PAD_W)),
    )


def render(width_px: int) -> Image.Image:
    """按 viewBox 比例渲染标识。"""
    unit = width_px * SUPERSAMPLE / VIEW_W
    w = int(round(VIEW_W * unit))
    h = int(round(VIEW_H * unit))
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def u(v: float) -> float:
        return v * unit

    def sw(v: float) -> float:
        return v * unit

    # A：长脚（末端带焊盘）+ 收短的右腿
    _stroke(d, [(u(30), u(3)), (u(11.9), u(35.9))], NAVY, sw(STROKE))
    _stroke(d, [(u(30), u(3)), (u(40), u(16))], NAVY, sw(STROKE))
    _pad(d, u(9), u(41), NAVY)

    # F：竖笔 + 顶横（末端带焊盘）+ 中横
    _stroke(d, [(u(35), u(24)), (u(35), u(41 - PAD_REACH))], CYAN, sw(STROKE))
    _stroke(d, [(u(35), u(24)), (u(58 - PAD_REACH), u(24))], CYAN, sw(STROKE))
    _pad(d, u(35), u(41), CYAN)
    _pad(d, u(58), u(24), CYAN)
    _stroke(d, [(u(35), u(32.5)), (u(50), u(32.5))], CYAN, sw(STROKE))

    return img.resize((width_px, int(round(width_px * VIEW_H / VIEW_W))), Image.LANCZOS)


def main() -> None:
    # static/ 在仓库根，脚本在 scripts/ 下
    out_dir = Path(__file__).resolve().parents[1] / "static" / "brand"
    out_dir.mkdir(parents=True, exist_ok=True)

    for width in (96, 192):
        path = out_dir / (f"af-mark.png" if width == 96 else "af-mark@2x.png")
        render(width).save(path, "PNG", optimize=True)
        print(f"  {path.relative_to(out_dir.parents[2])}  {path.stat().st_size} 字节")


if __name__ == "__main__":
    main()
