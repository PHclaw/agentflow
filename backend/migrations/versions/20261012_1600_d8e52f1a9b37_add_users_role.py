"""add users.role

Revision ID: d8e52f1a9b37
Revises: c7d41e9b2a55
Create Date: 2026-10-12 16:00:00.000000

新增用户角色列，用于管理后台的权限判定。

用 ``server_default='user'`` 而不是只给 ORM 侧 ``default``：已有数据行在
ALTER TABLE 时必须有值，只靠 ORM 默认值会让存量用户的 role 变成 NULL，
而 ``is_admin`` 判空会得到「既不是 user 也不是 admin」的第三种状态。
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'd8e52f1a9b37'
down_revision: Union[str, None] = 'c7d41e9b2a55'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'role',
                sa.String(length=20),
                nullable=False,
                server_default='user',
            )
        )


def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('role')
