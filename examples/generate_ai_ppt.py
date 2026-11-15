#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AI 介绍 PPT 自动生成示例
=========================

这是「示例二」：演示如何用代码自动生成一份结构完整的演示文稿。

产出结构（共 13 页）：
    封面页  →  目录页  →  章节分隔  →  内容页 ×8  →  总结页  →  结束页

内容要素覆盖：
    · AI 的定义与发展历程
    · 核心技术领域（机器学习 / 深度学习 / NLP / 计算机视觉）
    · 典型应用场景（医疗 / 金融 / 教育 / 自动驾驶 等）
    · 当前挑战与未来趋势

设计要点：
    · 内容与渲染分离：内容全部写在 CONTENT 里，排版交给渲染函数，
      换主题只需改 PALETTE，换内容只需改 CONTENT
    · 深→浅→深的「三明治」配色：封面与结尾用深色，内页用浅色
    · 每页都有视觉元素（图形、占位框、色块），不留纯文字页
    · 占位框标出「该放什么图」，方便后续替换成真实素材

用法：
    python examples/generate_ai_ppt.py                # 生成到当前目录
    python examples/generate_ai_ppt.py -o out.pptx    # 指定输出路径
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_LINE_DASH_STYLE
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

# --------------------------------------------------------------------------
# 一、主题：配色与字体
# --------------------------------------------------------------------------

# 16:9 画布
SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)

# 页面边距
MARGIN = Inches(0.75)
CONTENT_W = SLIDE_W - MARGIN * 2


@dataclass(frozen=True)
class Palette:
    """配色。深海军蓝为主，青色为辅助，薄荷绿作锐利强调。"""

    primary: RGBColor = RGBColor(0x0F, 0x1B, 0x3C)  # 深海军蓝（主，占 ~65%）
    secondary: RGBColor = RGBColor(0x1C, 0x72, 0x93)  # 青（辅）
    accent: RGBColor = RGBColor(0x00, 0xD9, 0xC0)  # 薄荷绿（强调，仅小面积）
    surface: RGBColor = RGBColor(0xF4, 0xF7, 0xFB)  # 内页底色
    card: RGBColor = RGBColor(0xFF, 0xFF, 0xFF)  # 卡片
    ink: RGBColor = RGBColor(0x14, 0x1B, 0x2E)  # 正文
    muted: RGBColor = RGBColor(0x64, 0x71, 0x89)  # 辅助信息
    line: RGBColor = RGBColor(0xD8, 0xDF, 0xEA)  # 分隔线
    white: RGBColor = RGBColor(0xFF, 0xFF, 0xFF)


PALETTE = Palette()

# 中文字体要在 latin 与 ea（East Asian）两个槽位都设置，否则会回退成宋体
FONT_HEAD = "微软雅黑"
FONT_BODY = "微软雅黑"


# --------------------------------------------------------------------------
# 二、内容：全部文案集中在这里
# --------------------------------------------------------------------------


@dataclass
class Slide:
    """一页内容。kind 决定用哪个渲染函数。"""

    kind: str
    title: str = ""
    kicker: str = ""
    subtitle: str = ""
    bullets: list[tuple[str, str]] = field(default_factory=list)
    items: list[tuple[str, str, str]] = field(default_factory=list)
    milestones: list[tuple[str, str]] = field(default_factory=list)
    left: tuple[str, list[str]] | None = None
    right: tuple[str, list[str]] | None = None
    placeholder: str = ""
    footer: str = ""


COVER = Slide(
    kind="cover",
    title="人工智能介绍",
    subtitle="从技术原理到产业落地",
    footer="2026 · 技术分享",
)

TOC = Slide(
    kind="toc",
    title="目录",
    kicker="CONTENTS",
    items=[
        ("01", "AI 的定义与发展历程", "从图灵测试到大模型时代"),
        ("02", "核心技术领域", "机器学习、深度学习、自然语言处理、计算机视觉"),
        ("03", "典型应用场景", "医疗、金融、教育、自动驾驶等行业实践"),
        ("04", "挑战与未来趋势", "数据隐私、算力成本、可解释性与智能体"),
    ],
)

