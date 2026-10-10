"""对话与工作流的衔接层。

对话入口有两个执行体：

- **配置了工作流的 Agent**：走 `workflow_runtime`，按画布上的编排执行，
  最终回复取自 response 节点。
- **没有工作流的 Agent**：维持原样，走 `IntegratedAgentRuntime` 或 AI Agent 引擎。

本模块只负责前者。调用方先用 `agent_has_workflow` 判断，返回 True 时走这里，
否则继续走原有链路 —— 这样对既有 Agent 的行为零影响。
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent, ChatSession
from app.services.workflow_runtime import (
    WorkflowState,
    extract_final_response,
    has_workflow,
    normalize_workflow_definition,
    workflow_runtime,
)


@dataclass
class WorkflowTurn:
    """一轮工作流对话的结果"""

    content: str
    session_id: Optional[str] = None
    state: Optional[WorkflowState] = None
    failed_nodes: List[str] = field(default_factory=list)
    #: 工作区新生成的产物（智能体节点写入的文件），需透传给前端展示下载
    files: List[dict] = field(default_factory=list)


def collect_workflow_files(state: WorkflowState) -> List[dict]:
    """汇总各节点产出的文件。

    智能体节点会把 AI Agent 引擎生成的文件写进自己的节点输出，
    但工作流的回复只取文本 —— 产物曾被整段丢弃，用户只能看到
    「已生成 xxx.md」却找不到附件。按节点执行顺序收集并去重。
    """
    collected: List[dict] = []
    seen: set = set()

    for node_result in state.execution_history:
        outputs = state.node_outputs.get(node_result.node_id, {}) or {}
        files = outputs.get("files") or []
        if not isinstance(files, list):
            continue
        for item in files:
            if not isinstance(item, dict):
                continue
            key = item.get("path") or item.get("url") or item.get("name")
            if not key or key in seen:
                continue
            seen.add(key)
            collected.append(item)

    return collected


def agent_has_workflow(agent: Agent) -> bool:
    """该 Agent 是否配置了可执行的工作流"""
    return has_workflow(agent.workflow_definition)


def build_workflow_for_agent(agent: Agent) -> Dict[str, Any]:
    """归一化工作流定义，并把 Agent 的配置注入缺省的节点。

    节点自己没配模型 / 知识库时用 Agent 上的配置兜底，否则从 Agent 进入对话时
    会出现：LLM 节点用默认模型、知识节点直接报「未配置知识库 ID」。
    """
    definition = normalize_workflow_definition(agent.workflow_definition)

    model_config = agent.model_config or {}
    model = model_config.get("model")
    temperature = model_config.get("temperature")
    knowledge_base_id = agent.knowledge_base_id
    system_prompt = (agent.settings or {}).get("system_prompt")

    for node in definition.get("nodes", []):
        data = node.setdefault("data", {})
        node_type = node.get("type")

        if node_type == "llm":
            if model and not data.get("model"):
                data["model"] = model
            if temperature is not None and "temperature" not in data:
                data["temperature"] = temperature
            if system_prompt and not data.get("system_prompt"):
                data["system_prompt"] = system_prompt

        elif node_type == "knowledge":
            if knowledge_base_id and not data.get("kb_id"):
                data["kb_id"] = knowledge_base_id

    return definition


def _status_value(result) -> str:
    return getattr(result.status, "value", result.status)


async def run_workflow_turn(agent: Agent, message: str, db: AsyncSession) -> WorkflowTurn:
    """执行该 Agent 的工作流，返回本轮回复。"""
    definition = build_workflow_for_agent(agent)

    state = await workflow_runtime.execute_workflow(
        workflow_def=definition,
        input_data={
            "user_message": message,
            # 技能节点需要调用者身份来鉴权
            "caller_id": agent.user_id,
            "agent_id": agent.id,
        },
        db_session=db,
    )

    content = extract_final_response(state)
    failed = [r for r in state.execution_history if _status_value(r) == "failed"]

    if not content:
        # 节点配置有问题时不能给用户一个空白回复，要把原因说出来
        if failed:
            first = failed[0]
            reason = first.error or "未知错误"
            content = f"工作流执行中断（节点 {first.node_id}）：{reason}"
        else:
            content = "工作流已执行，但没有产生回复内容。请检查响应节点的配置。"

    return WorkflowTurn(
        content=content,
        state=state,
        failed_nodes=[r.node_id for r in failed],
        files=collect_workflow_files(state),
    )


# ---------------------------------------------------------------------------
# 会话持久化：复用 chat_sessions，让工作流对话也能出现在历史记录里
# ---------------------------------------------------------------------------


async def load_or_create_session(
    db: AsyncSession,
    agent_id: str,
    user_id: str,
    session_id: Optional[str] = None,
) -> ChatSession:
    """取指定会话；没有则复用该 Agent 最近一个会话；再没有就新建。"""
    if session_id:
        session = await db.get(ChatSession, session_id)
        if session and session.agent_id == agent_id and session.user_id == user_id:
            return session

    stmt = (
        select(ChatSession)
        .where(ChatSession.agent_id == agent_id, ChatSession.user_id == user_id)
        .order_by(ChatSession.updated_at.desc())
        .limit(1)
    )
    session = (await db.execute(stmt)).scalar_one_or_none()
    if session:
        return session

    session = ChatSession(
        id=str(uuid.uuid4()),
        agent_id=agent_id,
        user_id=user_id,
        messages=[],
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


def append_turn(
    session: ChatSession,
    user_message: str,
    assistant_message: str,
    files: Optional[List[dict]] = None,
) -> None:
    """把一轮对话写入历史。

    消息结构与 /chat/{agent_id}/history 返回给前端的格式保持一致，
    这样工作流对话的记录能被对话页正常回填。

    files 也要存：产物是生成后就存在的文件路径，只存正文的话
    刷新页面后附件就消失了。
    """
    now = datetime.now(timezone.utc).isoformat()
    messages = list(session.messages or [])
    messages.append(
        {
            "id": str(uuid.uuid4()),
            "role": "user",
            "content": user_message,
            "timestamp": now,
        }
    )
    assistant_entry: Dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "role": "assistant",
        "content": assistant_message,
        "timestamp": now,
    }
    if files:
        assistant_entry["files"] = files
    messages.append(assistant_entry)
    # JSON 列需要整体重新赋值，SQLAlchemy 才能检测到变化
    session.messages = messages
    session.updated_at = datetime.now(timezone.utc)
