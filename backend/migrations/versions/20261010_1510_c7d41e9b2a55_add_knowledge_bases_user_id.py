"""add knowledge_bases.user_id

Revision ID: c7d41e9b2a55
Revises: a3a916f5f642
Create Date: 2026-10-10 15:10:00.000000

知识库此前没有归属字段，接口也只校验「已登录」，于是任何登录用户都能
看到、下载、删除别人的知识库。这里补上归属列，并把历史数据归给最早
注册的账号（那批库都是早期验证时创建的）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7d41e9b2a55'
down_revision: Union[str, None] = 'a3a916f5f642'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('knowledge_bases', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.String(length=36), nullable=True))
        batch_op.create_index('ix_knowledge_bases_user_id', ['user_id'], unique=False)

    # 历史数据没有归属信息，归给最早注册的账号，避免它们直接变成孤儿
    conn = op.get_bind()
    owner = conn.execute(
        sa.text("SELECT external_id FROM users ORDER BY created_at ASC LIMIT 1")
    ).scalar()
    if owner:
        conn.execute(
            sa.text("UPDATE knowledge_bases SET user_id = :owner WHERE user_id IS NULL"),
            {"owner": owner},
        )


def downgrade() -> None:
    with op.batch_alter_table('knowledge_bases', schema=None) as batch_op:
        batch_op.drop_index('ix_knowledge_bases_user_id')
        batch_op.drop_column('user_id')