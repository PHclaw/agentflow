"""专业 Skill 算法：编译 / 选型 / 调用消息组装。"""

from app.services.skill.compiler import (
    assemble_executable_md,
    compile_executable_spec,
    compile_specialty_skill,
)
from app.services.skill.invocation import prepare_call_messages
from app.services.skill.resolver import resolve_skills
from app.services.skill.taxonomy import infer_category, list_categories

from app.services.skill.store import get_skill, list_skills, save_skill

__all__ = [
    "assemble_executable_md",
    "compile_executable_spec",
    "compile_specialty_skill",
    "prepare_call_messages",
    "resolve_skills",
    "infer_category",
    "list_categories",
    "get_skill",
    "list_skills",
    "save_skill",
]