SLIDES: list[Slide] = [
    # ---------- 01 定义与发展历程 ----------
    Slide(
        kind="section",
        kicker="PART 01",
        title="AI 的定义与发展历程",
        subtitle="一条走了七十年、正在加速的技术曲线",
    ),
    Slide(
        kind="content",
        kicker="定义",
        title="什么是人工智能",
        bullets=[
            ("研究目标", "让机器表现出类似人类的感知、理解、推理与决策能力"),
            ("核心能力", "感知 → 理解 → 推理 → 决策 → 生成，构成完整的能力闭环"),
            ("范式转变", "从「人工编写规则」转向「从数据中自动学习规律」"),
        ],
        placeholder="此处插入：AI 能力雷达图（感知 / 理解 / 推理 / 决策 / 生成）",
    ),
    Slide(
        kind="timeline",
        kicker="历程",
        title="七十年，五个关键节点",
        milestones=[
            ("1956", "达特茅斯会议首次提出「人工智能」，学科诞生"),
            ("1997", "深蓝战胜国际象棋世界冠军，符号推理达到高峰"),
            ("2012", "AlexNet 夺冠，深度学习正式引爆"),
            ("2017", "Transformer 架构提出，为通用大模型奠基"),
            ("2022", "生成式 AI 走向大众，模型开始具备通用任务能力"),
        ],
        placeholder="此处插入：AI 发展历程时间轴（可与本页节点叠合成一张长图）",
    ),
    # ---------- 02 核心技术领域 ----------
    Slide(
        kind="section",
        kicker="PART 02",
        title="核心技术领域",
        subtitle="四根支柱，共同支撑起今天的 AI 能力",
    ),
    Slide(
        kind="grid",
        kicker="技术栈",
        title="四大核心技术",
        items=[
            ("机器学习", "Machine Learning", "从数据中自动归纳规律，是 AI 的方法论基础"),
            ("深度学习", "Deep Learning", "多层神经网络自动学习特征，擅长高维数据"),
            ("自然语言处理", "NLP", "让机器理解并生成人类语言，是大模型的直接产物"),
            ("计算机视觉", "Computer Vision", "让机器「看懂」图像与视频，落地最成熟的领域"),
        ],
        placeholder="此处插入：技术栈分层示意图（基础层 / 算法层 / 应用层）",
    ),
    Slide(
        kind="compare",
        kicker="技术对比",
        title="机器学习 vs 深度学习",
        left=(
            "机器学习",
            [
                "依赖人工特征工程",
                "对数据量要求中等",
                "可解释性较好",
                "适合结构化数据与业务规则明确的场景",
            ],
        ),
        right=(
            "深度学习",
            [
                "自动学习特征表示",
                "需要大规模数据与算力",
                "可解释性相对较弱",
                "擅长图像、语音、自然语言等非结构化数据",
            ],
        ),
        placeholder="此处插入：两种方法的错误率对比曲线",
    ),
    # ---------- 03 典型应用场景 ----------
    Slide(
        kind="section",
        kicker="PART 03",
        title="典型应用场景",
        subtitle="技术只有落到具体行业，才真正产生价值",
    ),
    Slide(
        kind="grid",
        kicker="行业落地",
        title="六个已经跑通的场景",
        items=[
            ("医疗健康", "Healthcare", "医学影像辅助诊断、蛋白质结构预测加速新药研发"),
            ("金融科技", "Fintech", "实时风控反欺诈、智能投顾、量化投研"),
            ("教育培训", "Education", "个性化学习路径规划、作业智能批改"),
            ("自动驾驶", "Autonomous Driving", "多传感器融合感知、实时路径规划与决策"),
            ("智能制造", "Manufacturing", "视觉质检、设备预测性维护"),
            ("内容创作", "Content", "文案生成、图像与视频生成、多语言翻译"),
        ],
        placeholder="此处插入：各行业 AI 渗透率对比图",
    ),
    Slide(
        kind="two-col",
        kicker="深入案例",
        title="医疗与金融：两条最快的落地路径",
        left=(
            "医疗健康",
            [
                "医学影像识别在部分病种上已超过初级放射科医生",
                "蛋白质结构预测把新药前期研发周期从数年压缩到数月",
                "关键约束：数据隐私与临床合规",
            ],
        ),
        right=(
            "金融科技",
            [
                "风控决策从秒级压缩到毫秒级，欺诈识别率显著提升",
                "智能投顾把专业投研服务下沉到长尾客户",
                "关键约束：可解释性与监管审计",
            ],
        ),
        placeholder="此处插入：两个行业的 AI 应用渗透曲线",
    ),
    # ---------- 04 挑战与趋势 ----------
    Slide(
        kind="section",
        kicker="PART 04",
        title="当前挑战与未来趋势",
        subtitle="既不高估短期，也不低估长期",
    ),
    Slide(
        kind="grid",
        kicker="挑战",
        title="四个必须正视的问题",
        items=[
            ("数据与隐私", "Data & Privacy", "高质量数据稀缺，合规要求持续提高"),
            ("算力成本", "Compute Cost", "大模型训练与推理成本高企，投入产出需要算账"),
            ("可解释性", "Explainability", "黑盒决策难以满足监管与信任要求"),
            ("安全与伦理", "Safety & Ethics", "深度伪造、偏见放大、责任归属尚无定论"),
        ],
        placeholder="此处插入：挑战影响程度矩阵（概率 × 影响）",
    ),
    Slide(
        kind="grid",
        kicker="趋势",
        title="四个确定的演进方向",
        items=[
            ("多模态融合", "Multimodal", "文本、图像、音频、视频统一表征，理解更接近人类"),
            ("端侧小模型", "On-device", "更低成本、更低延迟，隐私数据不出端"),
            ("智能体", "AI Agent", "从「回答问题」走向「自主规划并完成任务」"),
            ("人机协作", "Human + AI", "AI 成为生产力放大器，而非简单替代"),
        ],
        placeholder="此处插入：未来五年技术成熟度曲线",
    ),
]

