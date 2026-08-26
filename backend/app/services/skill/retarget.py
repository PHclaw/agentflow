"""会话锁在某个 Skill 时，若上传文件 + 指令明显属于另一 Skill，则改道。"""
from __future__ import annotations

from pathlib import Path

from app.logging_setup import get_logger
from app.services.skill.pdf_pipeline import route_intent

logger = get_logger("skill-retarget")

_PDF_FILE_OPS = {"merge", "split", "watermark", "to_docx", "to_doc"}


def _suffixes(uploaded_files: list[dict] | None) -> list[str]:
    out: list[str] = []
    for f in uploaded_files or []:
        name = str(f.get("name") or "").strip()
        if name:
            out.append(Path(name).suffix.lower())
    return out


def maybe_retarget_skill_id(
    current_skill_id: str | None,
    user_text: str,
    uploaded_files: list[dict] | None,
) -> str | None:
    """返回应改用的 skill id；无需改道时返回 None。"""
    current = (current_skill_id or "").strip()
    suffixes = _suffixes(uploaded_files)
    pdf_n = sum(1 for s in suffixes if s == ".pdf")
    if pdf_n >= 1 and route_intent(user_text or "") in _PDF_FILE_OPS:
        if current != "pdf":
            logger.info(
                "retarget %s -> pdf files=%s intent=%s",
                current or "(none)",
                pdf_n,
                route_intent(user_text or ""),
            )
            return "pdf"
    return None
