"""Skill 品类：由 specialty / 名称 / tags 推断，供广场浏览与选型加权。

品类收敛为演示友好的主轴：办公 / 文档 / 医疗 / 学术 / 翻译。
"""
from __future__ import annotations

from typing import Iterable

# (id, 展示名, 关键词) — 更具体的品类靠前，避免「报告/润色/邮件」误吸
CATEGORY_DEFS: list[tuple[str, str, tuple[str, ...]]] = [
    (
        "analytics",
        "数据",
        ("统计", "数据分析", "A/B", "假设检验", "样本量", "置信区间", "实验分析", "p-value", "效应量"),
    ),
    (
        "medical",
        "医疗",
        ("医疗", "医学", "临床", "病例", "SOAP", "诊疗", "护理", "药品", "健康", "病历", "查房", "STEMI", "眼科", "青光眼"),
    ),
    (
        "translate",
        "翻译",
        ("翻译", "中英", "英中", "英译", "中译", "localize", "localization", "双语", "口译", "笔译"),
    ),
    (
        "academic",
        "学术",
        ("学术", "论文", "科研", "综述", "文献", "投稿", "开题", "peer review", "IMRaD", "文献速读", "学术检索", "搜论文", "arXiv", "OpenAlex"),
    ),
    (
        "docs",
        "文档",
        (
            "文档",
            "公文",
            "业务报告",
            "报告生成",
            "排版",
            "说明书",
            "长文",
            "文稿",
            "校对",
            "格式",
            "润色",
            "PDF",
            "pdf",
            "合并PDF",
            "填表",
            "水印",
            "表单结构",
        ),
    ),
    (
        "office",
        "办公",
        (
            "办公",
            "会议",
            "纪要",
            "邮件",
            "汇报",
            "协作",
            "周报",
            "3P",
            "日程",
            "沟通",
            "待办",
            "议程",
            "PPT",
            "pptx",
            "演示文稿",
            "幻灯片",
            "PowerPoint",
        ),
    ),
    ("other", "其他", ()),
]

CATEGORY_LABELS = {cid: label for cid, label, _ in CATEGORY_DEFS}

# 广场默认只展示平台精选作者
CURATED_AUTHOR_ID = "platform-preset"


def list_categories() -> list[dict[str, str]]:
    return [{"id": cid, "name": label} for cid, label, _ in CATEGORY_DEFS]


def infer_category(
    specialty: str = "",
    name: str = "",
    description: str = "",
    tags: Iterable[str] | None = None,
) -> tuple[str, str]:
    """返回 (category_id, category_name)。"""
    blob = " ".join(
        [
            specialty or "",
            name or "",
            description or "",
            " ".join(tags or []),
        ]
    )
    text = blob.lower()
    for cid, label, keywords in CATEGORY_DEFS:
        if cid == "other":
            continue
        if any(k.lower() in text for k in keywords):
            return cid, label
    return "other", "其他"


def category_of_agent(agent) -> tuple[str, str]:
    return infer_category(
        specialty=getattr(agent, "specialty", None) or "",
        name=getattr(agent, "name", None) or "",
        description=getattr(agent, "description", None) or "",
        tags=getattr(agent, "tags", None) or [],
    )
