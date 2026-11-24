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
) -> Tuple[Optional[Agent], str, float]:
    """决定谁接这个任务。

    返回 (agent, 理由, 置信度)。agent 为 None 表示没人接：
    - 理由里会说明是「没有合适的」还是「需要用户确认」
    """
    if not agents:
        return None, "这个群还没有成员，先添加智能体", 0.0

    # 用户已 @ 指定 → 跳过路由
    if mentioned_agent is not None:
        return mentioned_agent, "由你直接指定", 1.0

    # manual 模式：不做自动派发
    if (group.route_mode or "auto") == "manual":
        names = "、".join(f"@{a.name}" for a in agents[:5])
        return None, f"这个群设成了手动指派，请用 @ 指定成员（{names}）", 0.0

    prompt = f"""你是任务调度器。下面是群里的智能体成员：

{chr(10).join(_agent_brief(a) for a in agents)}

用户任务：
{message}

判断哪一个成员最适合处理这个任务。判断依据是任务需要的能力与成员描述是否匹配，
不要因为名字听起来相关就选。

只输出 JSON，不要别的内容：
{{"assignee": "成员名字（没有合适的就填 null）", "reason": "一句话理由", "confidence": 0.0~1.0}}"""

    try:
        llm = LLMService()
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

    # 模型给了个不在列表里的名字
    logger.warning("group route picked unknown agent: %s", name)
    return None, f"调度结果指向了不存在的成员（{name}），请用 @ 指定", confidence


def build_reply_message(agent: Agent, question: str, asked_by: str) -> str:
    """构造发给 agent 的输入。

    三件事要说清楚：
    1. 它是谁（角色与能力边界）—— 群里只说「请回答」会让它越界答别人的活
    2. 这是群聊、什么任务、谁派的
    3. 输出要求：直接给结论，不要复述，缺信息就问
    """
    role = (agent.description or "").strip()
    role_line = f"你的角色：{agent.name}。{role}\n" if role else f"你的角色：{agent.name}。\n"

    return (
        role_line
        + f"\n你在一个多智能体工作群里。{asked_by} 发了一条任务，由你负责处理。\n"
        f"群里还有其他成员负责别的方向，只回答你职责范围内能确定的部分。\n\n"
        f"任务内容：\n{question}\n\n"
        "请直接给出结果，不要复述任务、不要说明你是被选中的。"
        "如果任务缺少必要信息，明确说明缺什么，不要猜。"
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
