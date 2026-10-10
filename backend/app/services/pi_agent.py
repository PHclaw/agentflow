"""PiAgent 运行时 —— 把外部 agent CLI 当作 Agent 的推理引擎。

设计参考 AlphaLens 的 ``backend/app/services/piagent.py``，但去掉了业务耦合
（企业情报提示词、情报档案整理、落库等），改为通用实现：

- 可执行文件发现：PIAGENT_EXE 配置 -> PATH -> 常见安装位置；
  Windows 下优先用 ``node|cli.js`` 绕开 .cmd 的 subprocess 兼容问题
- 提示词通过一次性临时文件传递，避免命令行长度限制与多行截断
- 子进程在独立线程中读取，经 Queue 转成异步事件流（uvicorn 事件循环
  在 Windows 上并不支持 asyncio subprocess）
- 解析 ``--mode json`` 的 JSON-lines 事件，归一化为本项目的 SSE 事件协议
- 过滤「我将读取文件」这类过程性叙述，避免暴露内部机制
- 对比工作区文件快照，把新生成的文件作为附件回传

对外只暴露 ``PiAgentRunner``；纯逻辑（命令拼装、事件解析、叙述过滤、
产物判定）都做成模块级函数或可单独实例化的类，便于单元测试。
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from queue import Empty, Queue
from typing import Any, AsyncIterator, Iterable, Sequence

from app.core.config import settings
from app.core.paths import pi_agent_workspace, pi_skills_root
from app.logging_setup import get_logger

logger = get_logger("pi_agent")


@dataclass
class AgentContext:
    """从 ORM 对象摘出来的只读上下文，避免执行过程中再触碰数据库会话。

    HTTP 接口（app/api/pi_agent.py）与工作流的智能体节点共用这一份构造逻辑。
    """

    id: str
    name: str
    description: str | None = None
    system_prompt: str = ""
    model_config: dict[str, Any] = field(default_factory=dict)
    settings: dict[str, Any] = field(default_factory=dict)


def build_agent_context(agent) -> AgentContext:
    """把 ORM Agent 转成执行上下文。"""
    model_config = agent.model_config if isinstance(agent.model_config, dict) else {}
    agent_settings = agent.settings if isinstance(agent.settings, dict) else {}

    # 系统提示词优先取 Agent 自身配置，供 build_system_prompt 使用
    system_prompt = str(model_config.get("system_prompt") or agent_settings.get("system_prompt") or "")

    return AgentContext(
        id=agent.id,
        name=agent.name,
        description=agent.description,
        system_prompt=system_prompt,
        model_config=dict(model_config),
        settings=dict(agent_settings),
    )

# Windows 上 asyncio 的默认事件循环不支持 subprocess；PiAgent 用线程 + 同步
# subprocess 绕开，这里仅保证策略正确，便于其它组件复用。
if sys.platform == "win32":  # pragma: no cover - 平台相关
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:  # noqa: BLE001
        pass

# 工作区扫描时始终跳过的目录
_SKIP_DIR_NAMES = {"skills", "node_modules", "__pycache__", ".git"}
# 单次最多回传的产物数量
_MAX_ARTIFACTS = 50

# 模型读到提示词文件后常先输出「我将读取该文件」，这类过程叙述既暴露内部机制
# 又无信息量，需要连同该句一起丢弃。
_NARRATION_PATTERNS = [
    re.compile(r"^\s*i'?ll\s+read", re.IGNORECASE),
    re.compile(r"^\s*i\s+will\s+read", re.IGNORECASE),
    re.compile(r"^\s*i'?m\s+going\s+to\s+read", re.IGNORECASE),
    re.compile(r"^\s*let\s+me\s+read", re.IGNORECASE),
    re.compile(r"^\s*reading\s+the\s+file", re.IGNORECASE),
    re.compile(r"^\s*let\s+me\s+(look|check|open)", re.IGNORECASE),
    re.compile(r"^\s*(好的[，,]?\s*)?我(先|来|去)?(读取|阅读|查看)(一下)?(该|这个)?文件"),
    re.compile(r"^\s*让我(先)?(读取|阅读|查看)一下"),
]

_SENTENCE_END_RE = re.compile(r"[.。!！?？\n]")


# --------------------------------------------------------------------------
# 可执行文件发现与命令拼装
# --------------------------------------------------------------------------

def find_pi_executable(configured: str | None = None, *, platform: str | None = None) -> str | None:
    """定位 pi 可执行文件。

    返回普通路径，或 Windows 下绕过 .cmd 时的 ``"node路径|cli.js路径"``。
    """
    platform = platform or sys.platform
    configured = (configured if configured is not None else settings.PIAGENT_EXE) or ""
    configured = configured.strip()

    if configured and configured.lower() not in ("pi", "pi.cmd", "pi.exe"):
        if os.path.exists(configured):
            return configured
        found = shutil.which(configured)
        if found:
            return found
        logger.warning("PIAGENT_EXE 不可用，回退到默认查找: %s", configured)

    path = shutil.which("pi")
    if not path:
        for candidate in (
            os.path.expanduser(r"~\AppData\Roaming\npm\pi.cmd"),
            os.path.expanduser(r"~\AppData\Roaming\npm\pi"),
        ):
            if os.path.exists(candidate):
                path = candidate
                break

    if not path:
        return None

    # Windows 上 .cmd 无法被 create_subprocess_exec 直接执行，
    # 且 cmd.exe 转义容易出错，优先改成 node + cli.js
    if platform == "win32" and path.lower().endswith(".cmd"):
        bypass = _node_cli_bypass(path)
        if bypass:
            return bypass
    return path


def _node_cli_bypass(cmd_path: str) -> str | None:
    """把 npm 全局的 pi.cmd 映射成 ``node|cli.js``。"""
    node_exe = shutil.which("node")
    if not node_exe:
        return None
    npm_dir = os.path.dirname(cmd_path)
    cli_js = os.path.join(
        npm_dir, "node_modules", "@earendil-works", "pi-coding-agent",
        "dist", "bundle", "cli.js",
    )
    if os.path.exists(cli_js):
        return f"{node_exe}|{cli_js}"
    return None


def wrap_cmd_for_windows(exe: str, args: Sequence[str], *, platform: str | None = None) -> list[str]:
    """把 (exe, args) 拼成可直接交给 subprocess 的 argv。

    - ``"node|cli.js"`` 形式：拆成 ``[node, cli.js, *args]``
    - Windows 上的 .cmd/.bat：用 cmd.exe /c 包裹，并用 list2cmdline 做正确转义
      （直接用空格拼接会在参数含引号时出错）
    """
    platform = platform or sys.platform

    if "|" in exe:
        head, tail = exe.split("|", 1)
        return [head, tail, *args]

    if platform == "win32" and exe.lower().endswith((".cmd", ".bat")):
        return ["cmd.exe", "/c", subprocess.list2cmdline([exe, *args])]

    return [exe, *args]


# --------------------------------------------------------------------------
# 输出净化
# --------------------------------------------------------------------------

def is_process_narration(text: str) -> bool:
    """判断文本开头是否为「我要去读文件」之类的过程声明。"""
    return any(pattern.match(text or "") for pattern in _NARRATION_PATTERNS)


def screen_stream_delta(
    prefix_buffer: str, settled: bool, delta: str, *, min_probe: int = 60
) -> tuple[str, bool, str]:
    """过滤流式输出开头的模型过程性叙述。

    在开头攒够 ``min_probe`` 个字符或遇到句末标点前不下发内容，避免误伤
    正常正文；判定为过程叙述则连同整句丢弃。

    Returns:
        (新的缓冲, 是否已判定完成, 本次应下发的文本)
    """
    if settled:
        return prefix_buffer, True, delta

    prefix_buffer += delta

    if len(prefix_buffer) < min_probe and not _SENTENCE_END_RE.search(prefix_buffer):
        return prefix_buffer, False, ""

    if is_process_narration(prefix_buffer):
        match = _SENTENCE_END_RE.search(prefix_buffer)
        remainder = prefix_buffer[match.end():] if match else ""
        return "", True, remainder

    return "", True, prefix_buffer


def strip_leading_narration(text: str) -> str:
    """最终答案的兜底净化：丢掉开头的过程叙述整句。"""
    if not text or not is_process_narration(text):
        return text
    match = _SENTENCE_END_RE.search(text)
    return text[match.end():].lstrip() if match else text


def is_usable_artifact(path: str | Path) -> bool:
    """判断工作区新增文件是否为有价值的产物。

    过滤两类噪音：curl 保存的网页快照（t*.html / p*.html）和空文件。
    """
    path = Path(path)
    name = path.name.lower()
    if name.endswith(".html") and len(name) <= 8 and name[0] in "tp":
        return False
    try:
        if path.stat().st_size == 0:
            return False
        head = path.read_text(encoding="utf-8", errors="ignore")[:3000].lower()
    except OSError:
        return False
    for marker in ("schemas.live.com", "window.si_st", 'name="referrer"', "/search?"):
        if marker in head:
            return False
    return True


# --------------------------------------------------------------------------
# JSON-lines 事件解析
# --------------------------------------------------------------------------

def parse_pi_event_line(line: str) -> dict[str, Any] | None:
    """把 pi 的一行 JSON 输出解析成事件字典；非 JSON 行返回 None。"""
    line = (line or "").strip()
    if not line.startswith("{"):
        return None
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        return None
    return event if isinstance(event, dict) else None


class PiEventParser:
    """把 pi 的 JSON-lines 事件流归一化成项目内的 SSE 事件。

    ``feed_line`` 返回「本次应下发的事件列表」，内部维护思考缓冲与开头净化
    缓冲，因此可以脱离子进程单独测试。
    """

    def __init__(self, *, thinking_flush_chars: int = 50, min_probe: int = 60) -> None:
        self._thinking_buffer: list[str] = []
        self._text_parts: list[str] = []
        self._prefix_buffer = ""
        self._prefix_settled = False
        self._thinking_flush_chars = thinking_flush_chars
        self._min_probe = min_probe

    @property
    def text(self) -> str:
        """已下发给用户的正文（不含被过滤的过程叙述）。"""
        return "".join(self._text_parts)

    def feed_line(self, line: str) -> list[dict[str, Any]]:
        events = parse_pi_event_line(line)
        if events is None:
            # 非 JSON 行按纯文本处理
            return self._emit_text((line or "") + "\n")
        return self._feed_event(events)

    def _feed_event(self, event: dict[str, Any]) -> list[dict[str, Any]]:
        event_type = event.get("type", "")

        if event_type == "turn_start":
            return [{"type": "log", "content": "开始处理…"}]

        if event_type == "message_start":
            if event.get("message", {}).get("role") == "assistant":
                return [{"type": "log", "content": "AI 正在思考…"}]
            return []

        if event_type == "message_update":
            return self._feed_assistant_event(event.get("assistantMessageEvent") or {})

        if event_type == "message_end":
            if event.get("message", {}).get("role") == "assistant":
                return [{"type": "log", "content": "思考完成"}]
            return []

        if event_type == "agent_end":
            return [{"type": "log", "content": "处理完成"}]

        return []

    def _feed_assistant_event(self, assistant_event: dict[str, Any]) -> list[dict[str, Any]]:
        subtype = assistant_event.get("type", "")

        if subtype == "thinking_delta":
            self._thinking_buffer.append(assistant_event.get("delta", ""))
            buffered = "".join(self._thinking_buffer)
            if len(buffered) >= self._thinking_flush_chars:
                self._thinking_buffer = []
                return [{"type": "thinking", "content": buffered}]
            return []

        if subtype == "thinking_end":
            if self._thinking_buffer:
                buffered = "".join(self._thinking_buffer)
                self._thinking_buffer = []
                return [{"type": "thinking", "content": buffered}]
            return []

        if subtype == "text_delta":
            return self._emit_text(assistant_event.get("delta", ""))

        if subtype == "toolcall_start":
            tool_name = (
                assistant_event.get("name")
                or assistant_event.get("toolName")
                or assistant_event.get("tool", {}).get("name")
                or ""
            )
            content = f"正在调用工具：{tool_name}" if tool_name else "正在调用工具…"
            return [{"type": "tool_call", "content": content}]

        return []

    def _emit_text(self, delta: str) -> list[dict[str, Any]]:
        if not delta:
            return []
        self._prefix_buffer, self._prefix_settled, to_send = screen_stream_delta(
            self._prefix_buffer, self._prefix_settled, delta, min_probe=self._min_probe
        )
        if not to_send:
            return []
        self._text_parts.append(to_send)
        return [{"type": "text", "content": to_send}]

    def flush(self) -> list[dict[str, Any]]:
        """流结束时冲刷剩余缓冲（未判定的开头文本 + 思考缓冲）。"""
        events: list[dict[str, Any]] = []

        if self._thinking_buffer:
            events.append({"type": "thinking", "content": "".join(self._thinking_buffer)})
            self._thinking_buffer = []

        if not self._prefix_settled and self._prefix_buffer:
            self._prefix_buffer, self._prefix_settled, to_send = screen_stream_delta(
                self._prefix_buffer, False, "", min_probe=0
            )
            if to_send:
                self._text_parts.append(to_send)
                events.append({"type": "text", "content": to_send})

        return events


# --------------------------------------------------------------------------
# 工作区快照与产物收集
# --------------------------------------------------------------------------

def _should_skip_dir(root: str) -> bool:
    parts = Path(root).parts
    return any(part in _SKIP_DIR_NAMES or (part.startswith(".") and part not in (".", "..")) for part in parts)


def snapshot_workspace(workspace: str | Path) -> set[str]:
    """记录工作区中现有文件，用于事后识别新增产物。"""
    workspace = str(workspace)
    snapshot: set[str] = set()
    for root, _dirs, files in os.walk(workspace):
        if _should_skip_dir(root):
            continue
        for name in files:
            if name.startswith("."):
                continue
            snapshot.add(os.path.join(root, name))
    return snapshot


def collect_new_files(workspace: str | Path, before: Iterable[str], *, agent_id: str) -> list[dict[str, Any]]:
    """对比快照，返回可下载的新产物列表。"""
    workspace = Path(workspace)
    before_set = set(before)
    results: list[dict[str, Any]] = []

    for root, _dirs, files in os.walk(workspace):
        if _should_skip_dir(root):
            continue
        for name in files:
            if name.startswith("."):
                continue
            path = os.path.join(root, name)
            if path in before_set or not is_usable_artifact(path):
                continue

            rel_path = os.path.relpath(path, workspace).replace(os.sep, "/")
            try:
                stat = os.stat(path)
            except OSError:
                continue

            results.append({
                "name": name,
                "path": rel_path,
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "url": f"/api/v1/pi/{agent_id}/files/{rel_path}",
            })
            if len(results) >= _MAX_ARTIFACTS:
                return results

    return results


# --------------------------------------------------------------------------
# 子进程执行
# --------------------------------------------------------------------------

def spawn_line_reader(
    cmd: Sequence[str],
    workspace: str,
    queue: Queue,
    timeout: int,
    env: dict[str, str] | None = None,
) -> None:
    """在（线程中的）子进程里逐行读取 stdout 并放入 queue。

    放入的消息形如 ``("line", 文本)`` / ``("done", 返回码)`` / ``("error", 说明)``。
    单独抽成模块级函数，便于测试时替换。
    """
    try:
        proc = subprocess.Popen(
            list(cmd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=workspace,
            env=env,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        try:
            for raw in proc.stdout:
                text = raw.decode("utf-8", errors="replace").strip()
                if text:
                    queue.put(("line", text))
            proc.wait(timeout=timeout)
        finally:
            queue.put(("done", proc.returncode))
    except Exception as exc:  # noqa: BLE001 - 需要把失败原因回传给调用方
        queue.put(("error", str(exc)))


# pi 从环境变量读取各 provider 的密钥；pydantic 读 .env 不会写回 os.environ，
# 因此需要显式把 settings 里的 key 透传给子进程。
_PROVIDER_KEY_VARS = (
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "DEEPSEEK_API_KEY",
)


def build_subprocess_env() -> dict[str, str]:
    """构造传给 pi 子进程的环境变量。

    继承当前进程环境，并把 backend/.env 中配置的模型密钥补齐
    （不覆盖已存在的环境变量）。
    """
    env = dict(os.environ)
    for var in _PROVIDER_KEY_VARS:
        if env.get(var):
            continue
        value = getattr(settings, var, "")
        if value:
            env[var] = str(value)
    return env


def resolve_skill_files(slugs: Iterable[str] | None) -> list[str]:
    """把技能 slug 解析成 SKILL.md 绝对路径。

    只接受单个目录名，禁止通过路径分隔符逃逸出技能根目录。
    """
    if not slugs:
        return []

    root = pi_skills_root()
    resolved: list[str] = []

    for raw in slugs:
        slug = str(raw).strip()
        if not slug or slug in (".", ".."):
            continue
        if "/" in slug or "\\" in slug or Path(slug).name != slug:
            logger.warning("忽略非法技能名: %s", slug)
            continue

        skill_file = root / slug / "SKILL.md"
        if skill_file.is_file():
            resolved.append(str(skill_file))
        else:
            logger.warning("技能不存在或缺少 SKILL.md: %s", slug)

    return resolved


def build_system_prompt(agent: Any) -> str:
    """组装 PiAgent 的系统提示词。

    优先使用 Agent 自身配置：model_config.system_prompt 或 settings.system_prompt；
    都没有时按名称/描述生成一份通用提示词。
    """
    model_config = getattr(agent, "model_config", None) or {}
    agent_settings = getattr(agent, "settings", None) or {}
    if isinstance(model_config, dict):
        configured = str(model_config.get("system_prompt") or "").strip()
        if configured:
            return configured
    if isinstance(agent_settings, dict):
        configured = str(agent_settings.get("system_prompt") or "").strip()
        if configured:
            return configured

    name = getattr(agent, "name", None) or "AI 助手"
    description = (getattr(agent, "description", None) or "").strip()

    lines = [f"你是「{name}」。"]
    if description:
        lines.append(f"你的职责：{description}")
    lines.extend([
        "",
        "# 通用规则",
        "1. 直接开始执行任务，不要声明「我将读取文件」「正在查看」之类的过程说明",
        "2. 不要向用户提及工作目录、文件路径、技能名称、工具列表等技术细节",
        "3. 严禁编造事实；不确定的信息要如实说明",
        "4. 内容较长（超过 1000 字、含表格或分多段）时，用 write_file 生成文件，",
        "   回复中只给出 2-3 句摘要和文件名",
    ])
    return "\n".join(lines)


class PiAgentUnavailableError(RuntimeError):
    """本机未安装 pi CLI。"""


class PiAgentRunner:
    """PiAgent 运行时封装。"""

    def __init__(self, *, exe: str | None = None, timeout: int | None = None) -> None:
        self._exe_override = exe
        self._timeout_override = timeout

    # ------------------------------------------------------------ 基础能力

    @property
    def exe(self) -> str | None:
        return find_pi_executable(self._exe_override)

    @property
    def timeout(self) -> int:
        return self._timeout_override or settings.PIAGENT_TIMEOUT

    def is_available(self) -> bool:
        return self.exe is not None

    def build_command(
        self,
        *,
        prompt_file: str,
        skill_files: Sequence[str],
        system_prompt: str,
        session_id: str | None,
    ) -> list[str]:
        """组装 pi 的 argv（不含 exe 本身）。"""
        cmd = [
            "-p",
            f"请读取文件 {prompt_file} 的内容，严格按照其中的要求执行；"
            "不要向用户提及文件路径或任何技术细节",
            "--mode",
            "json",
        ]

        if skill_files:
            for skill_file in skill_files:
                cmd.extend(["--skill", skill_file])
        else:
            cmd.append("--no-skills")

        if session_id:
            cmd.extend(["--session-id", session_id])

        if settings.PIAGENT_PROVIDER:
            cmd.extend(["--provider", settings.PIAGENT_PROVIDER])
        if settings.PIAGENT_MODEL:
            cmd.extend(["--model", settings.PIAGENT_MODEL])

        cmd.extend(["--system-prompt", system_prompt])
        return cmd

    # ------------------------------------------------------------ 运行入口

    async def stream(
        self,
        *,
        message: str,
        agent_id: str,
        agent: Any = None,
        session_id: str | None = None,
        skills: Iterable[str] | None = None,
        timeout: int | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """流式执行，逐条产出 SSE 事件。

        事件类型：``log`` / ``thinking`` / ``text`` / ``tool_call`` / ``done`` / ``error``。
        """
        exe = self.exe
        if not exe:
            yield {
                "type": "error",
                "content": "本机未找到 pi，请先安装：npm install -g @earendil-works/pi-coding-agent",
            }
            return

        workspace = pi_agent_workspace(agent_id)
        effective_timeout = timeout or self.timeout
        skill_files = resolve_skill_files(skills)
        system_prompt = build_system_prompt(agent) if agent is not None else build_system_prompt(None)

        prompt_file = workspace / f".agentflow_prompt_{uuid.uuid4().hex}.txt"
        try:
            prompt_file.write_text(message, encoding="utf-8")
        except OSError as exc:
            yield {"type": "error", "content": f"写入提示词文件失败：{exc}"}
            return

        files_before = snapshot_workspace(workspace)
        parser = PiEventParser()

        try:
            args = self.build_command(
                prompt_file=str(prompt_file),
                skill_files=skill_files,
                system_prompt=system_prompt,
                session_id=session_id,
            )
            cmd = wrap_cmd_for_windows(exe, args)
            logger.info("PiAgent 启动 agent=%s skills=%d workspace=%s", agent_id, len(skill_files), workspace)

            queue: Queue = Queue()
            thread = threading.Thread(
                target=spawn_line_reader,
                args=(cmd, str(workspace), queue, effective_timeout, build_subprocess_env()),
                daemon=True,
            )
            thread.start()

            while True:
                try:
                    item = queue.get(timeout=effective_timeout + 10)
                except Empty:
                    yield {"type": "error", "content": f"PiAgent 执行超时（{effective_timeout}s）"}
                    break

                kind = item[0]
                if kind == "done":
                    break
                if kind == "error":
                    yield {"type": "error", "content": f"执行错误：{item[1]}"}
                    break

                for event in parser.feed_line(item[1]):
                    yield event

            thread.join(timeout=5)

            for event in parser.flush():
                yield event

            new_files = collect_new_files(workspace, files_before, agent_id=agent_id)
            if new_files:
                yield {"type": "log", "content": f"生成了 {len(new_files)} 个文件"}

            final_text = strip_leading_narration(parser.text).strip()

            yield {
                "type": "done",
                "content": final_text,
                "files": new_files,
                "session_id": session_id,
            }

        finally:
            # 提示词用完即删，避免残留内容被后续请求读到
            try:
                prompt_file.unlink(missing_ok=True)
            except OSError:  # pragma: no cover - 清理失败不影响结果
                pass

    async def run(
        self,
        *,
        message: str,
        agent_id: str,
        agent: Any = None,
        session_id: str | None = None,
        skills: Iterable[str] | None = None,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        """非流式执行：把事件流收敛成最终结果。"""
        events: list[dict[str, Any]] = []
        async for event in self.stream(
            message=message,
            agent_id=agent_id,
            agent=agent,
            session_id=session_id,
            skills=skills,
            timeout=timeout,
        ):
            events.append(event)

        final = next((e for e in reversed(events) if e["type"] == "done"), None)
        if final is None:
            error = next((e for e in reversed(events) if e["type"] == "error"), None)
            return {
                "success": False,
                "error": error["content"] if error else "PiAgent 未返回结果",
                "content": "",
                "files": [],
                "events": events,
            }

        return {
            "success": True,
            "error": None,
            "content": final.get("content", ""),
            "files": final.get("files", []),
            "events": events,
        }


# 全局实例
pi_agent_runner = PiAgentRunner()
