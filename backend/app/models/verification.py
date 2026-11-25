"""验证码存储模型。

为什么不只用进程内存
--------------------
验证码的默认存储原本是「有 Redis 就用 Redis，没有就退回 uvicorn worker
的进程内存」。后者在两种常见情况下会**静默丢码**：

1. ``scripts/dev-backend.ps1`` 是用 ``uvicorn --reload`` 起的。每改存一次
   Python 文件，worker 就重启一次，内存里的验证码全部蒸发。而它装的
   ``requirements-lite.txt`` 刻意不带 Redis —— 于是**开发时最常走的这条路
   恰好每次都丢码**。
2. 多 worker / 多副本部署且没配 Redis 时，发码落在 A 进程、校验落在 B 进程。

两种情况的表现完全一样：用户收到邮件、把码填进去，得到「验证码已过期，
请重新获取」——**而且远没到 TTL**。因为键不是过期了，是根本不存在了。

改法：兜底存储改用数据库。数据库在本项目里是**必然存在**的依赖（Redis 不是），
所以它既能在单进程下扛住重启，也能在多进程间共享，且不需要任何额外组件。
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, Index, String, Text

from app.core.base import Base


class VerificationCode(Base):
    """一条验证码 / 冷却标记 / 频次计数。

    键的命名沿用 ``services.verification`` 里的 ``vcode:*`` 前缀，
    所以这个表里同时装着三种语义不同的行：验证码本体、重发冷却、每小时计数。
    它们共用「有值 + 有到期时间」这套结构，没必要拆表。

    刻意**不建外键指向 users**：验证码是在用户注册成功之前签发的，
    那个邮箱此刻还没有对应的用户行。
    """

    __tablename__ = "verification_codes"

    #: 完整键名，如 ``vcode:code:register:someone@example.com``
    key = Column(String(255), primary_key=True)

    #: 值。验证码是 JSON（哈希 + 试错次数 + 签发时间），计数是数字字符串。
    value = Column(Text, nullable=False)

    #: 到期时间（UTC）。
    #: **NULL 表示永不过期** —— 对应存储层 ``ttl <= 0`` 的语义，
    #: 那条约定被 ``CODE_RESEND_INTERVAL=0`` 的场景依赖着（见 issue_code）。
    expires_at = Column(DateTime, nullable=True)

    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    __table_args__ = (
        # 过期清理（DELETE ... WHERE expires_at < now）走这个索引
        Index("ix_verification_codes_expires_at", "expires_at"),
    )
