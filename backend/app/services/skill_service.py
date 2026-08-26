"""Skill 服务：定义存 skills/<slug>/，不再写 mct_agents。"""
from __future__ import annotations

import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.logging_setup import get_logger
from app.schemas import (
    AgentBuildRequest,
    AgentCallResponse,
    AgentCreate,
    AgentUpdate,
    ChatParams,
)
from app.services.agent_serializers import (
    serialize_for_role,
    to_owner,
    to_plaza_item,
    to_public,
)
from app.services.adapters.base import ChatResult
from app.services.model_runtime import run_chat
from app.services.prompt_utils import extract_variables
from app.services.skill.compiler import compile_executable_spec
from app.services.skill.invocation import prepare_call_messages, _resolve_system_text
from app.services.skill.store import (
    FileSkill,
    allocate_slug,
    delete_skill,
    get_skill,
    list_skills,
    save_skill,
)

logger = get_logger("skill")

__all__ = [
    "to_public",
    "to_owner",
    "serialize_for_role",
    "to_plaza_item",
    "compile_executable_spec",
    "default_workflow",
    "create_agent",
    "build_agent",
    "get_agent",
    "list_agents",
    "list_plaza_agents",
    "list_my_agents",
    "update_agent",
    "publish_agent",
    "publish_to_plaza",
    "deprecate_agent",
    "delete_agent",
    "call_agent",
    "migrate_stale_agent_models",
    "list_versions",
    "list_calls",
]


def _bump_version(current: str | None) -> str:
    if not current or current in {"v0.0.0", "0.0.0"}:
        return "v1.0.0"
    m = re.match(r"v?(\d+)\.(\d+)\.(\d+)", current)
    if not m:
        return "v1.0.0"
    major, minor, patch = (int(x) for x in m.groups())
    return f"v{major}.{minor + 1}.0"


def default_workflow(model: str, agent_id: str = "", version: str = "1.0.0") -> dict[str, Any]:
    return {
        "agentId": agent_id,
        "version": version,
        "steps": [
            {"name": "变量注入", "action": "injectVariables"},
            {"name": "模型调用", "action": "callModel", "model": model},
            {"name": "结果返回", "action": "formatOutput"},
        ],
    }


def _sync_workflow_model(workflow: dict[str, Any] | None, model: str) -> dict[str, Any]:
    wf = dict(workflow or {})
    steps = list(wf.get("steps") or [])
    new_steps: list[Any] = []
    for step in steps:
        if isinstance(step, dict) and step.get("action") == "callModel":
            new_steps.append({**step, "model": model})
        else:
            new_steps.append(step)
    if not new_steps:
        return default_workflow(model, str(wf.get("agentId") or ""), str(wf.get("version") or "1.0.0"))
    wf["steps"] = new_steps
    return wf


async def migrate_stale_agent_models(db: AsyncSession) -> int:
    """文件系统 Skill：把不在清单中的 model 写回 DEFAULT_MODEL。"""
    _ = db
    from app.services.model_validation import resolve_callable_model

    changed = 0
    for skill in list_skills(include_deprecated=True):
        target = resolve_callable_model(skill.model_name)
        if target == (skill.model_name or "").strip():
            continue
        logger.info(
            "migrate stale model skillId=%s %s -> %s",
            skill.id,
            skill.model_name,
            target,
        )
        skill.model_name = target
        skill.workflow = _sync_workflow_model(skill.workflow, target)
        save_skill(skill)
        changed += 1
    return changed


def _with_specialty_tag(tags: list[str] | None, specialty: str) -> list[str]:
    out = list(tags or [])
    s = (specialty or "").strip()
    if s and s not in out:
        out.insert(0, s)
    return out


def _normalize_triggers(raw: list[str] | None) -> list[str]:
    out: list[str] = []
    for t in raw or []:
        s = str(t).strip()
        if s and s not in out:
            out.append(s[:64])
    return out[:16]


