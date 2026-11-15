"""strip hardcoded model names from stored workflow definitions

Revision ID: c3f8a91d5e42
Revises: d8e52f1a9b37
Create Date: 2026-10-12 18:20:00.000000

数据迁移，不是结构迁移。

背景
----
节点里的 ``model`` 只是一个会被**原样发给「当前生效配置的端点」**的字符串，
而那个端点由每个用户自己配。预置模板和早期前端默认值却把模型名钉死在
节点上（``gpt-4`` / ``gpt-4o-mini``），于是本地 Ollama、DeepSeek 等用户
一执行就吃到 ``model 'gpt-4' not found``（HTTP 404）。

这里把 ``config.model`` / ``data.model`` 一律删掉，节点即回退到生效配置。

为什么连用户自建的 Agent 一起改
------------------------------
模型下拉此前解析失败、永远只显示写死的 ``gpt-4o-mini`` / ``gpt-4o``
两个选项。也就是说**没有任何用户可能主动选到一个在自己端点上存在的
模型**——存量里的模型名全部来自模板或前端默认值，不代表用户意图。
删掉它们只会让原本跑不起来的工作流恢复可用。
"""
import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'c3f8a91d5e42'
down_revision: Union[str, None] = 'd8e52f1a9b37'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


#: 需要清理的表与列。两处都是 JSON（SQLite 下存为 TEXT）
TARGETS = (
    ('workflow_templates', 'workflow_definition'),
    ('agents', 'workflow_definition'),
)


def _strip_models(payload):
    """删掉节点配置里写死的模型名；没改动时返回 None。"""
    if not isinstance(payload, dict):
        return None
    changed = False
    for node in payload.get('nodes') or []:
        if not isinstance(node, dict):
            continue
        # 模板用 config，编辑器用 data，两种写法都得清
        for key in ('config', 'data'):
            cfg = node.get(key)
            if isinstance(cfg, dict) and 'model' in cfg:
                cfg.pop('model')
                changed = True
    return payload if changed else None


def upgrade() -> None:
    bind = op.get_bind()
    for table, column in TARGETS:
        rows = bind.execute(
            sa.text(f'SELECT id, {column} FROM {table} WHERE {column} IS NOT NULL')
        ).fetchall()
        for row_id, raw in rows:
            if raw is None:
                continue
            try:
                data = json.loads(raw) if isinstance(raw, str) else raw
            except (TypeError, ValueError):
                # 存的不是合法 JSON：宁可不动，也不该在迁移里毁掉数据
                continue
            patched = _strip_models(data)
            if patched is None:
                continue
            bind.execute(
                sa.text(f'UPDATE {table} SET {column} = :value WHERE id = :id'),
                {'id': row_id, 'value': json.dumps(patched, ensure_ascii=False)},
            )


def downgrade() -> None:
    """无法还原。

    原始值可能是 gpt-4、gpt-4o-mini，也可能是用户手填的任意型号名，
    迁移时没有留档，这里只能放弃。
    """
    pass