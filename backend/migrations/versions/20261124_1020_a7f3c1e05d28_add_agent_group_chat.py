"""add agent_groups and group_messages

Revision ID: a7f3c1e05d28
Revises: b4e1c7a90f23
Create Date: 2026-11-24 10:20:00.000000

结构迁移。

为什么要新表，而不是复用 chat_sessions
------------------------------------
``chat_sessions`` 是**一对一**结构：``agent_id`` 非空，消息整体塞在一个
JSON 数组里。群聊有两个无法回避的差异：

1. **成员是多个**，一条会话对应 N 个 agent，塞不进 ``agent_id`` 这个单值字段；
2. **消息需要按时间分页**。JSON 数组只能整存整取，群聊消息量比单聊大得多，
   每次拉全量会越来越慢。

所以拆成两张表：``agent_groups`` 存群与成员，``group_messages`` 一行一条消息。

几个字段的取舍
--------------
``agent_ids`` 用 JSON 而不是关联表：成员数通常 3~10，不需要按成员反查群，
而关联表会让「保序」这件事变麻烦（顺序影响路由时的默认展示顺序）。

``group_messages.sender_name`` 冗余存一份显示名：成员被移出群后，历史消息
仍要能显示是谁说的，不能因为查不到 agent 就变成空白。

``meta`` 承载路由信息（``reply_to`` / ``route_reason`` / ``confidence``），
其中 ``reply_to`` 指向用户那条消息的 id —— 这是「接任务后 @ 回发起人」的
数据基础，前端据此渲染引用关系。

downgrade 直接丢表：群聊是纯新增能力，回滚不涉及任何已有数据的迁移。
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'a7f3c1e05d28'
down_revision: Union[str, None] = 'b4e1c7a90f23'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'agent_groups',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('agent_ids', sa.JSON(), nullable=False),
        # auto / manual / off
        sa.Column('route_mode', sa.String(length=16), nullable=False),
        sa.Column('settings', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_agent_groups_user_id', 'agent_groups', ['user_id'], unique=False)
    op.create_index('ix_agent_groups_created_at', 'agent_groups', ['created_at'], unique=False)

    op.create_table(
        'group_messages',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('group_id', sa.String(length=36), nullable=False),
        # user / agent / system
        sa.Column('sender_type', sa.String(length=12), nullable=False),
        sa.Column('sender_id', sa.String(length=36), nullable=True),
        sa.Column('sender_name', sa.String(length=100), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('meta', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_group_messages_group_id', 'group_messages', ['group_id'], unique=False)
    op.create_index('ix_group_messages_created_at', 'group_messages', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_group_messages_created_at', table_name='group_messages')
    op.drop_index('ix_group_messages_group_id', table_name='group_messages')
    op.drop_table('group_messages')
    op.drop_index('ix_agent_groups_created_at', table_name='agent_groups')
    op.drop_index('ix_agent_groups_user_id', table_name='agent_groups')
    op.drop_table('agent_groups')
