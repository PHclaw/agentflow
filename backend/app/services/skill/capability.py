"""识别「你会干什么」类能力询问：所有 Skill 统一跳过任务模板与工具。"""
from __future__ import annotations

import re
from typing import Any

from app.services.skill.intro_cards import card_for, format_card_markdown

INTRO_SYSTEM_ADDENDUM = (
    "【能力询问】用户在问本 Skill 能做什么、还能做什么、支不支持某功能、或怎么用，"
    "不是要立刻执行任务。用简体中文直接回答这一句。\n"
    "泛问（你会做什么 / 怎么用 / 介绍一下）：按 stdout 能力卡片完整介绍"
    "（能力清单、怎么开始、示例、注意）。\n"
    "具体问题（例如还会画什么图、支不支持饼图、SQL 怎么写）：先答这个问题，"
    "可从卡片摘相关条目，不要整页复述能力清单。\n"
    "禁止：套用任务模板（Bottom Line、会议纪要、病例 SOAP、文献笔记、结果/下载）；"
    "禁止声称已生成文件、已完成分析/检索/转换；禁止因为没有上传文件就说「无法介绍」；"
    "禁止复制系统时钟。"
)

_CAPABILITY_RE = re.compile(
    r"(你会?[干做]?(?:什么|啥)|你能[干做]?(?:什么|啥)|"
    r"能[干做]?(?:什么|啥)|会[干做]?(?:什么|啥)|可以做(?:什么|啥)|"
    r"有什么用|做什么用|有何用|"
    r"有什么功能|有哪些功能|怎么用|如何使用|怎样使用|怎么使用|"
    r"介绍一下你?自己?|你是谁|你是干(?:什么|啥)的|你是做(?:什么|啥)的|"
    r"能力介绍|功能介绍|你会什么|"
    r"what can you do|what do you do|how (?:do i|to) use|who are you)",
    re.I,
)

_ABILITY_ASK_RE = re.compile(
    r"(能不能|能否|可不可以|可以不可以|支不支持|支持不支持|会不会|"
    r"(?:能|可以)把?.{0,48}(?:转|转换|导出|提取|合并|拆分|生成|检索|整理|解析).{0,32}吗|"
    r"支持.{0,20}吗|会.{0,16}吗)",
    re.I,
)

_GREETING_RE = re.compile(
    r"^(?:你好|您好|嗨|哈喽|在吗|在不在|hi+|hello|hey)[啊呀哦呢哇！!。.?？\s]*$",
    re.I,
)

_TASK_HINTS = (
    "生成",
    "做一份",
    "做个",
    "帮我写",
    "帮我做",
    "帮我分析",
    "帮我合并",
    "帮我搜",
    "分析这份",
    "合并",
    "拆分",
    "提取",
    "检索",
    "搜索",
    "搜论文",
    "加水印",
    "改成",
    "写成",
    "整理成",
    "计算",
    "检验",
    "样本量",
    "置信区间",
    "读大纲",
)


def prefer_current_user_text(text: str) -> str:
    t = text or ""
    marker = "## 当前用户"
    if marker in t:
        t = t.rsplit(marker, 1)[-1]
    t = re.split(r"\n## (?:当前上传|上传文件|先前对话)", t, maxsplit=1)[0]
    return t.strip()


def is_capability_query(text: str) -> bool:
    """当前句是打招呼或问能力，且没有夹带明确任务。"""
    current = prefer_current_user_text(text)
    if not current:
        return False
    if _GREETING_RE.match(current.strip()):
        return True
    if len(current) > 160:
        return False
    if not _CAPABILITY_RE.search(current):
        return False
    rest = _CAPABILITY_RE.sub(" ", current)
    rest_compact = re.sub(r"[\s！!。.?？,，、呢啊呀哦哇的吧嘛]+", "", rest)
    if len(rest_compact) >= 8 and any(k in rest for k in _TASK_HINTS):
        return False
    return True


def is_ability_ask(text: str) -> bool:
    """「能不能转 word / 可以把 pdf 转 docx 吗」这类能力确认。"""
    current = prefer_current_user_text(text)
    if not current or len(current) > 180:
        return False
    if is_capability_query(current):
        return True
    return bool(_ABILITY_ASK_RE.search(current))


def should_intro_only(text: str, *, has_uploads: bool = False) -> bool:
    """正则兜底（单测/脚本直调）。线上走 intent_gate 模型判断。"""
    if is_capability_query(text):
        return True
    if has_uploads:
        return False
    return is_ability_ask(text)


INTENT_GATE_SYSTEM = (
    "你是技能路由，只判断用户这一句话的意图，不要回答内容本身。\n"
    "当前技能：{name}\n"
    "技能能做什么（供判断，不要展开介绍）：\n{blurb}\n\n"
    "intent=intro：问好；问能做什么/怎么用/还能做什么；问支不支持某能力或还能画哪些图，"
    "且没有要立刻执行的具体任务（没有论文主题、没有「现在就转/分析/检索/画图」的指令）。\n"
    "intent=task：要立刻检索/转换/生成/分析/整理/画图；或已上传文件并要求处理这些文件。\n"
    "有上传文件且用户像在下指令（转、分析、提取、导出、汇总、画图）→ task。\n"
    "只输出一行 JSON：{{\"intent\":\"intro\"}} 或 {{\"intent\":\"task\"}}"
)


