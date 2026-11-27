"""群聊自动补人。

当路由判定「群里没人能接这个任务」时，按任务现场造一个对口的智能体拉进群，
再把任务交给它。相当于给群配了一个「招聘」能力。

为什么必须有护栏
----------------
自动创建的成本不是一次 API 调用，而是**长期污染**：
凭空生成的成员会进入后续每一次路由的候选集，描述写得越泛，
后面派活越容易派错。所以：

- 单群上限 :data:`MAX_AUTO_MEMBERS` 个，到顶就不再招，直接告诉用户
- 新建成员在 ``settings`` 里打 ``auto_created`` 标记，方便识别与批量清理
- 只在路由明确返回「无人能接」时触发，正常流程不会走到这里
- 模型配置继承群里现有成员，避免新建的 Agent 因为没有模型而跑不起来
"""
import json
import re
from typing import Any, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.models.agent import Agent
from app.models.group import AgentGroup
from app.services.llm import LLMService

#: 单群自动补人的默认上限。超过这个数说明这个群的角色规划本身有问题，
#: 继续加人只会让路由更难判断。
#: 实际生效的上限可由群设置 auto_recruit_limit 覆盖（见 recruit_member）。
MAX_AUTO_MEMBERS = 3

#: 可配置上限的边界
MIN_AUTO_MEMBERS = 1
MAX_AUTO_MEMBERS_LIMIT = 8


def resolve_limit(group_settings: dict | None) -> int:
    """取这个群实际生效的自动补人上限。

    硬编码 3 太死：用户遇到「路由说没人能做但补不上」时没有余地。
    群里角色多、需要多种视角时（合规 + 技术 + 数据 + 运营）3 个明显不够。
    """
    raw = (group_settings or {}).get("auto_recruit_limit")
    if raw is None:
        return MAX_AUTO_MEMBERS
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return MAX_AUTO_MEMBERS
    return max(MIN_AUTO_MEMBERS, min(n, MAX_AUTO_MEMBERS_LIMIT))


def count_auto_created(agents: List[Agent]) -> int:
    """数一下群里已经自动创建了几个成员。"""
    n = 0
    for a in agents:
        settings = a.settings or {}
        if isinstance(settings, dict) and settings.get("auto_created"):
            n += 1
    return n


def _extract_json(text: str) -> Optional[dict]:
    """容错解析模型输出的 JSON（可能带代码围栏或前后解释）。"""
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


async def recruit_member(
    db: AsyncSession,
    group: AgentGroup,
    task: str,
    existing: List[Agent],
    user_id: str,
    role_hint: str | None = None,
) -> tuple[Optional[Agent], str]:
    """按任务招一个成员，返回 (新成员, 说明)。招不了时返回 (None, 原因)。

    调用方负责把它加进 ``group.agent_ids`` 并提交事务——这里只建 Agent 对象，
    不擅自改群成员，避免两步之间出错留下孤儿。

    role_hint 是接活的人明确说出的「缺什么角色」。它比从任务文本重新推断准得多：
    任务描述可能很含糊（「你执行吧」），而「数据建模工程师」是确切的。
    """
    limit = resolve_limit(group.settings)
    if count_auto_created(existing) >= limit:
        return None, (
            f"这个群已经自动补充了 {limit} 个成员，不再继续添加。"
            "可以在群设置里调大上限，或手动整理一下群成员"
        )

    # 继承模型配置：新建的 Agent 如果 provider 为空，执行时会直接报未配置
    inherited = {}
    for a in existing:
        cfg = a.model_config or {}
        if cfg.get("provider"):
            inherited = dict(cfg)
            break

    hint_line = (
        f"\n接活的同事明确指出需要补这类角色：{role_hint}\n"
        "请优先按这个方向命名和描述。"
        if role_hint
        else ""
    )

    prompt = f"""一个多智能体工作群接到了一个任务，但群里的成员都做不了。需要临时招一个人。

任务：
{task}
{hint_line}
现有成员（不要重复他们的方向）：
{chr(10).join(f"- {a.name}：{(a.description or '').strip() or '（未填写）'}" for a in existing)}

请设计一个真正能承担这个任务的角色。要求：
1. 名字具体到能看出职责，2-6 个字，不要用「助手」「专家」「小能人」这类泛称
2. 描述写清「擅长什么」和「不做什么」，40-70 字，用于后续派活判断
3. 只针对这个任务，不要设计成万能角色

只输出 JSON，不要别的内容：
{{"name": "角色名", "description": "能力描述"}}"""

    try:
        llm = LLMService(
            provider=inherited.get("provider", "openai"),
            model=inherited.get("model"),
        )
        raw = await llm.chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=300,
        )
    except Exception as exc:  # noqa: BLE001 - 招不到人不该让整轮对话失败
        logger.warning("recruit: llm failed: %s", exc)
        return None, "自动补人失败（模型不可用），请手动添加成员"

    data = _extract_json(raw)
    if not data:
        logger.warning("recruit: non-JSON output: %s", (raw or "")[:200])
        return None, "自动补人失败（模型返回格式异常），请手动添加成员"

    name = (data.get("name") or "").strip()[:100]
    desc = (data.get("description") or "").strip()[:500]
    if not name:
        return None, "自动补人失败（没生成出角色名），请手动添加成员"

    # 重名会让人分不清，加个后缀
    taken = {a.name for a in existing}
    if name in taken:
        for i in range(2, 10):
            if f"{name}{i}" not in taken:
                name = f"{name}{i}"
                break

    agent = Agent(
        user_id=user_id,
        name=name,
        description=desc,
        workflow_definition={"nodes": [], "edges": []},
        model_config=inherited,
        template=None,
        settings={
            "auto_created": True,
            "created_for_group": group.id,
            "recruit_reason": task[:200],
        },
        is_active=True,
    )
    db.add(agent)
    await db.flush()
    logger.info("recruit: created agent %s (%s) for group %s", name, agent.id, group.name)
    return agent, desc


def join_group(group: AgentGroup, agent: Agent) -> None:
    """把成员加到群列表末尾。

    用重新赋值而不是就地 append：``agent_ids`` 是 JSON 列，
    就地修改不会触发 SQLAlchemy 的变更检测，提交后可能没写进库。
    """
    ids = list(group.agent_ids or [])
    if agent.id not in ids:
        ids.append(agent.id)
    group.agent_ids = ids


def member_payload(agent: Agent) -> dict[str, Any]:
    return {
        "id": agent.id,
        "name": agent.name,
        "description": agent.description,
        "is_active": agent.is_active,
    }
