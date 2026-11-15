"""把 assets/banner.svg 变成会动的 assets/banner.gif。

做法：以静态横幅为底，逐帧往 </svg> 前注入动画元素，再用 Edge headless
逐帧截图，最后交给 ffmpeg 合成 GIF。一轮循环里在跑的东西：

    右侧节点图   走线上有数据流光点流过
    左侧标识     笔画上跑电流，笔画末端的焊盘荡开涟漪
    字标         一道斜向高光扫过 "agentflow"
    特性胶囊     轮流被点亮
    版本胶囊     描边轻微呼吸

为什么不用动画 SVG：GitHub 会把 SVG 交给 camo 代理并做净化，脚本一定被剥掉，
SMIL/CSS 动画在部分平台也不跑；GIF 是无条件播放的，和当初从 SVG 换 PNG 同一个理由。

用法：
    py scripts/build-banner-gif.py            # 出 assets/banner.gif
    py scripts/build-banner-gif.py --keep     # 保留中间帧
"""
import math
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SVG_IN = REPO / 'assets' / 'banner.svg'
GIF_OUT = REPO / 'assets' / 'banner.gif'
FRAME_DIR = REPO / 'assets' / '_banner_frames'

EDGE_CANDIDATES = [
    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
]

# ---- 动画参数 -------------------------------------------------------------
W, H = 1600, 440
FRAMES = 30          # 30 帧 @ 12fps = 2.5 秒一轮
FPS = 12
COMET = 5            # 每个光点拖几节尾巴，读起来才有"流过去"的方向感
TAIL_STEP = 0.045    # 尾巴每节落后的相位
DOT_R = 3.2
FONT = "'Segoe UI', 'PingFang SC', 'Microsoft YaHei', system-ui, sans-serif"

# 走线端点（banner 坐标；右侧节点图整体 translate(30,0)，这里已换算过）
# 前三元组是起点，后两元组是终点
H_WIRES = [
    (1080, 152, 1150, 152),   # 触发器 → LLM
    (1300, 152, 1370, 152),   # LLM   → 回复
    (1080, 312, 1150, 312),   # 知识库 → 工具
    (1300, 312, 1370, 312),   # 工具  → 条件
]
# 两段竖虚线，自上而下走
V_WIRES = [
    (1005, 178, 1005, 258),
    (1225, 178, 1225, 258),
]

CYAN = '#38C9F5'
WHITE = '#E7EBF5'

# ---- 字标扫光 -------------------------------------------------------------
TEXT = 'agentflow'
TEXT_POS = (246, 200)                  # 和 banner.svg 里的 <text> 完全一致，才能贴住字母
TEXT_SIZE = 66
TEXT_X0, TEXT_X1 = 244, 536            # 字标左右边界
TEXT_Y0, TEXT_Y1 = 126, 224            # 上下留够，"g" 的降部也在里头
SWEEP_W = 110                          # 光带宽；太窄在 12fps 下会觉得在跳，太宽就像整字一起亮
SWEEP_SPAN = 0.6                       # 一轮里用来扫的时间，其余留白，扫光才是"偶发事件"
SWEEP_SKEW = 18                        # 倾斜角度，斜着扫比竖直更有光泽感

# ---- 标识（Logo）笔画 -----------------------------------------------------
# 坐标由 AFMark 的 translate(100,132) scale(1.72) 换算而来，和 banner.svg 里的
# <path d="M30 3 L11.9 35.9"> 等一一对应
LOGO_X0, LOGO_Y0, LOGO_SCALE = 100, 132, 1.72
LOGO_STROKES = [
    # (起点, 终点, 颜色)：A 的两笔从顶点向外，F 的三笔
    ((30, 3), (11.9, 35.9), WHITE),      # A 长脚
    ((30, 3), (40, 16), WHITE),          # A 短脚
    ((35, 24), (35, 35.2), CYAN),        # F 竖笔
    ((35, 24), (52.2, 24), CYAN),        # F 顶横
    ((35, 32.5), (50, 32.5), CYAN),      # F 中横
]
LOGO_PADS = [(9, 41), (35, 41), (58, 24)]   # 焊盘圆心，做"信号抵达"的涟漪

