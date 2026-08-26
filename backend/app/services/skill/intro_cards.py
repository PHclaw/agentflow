"""Plaza Skill 能力卡片：介绍自己时给模型完整清单，而不是一句话 description。"""
from __future__ import annotations

from typing import Any

SkillCard = dict[str, Any]

SKILL_CARDS: dict[str, SkillCard] = {
    "pdf": {
        "name": "PDF处理助手",
        "blurb": "上传 PDF（或 Word/Excel/PPT）后，在对话里直接说要做什么即可；平台会真正生成可下载文件。",
        "can": [
            "合并多个 PDF，并给出下载",
            "按页拆分 PDF",
            "抽取正文文本（扫描件可能无字）",
            "提取表格，生成可下载 Excel",
            "提取 PDF 中的图片 / 内嵌文件",
            "文字水印（如「加水印：内部资料」）",
            "表单结构探测（可填字段 → JSON）",
            "解析为 Markdown（PDF / Word / Excel / PPT）",
            "PDF 转 Word：说「word / Word / 转成 word」默认生成 .docx；明确说「转成 doc / .doc」才尝试旧版 .doc",
        ],
        "how": "先在输入框上传文件，再发送具体指令。没有文件时也可以问「你会干什么」，我会介绍能力而不会假装已经转换。",
        "examples": [
            "把这份 PDF 转成 Word",
            "转化为 docx",
            "转成 doc",
            "把这几个 PDF 按 1、2、3 合并",
            "提取这个 PDF 里的所有表格，给我 Excel",
            "把 PDF 里的图片都提取出来",
            "加水印：内部资料",
        ],
        "cannot": [
            "不破解加密 PDF，不填写需密码的表单",
            "纯扫描件抽不出文字时，需要 OCR，当前不会自动 OCR",
            "转 Word 以解析出的文本/标题/表格为主，复杂排版、精确坐标布局可能与原稿有差异",
            "旧版 .doc 依赖本机 LibreOffice 或 Microsoft Word；没有时会提供 .docx 并说明",
        ],
    },
    "ppt-generation": {
        "name": "PPT助手",
        "blurb": "用问卷确认用途、页数、内容和信息密度，再给风格封面，确认后生成 16:9 HTML 演示稿和可编辑 PPTX。",
        "can": [
            "按问卷收集：用途、页数、内容来源、信息密度",
            "给出多套 HTML 风格封面供选择（回复如 1a / 1b / 1c）",
            "生成可在浏览器打开的完整 HTML 幻灯片 + 可编辑 PPTX",
            "读取已有 pptx，或按说明替换指定页内容",
        ],
        "how": "直接说「做一份 PPT」即可开始问卷。选项用题号+字母一次答完，例如 `1b 2a 3a 4b`。详细大纲请写在当前消息里；不要指望自动沿用很久以前的聊天，除非你写「用刚才对话里的材料」。",
        "examples": [
            "做一份季度复盘 PPT",
            "1b 2a 3a 4b",
            "用这份大纲生成 PPT（把大纲贴在同一条消息）",
            "读取我上传的 pptx，告诉我有几页",
        ],
        "cannot": [
            "没有正文内容时不会凭空生成完整稿",
            "不会做成不可编辑的纯图片幻灯片（默认产出可改字的 PPTX）",
        ],
    },
    "academic-search": {
        "name": "学术文献检索",
        "blurb": "按主题检索多源论文，给出带年份、venue、引用和可点链接的摘要表。中文主题会尽量扩成英文检索式再搜。",
        "can": [
            "检索 arXiv、Semantic Scholar、OpenAlex、DBLP、PubMed、Crossref",
            "输出标题 / 年份 / venue / 引用 / 详情·DOI·PDF 等链接",
            "按「只要某方面」在上一轮结果上收窄（refine），或按你的新主题重新搜",
            "中文问题自动补充英文检索词，避免只搜汉字漏掉论文",
        ],
        "how": "直接说主题和大概篇数，例如「帮我找 8 篇 …」。需要精读某一篇时，把题名复制到独立 Skill「文献速读笔记」，或发送 `\\lit-review-notes` 加标题——不要在本 Skill 里粘贴摘要。",
        "examples": [
            "搜索 2023 年以来 vision transformer 医学影像分割，给我前 8 篇",
            "帮我找几篇皮肤病相关的，只要皮肤病",
            "Swin UNETR 相关论文",
        ],
        "cannot": [
            "不绕过付费墙、不给 Sci-Hub",
            "不把检索和「文献速读笔记」合成一次任务",
            "不会编造未检索到的论文、DOI 或引用数",
        ],
    },
    "lit-review-notes": {
        "name": "文献速读笔记",
        "blurb": "只要论文标题：平台按标题检索题录和摘要，再整理成问题 / 方法 / 结果 / 局限 / 可引用观点。",
        "can": [
            "只根据标题检索 OpenAlex / Crossref / Semantic Scholar / arXiv",
            "输出结构化速读：研究问题、方法、关键结果、局限、可引用表述、待核实",
            "公式用 `$...$` 写出，便于页面渲染",
        ],
        "how": "把完整英文或中文题名发给我即可，不必粘贴摘要、也不必上传 PDF。也可从「学术文献检索」复制一条标题过来。",
        "examples": [
            "Swin UNETR++: Revisiting Efficient Transformer for 3D Medical Image Segmentation",
            "这篇论文说了什么：Attention Is All You Need",
        ],
        "cannot": [
            "检索失败时不会编造笔记",
            "摘要里没有的实验数字、页码、会议名会放进「待核实」，不会当成已证实结果",
            "不是文献检索器：要一批论文请用「学术文献检索」",
        ],
    },
    "meeting-minutes": {
        "name": "会议纪要助手",
        "blurb": "把会议笔记或逐字稿整理成可转发的标准纪要，突出决议和行动项。",
        "can": [
            "整理元信息、参会、议程、摘要",
            "每条决议写清决定 + 决策者 + 理由",
            "行动项表格：A1/A2…、负责人、截止日期、验收标准",
            "待决事项、风险、下次会议",
        ],
        "how": "粘贴会议笔记、聊天记录或逐字稿；能写清时间、出席人更好。没有材料时先介绍用法，不会用 TBD 填一篇假纪要。",
        "examples": [
            "把下面这段周会记录整理成纪要：……",
            "从这段逐字稿提取决议和行动项：……",
        ],
        "cannot": [
            "不编造未出现的人名或未做出的决策",
            "不确定的信息标 TBD，而不是猜",
        ],
    },
    "statistical-analyst": {
        "name": "统计分析助手",
        "blurb": "假设检验、样本量、置信区间：先跑白名单统计脚本，再按 Bottom Line 结构解读。",
        "can": [
            "两比例 / A/B 假设检验（p 值、95% CI、效应量）",
            "按基线转化率、MDE、功效估算样本量",
            "置信区间计算",
            "读取上传的 csv / xlsx（如「AB汇总」里的对照/实验 n 与转化数）",
        ],
        "how": "直接给出对照/实验的 n 与转化数，或上传 Excel。询问「你会干什么」时只介绍能力，不会套 Bottom Line 空表。",
        "examples": [
            "对照 n=5000 转化 250，实验 n=5000 转化 310，α=0.05，做比例检验",
            "基线 5%，相对提升 20%，power=0.8，每组要多少样本",
            "上传这份 xlsx，按 AB汇总做检验",
        ],
        "cannot": [
            "脚本没跑出的数字不会编",
            "仅教育 / 决策辅助，不构成正式审计意见",
        ],
    },
    "clinical-case-report": {
        "name": "临床病例报告",
        "blurb": "把病例材料整理成 SOAP 教学病例（危急提示、体征表、鉴别推理、按问题计划）。仅教育用途。",
        "can": [
            "叙事体现病史 + 表格化体征",
            "危急发现独立提示",
            "Assessment：主诊断、鉴别 3–5 条（支持/不支持）、风险分层",
            "Plan by problem（药物通用名 + 途径频次 + 监测）",
        ],
        "how": "粘贴主诉、现病史要点、体征和检查。没有病例内容时只介绍结构，不编造示意病人来凑模板。",
        "examples": [
            "按 SOAP 整理：62 岁女性右眼突发红痛 6 小时，IOP 52……",
            "把下面门诊记录写成教学病例报告：……",
        ],
        "cannot": [
            "非诊疗意见，不能替代临床判断",
            "用户已给的数值不得改写",
        ],
    },
    "excel": {
        "name": "Excel表格助手",
        "blurb": "上传 Excel/CSV 或粘贴表格后，可探查结构、SQL 分析、导出工作簿，并画出柱状/折线/饼/散点/直方图。",
        "can": [
            "读取多 sheet 的 xlsx / xls / csv / tsv，说明列类型与样例行",
            "描述统计（均值、最值、空值、类别频次）",
            "按你的问题汇总/筛选；也可直接跑 SELECT SQL",
            "把查询结果导出为可下载的 .xlsx（Arial 表头）",
            "粘贴空格表 / Markdown / CSV；「10支」「8块」自动当数字",
            "宽表「按类别汇总」会按列名透视，明细+汇总写入同一份 Excel",
            "画图：柱状、折线、饼图、散点、直方图（本地生成 PNG）",
        ],
        "how": "上传 xlsx/csv，或直接把表格贴在消息里（空格对齐即可）。例如贴完数据后说「按类别汇总，导出 Excel」。问「你会干什么」会介绍能力。",
        "examples": [
            "看看这份表有哪些列",
            "按类别汇总金额，导出 Excel",
            "SELECT category, SUM(amount) FROM Sheet1 GROUP BY category",
            "画一张销售额柱状图",
            "把下面这张表按类别汇总并导出（空格对齐的文本也可以）",
        ],
        "cannot": [
            "不做 A/B 假设检验与样本量（请用统计分析助手）",
            "不执行 INSERT/UPDATE/DROP 等改库 SQL",
            "复杂财务模型的 LibreOffice 重算公式可参考原 xlsx skill 脚本，当前以分析与导出为主",
            "地图/桑基等 AntV 远程图种未接入，常用统计图在本地生成",
        ],
    },
}


def card_for(skill_id: str | None = None, *, name: str = "") -> SkillCard | None:
    sid = (skill_id or "").strip()
    if sid and sid in SKILL_CARDS:
        return SKILL_CARDS[sid]
    n = (name or "").strip()
    for card in SKILL_CARDS.values():
        if n and card.get("name") == n:
            return card
    return None


def format_card_markdown(card: SkillCard) -> str:
    name = str(card.get("name") or "本助手")
    lines = [
        f"## 我能做什么",
        "",
        f"我是 **{name}**。{card.get('blurb') or ''}",
        "",
        "### 能力清单",
    ]
    for item in card.get("can") or []:
        lines.append(f"- {item}")
    if card.get("how"):
        lines.extend(["", "### 怎么开始", str(card["how"])])
    examples = list(card.get("examples") or [])
    if examples:
        lines.extend(["", "### 可以直接发送的示例"])
        for ex in examples:
            lines.append(f"- 「{ex}」")
    cannot = list(card.get("cannot") or [])
    if cannot:
        lines.extend(["", "### 做不到 / 注意"])
        for item in cannot:
            lines.append(f"- {item}")
    return "\n".join(lines).strip()


def format_card_stdout(card: SkillCard) -> str:
    return format_card_markdown(card)