SUMMARY = Slide(
    kind="summary",
    kicker="总结",
    title="四句话记住 AI",
    items=[
        ("01", "已经从实验室走向千行百业", "不再是概念，而是正在发生的生产力变革"),
        ("02", "技术主线清晰", "数据驱动 → 深度学习 → 大模型 → 智能体"),
        ("03", "落地靠三件事", "选对场景、保证数据质量、具备工程能力"),
        ("04", "保持理性", "既不高估短期，也不低估长期"),
    ],
)

CLOSING = Slide(
    kind="closing",
    title="谢谢观看",
    subtitle="欢迎交流与提问",
    footer="AI Introduction · 2026",
)


# --------------------------------------------------------------------------
# 三、绘制工具
# --------------------------------------------------------------------------


def set_font(run, name: str = FONT_BODY, size: float = 14,
             bold: bool = False, color: RGBColor | None = None,
             italic: bool = False) -> None:
    """设置字体。中文必须同时写 latin 与 ea 两个槽位。"""
    font = run.font
    font.name = name
    font.size = Pt(size)
    font.bold = bold
    font.italic = italic
    font.color.rgb = color or PALETTE.ink

    # _Run 的 XML 节点是 <a:r>，即 run._r
    rpr = run._r.get_or_add_rPr()
    for tag in ("a:latin", "a:ea", "a:cs"):
        el = rpr.find(qn(tag))
        if el is None:
            el = rpr.makeelement(qn(tag), {})
            rpr.append(el)
        el.set("typeface", name)


def add_textbox(slide, left, top, width, height,
                align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP):
    """文本框。margin 置 0，避免文字与形状边缘对不齐。"""
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    tf.paragraphs[0].alignment = align
    return box, tf


def add_para(tf, text: str, size: float = 14, bold: bool = False,
             color: RGBColor | None = None, space_before: float = 0,
             space_after: float = 0, first: bool = False,
             line_spacing: float = 1.25, align=PP_ALIGN.LEFT,
             font: str = FONT_BODY, italic: bool = False):
    """追加一个段落。first=True 表示复用 tf 里的首个空段落。"""
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.alignment = align
    p.line_spacing = line_spacing
    p.space_before = Pt(space_before)
    p.space_after = Pt(space_after)
    run = p.add_run()
    run.text = text
    set_font(run, name=font, size=size, bold=bold, color=color, italic=italic)
    return p


def add_rect(slide, left, top, width, height, fill: RGBColor,
             shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius: float = 0.06,
             line: RGBColor | None = None, line_w: float = 1.0):
    """纯色块。圆角半径用 adjustment 调，默认轻微圆角。"""
    shp = slide.shapes.add_shape(shape, left, top, width, height)
    shp.fill.solid()
    shp.fill.fore_color.rgb = fill
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line
        shp.line.width = Pt(line_w)
    shp.shadow.inherit = False
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        try:
            shp.adjustments[0] = radius
        except (IndexError, ValueError):
            pass
    return shp


def add_number_badge(slide, left, top, size, text: str, fill: RGBColor,
                     text_color: RGBColor, font_size: float = 14,
                     shape=MSO_SHAPE.OVAL, radius: float = 0.25):
    """编号圆牌。

    必须清掉内部边距：椭圆的内接文字区本就比外框小一圈，
    再叠加默认的 0.1" 左右边距，「01」这种两位数会被挤成上下两行。
    """
    badge = add_rect(slide, left, top, size, size, fill,
                     shape=shape, radius=radius)
    tf = badge.text_frame
    tf.word_wrap = False
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    run = p.add_run()
    run.text = text
    set_font(run, size=font_size, bold=True, color=text_color)
    return badge