# ---- 特性胶囊与版本胶囊 ---------------------------------------------------
CHIPS = [(248, 118), (378, 134), (524, 124), (660, 110), (782, 110)]
CHIP_Y, CHIP_H = 290, 34
VERSION_BOX = (560, 166, 92, 34)


def logo_pt(x: float, y: float) -> tuple:
    """标识内部坐标 → 横幅坐标。"""
    return (LOGO_X0 + LOGO_SCALE * x, LOGO_Y0 + LOGO_SCALE * y)


def ease(p: float) -> float:
    """两端慢、中间快，光点不会像匀速滑块那样生硬。"""
    return p * p * (3 - 2 * p)


def fade(p: float) -> float:
    """进线段淡入、出线段淡出，循环处不会突然出现/消失。"""
    if p < 0.18:
        return p / 0.18
    if p > 0.82:
        return (1 - p) / 0.18
    return 1.0


def comet(x0, y0, x1, y1, phase: float, r: float, peak: float,
          color: str = CYAN, tail_step: float = TAIL_STEP) -> str:
    """一段走线上的一串光点：头亮尾暗，且整体沿线段推进。"""
    out = []
    for k in range(COMET):
        p = phase - k * tail_step
        if p < 0 or p > 1:
            continue
        t = ease(p)
        x = x0 + (x1 - x0) * t
        y = y0 + (y1 - y0) * t
        # 头节点最亮最大，尾巴逐节衰减
        decay = (1 - k / COMET) ** 1.6
        a = fade(p) * decay * peak
        if a <= 0.01:
            continue
        rr = r * (0.45 + 0.55 * decay)
        # 外圈柔光 + 芯点：GIF 调色板有限，靠两层比靠渐变实惠
        out.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{rr * 2.6:.1f}" '
            f'fill="{color}" fill-opacity="{a * 0.16:.3f}"/>'
        )
        out.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{rr:.1f}" '
            f'fill="{color}" fill-opacity="{min(a, 1):.3f}"/>'
        )
    return ''.join(out)


def sweep_defs() -> str:
    """扫光要贴着字母轮廓，所以把字标原样复刻一份当裁剪路径。

    两个 tspan 的写法必须和 banner.svg 一致：letter-spacing 在 tspan 边界也生效，
    合并成一个 text 会让形状差几个像素，扫光的边就露出来了。
    """
    x, y = TEXT_POS
    return (
        '<defs>'
        '<linearGradient id="_afgSweep" x1="0" y1="0" x2="1" y2="0">'
        '<stop offset="0" stop-color="#FFFFFF" stop-opacity="0"/>'
        '<stop offset="0.42" stop-color="#CFEFFF" stop-opacity="0.95"/>'
        '<stop offset="0.58" stop-color="#CFEFFF" stop-opacity="0.95"/>'
        '<stop offset="1" stop-color="#FFFFFF" stop-opacity="0"/>'
        '</linearGradient>'
        # 压暗层要沿光带挖空，挖空区就用这段黑白渐变描述
        '<linearGradient id="_afgGap" x1="0" y1="0" x2="1" y2="0">'
        '<stop offset="0" stop-color="#FFFFFF"/>'
        '<stop offset="0.3" stop-color="#000000"/>'
        '<stop offset="0.7" stop-color="#000000"/>'
        '<stop offset="1" stop-color="#FFFFFF"/>'
        '</linearGradient>'
        '<clipPath id="_afgText">'
        f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{TEXT_SIZE}" '
        'font-weight="600" letter-spacing="-2">'
        '<tspan>agent</tspan><tspan>flow</tspan></text>'
        '</clipPath>'
        '</defs>'
    )


def sweep_env(q: float) -> float:
    """压暗层要跟着光带一起淡入淡出。

    不然 p≈0 时"光带之外全暗"已经生效，从循环末尾切回第一帧，字标会先暗一下。
    """
    if q < 0.12:
        return q / 0.12
    if q > 0.82:
        return (1 - q) / 0.18
    return 1.0