def _apply_create_fields(
    skill: FileSkill,
    payload: AgentCreate,
    author_id: str,
    author_name: str,
) -> None:
    vars_meta = [{"name": v, "type": "string"} for v in extract_variables(payload.user_prompt)]
    skill.name = payload.name
    skill.description = payload.description
    skill.specialty = (payload.specialty or "").strip()[:64]
    skill.router_blurb = (payload.router_blurb or "").strip()[:256]
    skill.triggers = _normalize_triggers(payload.triggers)
    skill.tags = payload.tags
    skill.model_name = payload.model
    skill.model_params = payload.params.model_dump(by_alias=True)
    skill.system_prompt_enc = payload.system_prompt
    skill.user_prompt_template = payload.user_prompt
    skill.variables = vars_meta
    skill.author_id = author_id
    skill.author_name = author_name
    skill.visibility = payload.visibility
    skill.examples = payload.examples


async def create_agent(
    db: AsyncSession,
    user_id: str,
    author_name: str,
    payload: AgentCreate,
) -> FileSkill:
    _ = db
    from app.services.model_validation import require_known_model

    payload = payload.model_copy(update={"model": require_known_model(payload.model)})
    slug = allocate_slug(payload.name)
    now = datetime.utcnow()
    skill = FileSkill(
        id=slug,
        name=payload.name,
        status="draft",
        version="v0.0.0",
        created_at=now,
        updated_at=now,
    )
    _apply_create_fields(skill, payload, user_id, author_name)
    skill.workflow = default_workflow(payload.model, slug)
    return save_skill(skill)


async def build_agent(
    db: AsyncSession,
    user_id: str,
    author_name: str,
    payload: AgentBuildRequest,
) -> FileSkill:
    from app.services.model_validation import require_known_model

    model = require_known_model(payload.model)
    payload = payload.model_copy(update={"model": model})
    compiled = await compile_executable_spec(
        db,
        user_id=user_id,
        author_name=author_name,
        name=payload.name,
        description=payload.description,
        model=payload.model,
        system_prompt=payload.system_prompt,
        user_prompt=payload.user_prompt,
        specialty=payload.specialty or "",
    )
    create_payload = AgentCreate(
        name=payload.name,
        description=payload.description,
        specialty=payload.specialty or "",
        routerBlurb=compiled.get("router_blurb") or "",
        triggers=compiled.get("triggers") or [],
        model=payload.model,
        systemPrompt=compiled["system"],
        userPrompt=compiled["user"],
        params=payload.params,
        tags=_with_specialty_tag(payload.tags, payload.specialty or ""),
        visibility=payload.visibility,
        examples=payload.examples,
    )
    skill = await create_agent(db, user_id, author_name, create_payload)
    skill.md_doc = compiled["md_doc"]
    skill.workflow = default_workflow(payload.model, skill.id)
    return save_skill(skill)


async def get_agent(db: AsyncSession, agent_id: str) -> FileSkill | None:
    _ = db
    return get_skill(agent_id)


async def list_agents(db: AsyncSession, user_id: str) -> list[FileSkill]:
    """可见列表：自己的 + 已发布 team/public。"""
    _ = db
    out: list[FileSkill] = []
    seen: set[str] = set()
    for s in list_skills(include_deprecated=False):
        mine = s.author_id == user_id
        published_open = s.status == "published" and s.visibility in {"team", "public"}
        if mine or published_open:
            if s.id not in seen:
                seen.add(s.id)
                out.append(s)
    return out


async def list_plaza_agents(
    db: AsyncSession,
    *,
    exclude_author_id: str | None = None,
    specialty: str | None = None,
    category: str | None = None,
    curated_only: bool = True,
) -> list[FileSkill]:
    _ = db
    from app.services.skill.taxonomy import category_of_agent

    agents = list_skills(
        curated_only=curated_only,
        specialty=specialty,
        statuses={"published"},
    )
    agents = [a for a in agents if a.visibility in {"team", "public"}]
    if not curated_only and exclude_author_id:
        agents = [a for a in agents if a.author_id != exclude_author_id]
    cat = (category or "").strip().lower()
    if cat and cat != "all":
        agents = [a for a in agents if category_of_agent(a)[0] == cat]
    return agents


async def list_my_agents(db: AsyncSession, user_id: str) -> list[FileSkill]:
    _ = db
    return list_skills(author_id=user_id, include_deprecated=False)


