"""多智能体群聊：路由与回复。

核心问题：用户发一条任务，谁来回？

这里用「一次 LLM 路由」解决——把任务和所有成员的能力描述一起交给模型，
让它选一个最合适的。相比「每个成员自荐打分」（N 次调用），成本低一个数量级。

三个必须处理的边界：
1. 模型说不清选谁（低置信度）→ 不硬派，反问用户
2. 明确没有合适的人 → 直说，不要随便派一个
3. 用户已经 @ 了某个人 → 跳过路由，直接给那个人

回复时的「@ 回发起人」由两处协作完成：
- content 开头带 `@用户名`，符合聊天习惯
- meta.reply_to 指向用户那条消息 id，供前端渲染成引用块
"""
import json
import re
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.models.agent import Agent
from app.models.group import AgentGroup, GroupMessage
from app.models.user import User
from app.services.llm import LLMService

# 置信度低于这个值时，不硬派，改为反问用户
LOW_CONFIDENCE = 0.5


def display_name_of_user(user: Optional[User]) -> str:
    """用户显示名：优先昵称，其次邮箱前缀，最后兜底。"""
    if not user:
        return "你"
    if user.nickname:
        return user.nickname
    if user.email:
        return user.email.split("@")[0]
    return "你"


async def resolve_user(db: AsyncSession, user_external_id: str) -> Optional[User]:
    """按 external_id 查用户（Agent.user_id 用的是 external_id）。"""
    if not user_external_id:
        return None
    row = await db.execute(select(User).where(User.external_id == user_external_id))
    return row.scalars().first()


def _extract_json(text: str) -> Optional[dict]:
    """从模型输出里抠出 JSON。

    模型经常在 JSON 前后加解释或 ```json 代码块，直接 json.loads 会失败。
    这里先去掉代码围栏，再退化为「找第一个 { 到最后一个 }」。
    """
    if not text:
        return None
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    try:
        return json.loads(cleaned)
    except Exception:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(cleaned[start:end + 1])
            except Exception:
                return None
    return None


def _agent_brief(agent: Agent) -> str:
    """把 agent 压成一行能力描述，喂给路由模型。

    description 为空时退化为名字——路由准确率很大程度取决于这段文字，
    所以界面上应该引导用户填写。
    """
    desc = (agent.description or "").strip().replace("\n", " ")
    if len(desc) > 120:
        desc = desc[:120] + "…"
    return f"- {agent.name}：{desc or '（未填写能力描述）'}"


