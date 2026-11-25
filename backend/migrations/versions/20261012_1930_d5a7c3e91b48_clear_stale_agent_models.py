"""clear stale default model names from agents.model_config

Revision ID: d5a7c3e91b48
Revises: c3f8a91d5e42
Create Date: 2026-10-12 19:30:00.000000

数据迁移，不是结构迁移。

背景
----
``create_agent`` 在未指定 ``llm_config`` 时、以及「用模板创建 Agent」那条路径上，
都会把 ``model`` 写成硬编码的 ``gpt-4o-mini``。而 ``agent_turn`` 会把 Agent 的
模型名**注入到未指定模型的 LLM 节点**上 —— 于是上一条迁移刚从工作流节点里
清掉的 ``gpt-4o-mini``，转头又被 Agent 的配置填了回去，工作流照样报
``model 'gpt-4o-mini' not found``。

真正的根因在 ``LLMService``：它只取生效配置的**凭证**，丢掉了 ``model`` 字段，
所以即使把模型名清空也会退回 ``settings.OPENAI_MODEL``。已一并修掉。

为什么可以放心清这三个名字
------------------------
模型下拉此前解析失败、永远只显示这几个写死的选项。也就是说，**没有任何用户
可能主动选到一个在自己端点上真的存在的模型**；存量里的这三个值全部来自默认值，
不代表用户意图。清成空串后它们改为「跟随生效配置」—— 对真正的 OpenAI 用户而言
那正是他配好的模型，对本地端点用户则不再报错。

downgrade 无法还原原始值（可能是三者之一），只能放弃。
"""
import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'd5a7c3e91b48'
down_revision: Union[str, None] = 'c3f8a91d5e42'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


#: 项目写死的默认模型名。这些从来不是用户的真实选择。
STALE_MODELS = ('gpt-4o-mini', 'gpt-4o', 'gpt-4')


def upgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text('SELECT id, model_config FROM agents WHERE model_config IS NOT NULL')
    ).fetchall()

    for row_id, raw in rows:
        if raw is None:
            continue
        try:
            cfg = json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, ValueError):
            # 存的不是合法 JSON：宁可不动，也不该在迁移里毁掉数据
            continue
        if not isinstance(cfg, dict):
            continue
        if cfg.get('model') not in STALE_MODELS:
            continue

        cfg['model'] = ''
        bind.execute(
            sa.text('UPDATE agents SET model_config = :value WHERE id = :id'),
            {'id': row_id, 'value': json.dumps(cfg, ensure_ascii=False)},
        )


def downgrade() -> None:
    """无法还原 —— 原始值可能是三者之一，迁移时没有留档。"""
    pass