async def update_agent(db: AsyncSession, agent: FileSkill, payload: AgentUpdate) -> FileSkill:
    _ = db
    from app.services.model_validation import require_known_model

    if payload.model is not None:
        payload = payload.model_copy(update={"model": require_known_model(payload.model)})
    if payload.name is not None:
        agent.name = payload.name
    if payload.description is not None:
        agent.description = payload.description
    if payload.specialty is not None:
        agent.specialty = (payload.specialty or "").strip()[:64]
    if payload.router_blurb is not None:
        agent.router_blurb = (payload.router_blurb or "").strip()[:256]
    if payload.triggers is not None:
        agent.triggers = _normalize_triggers(payload.triggers)
    if payload.model is not None:
        agent.model_name = payload.model
        agent.workflow = _sync_workflow_model(agent.workflow, payload.model)
    if payload.system_prompt is not None:
        agent.system_prompt_enc = payload.system_prompt
    if payload.user_prompt is not None:
        agent.user_prompt_template = payload.user_prompt
        agent.variables = [
            {"name": v, "type": "string"} for v in extract_variables(payload.user_prompt)
        ]
    if payload.params is not None:
        agent.model_params = payload.params.model_dump(by_alias=True)
    if payload.tags is not None:
        agent.tags = payload.tags
    if payload.visibility is not None:
        agent.visibility = payload.visibility
    if payload.examples is not None:
        agent.examples = payload.examples
    if payload.md_doc is not None:
        agent.md_doc = payload.md_doc
    if payload.workflow is not None:
        agent.workflow = payload.workflow
    return save_skill(agent)


async def publish_agent(
    db: AsyncSession,
    agent: FileSkill,
    changelog: str,
    version: str | None = None,
    *,
    visibility: str | None = None,
    optimize: bool = False,
    user_id: str | None = None,
) -> FileSkill:
    if visibility:
        agent.visibility = visibility
    if optimize:
        compiled = await compile_executable_spec(
            db,
            user_id=user_id or agent.author_id,
            author_name=agent.author_name,
            name=agent.name,
            description=agent.description,
            model=agent.model_name,
            system_prompt=_resolve_system_text(agent.system_prompt_enc),
            user_prompt=agent.user_prompt_template,
            specialty=agent.specialty or "",
        )
        agent.md_doc = compiled["md_doc"]
        agent.system_prompt_enc = compiled["system"]
        agent.user_prompt_template = compiled["user"]
        agent.router_blurb = (compiled.get("router_blurb") or agent.router_blurb or "")[:256]
        agent.triggers = _normalize_triggers(compiled.get("triggers") or agent.triggers)
        agent.variables = [
            {"name": v, "type": "string"}
            for v in extract_variables(compiled["user"])
        ]
        agent.workflow = default_workflow(
            agent.model_name, agent.id, (version or _bump_version(agent.version)).lstrip("v")
        )

    new_version = version or _bump_version(agent.version)
    agent.version = new_version
    agent.changelog = changelog
    agent.status = "published"
    agent.published_at = datetime.utcnow()
    # 不再写入 mct_agent_versions
    return save_skill(agent)


async def publish_to_plaza(
    db: AsyncSession,
    user_id: str,
    author_name: str,
    *,
    name: str,
    description: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    specialty: str,
    intent: str = "",
    params: ChatParams | None = None,
    tags: list[str] | None = None,
    visibility: str = "team",
    changelog: str = "",
    examples: list[dict[str, Any]] | None = None,
) -> FileSkill:
    from app.services.model_validation import require_known_model

    specialty_text = (specialty or "").strip()
    if not specialty_text:
        raise ValueError("specialty 不能为空：请填写专业方向")
    model = require_known_model(model)
    compiled = await compile_executable_spec(
        db,
        user_id=user_id,
        author_name=author_name,
        name=name,
        description=description,
        model=model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        intent=intent,
        specialty=specialty_text,
    )
    final_tags = _with_specialty_tag(tags, specialty_text)
    payload = AgentCreate(
        name=name,
        description=description,
        specialty=specialty_text,
        routerBlurb=compiled.get("router_blurb") or "",
        triggers=compiled.get("triggers") or [],
        model=model,
        systemPrompt=compiled["system"],
        userPrompt=compiled["user"],
        params=params or ChatParams(),
        tags=final_tags,
        visibility="team" if visibility == "private" else visibility,
        examples=examples or [],
    )
    skill = await create_agent(db, user_id, author_name, payload)
    skill.md_doc = compiled["md_doc"]
    skill.workflow = default_workflow(model, skill.id)
    save_skill(skill)
    log = (changelog or "").strip() or f"发布专业 Skill：{specialty_text}"
    return await publish_agent(
        db,
        skill,
        changelog=log,
        version="v1.0.0",
        visibility=payload.visibility,
        optimize=False,
        user_id=user_id,
    )