async def route_task(
    db: AsyncSession,
    group: AgentGroup,
    agents: List[Agent],
    message: str,
    mentioned_agent: Optional[Agent] = None,
    mention_reason: str = "由你直接指定",
) -> Tuple[Optional[Agent], str, float]:
    """决定谁接这个任务。

    返回 (agent, 理由, 置信度)。agent 为 None 表示没人接：
    - 理由里会说明是「没有合适的」还是「需要用户确认」
    """
    if not agents:
        return None, "这个群还没有成员，先添加智能体", 0.0

    # 已确定接单人（@ 指定 或 引用回复推断）→ 跳过路由
    if mentioned_agent is not None:
        return mentioned_agent, mention_reason, 1.0

    # manual 模式：不做自动派发
    if (group.route_mode or "auto") == "manual":
        names = "、".join(f"@{a.name}" for a in agents[:5])
        return None, f"这个群设成了手动指派，请用 @ 指定成员（{names}）", 0.0

    # 路由完全靠 description 判断能力。描述为空时模型只能瞎猜，
    # 实测会幻觉出「文案编辑」这种群里根本不存在的名字。
    # 与其给用户一个莫名其妙的报错，不如在调用前就拦住并说清楚。
    blank = [a for a in agents if not (a.description or "").strip()]
    if blank:
        names = "、".join(a.name for a in blank[:3])
        if len(blank) == len(agents):
            return None, (
                f"群成员（{names}）都没有填写能力描述，无法判断谁适合接这个任务。"
                "请在 Agent 设置里补充描述，或直接用 @ 指定成员"
            ), 0.0
        return None, (
            f"以下成员没有能力描述：{names}。请补全描述后再自动派发，"
            "或直接用 @ 指定其他成员"
        ), 0.0

    prompt = f"""你是任务调度器。下面是群里的智能体成员：

{chr(10).join(_agent_brief(a) for a in agents)}

用户任务：
{message}

判断哪一个成员最适合处理这个任务。判断依据是任务需要的能力与成员描述是否匹配，
不要因为名字听起来相关就选。

【重要】宁可返回 null，也不要赌。
如果任务需要的能力在成员的描述里找不到明确对应——比如成员只写了
「软件方面的东西」「我的助手」这类模糊描述，而你需要的能力它是否覆盖并不确定——
说明现有成员里没有真正能接这个的人。把 assignee 填 null，系统会按任务补一位
描述清晰的新成员，这比让一个不确定的人硬答可靠得多。

反过来，如果你确实能根据描述确认某位成员覆盖了任务所需能力，就选他，
并把 confidence 给足。

如果输入里带了【补充说明】，说明有成员已经看过任务并表示做不了。这时要分清两种情况：
· 别人更合适 → 填那位成员的名字
· 现有成员都不具备所需能力（缺这个方向的人）→ assignee 填 null，
  系统会按任务自动补一位新成员

只输出 JSON，不要别的内容：
{{"assignee": "成员名字（没有合适的就填 null）", "reason": "一句话理由", "confidence": 0.0~1.0}}"""

    try:
        # 路由模型跟随群里第一个成员的配置：
        # 不写死 provider，否则用户把 Agent 配成 DeepSeek / Ollama 时，
        # 路由仍去调默认端点，表现成「明明配了模型却报未配置」。
        router_cfg = agents[0].model_config or {}
        llm = LLMService(
            provider=router_cfg.get("provider", "openai"),
            model=router_cfg.get("model"),
        )
        raw = await llm.chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,      # 路由要稳定，不要发散
            max_tokens=300,
        )
    except Exception as exc:  # noqa: BLE001 - 路由失败不该让整个请求挂掉
        logger.warning("group route failed: %s", exc)
        return None, "调度模型暂时不可用，请直接用 @ 指定成员", 0.0

    data = _extract_json(raw)
    if not data:
        logger.warning("group route returned non-JSON: %s", (raw or "")[:200])
        return None, "调度结果无法解析，请用 @ 指定成员", 0.0

    name = (data.get("assignee") or "").strip()
    reason = (data.get("reason") or "").strip() or "未说明理由"
    try:
        confidence = float(data.get("confidence") or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0

    if not name or name.lower() in ("null", "none", "无"):
        return None, reason or "现有成员都不擅长这个任务", confidence

    # 名字可能带 @ 或空格，做一次宽松匹配
    target = name.lstrip("@").strip()
    for agent in agents:
        if agent.name.strip() == target:
            if confidence < LOW_CONFIDENCE:
                return None, f"不确定该谁接（{reason}），请用 @ 指定成员", confidence
            return agent, reason, confidence

    # 模型给了个不在列表里的名字。除了报错，把真实成员列出来，
    # 用户才知道该 @ 谁 —— 否则只能回到群里翻成员列表。
    logger.warning("group route picked unknown agent: %s", name)
    actual = "、".join(f"@{a.name}" for a in agents[:5])
    return None, (
        f"调度模型返回了不存在的成员（{name}），未自动派发。"
        f"当前成员：{actual}。请用 @ 指定其中一位"
    ), confidence


#: 协作接力提示词。协作模式下才发——single 模式下让它主动交接，
#: 用户看到的仍是「一个人答完」，反而变啰嗦。
COLLAB_BLOCK = (
    "【关于协作接力】\n"
    "如果你已经把自己负责的部分做好了，但这个任务还有明显该由别人补的部分"
    "（例如你给的是数据结论，还需要有人补技术可行性；你给的是文案，"
    "还需要有人核事实），不要自己硬包办。在最后单独一行输出：\n"
    "[[NEXT: 成员名 | 要他补充什么，如 补充技术可行性评估]]\n"
    "系统会把你已经得出的结论一起转给他，由他接着补完。\n"
    "注意：优先交给**不同方向**的成员，不要把活原样交回上一位——"
    "两个人来回弹同样的内容对用户没有价值。\n"
    "只有真的需要别人补时才用；你一个人能做完就自己做完。\n\n"
)


def _roster_block(agent: Agent, peers: Optional[List[Agent]]) -> str:
    """列出群里其他成员。

    转交与协作接力都要求模型知道能交给谁——不列的话它只能编一个
    群里并不存在的名字（实测出现过「已转给数据分析同事」这种）。
    """
    others = [p for p in (peers or []) if p.id != agent.id]
    if not others:
        return ""
    lines = [
        f"- {p.name}：{(p.description or '（未填写能力描述）').strip() or '（未填写能力描述）'}"
        for p in others
    ]
    return (
        "\n群里的其他成员（只能交给他们，不能编造别的名字）：\n"
        + "\n".join(lines)
        + "\n"
    )


def build_reply_message(
    agent: Agent,
    question: str,
    asked_by: str,
    peers: Optional[List[Agent]] = None,
    collaboration: bool = False,
) -> str:
    """构造发给 agent 的输入。

    五件事要说清楚：
    1. 它是谁（角色与能力边界）—— 群里只说「请回答」会让它越界答别人的活
    2. 群里还有谁（否则它想转交却不知道该转给谁，只能编一个名字）
    3. 这是群聊、什么任务、谁派的
    4. 输出要求：直接给结论，不要复述，缺信息就问
    5. collaboration=True 时额外告诉它可以「接力」——把自己那部分做完，
       再点名请别人补上另一部分。这是协作，不是推诿。
    """
    role = (agent.description or "").strip()
    role_line = f"你的角色：{agent.name}。{role}\n" if role else f"你的角色：{agent.name}。\n"

    # 列出其他成员：转交协议要能落地，前提是它知道可选的人有哪些。
    # 不列的话模型会写出「已转给数据分析同事」这种群里并不存在的人。
    roster = _roster_block(agent, peers)

    return (
        role_line
        + roster
        + f"\n你在一个多智能体工作群里。{asked_by} 发了一条任务，由你负责处理。\n"
        f"群里还有其他成员负责别的方向，只回答你职责范围内能确定的部分。\n\n"
        f"任务内容：\n{question}\n\n"
        "请直接给出结果，不要复述任务、不要说明你是被选中的。"
        "如果任务缺少必要信息，明确说明缺什么，不要猜。\n"
        "回复要短：能一两句说清就不要展开成三段。"
        "文件已经收到时不要再说「我已收到文件」，直接给结果。\n\n"
        + (COLLAB_BLOCK if collaboration else "")
        + "【转交协议｜必须遵守】\n"
        "如果这个任务超出你的职责，光说「不在我职责范围内」是不够的——"
        "那会让任务停在你这里，用户拿不到结果。\n"
        "你必须做两件事：\n"
        "1. 先说清你能确认的部分（没有就省略）\n"
        "2. 在最后单独一行，严格按下面格式输出，不能改写、不能加引号：\n"
        "[[HANDOFF: 成员名 | 一句话理由]]\n"
        "例如：[[HANDOFF: 数据分析师 | 涉及表格计算与汇总，超出文案职责]]\n"
        "系统识别到这一行才会真的把任务转给他，并带上你上面写的内容。\n"
        "只在确实做不了时使用；能做就自己做，不要为了省事而转交。\n\n"
        "【关于缺人】\n"
        "如果你判断是「群里根本没人能接这个任务」——不是别人更适合，"
        "而是没有这个方向的人——不要转给任何现有成员，转来转去也解决不了。"
        "这时在最后单独一行输出：\n"
        "[[NEED_MEMBER: 需要补什么角色，如 数据建模工程师]]\n"
        "系统会按这个描述创建一位新成员并交给他。\n\n"
        "【重要】如果群里的其他成员也都不适合（比如没有做数据的人），"
        "不要硬答，也不要假装转交，直接说清楚：「群里没有擅长 X 的成员」，"
        "并建议用户补充成员或自己确认。硬答会给出不可靠的结论，比不答更糟。"
    )


#: 转交协议：``[[HANDOFF: 成员名 | 理由]]``
#: 用双中括号包住，正常回复里几乎不会出现；冒号中英文都接受，
#: 因为模型偶尔会输出全角冒号。
_HANDOFF_RE = re.compile(
    r"\[\[\s*HANDOFF\s*[:：]\s*([^|\]|]+?)\s*\|\s*([^\]|]*?)\s*\]\]",
    re.IGNORECASE,
)


def parse_handoff(text: str) -> Tuple[Optional[str], str]:
    """从回复里取出转交目标与理由。没有标记时返回 (None, "")。"""
    if not text:
        return None, ""
    m = _HANDOFF_RE.search(text)
    if not m:
        return None, ""
    return m.group(1).strip(), m.group(2).strip()


#: 「群里没人能做」的显式标记 ``[[NEED_MEMBER: 能力描述]]``。
#: 比关键词猜测可靠得多：模型明确表达了缺人，系统照做即可。
_NEED_MEMBER_RE = re.compile(
    r"\[\[\s*NEED_MEMBER\s*[:：]\s*([^\]]+?)\s*\]\]",
    re.IGNORECASE,
)


def parse_need_member(text: str) -> Optional[str]:
    """解析「群里缺人」标记，返回需要补的角色描述。

    没有标记时返回 None——这是最可靠的触发信号，比从自然语言里猜准得多。
    """
    if not text:
        return None
    m = _NEED_MEMBER_RE.search(text)
    if not m:
        return None
    desc = m.group(1).strip()
    return desc or "该任务所需的专职角色"


def strip_handoff(text: str) -> str:
    """去掉协议标记，留下真正要给用户看的内容。

    模型常把「我先说明 A，再转交 B」写在同一条里，
    前半段是有价值的信息，要保留下来传给下一位。
    """
    if not text:
        return ""
    out = _HANDOFF_RE.sub("", text)
    out = _NEED_MEMBER_RE.sub("", out)
    return out.strip()


#: 模型经常「说了不归我管」但忘了输出协议标记，任务就卡在它这里。
#: 用这组词做兜底识别；只在回复很短时才认定为推辞——长回复通常已经
#: 给了实质内容，不该被误判成拒绝。
_REFUSAL_RE = re.compile(
    r"(不在.{0,6}职责|不属于.{0,4}(职责|范围)|超出.{0,4}(职责|能力)"
    r"|请转给|建议(由|转给)|需要转交给|无法处理这类|我不负责|不负责这块)"
)

#: 「群里没人能做」的强信号。这类话通常出现在长回复里（先说能做什么，
#: 再说缺人），所以不受长度限制——它指向的是人力不足，不是信息不足。
_NOBODY_RE = re.compile(
    r"(群里没有|群内没有|没有擅长|缺少(擅长|相关|对口)"
    r"|建议(补充|添加|增加|引入)[^，。；\n]{0,10}(成员|同事|人))"
)


def looks_like_refusal(text: str) -> bool:
    body = (text or "").strip()
    if not body:
        return False
    # 明确说「群里没人能做」时不看长度：这种回复往往先讲了能做的部分，
    # 真正关键的「缺人」在末尾一句，按长度过滤会把它们全漏掉。
    if _NOBODY_RE.search(body):
        return True
    # 弱拒绝词（「不归我管」这类）只在短回复里认。
    # 长回复通常已经给了实质内容，只是顺带提了一句边界，
    # 那种情况转交等于把已经答好的内容丢掉重来。
    if len(body) > 150:
        return False
    return bool(_REFUSAL_RE.search(body))


def says_nobody(text: str) -> bool:
    """回复里是否明确说了「群里没人能做」。

    这个判断比路由模型更可信：回答的人刚读完成员列表和任务原文，
    而路由模型只看成员描述，遇到空泛的描述（如「软件方面的东西」）
    会硬选一个不合适的，于是「缺人」被误处理成「转交」。
    """
    return bool(_NOBODY_RE.search(text or ""))


def find_agent_by_name(agents: List[Agent], name: str) -> Optional[Agent]:
    """按名字找成员。模型可能带 @ 或多余空格，做一次宽松匹配。"""
    target = (name or "").lstrip("@").strip()
    if not target:
        return None
    for a in agents:
        if a.name.strip() == target:
            return a
    # 退一步：允许「数据分析同事」这种近似称呼命中「数据分析师」
    for a in agents:
        if target in a.name or a.name in target:
            return a
    return None


def build_recruit_prompt(
    agent: Agent,
    task: str,
    asked_by: str,
    files_note: str = "",
    collaboration: bool = False,
    peers: Optional[List[Agent]] = None,
) -> str:
    """新成员接手时的开场。

    新成员不知道自己是「被临时招来的」，也不知道前面发生了什么。
    不说清楚的话，它会像普通成员那样回答，缺的信息也不会主动要。
    """
    role = (agent.description or "").strip()
    role_line = f"你的角色：{agent.name}。{role}\n" if role else f"你的角色：{agent.name}。\n"

    parts = [
        role_line,
        _roster_block(agent, peers),
        f"\n你刚被加入这个多智能体工作群。{asked_by} 提了一个任务，"
        "群里原有成员都表示做不了，所以由你接手。\n\n",
        f"任务内容：\n{task}\n\n",
    ]
    if files_note:
        parts.append(files_note + "\n\n")
    if collaboration:
        parts.append(COLLAB_BLOCK)
    parts.append(
        "请直接开始处理：能确定的就给结论，缺什么就明确说缺什么，"
        "不要复述任务、不要说明你是新加入的。"
    )
    return "".join(parts)


def build_reroute_message(original: str, agent_name: str, refusal: str) -> str:
    """给「重新派活」的路由补上下文。

    路由第一次只看用户那句话（常常是「你执行吧」这种），根本看不出
    需要什么能力，于是随便挑一个。把接活的人说「做不了」的原文喂回去，
    路由才判断得出「这个方向群里根本没人」。

    这是从关键词猜测升级到语义判断的关键一步。
    """
    return (
        f"{original}\n\n"
        f"【补充说明】{agent_name} 看过任务后表示无法承担，它的说明是：\n"
        f"{refusal.strip()[:400]}\n\n"
        "请据此重新判断：群里有没有成员能真正完成这个任务？\n"
        "注意区分两种情况：\n"
        "· 只是别人更合适 → 选出那位成员的名字\n"
        "· 缺的是这个方向的人（现有成员都不具备所需能力）→ assignee 填 null，"
        "系统会按任务补一位新成员"
    )


#: 协作接力标记 ``[[NEXT: 成员名 | 要补充什么]]``。
#: 与 ``[[HANDOFF: ...]]`` 的区别很关键：
#:   HANDOFF = 「我做不了，换人」（推诿，用户看到的是甩锅）
#:   NEXT    = 「我这块做完了，请他补上另一半」（协作，用户看到的是接力）
_NEXT_RE = re.compile(
    r"\[\[\s*NEXT\s*[:：]\s*([^|\]|]+?)\s*\|\s*([^\]|]*?)\s*\]\]",
    re.IGNORECASE,
)


def parse_next(text: str) -> tuple[Optional[str], str]:
    """解析协作接力标记，返回 (下一个成员名, 要补充的内容)。

    没有标记时返回 (None, "")。
    """
    if not text:
        return None, ""
    m = _NEXT_RE.search(text)
    if not m:
        return None, ""
    return m.group(1).strip(), m.group(2).strip()


def strip_protocol(text: str) -> str:
    """去掉所有协议标记，留下给用户看的正文。"""
    if not text:
        return ""
    out = _HANDOFF_RE.sub("", text)
    out = _NEED_MEMBER_RE.sub("", out)
    out = _NEXT_RE.sub("", out)
    return out.strip()


def build_chain_prompt(
    next_agent: Agent,
    original_task: str,
    contributions: List[tuple[str, str]],
    focus: str,
    asked_by: str,
    peers: Optional[List[Agent]] = None,
) -> str:
    """接力给下一位时的任务描述。

    要带上**所有**前序成员的发言，而不只是上一位——协作是链式的，
    只给最后一个人的发言，第三位就看不到第一位的结论了。

    focus 是上一位点名要这位补充的内容。
    """
    if contributions:
        history = "\n\n".join(
            f"【{name} 的部分】\n{text}" for name, text in contributions
        )
        history_block = f"同事们已经完成的部分：\n{history}\n\n"
    else:
        history_block = ""

    focus_line = (
        f"上一位点名请你补充：{focus}\n请聚焦这部分，不要重复别人已经做过的。\n\n"
        if focus
        else ""
    )

    return (
        f"原始任务（{asked_by} 提出）：\n{original_task}\n\n"
        + _roster_block(next_agent, peers)
        + history_block
        + focus_line
        + "请接着完成你负责的部分。\n"
        "可以直接引用同事已经得出的结论，不要推翻重做；"
        "如果发现他们的结论有问题，明确指出并说明理由。\n"
        "回复要短，能一两句说清就不要展开成三段。"
    )


def build_handoff_prompt(
    next_agent: Agent,
    original_task: str,
    from_agent: Agent,
    carried: str,
    asked_by: str,
) -> str:
    """转交后的任务描述。

    必须带上前一位已经确认的内容，否则接手的人会把同样的活重做一遍，
    用户看到的就是「换个人重来」而不是「接力」。
    """
    return (
        f"原始任务（{asked_by} 提出）：\n{original_task}\n\n"
        f"前一位同事「{from_agent.name}」已经处理过一轮，他确认的内容如下：\n"
        f"{carried or '（没有留下可用信息）'}\n\n"
        "请接力完成。不要重复他做过的事，"
        "也不要再问他已经确认过的信息；只处理他留给你的部分。\n"
        "如果任务确实还缺关键信息，直接说明缺什么。"
    )


def format_reply_content(agent: Agent, text: str, asked_by: str) -> str:
    """给回复加上 @ 发起人。"""
    body = (text or "").strip()
    prefix = f"@{asked_by} "
    if body.startswith(prefix.strip()):
        return body
    return prefix + body


async def save_message(
    db: AsyncSession,
    group_id: str,
    sender_type: str,
    content: str,
    sender_id: Optional[str] = None,
    sender_name: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> GroupMessage:
    """落一条群消息。"""
    msg = GroupMessage(
        group_id=group_id,
        sender_type=sender_type,
        sender_id=sender_id,
        sender_name=sender_name,
        content=content,
        meta=meta or {},
    )
    db.add(msg)
    await db.flush()
    return msg


async def load_agents(db: AsyncSession, group: AgentGroup) -> List[Agent]:
    """按 agent_ids 的顺序取出成员，跳过已被删除的。"""
    ids = list(group.agent_ids or [])
    if not ids:
        return []
    rows = await db.execute(select(Agent).where(Agent.id.in_(ids)))
    found = {a.id: a for a in rows.scalars().all()}
    return [found[i] for i in ids if i in found]


def find_mentioned_agent(agents: List[Agent], message: str) -> Optional[Agent]:
    """从消息里识别 @成员。

    只做精确名字匹配（长名字优先），避免「@数据」误命中「@数据分析师」。
    """
    for agent in sorted(agents, key=lambda a: len(a.name), reverse=True):
        if f"@{agent.name}" in message:
            return agent
    return None
