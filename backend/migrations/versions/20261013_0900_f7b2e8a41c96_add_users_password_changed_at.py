"""add users.password_changed_at

Revision ID: f7b2e8a41c96
Revises: d5a7c3e91b48
Create Date: 2026-10-13 09:00:00.000000

结构迁移。

为什么要这一列
------------
改密码必须能把**已经发出去的 token** 作废。原来的实现做不到：
token 是无状态 JWT，有效期 7 天，签发之后服务端没有任何凭据能把它撤回。
结果是账号被盗后用户改了密码，入侵者手里的 token 还能继续用满一周 ——
「改密码」这个最基本的安全动作形同虚设。

做法：token 里带上签发时的 ``password_changed_at``，鉴权时和库里的当前值比对。
鉴权链路本来就查一次库（为了确认账号没被停用），所以这个判断不增加额外往返。

downgrade 只是丢一列；已签发的 token 里带的 ``pwd_ts`` 会被忽略，
退回到「改密码不踢人」的旧行为。
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'f7b2e8a41c96'
down_revision: Union[str, None] = 'd5a7c3e91b48'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('password_changed_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'password_changed_at')