def add_visual_placeholder(slide, left, top, width, height, label: str):
    """视觉元素占位框。

    用虚线框明确标出「这里该放什么图」，替换素材时按框尺寸裁图即可。
    """
    shp = add_rect(slide, left, top, width, height,
                   fill=RGBColor(0xEC, 0xF2, 0xF9),
                   line=PALETTE.secondary, line_w=1.25)
    shp.line.dash_style = MSO_LINE_DASH_STYLE.DASH

    tf = shp.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = tf.margin_right = Inches(0.3)
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    run = p.add_run()
    run.text = label
    set_font(run, size=12, color=PALETTE.secondary, italic=True)
    return shp


def new_slide(prs, bg: RGBColor):
    """新建一页并铺底色。用全屏矩形代替背景，比改版式更直观。"""
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # 6 = 空白版式
    add_rect(slide, 0, 0, SLIDE_W, SLIDE_H, bg, shape=MSO_SHAPE.RECTANGLE)
    return slide


def add_page_number(slide, index: int, total: int, dark: bool = False):
    """页码。深色页用浅字，浅色页用灰字。"""
    color = RGBColor(0x8A, 0x99, 0xB0) if dark else PALETTE.muted
    box, tf = add_textbox(slide, SLIDE_W - MARGIN - Inches(1.2),
                          SLIDE_H - Inches(0.62), Inches(1.2), Inches(0.3),
                          align=PP_ALIGN.RIGHT)
    add_para(tf, f"{index:02d} / {total:02d}", size=10, color=color, first=True)


def add_footer(slide, text: str, dark: bool = False):
    color = RGBColor(0x8A, 0x99, 0xB0) if dark else PALETTE.muted
    box, tf = add_textbox(slide, MARGIN, SLIDE_H - Inches(0.62),
                          Inches(6), Inches(0.3))
    add_para(tf, text, size=10, color=color, first=True)


def add_kicker_and_title(slide, kicker: str, title: str,
                         on_dark: bool = False) -> float:
    """页眉：小标签 + 大标题。不用标题下划线（那是 AI 生成稿的典型痕迹）。"""
    y = Inches(0.62)
    if kicker:
        box, tf = add_textbox(slide, MARGIN, y, CONTENT_W, Inches(0.3))
        add_para(tf, kicker.upper(), size=11, bold=True,
                 color=PALETTE.accent if on_dark else PALETTE.secondary, first=True)
        y += Inches(0.36)

    box, tf = add_textbox(slide, MARGIN, y, CONTENT_W, Inches(0.7))
    add_para(tf, title, size=32, bold=True, font=FONT_HEAD,
             color=PALETTE.white if on_dark else PALETTE.primary,
             line_spacing=1.1, first=True)
    return y + Inches(0.95)


# --------------------------------------------------------------------------
# 四、各类页面渲染
# --------------------------------------------------------------------------


def render_cover(prs, s: Slide, index: int, total: int):
    slide = new_slide(prs, PALETTE.primary)

    # 右侧装饰：同心圆，呼应「神经网络」的视觉母题
    for d in (4.6, 3.4, 2.2):
        size = Inches(d)
        cx = SLIDE_W - Inches(1.9)
        cy = SLIDE_H / 2
        circle = add_rect(slide, int(cx - size / 2), int(cy - size / 2), size, size,
                          PALETTE.primary, shape=MSO_SHAPE.OVAL,
                          line=PALETTE.accent, line_w=1.0)
        circle.fill.background()
        circle.line.color.rgb = PALETTE.accent

    # 左侧色条：贯穿全篇的视觉母题之一
    add_rect(slide, MARGIN, Inches(2.28), Inches(0.09), Inches(1.5),
             PALETTE.accent, shape=MSO_SHAPE.RECTANGLE)

    box, tf = add_textbox(slide, MARGIN + Inches(0.36), Inches(2.2),
                          Inches(7.4), Inches(1.0))
    add_para(tf, s.kicker or "AI INTRODUCTION", size=12, bold=True,
             color=PALETTE.accent, first=True)

    box, tf = add_textbox(slide, MARGIN + Inches(0.36), Inches(2.62),
                          Inches(7.4), Inches(1.4))
    add_para(tf, s.title, size=54, bold=True, font=FONT_HEAD,
             color=PALETTE.white, line_spacing=1.05, first=True)

    box, tf = add_textbox(slide, MARGIN + Inches(0.36), Inches(4.12),
                          Inches(7.4), Inches(0.5))
    add_para(tf, s.subtitle, size=18, color=RGBColor(0x9F, 0xB3, 0xCE), first=True)

    box, tf = add_textbox(slide, MARGIN + Inches(0.36), Inches(4.86),
                          Inches(7.4), Inches(0.4))
    add_para(tf, s.footer, size=12, color=RGBColor(0x6E, 0x82, 0xA0), first=True)

    add_page_number(slide, index, total, dark=True)