def build_intent_gate_prompt(
    agent: Any,
    user_text: str,
    *,
    uploaded_files: list[dict] | None = None,
) -> tuple[str, str]:
    name = getattr(agent, "name", None) or "本助手"
    sid = getattr(agent, "id", None) or ""
    card = card_for(sid, name=name)
    if card:
        blurb = str(card.get("blurb") or "")
        cans = "；".join(str(x) for x in (card.get("can") or [])[:8])
        if cans:
            blurb = f"{blurb}\n{cans}"
    else:
        blurb = (getattr(agent, "description", None) or "")[:800]
    system = INTENT_GATE_SYSTEM.format(name=name, blurb=blurb[:1200] or "（见技能名）")
    user = "用户原话：\n" + prefer_current_user_text(user_text)[:800]
    names = [
        str(f.get("name") or "").strip()
        for f in (uploaded_files or [])
        if f.get("name")
    ]
    if names:
        user += "\n已上传文件：" + "、".join(names[:9])
    else:
        user += "\n已上传文件：无"
    return system, user


def parse_intent_gate(raw: str) -> str:
    """返回 intro 或 task；解析失败当 task，避免误伤真正任务。"""
    compact = re.sub(r"\s+", "", (raw or "").lower())
    if '"intent":"intro"' in compact or "'intent':'intro'" in compact:
        return "intro"
    return "task"


def intro_trace(
    agent: Any | None = None,
    *,
    name: str = "",
    description: str = "",
    skill_id: str = "",
) -> dict[str, Any]:
    sid = skill_id or (getattr(agent, "id", None) or "")
    skill_name = name or (getattr(agent, "name", None) or "本助手")
    card = card_for(sid, name=skill_name)
    if card:
        stdout = format_card_markdown(card)
        skill_name = str(card.get("name") or skill_name)
    else:
        blurb = description or (getattr(agent, "description", None) or "")
        specialty = getattr(agent, "specialty", None) or ""
        triggers = list(getattr(agent, "triggers", None) or [])[:12]
        stdout_parts = [f"name: {skill_name}"]
        if specialty:
            stdout_parts.append(f"specialty: {specialty}")
        if blurb:
            stdout_parts.append("description:\n" + str(blurb).strip()[:4000])
        if triggers:
            stdout_parts.append("triggers: " + "、".join(str(x) for x in triggers))
        stdout_parts.append(
            "请按 description 逐条介绍能力、怎么开始、至少 3 个可直接发送的示例，以及做不到的事。"
        )
        stdout = "\n".join(stdout_parts)
    return {
        "intent": "intro",
        "script": None,
        "exitCode": 0,
        "stdout": stdout,
        "stderr": "",
        "note": (
            f"用户在询问「{skill_name}」能做什么。"
            "不要执行任务、不要生成文件；按 stdout 能力卡片做完整介绍，并列出全部示例。"
        ),
        "name": skill_name,
        "skillId": sid,
    }


def format_intro_tool_result(trace: dict[str, Any] | None) -> str:
    if not trace:
        return "intent: intro\n请介绍本 Skill 能力，不要执行任务。"
    parts = [
        f"intent: {trace.get('intent')}",
        f"exitCode: {trace.get('exitCode')}",
    ]
    if trace.get("note"):
        parts.append(f"note: {trace['note']}")
    if trace.get("stdout"):
        parts.append("stdout:\n" + str(trace["stdout"]))
    parts.append(
        "重要：intent=intro。必须覆盖 stdout 能力清单、怎么开始、全部示例与注意。"
        "禁止套用任务输出结构，禁止声称已生成下载文件。"
    )
    return "\n".join(parts)


def intro_fallback_output(trace: dict[str, Any] | None, agent: Any | None = None) -> str:
    sid = (trace or {}).get("skillId") or getattr(agent, "id", None) or ""
    name = (trace or {}).get("name") or getattr(agent, "name", None) or ""
    card = card_for(str(sid), name=str(name))
    if card:
        return format_card_markdown(card)
    raw = (trace or {}).get("stdout") or ""
    if raw.strip().startswith("## "):
        return str(raw).strip()
    name = name or "本助手"
    desc = (getattr(agent, "description", None) or "").strip()
    if not desc:
        m = re.search(r"description:\n([\s\S]+?)(?:\ntriggers:|\Z)", raw)
        desc = (m.group(1).strip() if m else raw)[:2000]
    if not desc:
        desc = "直接说出具体任务即可；需要文件时请先上传。"
    return (
        f"## 我能做什么\n\n我是 **{name}**。\n\n{desc}\n\n"
        "直接发具体需求即可（可先上传文件）。"
    )
