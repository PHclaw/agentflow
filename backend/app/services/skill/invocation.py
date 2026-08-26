"""Skill 调用消息组装：纯 system + 已注入变量的 user。"""
from __future__ import annotations

from app.security import decrypt_text
from app.services.prompt_utils import (
    build_executable_user,
    extract_system_from_spec_md,
    looks_like_spec_md,
)


def _resolve_system_text(raw: str) -> str:
    """文件 Skill 存明文；旧库密文仍尝试解密。"""
    text = (raw or "").strip()
    if not text:
        return ""
    # Fernet token 通常以 gAAAA 开头
    if text.startswith("gAAAA"):
        try:
            return decrypt_text(text).strip()
        except ValueError:
            return text
    return text


def resolve_call_system(agent) -> str:
    """调用时只用纯 System，不把整份 Spec MD 塞给模型。"""
    raw = _resolve_system_text(getattr(agent, "system_prompt_enc", None) or "")
    md = (getattr(agent, "md_doc", None) or "").strip()
    extracted = extract_system_from_spec_md(md) or extract_system_from_spec_md(raw)
    if extracted:
        return extracted
    if raw and not looks_like_spec_md(raw):
        return raw
    if md and not looks_like_spec_md(md):
        return md
    return raw or md


def prepare_call_messages(
    agent,
    variables: dict[str, str] | None,
) -> tuple[str, str]:
    """返回 (system, user_text)，user 已渲染且保证变量内容进入正文。"""
    system = resolve_call_system(agent)
    if not system:
        raise ValueError("智能体缺少可执行 System Prompt，请拥有者重新优化发布")
    user_text = build_executable_user(
        getattr(agent, "user_prompt_template", None) or "{{input}}",
        variables,
    )
    return system, user_text