def render_toc(prs, s: Slide, index: int, total: int):
    slide = new_slide(prs, PALETTE.surface)
    y = add_kicker_and_title(slide, s.kicker, s.title)

    row_h = Inches(0.97)
    for i, (num, name, desc) in enumerate(s.items):
        top = y + i * row_h

        # 编号圆牌
        add_number_badge(slide, MARGIN, top + Inches(0.06), Inches(0.7), num,
                         PALETTE.primary, PALETTE.accent, font_size=15)

        box, tf = add_textbox(slide, MARGIN + Inches(0.92), top,
                              CONTENT_W - Inches(1.0), Inches(0.4))
        add_para(tf, name, size=19, bold=True, font=FONT_HEAD,
                 color=PALETTE.primary, first=True)

        box, tf = add_textbox(slide, MARGIN + Inches(0.92), top + Inches(0.38),
                              CONTENT_W - Inches(1.0), Inches(0.34))
        add_para(tf, desc, size=12.5, color=PALETTE.muted, first=True)

        if i < len(s.items) - 1:
            add_rect(slide, MARGIN + Inches(0.92), top + row_h - Inches(0.1),
                     CONTENT_W - Inches(1.0), Emu(9525), PALETTE.line,
                     shape=MSO_SHAPE.RECTANGLE)

    add_page_number(slide, index, total)


def render_section(prs, s: Slide, index: int, total: int):
    """章节分隔页。深色底，形成节奏。"""
    slide = new_slide(prs, PALETTE.primary)

    add_rect(slide, MARGIN, Inches(2.9), Inches(0.09), Inches(1.35),
             PALETTE.accent, shape=MSO_SHAPE.RECTANGLE)

    box, tf = add_textbox(slide, MARGIN + Inches(0.36), Inches(2.82),
                          Inches(9), Inches(0.4))
    add_para(tf, s.kicker, size=13, bold=True, color=PALETTE.accent, first=True)

    box, tf = add_textbox(slide, MARGIN + Inches(0.36), Inches(3.22),
                          Inches(9.6), Inches(0.9))
    add_para(tf, s.title, size=40, bold=True, font=FONT_HEAD,
             color=PALETTE.white, line_spacing=1.1, first=True)

    box, tf = add_textbox(slide, MARGIN + Inches(0.36), Inches(4.2),
                          Inches(9), Inches(0.4))
    add_para(tf, s.subtitle, size=15, color=RGBColor(0x9F, 0xB3, 0xCE), first=True)

    # 右下角序号水印
    box, tf = add_textbox(slide, SLIDE_W - Inches(3.2), SLIDE_H - Inches(2.5),
                          Inches(2.6), Inches(1.4), align=PP_ALIGN.RIGHT)
    add_para(tf, s.kicker.replace("PART ", ""), size=72, bold=True,
             font=FONT_HEAD, color=RGBColor(0x1B, 0x2A, 0x52), first=True)

    add_page_number(slide, index, total, dark=True)


def render_content(prs, s: Slide, index: int, total: int):
    """左文右图：要点在左，视觉占位在右。"""
    slide = new_slide(prs, PALETTE.surface)
    y = add_kicker_and_title(slide, s.kicker, s.title)

    text_w = Inches(6.5)
    for i, (head, desc) in enumerate(s.bullets):
        top = y + i * Inches(1.18)

        # 编号圆牌
        add_number_badge(slide, MARGIN, top + Inches(0.02), Inches(0.4), str(i + 1),
                         PALETTE.secondary, PALETTE.white, font_size=12)

        box, tf = add_textbox(slide, MARGIN + Inches(0.58), top,
                              text_w - Inches(0.6), Inches(0.38))
        add_para(tf, head, size=17, bold=True, font=FONT_HEAD,
                 color=PALETTE.primary, first=True)

        box, tf = add_textbox(slide, MARGIN + Inches(0.58), top + Inches(0.4),
                              text_w - Inches(0.6), Inches(0.62))
        add_para(tf, desc, size=13.5, color=PALETTE.muted, line_spacing=1.35, first=True)

    add_visual_placeholder(slide, MARGIN + text_w + Inches(0.5), y,
                           CONTENT_W - text_w - Inches(0.5), Inches(3.9),
                           s.placeholder)
    add_page_number(slide, index, total)