def text_sweep(i: int) -> str:
    """一道斜光扫过字标，像探照灯划过去。

    字标本来就是近白色，单靠提亮看不出多少变化，所以让光带之外压暗、
    光带之内提亮：一暗一亮，扫过去的动作才立得住。
    其余时间什么都不画，扫光才是"偶发事件"而不是常驻特效。
    """
    p = i / FRAMES
    if p >= SWEEP_SPAN:
        return ''
    q = p / SWEEP_SPAN
    # 从字标左侧之外扫到右侧之外
    x = TEXT_X0 - SWEEP_W + (TEXT_X1 - TEXT_X0 + SWEEP_W) * q
    # skewX 只改 x，所以按字标中心高度补偿，让光带斜着落正
    x += math.tan(math.radians(SWEEP_SKEW)) * (TEXT_Y0 + TEXT_Y1) / 2
    tw, th = TEXT_X1 - TEXT_X0, TEXT_Y1 - TEXT_Y0
    env = sweep_env(q)
    return (
        # 掩膜：整块字标先铺白（压暗层照常盖住），再沿光带涂黑挖空
        '<defs><mask id="_afgDim" maskUnits="userSpaceOnUse" '
        f'x="{TEXT_X0}" y="{TEXT_Y0}" width="{tw}" height="{th}">'
        f'<rect x="{TEXT_X0}" y="{TEXT_Y0}" width="{tw}" height="{th}" fill="#FFFFFF"/>'
        f'<g transform="skewX(-{SWEEP_SKEW})">'
        f'<rect x="{x:.1f}" y="{TEXT_Y0}" width="{SWEEP_W}" height="{th}" '
        'fill="url(#_afgGap)"/>'
        '</g></mask></defs>'
        '<g clip-path="url(#_afgText)">'
        f'<rect x="{TEXT_X0}" y="{TEXT_Y0}" width="{tw}" height="{th}" '
        f'fill="#04101F" fill-opacity="{0.35 * env:.3f}" mask="url(#_afgDim)"/>'
        f'<g transform="skewX(-{SWEEP_SKEW})">'
        f'<rect x="{x:.1f}" y="{TEXT_Y0}" width="{SWEEP_W}" height="{th}" '
        'fill="url(#_afgSweep)"/>'
        '</g></g>'
    )


def logo_flow(i: int) -> str:
    """标识的笔画上跑电流，笔画末端的焊盘荡开涟漪——和右侧节点图同一个世界。"""
    p = i / FRAMES
    out = []
    for idx, (a, b, color) in enumerate(LOGO_STROKES):
        x0, y0 = logo_pt(*a)
        x1, y1 = logo_pt(*b)
        # 笔画短，尾巴间距得放大，否则拖尾挤成一坨
        out.append(comet(
            x0, y0, x1, y1, (p + idx * 0.13) % 1.0,
            3.4, 0.85, color=color, tail_step=0.1,
        ))
    for idx, (px, py) in enumerate(LOGO_PADS):
        t = (p + idx * 0.33) % 1.0
        if t >= 0.4:
            continue
        k = t / 0.4
        cx, cy = logo_pt(px, py)
        out.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{8 + 13 * k:.1f}" fill="none" '
            f'stroke="{CYAN}" stroke-opacity="{(1 - k) * 0.45:.3f}" stroke-width="1.8"/>'
        )
    return ''.join(out)


def chip_focus(i: int) -> str:
    """特性胶囊轮流被点亮，给画面一点轻快的节拍。"""
    p = i / FRAMES
    n = len(CHIPS)
    pos = p * n
    out = []
    for idx, (x, w) in enumerate(CHIPS):
        d = abs(pos - idx - 0.5)
        d = min(d, n - d)      # 按环算距离，循环接缝处才不会突然全灭
        k = max(0.0, 1 - d / 0.55)
        if k <= 0.02:
            continue
        out.append(
            f'<rect x="{x}" y="{CHIP_Y}" width="{w}" height="{CHIP_H}" rx="17" '
            f'fill="{CYAN}" fill-opacity="{0.12 * k:.3f}" '
            f'stroke="{CYAN}" stroke-opacity="{0.8 * k:.3f}"/>'
        )
    return ''.join(out)