async def deprecate_agent(db: AsyncSession, agent: FileSkill) -> FileSkill:
    _ = db
    agent.status = "deprecated"
    return save_skill(agent)


async def delete_agent(db: AsyncSession, agent: FileSkill) -> None:
    _ = db
    delete_skill(agent.id, purge=True)


def _fallback_output_from_tools(tool_trace: dict | None, exc: BaseException) -> str | None:
    """工具已成功产出文件时，上游模型失败也不要把整次调用打成 502。"""
    if not tool_trace:
        return None
    try:
        code = int(tool_trace.get("exitCode") if tool_trace.get("exitCode") is not None else 1)
    except (TypeError, ValueError):
        code = 1
    url = tool_trace.get("downloadUrl")
    urls = tool_trace.get("downloadUrls") or []
    if code != 0 or not (url or urls):
        return None
    name = tool_trace.get("downloadName") or "结果文件"
    note = tool_trace.get("note") or "已在服务端完成处理"
    lines = [
        "## 结果",
        str(note),
        "",
        "## 下载",
    ]
    if url:
        lines.append(f"- [{name}]({url})")
    for u in urls:
        lines.append(f"- [{u}]({u})")
    lines.extend(
        [
            "",
            "（模型解读暂时不可用，已直接返回工具产出。可稍后重试以获得文字说明。）",
        ]
    )
    _ = exc
    return "\n".join(lines)