def render_timeline(prs, s: Slide, index: int, total: int):
    """横向时间轴：一条主线 + 若干节点。"""
    slide = new_slide(prs, PALETTE.surface)
    y = add_kicker_and_title(slide, s.kicker, s.title)

    n = len(s.milestones)
    avail = CONTENT_W - Inches(0.4)
    step = int(avail / n) if n else 0
    axis_y = y + Inches(1.85)

    # 主轴线
    add_rect(slide, MARGIN + Inches(0.2), axis_y, avail, Emu(19050),
             PALETTE.line, shape=MSO_SHAPE.RECTANGLE)

    for i, (year, desc) in enumerate(s.milestones):
        cx = MARGIN + Inches(0.2) + i * step + step // 2

        # 节点圆点（交替强调色，形成节奏）
        dot_color = PALETTE.accent if i % 2 == 0 else PALETTE.secondary
        d = Inches(0.34)
        add_rect(slide, int(cx - d / 2), int(axis_y - d / 2 + Emu(9525)), d, d,
                 dot_color, shape=MSO_SHAPE.OVAL)

        # 年份（轴上方）
        box, tf = add_textbox(slide, int(cx - step / 2), axis_y - Inches(0.78),
                              step, Inches(0.4), align=PP_ALIGN.CENTER)
        add_para(tf, year, size=21, bold=True, font=FONT_HEAD,
                 color=PALETTE.primary, first=True)

        # 说明（轴下方）
        box, tf = add_textbox(slide, int(cx - step / 2) + Inches(0.14),
                              axis_y + Inches(0.3), step - Inches(0.28), Inches(1.3),
                              align=PP_ALIGN.CENTER)
        add_para(tf, desc, size=11.5, color=PALETTE.muted,
                 line_spacing=1.35, first=True)

    # 占位带避开右下角页码
    add_visual_placeholder(slide, MARGIN, SLIDE_H - MARGIN - Inches(0.75),
                           CONTENT_W - Inches(1.6), Inches(0.75), s.placeholder)
    add_page_number(slide, index, total)


def render_grid(prs, s: Slide, index: int, total: int):
    """卡片网格：4 项走 2×2，6 项走 3×2，底部留一条视觉占位带。"""
    slide = new_slide(prs, PALETTE.surface)
    y = add_kicker_and_title(slide, s.kicker, s.title)

    n = len(s.items)
    cols = 2 if n <= 4 else 3
    rows = (n + cols - 1) // cols
    gap = Inches(0.28)

    # 占位带固定在底部：挤在标题旁时文字会被压成两行、框也显得局促
    ph_h = Inches(0.6)
    ph_top = SLIDE_H - MARGIN - ph_h
    grid_h = ph_top - y - Inches(0.26)

    card_w = int((CONTENT_W - gap * (cols - 1)) / cols)
    card_h = int((grid_h - gap * (rows - 1)) / rows)

    for i, (name, en, desc) in enumerate(s.items):
        r, c = divmod(i, cols)
        left = MARGIN + c * (card_w + gap)
        top = y + r * (card_h + gap)

        add_rect(slide, left, top, card_w, card_h, PALETTE.card,
                 line=PALETTE.line, line_w=1.0)

        # 左上小色块：把「图标位」标出来（后续可换成真实图标）
        add_rect(slide, left + Inches(0.26), top + Inches(0.24),
                 Inches(0.36), Inches(0.36), PALETTE.accent,
                 shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.25)

        box, tf = add_textbox(slide, left + Inches(0.76), top + Inches(0.22),
                              card_w - Inches(1.0), Inches(0.4))
        add_para(tf, name, size=15.5, bold=True, font=FONT_HEAD,
                 color=PALETTE.primary, first=True)

        box, tf = add_textbox(slide, left + Inches(0.76), top + Inches(0.6),
                              card_w - Inches(1.0), Inches(0.26))
        add_para(tf, en, size=10, bold=True, color=PALETTE.secondary, first=True)

        box, tf = add_textbox(slide, left + Inches(0.26), top + Inches(0.98),
                              card_w - Inches(0.52), card_h - Inches(1.2))
        add_para(tf, desc, size=12, color=PALETTE.muted,
                 line_spacing=1.4, first=True)

    # 占位带避开右下角页码，留出 1.6" 空档
    add_visual_placeholder(slide, MARGIN, ph_top,
                           CONTENT_W - Inches(1.6), ph_h, s.placeholder)
    add_page_number(slide, index, total)


