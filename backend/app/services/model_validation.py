from __future__ import annotations

from app.config import get_settings
from app.services.model_catalog import get_model_entry, list_model_names
from app.services.model_runtime import resolve_credentials


def require_api_key() -> tuple[str, str | None]:
    api_key, base_url = resolve_credentials()
    if not api_key:
        raise ValueError("未配置 API Key：请设置环境变量 CHATZOC_API_KEY 或 DASHSCOPE_API_KEY")
    return api_key, base_url


def require_known_model(model: str) -> str:
    """校验模型名在 config/models.json 启用清单中；返回规范 name。"""
    name = (model or "").strip()
    if not name:
        raise ValueError("model 不能为空")
    entry = get_model_entry(name)
    if not entry:
        known = ", ".join(list_model_names()[:12]) or "(清单为空)"
        raise ValueError(f"未知或未启用模型: {name}；可用: {known}")
    return str(entry["name"])


def resolve_callable_model(model: str | None) -> str:
    """调用路径：清单内用原模型，否则回落到 DEFAULT_MODEL（兼容旧 Skill）。"""
    name = (model or "").strip()
    if name:
        entry = get_model_entry(name)
        if entry:
            return str(entry["name"])
    return require_known_model(get_settings().default_model)


def require_known_models(models: list[str]) -> list[str]:
    return [require_known_model(m) for m in models]


def friendly_upstream_error(exc: BaseException) -> str:
    """把上游常见计费/配额错误转成可读中文。"""
    msg = (str(exc) or "").strip()
    name = type(exc).__name__
    blob = f"{name} {msg}".lower()
    if "FreeTierOnly" in msg or "Free quota exhausted" in msg:
        return (
            "模型免费额度已用尽或上游拒绝调用。请确认 ChatZOC（chatzoc_9b_B）可用，"
            "或检查 CHATZOC_BASE_URL / CHATZOC_API_KEY。"
        )
    if "timeout" in blob or "timed out" in blob:
        return "上游模型连接超时，请稍后重试。若 Skill 已生成文件，可刷新会话或再发一次。"
    if "connect" in blob and ("refused" in blob or "error" in blob):
        return "无法连接上游模型网关，请检查 CHATZOC_BASE_URL 是否可达。"
    if not msg:
        return f"上游调用失败（{name}）"
    return msg
