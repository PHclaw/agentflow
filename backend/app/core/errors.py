"""把内部异常转成对外的安全文案。

背景：接口在异常分支里直接把 `str(exc)` 回给前端，会把文件路径、依赖版本、
SQL 片段甚至连接串片段带出去（CodeQL 的 py/stack-trace-exposure 就是指这个）。
但用户又需要一个能反馈给我们的凭据，所以折中做法是：

- 完整异常（含堆栈）只进日志，附一个短 trace id
- 响应里只给固定文案 + trace id，用户报障时报 trace id 即可定位
"""
from __future__ import annotations

import logging
import uuid

logger = logging.getLogger(__name__)

DEFAULT_FALLBACK = "服务暂时不可用，请稍后重试"


def log_and_mask(
    exc: BaseException,
    *,
    where: str,
    fallback: str = DEFAULT_FALLBACK,
) -> tuple[str, str]:
    """记录异常并返回 (trace_id, 对外文案)。

    where 用来在日志里定位来源，例如 "billing.webhook"。
    """
    trace_id = uuid.uuid4().hex[:12]
    logger.exception("[%s] %s (trace=%s)", where, exc, trace_id)
    return trace_id, f"{fallback}（trace: {trace_id}）"