def render_compare(prs, s: Slide, index: int, total: int):
    """左右对比：两栏卡片，标题色区分。"""
    slide = new_slide(prs, PALETTE.surface)
    y = add_kicker_and_title(slide, s.kicker, s.title)

    gap = Inches(0.36)
    col_w = int((CONTENT_W - gap) / 2)
    # 高度按到页脚的可用空间反推，避免底部留出大片空白
    ph_h = Inches(1.62)
    col_h = SLIDE_H - MARGIN - y - ph_h - Inches(0.32)

    for c, (head, lines) in enumerate([s.left, s.right]):
        left = MARGIN + c * (col_w + gap)
        head_color = PALETTE.secondary if c == 0 else PALETTE.primary
        accent_color = PALETTE.accent if c == 1 else PALETTE.line

        add_rect(slide, left, y, col_w, col_h, PALETTE.card,
                 line=PALETTE.line, line_w=1.0)
        # 顶部色带：区分两栏
        add_rect(slide, left, y, col_w, Inches(0.07), head_color,
                 shape=MSO_SHAPE.RECTANGLE)

        box, tf = add_textbox(slide, left + Inches(0.32), y + Inches(0.28),
                              col_w - Inches(0.64), Inches(0.4))
        add_para(tf, head, size=19, bold=True, font=FONT_HEAD,
                 color=head_color, first=True)

        box, tf = add_textbox(slide, left + Inches(0.32), y + Inches(0.82),
                              col_w - Inches(0.64), col_h - Inches(1.0))
        for i, line in enumerate(lines):
            add_para(tf, "· " + line, size=12.5, color=PALETTE.ink,
                     space_after=7, line_spacing=1.3, first=(i == 0))

        # 左右各一个小标记，强化对比
        add_rect(slide, left + col_w - Inches(0.5), y + Inches(0.32),
                 Inches(0.18), Inches(0.18), accent_color, shape=MSO_SHAPE.OVAL)

    add_visual_placeholder(slide, MARGIN, y + col_h + Inches(0.32),
                           CONTENT_W - Inches(1.6), ph_h, s.placeholder)
    add_page_number(slide, index, total)


def render_two_col(prs, s: Slide, index: int, total: int):
    """两栏要点 + 底部视觉占位。"""
    slide = new_slide(prs, PALETTE.surface)
    y = add_kicker_and_title(slide, s.kicker, s.title)

    gap = Inches(0.4)
    col_w = int((CONTENT_W - gap) / 2)

    for c, (head, lines) in enumerate([s.left, s.right]):
        left = MARGIN + c * (col_w + gap)
        head_color = PALETTE.secondary if c == 0 else PALETTE.primary

        add_rect(slide, left, y, col_w, Inches(2.42), PALETTE.card,
                 line=PALETTE.line, line_w=1.0)

        badge = add_rect(slide, left + Inches(0.3), y + Inches(0.28),
                         Inches(0.34), Inches(0.34), head_color,
                         shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.25)

        box, tf = add_textbox(slide, left + Inches(0.78), y + Inches(0.26),
                              col_w - Inches(1.1), Inches(0.4))
        add_para(tf, head, size=17, bold=True, font=FONT_HEAD,
                 color=PALETTE.primary, first=True)

        box, tf = add_textbox(slide, left + Inches(0.32), y + Inches(0.82),
                              col_w - Inches(0.64), Inches(1.4))
        for i, line in enumerate(lines):
            add_para(tf, "— " + line, size=12, color=PALETTE.ink,
                     space_after=8, line_spacing=1.35, first=(i == 0))

    add_visual_placeholder(slide, MARGIN, y + Inches(2.72),
                           CONTENT_W, Inches(1.16), s.placeholder)
    add_page_number(slide, index, total)


# 总结页右侧的三个数据看点。数字都能从本册内容里对上：
# 1956→2026 是 70 年；正文列了 4 项核心技术、6 个应用场景
SUMMARY_STATS = [
    ("70", "年", "从达特茅斯会议到今天的演进跨度"),
    ("4", "项", "支撑起当前 AI 能力的核心技术领域"),
    ("6", "大", "已经跑通并规模化的行业应用场景"),
]


