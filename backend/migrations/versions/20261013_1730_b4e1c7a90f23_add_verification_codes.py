"""add verification_codes

Revision ID: b4e1c7a90f23
Revises: f7b2e8a41c96
Create Date: 2026-10-13 17:30:00.000000

结构迁移。

为什么要这张表
--------------
验证码的兜底存储原本是 uvicorn worker 的**进程内存**（没配 Redis 时）。
它在两种情况下会静默丢码：

1. ``scripts/dev-backend.ps1`` 用 ``uvicorn --reload`` 启动，改一次 Python
   文件就重启一次 worker，内存里的验证码全部蒸发。而它装的
   ``requirements-lite.txt`` 刻意不含 Redis —— 开发时最常走的这条路，
   恰好每次都丢码。
2. 多 worker / 多副本且没配 Redis：发码落在 A 进程、校验落在 B 进程。

两者症状一致：用户收到邮件、填进去，得到「验证码已过期，请重新获取」，
**而且远没到 TTL**。键不是过期了，是根本不存在了。

数据库是本项目**必然存在**的依赖（Redis 不是），所以拿它当兜底：
单进程能扛重启，多进程能共享，且不需要引入任何额外组件。

表的键名沿用 ``vcode:*`` 前缀，所以验证码本体、重发冷却、每小时计数
共用这一张表 —— 三者都是「有值 + 有到期时间」，没必要拆开。

``expires_at`` 允许为 NULL，表示永不过期：对应存储层 ``ttl <= 0`` 的既有
语义，``CODE_RESEND_INTERVAL=0`` 时会用到（见 ``services/verification``）。

downgrade 直接丢表：验证码本来就是短命数据，回滚后重新获取即可。
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'b4e1c7a90f23'
down_revision: Union[str, None] = 'f7b2e8a41c96'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'verification_codes',
        sa.Column('key', sa.String(length=255), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('key'),
    )
    op.create_index(
        'ix_verification_codes_expires_at',
        'verification_codes',
        ['expires_at'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_verification_codes_expires_at', table_name='verification_codes')
    op.drop_table('verification_codes')