async def call_agent(
    db: AsyncSession,
    agent: FileSkill,
    caller_id: str,
    variables: dict[str, str],
    *,
    uploaded_files: list[dict] | None = None,
    conversation_id: str | None = None,
) -> AgentCallResponse:
    if agent.status not in {"published", "draft"}:
        raise PermissionError("智能体不可用")
    if agent.status == "draft" and agent.author_id != caller_id:
        raise PermissionError("草稿仅创建者可调用")
    if agent.status == "published" and agent.visibility == "private" and agent.author_id != caller_id:
        raise PermissionError("私有智能体仅创建者可调用")

    started = time.perf_counter()

    from app.services.model_validation import resolve_callable_model
    from app.services.skill.plus_resolve import apply_plus_to_variables
    from app.services.skill.stat_pipeline import (
        format_tool_result,
        is_statistical_skill,
        run_statistical_tools,
    )
    from app.services.skill.capability import (
        INTRO_SYSTEM_ADDENDUM,
        format_intro_tool_result,
        intro_fallback_output,
        intro_trace,
        is_ability_ask,
        is_capability_query,
        should_intro_only,
    )
    from app.services.skill.intent_gate import _ppt_wizard_busy
    from app.services.uploads import format_file_summary, inject_current_files

    plus_token, vars_clean = apply_plus_to_variables(variables or {})
    if plus_token:
        logger.info("call_agent ignore plus token=%s skillId=%s", plus_token, agent.id)

    tool_trace: dict | None = None
    agent_loop_output: str | None = None
    enriched = dict(vars_clean)
    enriched.setdefault("file_summary", format_file_summary(uploaded_files))
    enriched.setdefault("tool_result", "（无脚本结果）")
    extra_latency = 0
    skip_tools = (not _ppt_wizard_busy(agent, conversation_id)) and should_intro_only(
        enriched.get("input") or "",
        has_uploads=bool(uploaded_files),
    )

    if skip_tools:
        tool_trace = intro_trace(agent)
        enriched["tool_result"] = format_intro_tool_result(tool_trace)
    else:
        from app.services.skill.academic_search_pipeline import (
            format_academic_tool_result,
            is_academic_search_skill,
        )
        from app.services.skill.excel_pipeline import (
            format_excel_tool_result,
            is_excel_skill,
        )
        from app.services.skill.lit_review_pipeline import (
            format_lit_review_tool_result,
            is_lit_review_skill,
        )
        from app.services.skill.pdf_pipeline import (
            format_pdf_tool_result,
            is_pdf_skill,
        )
        from app.services.skill.ppt_pipeline import (
            format_ppt_tool_result,
            is_ppt_skill,
        )
        from app.services.skill_agent.orchestrator import run_skill_orchestrator
        from app.services.skill_agent.router import (
            excel_workbook_only,
            export_trace_has_sheet,
            sanitize_export_trace,
            try_excel_workbook_direct,
        )

        model_for_agent = resolve_callable_model(agent.model_name)
        pack = None
        try:
            pack = await run_skill_orchestrator(
                db,
                agent,
                user_text=enriched.get("input") or "",
                uploaded_files=uploaded_files,
                model=model_for_agent,
                temperature=min(float((agent.model_params or {}).get("temperature") or 0.4), 0.35),
                max_tokens=int((agent.model_params or {}).get("maxTokens") or 2048),
                caller_id=caller_id,
                conversation_id=conversation_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("skill orchestrator fail skillId=%s err=%s", agent.id, exc)
            pack = None
            if is_excel_skill(agent):
                from app.services.skill.excel_pipeline import run_excel_tools

                tool_trace = run_excel_tools(
                    enriched.get("input") or "",
                    uploaded_files=uploaded_files,
                )
            elif is_pdf_skill(agent):
                from app.services.skill.pdf_pipeline import run_pdf_tools

                tool_trace = run_pdf_tools(
                    enriched.get("input") or "",
                    uploaded_files=uploaded_files,
                )
            elif is_statistical_skill(agent):
                tool_trace = run_statistical_tools(
                    enriched.get("input") or "",
                    uploaded_files=uploaded_files,
                    scripts_dir=getattr(agent, "scripts_dir", None),
                )
            elif is_ppt_skill(agent):
                from app.services.skill.ppt_pipeline import run_ppt_tools

                tool_trace = run_ppt_tools(
                    enriched.get("input") or "",
                    uploaded_files=uploaded_files,
                    conversation_id=conversation_id,
                )
            elif is_academic_search_skill(agent):
                from app.services.skill.academic_search_pipeline import run_academic_search

                tool_trace = run_academic_search(
                    enriched.get("input") or "",
                    conversation_id=conversation_id,
                )
            elif is_lit_review_skill(agent):
                from app.services.skill.lit_review_pipeline import run_lit_review_prepare

                try:
                    tool_trace = run_lit_review_prepare(
                        enriched.get("input") or "",
                        conversation_id=conversation_id,
                    )
                except Exception as prep_exc:  # noqa: BLE001
                    logger.warning("lit-review prepare fail: %s", prep_exc)
                    tool_trace = {
                        "intent": "notes",
                        "script": "lit-review-notes",
                        "exitCode": 1,
                        "note": "文献速读准备失败",
                        "stdout": "",
                        "stderr": str(prep_exc),
                    }
        if pack is not None:
            extra_latency += int(pack.latency_ms or 0)
            tool_trace = pack.tool_trace
            agent_loop_output = pack.output
            if pack.fallback:
                logger.info("skill orchestrator heuristic tools skillId=%s", agent.id)
        if is_excel_skill(agent) and excel_workbook_only(enriched.get("input") or ""):
            if not export_trace_has_sheet(tool_trace):
                forced = try_excel_workbook_direct(enriched.get("input") or "", uploaded_files)
                if forced is not None:
                    tool_trace = forced.tool_trace
                    if not agent_loop_output:
                        from app.services.skill_agent.router import export_user_reply

                        agent_loop_output = export_user_reply(
                            tool_trace.get("downloadUrl"),
                            tool_trace.get("downloadName"),
                        )
            tool_trace = sanitize_export_trace(tool_trace)
        if is_pdf_skill(agent) and tool_trace and tool_trace.get("intent") in {
            "split",
            "merge",
            "watermark",
            "to_docx",
            "to_doc",
        }:
            urls = [str(u) for u in (tool_trace.get("downloadUrls") or []) if u]
            if tool_trace.get("downloadUrl"):
                urls.insert(0, str(tool_trace["downloadUrl"]))
            files = [
                u
                for u in dict.fromkeys(urls)
                if not re.search(r"\.(png|jpe?g|gif|webp)(\?|$)", u, re.I)
            ]
            tool_trace = {
                **tool_trace,
                "imageUrl": None,
                "downloadUrls": files,
                "downloadUrl": files[0] if files else None,
            }
        if is_ppt_skill(agent) and tool_trace and tool_trace.get("intent") == "compose":
            agent_loop_output = None
        if tool_trace:
            if is_excel_skill(agent):
                enriched["tool_result"] = format_excel_tool_result(tool_trace)
            elif is_pdf_skill(agent):
                enriched["tool_result"] = format_pdf_tool_result(tool_trace)
            elif is_statistical_skill(agent):
                enriched["tool_result"] = format_tool_result(tool_trace)
            elif is_ppt_skill(agent):
                enriched["tool_result"] = format_ppt_tool_result(tool_trace)
            elif is_academic_search_skill(agent):
                enriched["tool_result"] = format_academic_tool_result(tool_trace)
            elif is_lit_review_skill(agent):
                if tool_trace.get("exitCode") == 0 and tool_trace.get("stdout"):
                    enriched["input"] = str(tool_trace["stdout"])
                elif tool_trace.get("exitCode") not in (None, 0):
                    enriched["input"] = (
                        "按标题检索失败，请说明找不到该论文，禁止编造速读笔记。\n"
                        f"{tool_trace.get('stderr') or tool_trace.get('note') or ''}"
                    )
                enriched["tool_result"] = format_lit_review_tool_result(tool_trace)

    params = ChatParams.model_validate(agent.model_params or {})

    if (
        not skip_tools
        and tool_trace
        and tool_trace.get("intent") == "compose"
        and is_ppt_skill(agent)
    ):
        from app.services.skill.ppt_pipeline import generate_pptx
        from app.services.skill.ppt_wizard import (
            COMPOSE_SYSTEM,
            apply_composed_plan,
            expand_plan,
            is_off_topic,
            merge_parsed_tables,
            parse_slides_json,
        )

        spec = tool_trace.get("compose") or {}
        compose_user = str(tool_trace.get("stdout") or "")
        plan = None
        try:
            plan_res = await run_chat(
                db,
                user_id=agent.author_id,
                model=resolve_callable_model(agent.model_name),
                system=COMPOSE_SYSTEM,
                user=compose_user,
                variables=None,
                temperature=0.35,
                max_tokens=max(params.max_tokens, 6144),
                scene="skill-ppt-compose",
                log_extra={
                    "skillId": agent.id,
                    "skill": agent.name or "",
                    "caller": caller_id,
                    "wizard": "compose",
                },
            )
            extra_latency += int(plan_res.latency_ms or 0)
            plan = parse_slides_json(plan_res.output or "")
        except Exception as exc:  # noqa: BLE001
            logger.warning("ppt compose model fail: %s", exc)
        outline = str(spec.get("raw_outline") or enriched.get("input") or "")
        from app.services.skill.ppt_wizard import parse_detailed_spec

        parsed = parse_detailed_spec(outline)
        if plan and parsed:
            if is_off_topic(str(parsed.get("title") or ""), str(plan.get("title") or "")):
                logger.info("ppt compose off-topic title user=%r model=%r", parsed.get("title"), plan.get("title"))
                if re.search(r"技术架构|年度工作|演进汇报", str(plan.get("title") or "")):
                    plan = parsed
                else:
                    plan["title"] = parsed.get("title") or plan.get("title")
            plan = merge_parsed_tables(plan, parsed)
        elif not plan and parsed:
            plan = parsed
        if not plan:
            from app.services.skill.ppt_pipeline import build_plan

            plan = expand_plan(
                build_plan(outline),
                int(spec.get("slide_count") or 8),
                lock=True,
            )
        tool_trace = apply_composed_plan(spec, plan, generate_pptx)
        enriched["tool_result"] = format_ppt_tool_result(tool_trace)

    system, user_text = prepare_call_messages(agent, enriched)
    from app.services.skill.doc_parser import PARSEABLE_SUFFIX

    user_text = inject_current_files(user_text, uploaded_files)
    parseable = any(
        Path(str(f.get("name") or "")).suffix.lower() in PARSEABLE_SUFFIX
        for f in (uploaded_files or [])
    )
    if skip_tools:
        system = system.rstrip() + "\n\n" + INTRO_SYSTEM_ADDENDUM
    elif uploaded_files and parseable:
        system = (
            system.rstrip()
            + "\n\n硬性规则：若用户消息含「当前上传文件」，必须以其为唯一分析对象；"
            "不得引用历史对话中的其它文件名或旧报告数据，不得编造未出现在上传文件中的样本。"
        )
    model = resolve_callable_model(agent.model_name)
    if model != (agent.model_name or "").strip():
        logger.info(
            "call remap model skillId=%s %s -> %s",
            agent.id,
            agent.model_name,
            model,
        )
        agent.model_name = model
        agent.workflow = _sync_workflow_model(agent.workflow, model)

    if agent_loop_output and not skip_tools:
        result = ChatResult(output=agent_loop_output, latency_ms=extra_latency)
    else:
        try:
            result = await run_chat(
                db,
                user_id=agent.author_id,
                model=model,
                system=system,
                user=user_text,
                variables=None,
                temperature=params.temperature,
                max_tokens=params.max_tokens,
                scene="skill",
                log_extra={
                    "skillId": agent.id,
                    "skill": agent.name or "",
                    "specialty": agent.specialty or "",
                    "version": agent.version or "",
                    "caller": caller_id,
                },
            )
            if extra_latency:
                result.latency_ms = int(result.latency_ms or 0) + extra_latency
        except Exception as exc:  # noqa: BLE001
            fallback = _fallback_output_from_tools(tool_trace, exc)
            if not fallback and tool_trace and tool_trace.get("intent") == "intro":
                fallback = intro_fallback_output(tool_trace, agent)
            if not fallback and (
                is_capability_query(enriched.get("input") or "")
                or is_ability_ask(enriched.get("input") or "")
            ):
                fallback = intro_fallback_output(intro_trace(agent), agent)
            if fallback:
                logger.warning(
                    "model fail after tools, use fallback skillId=%s errType=%s err=%r",
                    agent.id,
                    type(exc).__name__,
                    str(exc).strip() or repr(exc),
                )
                result = ChatResult(output=fallback, latency_ms=extra_latency)
            else:
                raise

    wall_ms = int((time.perf_counter() - started) * 1000)
    result.latency_ms = wall_ms

    # 内网演示：不在每次调用时写回 SKILL.md，避免 git 脏文件
    agent.total_calls = int(agent.total_calls or 0) + 1
    logger.info(
        "call skill=%s skillId=%s specialty=%s version=%s model=%s caller=%s "
        "latencyMs=%s tokensIn=%s tokensOut=%s outChars=%s sysChars=%s userChars=%s",
        agent.name or "",
        agent.id,
        agent.specialty or "",
        agent.version,
        model,
        caller_id,
        result.latency_ms,
        result.tokens_input,
        result.tokens_output,
        len(result.output or ""),
        len(system),
        len(user_text),
    )
    trace_out = None
    if tool_trace:
        stdout = tool_trace.get("stdout") or ""
        stderr = tool_trace.get("stderr") or ""
        trace_out = {
            "intent": tool_trace.get("intent"),
            "script": tool_trace.get("script"),
            "exitCode": tool_trace.get("exitCode"),
            "note": tool_trace.get("note"),
            "stdoutPreview": stdout[:4000],
            "stderrPreview": stderr[:1000],
            "downloadUrl": tool_trace.get("downloadUrl"),
            "downloadName": tool_trace.get("downloadName"),
            "downloadUrls": tool_trace.get("downloadUrls"),
            "imageUrl": tool_trace.get("imageUrl") if tool_trace.get("intent") == "chart" else None,
        }
    return AgentCallResponse(
        output=result.output,
        latencyMs=result.latency_ms,
        agentVersion=agent.version,
        toolTrace=trace_out,
        resolvedSkillId=agent.id,
        resolvedSkillName=agent.name,
    )


async def list_versions(db: AsyncSession, agent_id: str) -> list:
    """版本快照已停写；返回空列表。"""
    _ = db, agent_id
    return []


async def list_calls(db: AsyncSession, agent_id: str, limit: int = 50) -> list:
    _ = db, agent_id, limit
    return []