def render_summary(prs, s: Slide, index: int, total: int):
    """总结页：左侧结论，右侧数据看点。深色底收尾。"""
    slide = new_slide(prs, PALETTE.primary)

    add_kicker_and_title(slide, s.kicker, s.title, on_dark=True)

    # 左侧收窄，把右侧让给数据面板
    panel_w = Inches(3.9)
    rows_w = CONTENT_W - panel_w - Inches(0.6)

    y = Inches(2.16)
    row_h = Inches(1.0)
    for i, (num, head, desc) in enumerate(s.items):
        top = y + i * row_h

        add_number_badge(slide, MARGIN, top, Inches(0.5), num,
                         PALETTE.accent, PALETTE.primary, font_size=12,
                         shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.22)

        box, tf = add_textbox(slide, MARGIN + Inches(0.72), top - Inches(0.02),
                              rows_w - Inches(0.72), Inches(0.38))
        add_para(tf, head, size=15.5, bold=True, font=FONT_HEAD,
                 color=PALETTE.white, first=True)

        box, tf = add_textbox(slide, MARGIN + Inches(0.72), top + Inches(0.32),
                              rows_w - Inches(0.72), Inches(0.32))
        add_para(tf, desc, size=11.5, color=RGBColor(0x9F, 0xB3, 0xCE), first=True)

    # 右侧数据面板：给结论页补一个视觉重心
    panel_x = MARGIN + rows_w + Inches(0.6)
    panel_top = Inches(2.16)
    panel_h = Inches(4.1)
    add_rect(slide, panel_x, panel_top, panel_w, panel_h,
             RGBColor(0x16, 0x24, 0x4C), line=RGBColor(0x24, 0x3A, 0x66), line_w=1.0)

    stat_h = Inches(1.36)
    for i, (num, unit, label) in enumerate(SUMMARY_STATS):
        top = panel_top + Inches(0.06) + i * stat_h
        if i:
            add_rect(slide, panel_x + Inches(0.42), top - Inches(0.04),
                     panel_w - Inches(0.84), Emu(9525),
                     RGBColor(0x28, 0x3E, 0x6C), shape=MSO_SHAPE.RECTANGLE)

        # 大数字 + 单位：单位用小字，避免数字被拉长变形
        box, tf = add_textbox(slide, panel_x + Inches(0.42), top + Inches(0.2),
                              panel_w - Inches(0.84), Inches(0.6))
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        r1 = p.add_run()
        r1.text = num
        set_font(r1, name=FONT_HEAD, size=40, bold=True, color=PALETTE.accent)
        r2 = p.add_run()
        r2.text = " " + unit
        set_font(r2, size=14, bold=True, color=PALETTE.accent)

        box, tf = add_textbox(slide, panel_x + Inches(0.42), top + Inches(0.86),
                              panel_w - Inches(0.84), Inches(0.4))
        add_para(tf, label, size=10.5, color=RGBColor(0x8F, 0xA6, 0xC4),
                 line_spacing=1.25, first=True)

    add_page_number(slide, index, total, dark=True)


def render_closing(prs, s: Slide, index: int, total: int):
    slide = new_slide(prs, PALETTE.primary)

    # 与封面呼应的同心圆
    for d in (3.6, 2.6, 1.6):
        size = Inches(d)
        cx, cy = Inches(6.67), SLIDE_H / 2
        circle = add_rect(slide, int(cx - size / 2), int(cy - size / 2), size, size,
                          PALETTE.primary, shape=MSO_SHAPE.OVAL)
        circle.fill.background()
        circle.line.color.rgb = RGBColor(0x24, 0x3A, 0x66)
        circle.line.width = Pt(1.0)

    box, tf = add_textbox(slide, 0, Inches(3.02), SLIDE_W, Inches(0.9),
                          align=PP_ALIGN.CENTER)
    add_para(tf, s.title, size=44, bold=True, font=FONT_HEAD,
             color=PALETTE.white, align=PP_ALIGN.CENTER, first=True)

    box, tf = add_textbox(slide, 0, Inches(4.0), SLIDE_W, Inches(0.5),
                          align=PP_ALIGN.CENTER)
    add_para(tf, s.subtitle, size=16, color=PALETTE.accent,
             align=PP_ALIGN.CENTER, first=True)

    box, tf = add_textbox(slide, 0, SLIDE_H - Inches(0.95), SLIDE_W, Inches(0.3),
                          align=PP_ALIGN.CENTER)
    add_para(tf, s.footer, size=10, color=RGBColor(0x6E, 0x82, 0xA0),
             align=PP_ALIGN.CENTER, first=True)


RENDERERS = {
    "cover": render_cover,
    "toc": render_toc,
    "section": render_section,
    "content": render_content,
    "timeline": render_timeline,
    "grid": render_grid,
    "compare": render_compare,
    "two-col": render_two_col,
    "summary": render_summary,
    "closing": render_closing,
}


def build_deck() -> Presentation:
    """按顺序把全部页面组装成一份演示文稿。"""
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H

    deck = [COVER, TOC, *SLIDES, SUMMARY, CLOSING]
    total = len(deck)

    for i, s in enumerate(deck, start=1):
        renderer = RENDERERS.get(s.kind)
        if renderer is None:
            raise ValueError(f"未知的页面类型：{s.kind}")
        renderer(prs, s, i, total)

    return prs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成《人工智能介绍》演示文稿")
    parser.add_argument("-o", "--output", default="人工智能介绍.pptx",
                        help="输出文件路径（默认 人工智能介绍.pptx）")
    args = parser.parse_args(argv)

    prs = build_deck()
    prs.save(args.output)

    size_kb = os.path.getsize(args.output) / 1024
    print(f"已生成：{args.output}")
    print(f"  页数：{len(prs.slides)} 页")
    print(f"  大小：{size_kb:.1f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
