"""把现有 PDF/PPT/统计/检索管线挂进同一套 Skill Agent 循环。"""
from __future__ import annotations

from typing import Any, Callable

from app.logging_setup import get_logger

logger = get_logger("skill-agent-pipeline")

Runner = Callable[..., dict[str, Any]]


class PipelineToolSession:
    """一次 execute = 跑原管线；可用 focus 针对清单里尚未完成的子句再跑。"""

    def __init__(
        self,
        user_text: str,
        uploaded_files: list[dict] | None,
        *,
        skill_body: str = "",
        runner: Runner,
        runner_kwargs: dict[str, Any] | None = None,
    ):
        self.user_text = user_text or ""
        self.current = user_text or ""
        self.uploaded = uploaded_files or []
        self.skill_body = skill_body or ""
        self._runner = runner
        self._kwargs = dict(runner_kwargs or {})
        self.download_urls: list[str] = []
        self.download_name = ""
        self.last_note = ""
        self.last_stdout = ""
        self._trace: dict[str, Any] = {}

    def read_skill(self, _args: dict[str, Any] | None = None) -> dict[str, Any]:
        body = (self.skill_body or "").strip()
        return {"ok": True, "body": body[:8000] or "（无额外 SKILL.md 正文）"}

    def execute(self, args: dict[str, Any] | None = None) -> dict[str, Any]:
        args = args or {}
        focus = str(args.get("focus") or args.get("instruction") or "").strip()
        text = focus or self.user_text
        try:
            trace = self._runner(text, **self._kwargs)
        except TypeError:
            trace = self._runner(text)
        except Exception as exc:  # noqa: BLE001
            logger.warning("pipeline execute fail: %s", exc)
            return {"ok": False, "error": str(exc)}
        self._absorb(trace)
        ok = int(trace.get("exitCode") if trace.get("exitCode") is not None else 1) == 0
        if trace.get("exitCode") is None and (trace.get("downloadUrl") or trace.get("stdout")):
            ok = True
        return {
            "ok": ok,
            "intent": trace.get("intent"),
            "note": trace.get("note") or "",
            "stdout": str(trace.get("stdout") or "")[:4000],
            "downloadUrl": trace.get("downloadUrl"),
            "downloadName": trace.get("downloadName"),
            "downloadUrls": list(self.download_urls),
        }

    run_pipeline = execute

    def _absorb(self, trace: dict[str, Any]) -> None:
        self._trace = dict(trace or {})
        urls = list(trace.get("downloadUrls") or [])
        if trace.get("downloadUrl"):
            urls.insert(0, str(trace["downloadUrl"]))
        for u in urls:
            if u and u not in self.download_urls:
                self.download_urls.append(u)
        if trace.get("downloadName"):
            self.download_name = str(trace["downloadName"])
        self.last_note = str(trace.get("note") or "")
        self.last_stdout = str(trace.get("stdout") or self.last_note)

    def to_tool_trace(self, *, intent: str = "task", exit_code: int = 0) -> dict[str, Any]:
        tr = dict(self._trace or {})
        urls = list(dict.fromkeys(self.download_urls))
        tr.setdefault("intent", intent)
        tr["script"] = tr.get("script") or "skill_agent"
        tr["exitCode"] = tr.get("exitCode") if tr.get("exitCode") is not None else exit_code
        tr["stdout"] = (self.last_stdout or tr.get("stdout") or "")[:14000]
        tr["note"] = self.last_note or tr.get("note") or "Skill Agent 已执行工具"
        if urls:
            tr["downloadUrl"] = urls[0]
            tr["downloadUrls"] = urls
            tr["downloadName"] = self.download_name or tr.get("downloadName")
        return tr


def pipeline_tool_defs() -> list[dict[str, Any]]:
    return [
        {
            "name": "read_skill",
            "description": "读取当前 Skill 的 SKILL.md 细则。",
            "parameters": {"type": "object", "properties": {}},
        },
        {
            "name": "execute",
            "description": "执行本 Skill 的本地能力。用户有多步时，"
            "用 focus 传入尚未完成的那一句（不要一次说完却漏做）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "focus": {
                        "type": "string",
                        "description": "当前要完成的子任务原文",
                    }
                },
            },
        },
    ]
