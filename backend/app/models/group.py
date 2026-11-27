"""多智能体群聊模型。

与 ChatSession 的区别：
- ChatSession 是一对一（一个 agent），消息整体存成一个 JSON 数组
- 群聊有多个成员，消息量大且需要按时间分页，所以独立成表

设计要点：
- AgentGroup.agent_ids 存成员，不建关联表——成员数量小（通常 3~10），
  而且需要保序（先加的在前面，影响路由时的默认顺序）
- GroupMessage 用 sender_type 区分「用户 / 智能体 / 系统」三类发言，
  系统发言用于展示路由决策（「XX 接下了这个任务」），让过程可见
- meta 里存 reply_to 指向被回应的消息，实现「接任务后 @ 回发起人」
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, String, Text, UniqueConstraint

from app.core.base import Base


class AgentGroup(Base):
    """智能体群聊"""

    __tablename__ = "agent_groups"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)

    # 成员 agent_id 列表，保持添加顺序
    agent_ids = Column(JSON, nullable=False, default=list)

    # 路由模式：
    #   auto   —— 由模型判断谁接（默认）
    #   manual —— 必须手动 @ 指定，不做自动派发
    #   off    —— 不路由，所有成员都回复（头脑风暴模式）
    route_mode = Column(String(16), nullable=False, default="auto")

    # 预留扩展：是否允许转交、单轮最多几人发言等
    settings = Column(JSON, nullable=False, default=dict)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class GroupMessage(Base):
    """群聊消息"""

    __tablename__ = "group_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    group_id = Column(String(36), nullable=False, index=True)

    # user（用户）/ agent（智能体）/ system（路由提示等系统消息）
    sender_type = Column(String(12), nullable=False)
    # agent 发言时为 agent_id；用户发言时为空；系统消息为空
    sender_id = Column(String(36), nullable=True)
    # 冗余一份显示名，避免每次查库；成员删除后历史消息仍可读
    sender_name = Column(String(100), nullable=True)

    content = Column(Text, nullable=False)

    # meta 里可能包含：
    #   reply_to      —— 被回应的消息 id（智能体接任务时指向用户那条）
    #   route_reason  —— 为什么选了这个智能体
    #   confidence    —— 路由置信度
    #   tokens        —— 本次消耗
    #   mentions      —— 被 @ 的成员名列表
    #   mention_all   —— @ 全体成员
    #   edited_at     —— 最后编辑时间（编辑后显示「已编辑」）
    meta = Column(JSON, nullable=False, default=dict)

    # 撤回：保留行、清空内容，历史链路不塌
    is_revoked = Column(Boolean, nullable=False, default=False, index=True)
    revoked_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class MessageReaction(Base):
    """消息表情回应。同一个人对同一消息同一表情只有一条。"""

    __tablename__ = "message_reactions"
    __table_args__ = (
        UniqueConstraint("message_id", "user_id", "emoji", name="uq_reaction_user_emoji"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(Integer, nullable=False, index=True)
    group_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), nullable=False)
    emoji = Column(String(16), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class MessageRead(Base):
    """已读回执。用户进群/看到消息时写入。"""

    __tablename__ = "message_reads"
    __table_args__ = (
        UniqueConstraint("message_id", "user_id", name="uq_message_read_user"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(Integer, nullable=False, index=True)
    group_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), nullable=False)
    read_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
