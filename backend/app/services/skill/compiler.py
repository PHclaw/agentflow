"""Skill Spec 编译：草稿 → 纯 system + user 模板 + md_doc + 路由元数据。"""
from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.json_task import run_json_task
from app.services.prompt_utils import extract_variables

_COMPILE_SYSTEM = (
    "你是「专业 Skill 架构师」。把草稿升级为某一专业方向的专属 Executable Specification，"
    "可直接作为调用时的 system / user 模板。\n"
    "必须只输出一个 JSON 对象，不要 Markdown 围栏，不要多余解释。\n"
    "字段固定：\n"
    "- system: string，该专业领域的可执行角色、能力边界、术语规范、禁止事项"
    "（作为调用时的 system，勿写 Markdown 文档结构）\n"
    "- user: string，可执行 User Prompt 模板，可变输入必须用 {{变量名}}\n"
    "- requirements: string，该专业下的约束与验收标准（简短条目）\n"
    "- routerBlurb: string，1～2 句「适用场景」摘要，专供选型，不要写内部 Prompt\n"
    "- triggers: string 数组，3～8 个触发词/短句（用户可能怎么问），专供选型\n"
    "硬性要求：\n"
    "1) 必须紧扣给定「专业方向」，禁止写成泛化通用助手。\n"
    "2) 明确该专业会做什么 / 不做什么，以及领域术语与输出验收。\n"
    "3) 内容必须足够完备，可直接用于模型调用；不要空话套话。\n"
    "4) user 必须保留或声明至少一处 {{变量}}（优先 {{input}}），"
    "以便调用时注入用户真实问题；禁止写成没有占位符的固定寒暄。\n"
    "5) routerBlurb/triggers 只描述「何时选用本 Skill」，不要泄露 system 全文。"
)


def assemble_executable_md(
    *,
    name: str,
    description: str,
    author_name: str,
    system_out: str,
    user_out: str,
    requirements: str = "",
    specialty: str = "",
) -> str:
    """组装专业 Skill Executable Spec MD（文档用；调用时不整份塞给模型）。"""
    vars_found = extract_variables(user_out)
    var_lines = "\n".join(f"- `{v}`" for v in vars_found) or "- （无变量）"
    req = requirements.strip() or "按该专业目标高质量完成输出；不输出无关解释。"
    specialty_line = (specialty or "").strip() or "（未指定）"
    return (
        f"# {name}\n"
        f"> 专业 Skill Executable Specification | 专业: {specialty_line} | 发布人: {author_name}\n\n"
        f"## 专业方向\n{specialty_line}\n\n"
        f"## 目标\n{description or name}\n\n"
        f"## 输入变量\n{var_lines}\n\n"
        f"## 调用 Prompt（实际发给模型）\n\n"
        f"### System\n```text\n{system_out.strip()}\n```\n\n"
        f"### User\n```text\n{user_out.strip()}\n```\n\n"
        f"## 约束与验收\n{req}\n"
    )


def _ensure_user_placeholders(user_out: str, user_prompt: str) -> str:
    if extract_variables(user_out):
        return user_out
    draft_vars = extract_variables(user_prompt)
    if draft_vars:
        return user_out.rstrip() + "\n\n" + "\n".join(f"{{{{{v}}}}}" for v in draft_vars)
    return user_out.rstrip() + "\n\n{{input}}"


def _ensure_file_summary(user_out: str) -> str:
    text = user_out or ""
    if "{{file_summary}}" in text:
        return text
    return text.rstrip() + "\n\n## 当前上传文件\n{{file_summary}}"


def _normalize_triggers(raw: Any, *, specialty: str, name: str) -> list[str]:
    out: list[str] = []
    if isinstance(raw, list):
        for item in raw:
            s = str(item).strip()
            if s and s not in out:
                out.append(s[:64])
    if not out:
        for s in (specialty, name):
            s = (s or "").strip()
            if s and s not in out:
                out.append(s[:64])
    return out[:8]


def _fallback_blurb(*, specialty: str, description: str, name: str) -> str:
    base = (description or specialty or name or "专业技能").strip()
    return f"适用于：{base}"[:256]


async def compile_executable_spec(
    db: AsyncSession,
    *,
    user_id: str,
    author_name: str,
    name: str,
    description: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    intent: str = "",
    specialty: str = "",
) -> dict[str, Any]:
    """草稿 → 专业专属 Skill Spec。

    返回：
    - system: 纯可执行角色指令（调用时用）
    - user: 带 {{变量}} 的模板
    - md_doc: 完整 Spec 文档（给人看 / 版本快照）
    - router_blurb / triggers: 选型元数据（公开，不进执行 system）
    """
    specialty_text = (specialty or "").strip()
    user = (
        f"【名称】{name}\n"
        f"【专业方向】{specialty_text or '（未指定，请按描述推断并写清专业边界）'}\n"
        f"【描述】{description}\n"
        f"【运行模型】{model}\n"
        f"【发布人】{author_name}\n"
        f"【用户意图】{intent or '（无）'}\n"
        f"【草稿 System】\n{system_prompt or '（空）'}\n\n"
        f"【草稿 User】\n{user_prompt or '（空）'}\n\n"
        "请输出 system / user / requirements / routerBlurb / triggers。"
    )
    task = await run_json_task(
        db,
        user_id=user_id,
        system=_COMPILE_SYSTEM,
        user=user,
        temperature=0.25,
        max_tokens=4096,
    )
    parsed = task.data
    system_out = str(parsed.get("system") or system_prompt or "You are a helpful assistant.")
    user_out = _ensure_file_summary(
        _ensure_user_placeholders(
            str(parsed.get("user") or user_prompt or "{{input}}"),
            user_prompt,
        )
    )
    requirements = str(parsed.get("requirements") or "")
    router_blurb = str(parsed.get("routerBlurb") or parsed.get("router_blurb") or "").strip()
    if not router_blurb:
        router_blurb = _fallback_blurb(
            specialty=specialty_text, description=description, name=name
        )
    triggers = _normalize_triggers(
        parsed.get("triggers"), specialty=specialty_text, name=name
    )
    md_doc = assemble_executable_md(
        name=name,
        description=description,
        author_name=author_name,
        system_out=system_out,
        user_out=user_out,
        requirements=requirements,
        specialty=specialty_text,
    )
    return {
        "system": system_out.strip(),
        "user": user_out,
        "requirements": requirements,
        "md_doc": md_doc,
        "router_blurb": router_blurb[:256],
        "triggers": triggers,
        "raw": task.raw,
    }


async def compile_specialty_skill(
    db: AsyncSession,
    *,
    user_id: str,
    author_name: str,
    name: str,
    description: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    specialty: str,
    intent: str = "",
) -> dict[str, Any]:
    """专业 Skill 编译入口（语义别名）。"""
    return await compile_executable_spec(
        db,
        user_id=user_id,
        author_name=author_name,
        name=name,
        description=description,
        model=model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        intent=intent,
        specialty=specialty,
    )