def version_breath(i: int) -> str:
    """版本胶囊的描边轻微呼吸，不抢戏，但画面不会死。"""
    a = 0.5 + 0.5 * math.sin(2 * math.pi * i / FRAMES)
    x, y, w, h = VERSION_BOX
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="17" fill="none" '
        f'stroke="{CYAN}" stroke-opacity="{0.10 + 0.32 * a:.3f}"/>'
    )


def frame_overlay(i: int) -> str:
    p = i / FRAMES
    parts = [sweep_defs(), '<g clip-path="inset(0)">']
    # 上行走线与下行走线错开半轮，画面不会整片一起闪
    for idx, (x0, y0, x1, y1) in enumerate(H_WIRES):
        phase = p if idx < 2 else (p + 0.5) % 1.0
        parts.append(comet(x0, y0, x1, y1, phase, DOT_R, 1.0))
    for idx, (x0, y0, x1, y1) in enumerate(V_WIRES):
        phase = (p + 0.25 + idx * 0.15) % 1.0
        parts.append(comet(x0, y0, x1, y1, phase, DOT_R * 0.8, 0.75))
    # 左侧的动静：标识通电、字标扫光、胶囊轮流点亮，三者相位天然错开
    parts.append(logo_flow(i))
    parts.append(text_sweep(i))
    parts.append(chip_focus(i))
    parts.append(version_breath(i))
    parts.append('</g>')
    return ''.join(parts)


def find_edge() -> str:
    for c in EDGE_CANDIDATES:
        if Path(c).exists():
            return c
    raise SystemExit('没找到 msedge.exe，把路径填进 EDGE_CANDIDATES')


def main() -> int:
    if not SVG_IN.exists():
        raise SystemExit(f'缺少 {SVG_IN}')
    base = SVG_IN.read_text(encoding='utf-8')
    if '</svg>' not in base:
        raise SystemExit('banner.svg 结构异常：没有 </svg>')

    if FRAME_DIR.exists():
        shutil.rmtree(FRAME_DIR)
    FRAME_DIR.mkdir(parents=True)

    edge = find_edge()
    print(f'[1/3] 生成 {FRAMES} 帧 SVG（Edge: {edge}）')

    pngs = []
    for i in range(FRAMES):
        svg = base.replace('</svg>', frame_overlay(i) + '\n</svg>')
        svg_path = FRAME_DIR / f'f{i:02d}.svg'
        svg_path.write_text(svg, encoding='utf-8')

        png_path = FRAME_DIR / f'f{i:02d}.png'
        subprocess.run(
            [
                edge, '--headless', '--disable-gpu', '--hide-scrollbars',
                '--force-device-scale-factor=1',
                f'--window-size={W},{H}',
                f'--screenshot={png_path}',
                'file:///' + str(svg_path).replace('\\', '/'),
            ],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
        )
        if not png_path.exists():
            raise SystemExit(f'第 {i} 帧渲染失败')
        pngs.append(png_path)
        print(f'      帧 {i + 1}/{FRAMES}', end='\r')
    print()

    print('[2/3] 合成 GIF（先生成全局调色板，避免逐帧偏色）')
    palette = FRAME_DIR / 'palette.png'
    subprocess.run(
        ['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
         '-framerate', str(FPS), '-i', str(FRAME_DIR / 'f%02d.png'),
         '-vf', 'palettegen=max_colors=160:stats_mode=diff', str(palette)],
        check=True,
    )
    subprocess.run(
        ['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
         '-framerate', str(FPS), '-i', str(FRAME_DIR / 'f%02d.png'),
         '-i', str(palette),
         '-lavfi', 'paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle',
         '-loop', '0', str(GIF_OUT)],
        check=True,
    )

    size_mb = GIF_OUT.stat().st_size / 1048576
    print(f'[3/3] 完成 {GIF_OUT.relative_to(REPO)}  {size_mb:.2f} MB  '
          f'{W}x{H} @ {FPS}fps / {FRAMES} 帧')

    if '--keep' not in sys.argv:
        shutil.rmtree(FRAME_DIR, ignore_errors=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
