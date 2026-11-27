"""群聊交互增强：撤回/编辑标记、已读回执、表情回应。

Revision ID: a1b2c3d4e5f6
Revises: (head)
Create Date: 2026-11-25
"""
from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "a7f3c1e05d28"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    return column in {c["name"] for c in sa.inspect(bind).get_columns(table)}


def _has_table(table: str) -> bool:
    return table in sa.inspect(op.get_bind()).get_table_names()


def upgrade():
    # group_messages 新增两列；老库需要补，避免 SELECT 报 no such column
    if not _has_column("group_messages", "is_revoked"):
        op.add_column(
            "group_messages",
            sa.Column("is_revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    if not _has_column("group_messages", "revoked_at"):
        op.add_column("group_messages", sa.Column("revoked_at", sa.DateTime(), nullable=True))

    if not _has_table("message_reactions"):
        op.create_table(
            "message_reactions",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("message_id", sa.Integer(), nullable=False, index=True),
            sa.Column("group_id", sa.String(36), nullable=False, index=True),
            sa.Column("user_id", sa.String(36), nullable=False),
            sa.Column("emoji", sa.String(16), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("message_id", "user_id", "emoji", name="uq_reaction_user_emoji"),
        )

    if not _has_table("message_reads"):
        op.create_table(
            "message_reads",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("message_id", sa.Integer(), nullable=False, index=True),
            sa.Column("group_id", sa.String(36), nullable=False, index=True),
            sa.Column("user_id", sa.String(36), nullable=False),
            sa.Column("read_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("message_id", "user_id", name="uq_message_read_user"),
        )


def downgrade():
    for table in ("message_reads", "message_reactions"):
        if _has_table(table):
            op.drop_table(table)
    if _has_column("group_messages", "revoked_at"):
        op.drop_column("group_messages", "revoked_at")
    if _has_column("group_messages", "is_revoked"):
        op.drop_column("group_messages", "is_revoked")
