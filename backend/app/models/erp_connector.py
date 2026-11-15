"""外部只读数据源（ERP）连接器配置模型。

用途：把第三方 ERP 的**只读**数据库接入工作流的 `erp_read` 工具节点，
读到的数据（脱敏后）再灌给下游的智能体节点（PiAgent）。

安全约束（与字段设计一一对应）：
- 只读：本模型只描述连接与白名单，执行侧只会拼 `SELECT ... LIMIT`，
  且对 Postgres 强制 `default_transaction_read_only`。真正的硬隔离仍
  依赖对方提供**只读账号**。
- 凭证：密码以 Fernet 密文落库（``password_enc``），接口层永不回传明文。
- 表白名单：``allowed_tables`` 限定可查的表，杜绝任意表拖取。
- 归属隔离：``owner_id`` 绑定创建用户，非本人不可见 / 不可用。
"""
import uuid

from sqlalchemy import (
    Boolean, Column, DateTime, Integer, JSON, String, Text, UniqueConstraint,
)

from app.core.base import Base


class ERPConnectorConfig(Base):
    """第三方 ERP 只读连接器。"""

    __tablename__ = "erp_connectors"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # 归属用户（users.external_id）。所有查询都按它隔离，参照知识库 user_id 的教训。
    owner_id = Column(String(36), nullable=False, index=True)

    # 用户可读别名，同一归属下唯一
    alias = Column(String(64), nullable=False)

    # 方言：postgresql | sqlite（异步驱动 asyncpg / aiosqlite 已在依赖内）。
    # 其它库（mysql/mssql/oracle）需另装对应异步驱动后再在此扩展。
    db_type = Column(String(32), nullable=False, default="postgresql")

    host = Column(String(255), nullable=True)
    port = Column(Integer, nullable=True)
    database = Column(String(255), nullable=False, default="")
    schema = Column(String(128), nullable=True)
    user = Column(String(128), nullable=True)
    # Fernet 密文；sqlite 场景可为空
    password_enc = Column(Text, nullable=False, default="")

    # 可选：直接给出完整 SQLAlchemy 异步 URL，给了就优先用它（便于特殊参数）。
    dsn_override = Column(Text, nullable=True)

    # 允许查询的表名白名单（大小写不敏感）。空列表 = 一律拒绝。
    allowed_tables = Column(JSON, nullable=False, default=list)

    # 字段映射 / 脱敏规则：{ "<列名>": {"as": "<对外名>", "mask": "none|pii|drop"} }
    # 按列名全局套用；未列出的列原样透出。
    field_map = Column(JSON, nullable=False, default=dict)

    # 单次读取的行上限（仍受全局 CONNECTOR_MAX_ROW_LIMIT 二次封顶）。
    row_limit = Column(Integer, nullable=False, default=200)
    connect_timeout = Column(Integer, nullable=False, default=10)

    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("owner_id", "alias", name="uq_erp_connector_owner_alias"),
    )
