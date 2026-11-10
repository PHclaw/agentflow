"""测试 PiAgent 运行时（app/services/pi_agent.py）与 API 层。

覆盖点：
- Windows 命令拼装与可执行文件发现
- 过程性叙述过滤（流式缓冲 + 最终兜底）
- 产物判定、工作区快照与新增文件收集
- JSON-lines 事件解析与归一化
- 技能解析、系统提示词组装
- 通过替换子进程读取器，端到端跑一遍事件流
- API 开关、路径穿越防护
"""
import json
import subprocess
from pathlib import Path

import pytest

from app.api import pi_agent as pi_api
from app.core.config import settings
from app.services import pi_agent as pi_mod
from app.services.pi_agent import (
    PiAgentRunner,
    PiEventParser,
    build_system_prompt,
    collect_new_files,
    find_pi_executable,
    is_process_narration,
    is_usable_artifact,
    resolve_skill_files,
    screen_stream_delta,
    snapshot_workspace,
    strip_leading_narration,
    wrap_cmd_for_windows,
)


# --------------------------------------------------------------------------
# 命令拼装与可执行文件发现
# --------------------------------------------------------------------------

class TestWrapCmd:
    def test_plain_executable(self):
        assert wrap_cmd_for_windows("/usr/bin/pi", ["-p", "hi"], platform="linux") == [
            "/usr/bin/pi", "-p", "hi",
        ]

    def test_node_bypass_format(self):
        result = wrap_cmd_for_windows("node|/app/cli.js", ["-p", "x"], platform="win32")
        assert result == ["node", "/app/cli.js", "-p", "x"]

    def test_windows_cmd_is_wrapped_with_proper_escaping(self):
        result = wrap_cmd_for_windows(r"C:\npm\pi.cmd", ["-p", "hello world"], platform="win32")

        assert result[0] == "cmd.exe"
        assert result[1] == "/c"
        # 交给 list2cmdline 处理，含空格参数必须被引号包住
        assert '"hello world"' in result[2]
        assert result[2].startswith(r"C:\npm\pi.cmd")

    def test_windows_cmd_escapes_embedded_quotes(self):
        result = wrap_cmd_for_windows(r"C:\npm\pi.cmd", ["-p", 'say "hi"'], platform="win32")
        cmd_str = result[2]

        # 反斜杠转义后仍应是一条可被解析的命令行
        assert subprocess.list2cmdline([r"C:\npm\pi.cmd", "-p", 'say "hi"']) == cmd_str


class TestFindPi:
    def test_explicit_existing_path_wins(self, tmp_path, monkeypatch):
        fake = tmp_path / "my-pi"
        fake.write_text("", encoding="utf-8")
        monkeypatch.setattr(pi_mod.shutil, "which", lambda name: None)

        assert find_pi_executable(str(fake), platform="linux") == str(fake)

    def test_falls_back_to_path_lookup(self, monkeypatch):
        monkeypatch.setattr(pi_mod.shutil, "which", lambda name: "/usr/local/bin/pi" if name == "pi" else None)

        assert find_pi_executable("pi", platform="linux") == "/usr/local/bin/pi"

    def test_returns_none_when_missing(self, monkeypatch):
        monkeypatch.setattr(pi_mod.shutil, "which", lambda name: None)
        monkeypatch.setattr(pi_mod.os.path, "exists", lambda path: False)

        assert find_pi_executable("pi", platform="linux") is None

    def test_windows_cmd_uses_node_bypass(self, tmp_path, monkeypatch):
        npm_dir = tmp_path / "npm"
        cli_js = npm_dir / "node_modules" / "@earendil-works" / "pi-coding-agent" / "dist" / "bundle" / "cli.js"
        cli_js.parent.mkdir(parents=True)
        cli_js.write_text("", encoding="utf-8")

        def fake_which(name):
            return {"pi": str(npm_dir / "pi.cmd"), "node": r"C:\node\node.exe"}.get(name)

        monkeypatch.setattr(pi_mod.shutil, "which", fake_which)

        result = find_pi_executable("pi", platform="win32")

        assert result == rf"C:\node\node.exe|{cli_js}"


# --------------------------------------------------------------------------
# 过程性叙述过滤
# --------------------------------------------------------------------------

class TestNarrationFiltering:
    @pytest.mark.parametrize(
        "text",
        [
            "I'll read the file first.",
            "let me read the prompt",
            "我先读取一下这个文件。",
            "让我先查看一下内容",
        ],
    )
    def test_detects_narration(self, text):
        assert is_process_narration(text) is True

    def test_normal_text_is_not_narration(self):
        assert is_process_narration("科理咨询成立于 2008 年。") is False

    def test_buffer_below_threshold_emits_nothing(self):
        buffer, settled, to_send = screen_stream_delta("", False, "短文本")

        assert to_send == ""
        assert settled is False
        assert buffer == "短文本"

    def test_settled_state_passes_delta_through(self):
        _, settled, to_send = screen_stream_delta("", True, "后续内容")

        assert (settled, to_send) == (True, "后续内容")

    def test_narration_is_dropped_with_remainder_kept(self):
        buffer, settled, to_send = screen_stream_delta("", False, "I'll read the file now. 真正的答案是 42。")

        assert settled is True
        assert buffer == ""
        assert "真正的答案" in to_send
        assert "read the file" not in to_send

    def test_normal_prefix_is_released_after_probe(self):
        long_text = "这是一段完全正常的回答内容，" * 5
        buffer, settled, to_send = screen_stream_delta("", False, long_text)

        assert settled is True
        assert to_send == long_text

    def test_sentence_end_triggers_early_judgement(self):
        _, settled, to_send = screen_stream_delta("", False, "你好。")

        assert settled is True
        assert to_send == "你好。"

    def test_strip_leading_narration_removes_sentence(self):
        assert strip_leading_narration("I'll read the file. 结论如下") == "结论如下"

    def test_strip_leading_narration_keeps_clean_text(self):
        assert strip_leading_narration("结论如下") == "结论如下"


# --------------------------------------------------------------------------
# 产物判定与工作区快照
# --------------------------------------------------------------------------

class TestArtifacts:
    def test_real_html_is_usable(self, tmp_path):
        f = tmp_path / "分析报告.html"
        f.write_text("<html><body>报告正文</body></html>", encoding="utf-8")

        assert is_usable_artifact(f) is True

    def test_empty_file_rejected(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_text("", encoding="utf-8")

        assert is_usable_artifact(f) is False

    def test_short_curl_snapshot_rejected(self, tmp_path):
        f = tmp_path / "t1.html"
        f.write_text("<html>snapshot</html>", encoding="utf-8")

        assert is_usable_artifact(f) is False

    def test_search_result_page_rejected(self, tmp_path):
        f = tmp_path / "results.html"
        f.write_text('<html>see /search?q=x and window.si_st</html>', encoding="utf-8")

        assert is_usable_artifact(f) is False

    def test_snapshot_and_collect_new_files(self, tmp_path):
        workspace = tmp_path / "ws"
        workspace.mkdir()
        existing = workspace / "old.txt"
        existing.write_text("old", encoding="utf-8")

        before = snapshot_workspace(workspace)
        assert str(existing) in before

        new_file = workspace / "新报告.html"
        new_file.write_text("<html>内容</html>", encoding="utf-8")
        (workspace / ".hidden").write_text("x", encoding="utf-8")

        results = collect_new_files(workspace, before, agent_id="agent-1")

        assert [r["name"] for r in results] == ["新报告.html"]
        assert results[0]["url"] == "/api/v1/pi/agent-1/files/新报告.html"

    def test_skips_node_modules_and_hidden_dirs(self, tmp_path):
        workspace = tmp_path / "ws"
        (workspace / "node_modules").mkdir(parents=True)
        (workspace / ".cache").mkdir()
        (workspace / "node_modules" / "a.html").write_text("<html>x</html>", encoding="utf-8")
        (workspace / ".cache" / "b.html").write_text("<html>x</html>", encoding="utf-8")

        results = collect_new_files(workspace, set(), agent_id="a")

        assert results == []


# --------------------------------------------------------------------------
# 事件解析
# --------------------------------------------------------------------------

class TestPiEventParser:
    def test_lifecycle_events_become_logs(self):
        parser = PiEventParser()

        assert parser.feed_line(json.dumps({"type": "turn_start"})) == [
            {"type": "log", "content": "开始处理…"}
        ]
        assert parser.feed_line(json.dumps({"type": "message_start", "message": {"role": "assistant"}})) == [
            {"type": "log", "content": "AI 正在思考…"}
        ]
        assert parser.feed_line(json.dumps({"type": "agent_end"})) == [
            {"type": "log", "content": "处理完成"}
        ]

    def test_thinking_delta_flushes_at_threshold(self):
        parser = PiEventParser(thinking_flush_chars=10)

        assert parser.feed_line(json.dumps({
            "type": "message_update",
            "assistantMessageEvent": {"type": "thinking_delta", "delta": "12345"},
        })) == []

        events = parser.feed_line(json.dumps({
            "type": "message_update",
            "assistantMessageEvent": {"type": "thinking_delta", "delta": "67890"},
        }))

        assert events == [{"type": "thinking", "content": "1234567890"}]

    def test_thinking_end_flushes_remainder(self):
        parser = PiEventParser(thinking_flush_chars=100)
        parser.feed_line(json.dumps({
            "type": "message_update",
            "assistantMessageEvent": {"type": "thinking_delta", "delta": "abc"},
        }))

        events = parser.feed_line(json.dumps({
            "type": "message_update",
            "assistantMessageEvent": {"type": "thinking_end"},
        }))

        assert events == [{"type": "thinking", "content": "abc"}]

    def test_text_delta_accumulates_and_filters_narration(self):
        parser = PiEventParser()
        parser.feed_line(json.dumps({
            "type": "message_update",
            "assistantMessageEvent": {"type": "text_delta", "delta": "I'll read the file. 结论：增长"},
        }))

        assert "结论：增长" in parser.text
        assert "read the file" not in parser.text

    def test_toolcall_start_reports_tool_name(self):
        parser = PiEventParser()

        events = parser.feed_line(json.dumps({
            "type": "message_update",
            "assistantMessageEvent": {"type": "toolcall_start", "name": "write_file"},
        }))

        assert events == [{"type": "tool_call", "content": "正在调用工具：write_file"}]

    def test_plain_text_line_is_treated_as_text(self):
        parser = PiEventParser()

        events = parser.feed_line("这是一行纯文本输出")

        assert any(e["type"] == "text" for e in events)

    def test_flush_releases_pending_prefix(self):
        """开头不足 min_probe 且无句末标点时内容会挂起，流结束必须冲刷出来。"""
        parser = PiEventParser()
        parser.feed_line(json.dumps({
            "type": "message_update",
            "assistantMessageEvent": {"type": "text_delta", "delta": "短"},
        }))

        assert parser.text == ""

        events = parser.flush()

        assert events == [{"type": "text", "content": "短"}]
        assert parser.text == "短"

    def test_plain_text_line_ends_sentence_and_flushes_immediately(self):
        """纯文本行会补换行，换行视为句末，应立刻下发。"""
        parser = PiEventParser()

        events = parser.feed_line("短")

        assert events == [{"type": "text", "content": "短\n"}]
        assert parser.flush() == []


# --------------------------------------------------------------------------
# 技能与系统提示词
# --------------------------------------------------------------------------

class TestSkillsAndPrompt:
    def test_resolve_skill_files_from_root(self, tmp_path, monkeypatch):
        skill_dir = tmp_path / "excel"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# excel", encoding="utf-8")

        monkeypatch.setattr(pi_mod, "pi_skills_root", lambda: tmp_path)

        resolved = resolve_skill_files(["excel"])

        assert resolved == [str(skill_dir / "SKILL.md")]

    def test_rejects_path_traversal_in_skill_name(self, tmp_path, monkeypatch):
        monkeypatch.setattr(pi_mod, "pi_skills_root", lambda: tmp_path)

        assert resolve_skill_files(["../secret"]) == []
        assert resolve_skill_files([r"..\secret"]) == []

    def test_missing_skill_is_skipped(self, tmp_path, monkeypatch):
        monkeypatch.setattr(pi_mod, "pi_skills_root", lambda: tmp_path)
        (tmp_path / "nofile").mkdir()

        assert resolve_skill_files(["nofile", "ghost"]) == []

    def test_empty_slug_list_returns_empty(self):
        assert resolve_skill_files(None) == []
        assert resolve_skill_files([]) == []

    def test_provider_and_model_flags_included_when_configured(self, monkeypatch, tmp_path):
        monkeypatch.setattr(settings, "PIAGENT_PROVIDER", "openai")
        monkeypatch.setattr(settings, "PIAGENT_MODEL", "gpt-4o-mini")

        runner = PiAgentRunner()
        cmd = runner.build_command(
            prompt_file=str(tmp_path / "p.txt"),
            skill_files=[],
            system_prompt="sp",
            session_id=None,
        )

        assert "--provider" in cmd and "openai" in cmd
        assert "--model" in cmd and "gpt-4o-mini" in cmd

    def test_provider_flags_absent_by_default(self, monkeypatch, tmp_path):
        monkeypatch.setattr(settings, "PIAGENT_PROVIDER", "")
        monkeypatch.setattr(settings, "PIAGENT_MODEL", "")

        runner = PiAgentRunner()
        cmd = runner.build_command(
            prompt_file=str(tmp_path / "p.txt"),
            skill_files=[],
            system_prompt="sp",
            session_id=None,
        )

        assert "--provider" not in cmd
        assert "--model" not in cmd


class TestSubprocessEnv:
    """provider 密钥需要从 settings 透传给子进程"""

    def test_forwards_configured_key(self, monkeypatch):
        monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-from-dotenv")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        env = pi_mod.build_subprocess_env()

        assert env["OPENAI_API_KEY"] == "sk-from-dotenv"

    def test_existing_environment_wins(self, monkeypatch):
        monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-from-dotenv")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-from-env")

        env = pi_mod.build_subprocess_env()

        assert env["OPENAI_API_KEY"] == "sk-from-env"

    def test_empty_settings_are_not_injected(self, monkeypatch):
        for var in pi_mod._PROVIDER_KEY_VARS:
            monkeypatch.delenv(var, raising=False)
            # settings 只声明了部分 provider 的 key；pydantic 对未声明字段会抛
            # ValueError（不是 AttributeError），因此需先判断存在性
            if hasattr(settings, var):
                monkeypatch.setattr(settings, var, "")

        env = pi_mod.build_subprocess_env()

        assert not any(var in env for var in pi_mod._PROVIDER_KEY_VARS)

    def test_prompt_from_model_config(self):
        class A:
            name = "客服助手"
            description = "回答售后问题"
            model_config = {"system_prompt": "只回答售后问题"}
            settings = {}

        assert build_system_prompt(A()) == "只回答售后问题"

    def test_prompt_from_settings(self):
        class A:
            name = "客服助手"
            description = ""
            model_config = {}
            settings = {"system_prompt": "来自 settings"}

        assert build_system_prompt(A()) == "来自 settings"

    def test_default_prompt_includes_name_and_description(self):
        class A:
            name = "销售助手"
            description = "生成报价单"
            model_config = {}
            settings = {}

        prompt = build_system_prompt(A())

        assert "销售助手" in prompt
        assert "生成报价单" in prompt
        assert "不要向用户提及工作目录" in prompt


# --------------------------------------------------------------------------
# 端到端：替换子进程读取器
# --------------------------------------------------------------------------

class TestRunnerStream:
    @pytest.fixture
    def workspace(self, tmp_path, monkeypatch):
        monkeypatch.setattr(settings, "PIAGENT_WORKSPACE_ROOT", str(tmp_path))
        monkeypatch.setattr(pi_mod, "find_pi_executable", lambda configured=None, **kw: "pi")
        return tmp_path

    @pytest.fixture
    def fake_reader(self, monkeypatch):
        """替换子进程读取器，产出预置的 JSON-lines 行。"""
        captured = {}

        def install(lines, returncode=0, produce=None):
            def fake_spawn(cmd, workspace, queue, timeout, env=None):
                captured["cmd"] = list(cmd)
                captured["workspace"] = workspace
                captured["env"] = env
                if produce:
                    produce(Path(workspace))
                for line in lines:
                    queue.put(("line", line))
                queue.put(("done", returncode))

            monkeypatch.setattr(pi_mod, "spawn_line_reader", fake_spawn)
            return captured

        return install

    async def test_stream_emits_events_and_final_text(self, workspace, fake_reader):
        captured = fake_reader([
            json.dumps({"type": "turn_start"}),
            json.dumps({
                "type": "message_update",
                "assistantMessageEvent": {"type": "text_delta", "delta": "最终结论：业务增长。"},
            }),
            json.dumps({"type": "agent_end"}),
        ])

        runner = PiAgentRunner(timeout=5)
        events = [
            e async for e in runner.stream(message="分析一下", agent_id="agent-1", skills=None)
        ]

        kinds = [e["type"] for e in events]
        assert "log" in kinds
        assert kinds[-1] == "done"

        done = events[-1]
        assert "业务增长" in done["content"]
        assert done["files"] == []
        # 提示词以文件方式传递，且命令里带了 --no-skills
        assert "--no-skills" in captured["cmd"]
        assert any("请读取文件" in arg for arg in captured["cmd"])

    async def test_stream_detects_generated_files(self, workspace, fake_reader):
        def produce(ws: Path):
            (ws / "报告.html").write_text("<html>报告正文</html>", encoding="utf-8")

        fake_reader(
            [json.dumps({
                "type": "message_update",
                "assistantMessageEvent": {"type": "text_delta", "delta": "已生成报告。"},
            })],
            produce=produce,
        )

        runner = PiAgentRunner(timeout=5)
        events = [e async for e in runner.stream(message="生成报告", agent_id="agent-2")]

        done = events[-1]
        assert [f["name"] for f in done["files"]] == ["报告.html"]
        assert done["files"][0]["url"].startswith("/api/v1/pi/agent-2/files/")
        assert any(e["type"] == "log" and "生成了 1 个文件" in e["content"] for e in events)

    async def test_stream_reports_reader_error(self, workspace, monkeypatch):
        monkeypatch.setattr(pi_mod, "find_pi_executable", lambda configured=None, **kw: "pi")

        def failing_spawn(cmd, workspace, queue, timeout, env=None):
            queue.put(("error", "boom"))

        monkeypatch.setattr(pi_mod, "spawn_line_reader", failing_spawn)

        runner = PiAgentRunner(timeout=5)
        events = [e async for e in runner.stream(message="x", agent_id="a")]

        assert events[0]["type"] == "error"
        assert "boom" in events[0]["content"]

    async def test_stream_without_pi_reports_install_hint(self, tmp_path, monkeypatch):
        monkeypatch.setattr(pi_mod, "find_pi_executable", lambda configured=None, **kw: None)

        runner = PiAgentRunner(timeout=5)
        events = [e async for e in runner.stream(message="x", agent_id="a")]

        assert events == [{
            "type": "error",
            "content": "本机未找到 pi，请先安装：npm install -g @earendil-works/pi-coding-agent",
        }]

    async def test_prompt_file_is_removed_after_run(self, workspace, fake_reader):
        captured = fake_reader([])

        runner = PiAgentRunner(timeout=5)
        [e async for e in runner.stream(message="内容", agent_id="agent-3")]

        leftover = [p for p in Path(captured["workspace"]).glob(".agentflow_prompt_*")]
        assert leftover == []

    async def test_run_converges_to_result(self, workspace, fake_reader):
        fake_reader([json.dumps({
            "type": "message_update",
            "assistantMessageEvent": {"type": "text_delta", "delta": "答案。"},
        })])

        runner = PiAgentRunner(timeout=5)
        result = await runner.run(message="问题", agent_id="agent-4")

        assert result["success"] is True
        assert result["content"] == "答案。"
        assert result["files"] == []

    async def test_command_includes_session_and_skills(self, workspace, fake_reader, tmp_path, monkeypatch):
        skill_dir = tmp_path / "excel"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# excel", encoding="utf-8")
        monkeypatch.setattr(pi_mod, "pi_skills_root", lambda: tmp_path)

        captured = fake_reader([])

        runner = PiAgentRunner(timeout=5)
        [e async for e in runner.stream(message="x", agent_id="agent-5", session_id="s1", skills=["excel"])]

        cmd = captured["cmd"]
        assert "--session-id" in cmd and "s1" in cmd
        assert "--skill" in cmd
        assert str(skill_dir / "SKILL.md") in cmd
        assert "--system-prompt" in cmd


# --------------------------------------------------------------------------
# API 层
# --------------------------------------------------------------------------

class TestPiApi:
    def test_resolve_workspace_file_blocks_traversal(self, tmp_path):
        from fastapi import HTTPException

        workspace = tmp_path / "ws"
        workspace.mkdir()
        outside = tmp_path / "secret.txt"
        outside.write_text("top-secret", encoding="utf-8")

        for attempt in ("../secret.txt", r"..\secret.txt", "a/../../secret.txt"):
            with pytest.raises(HTTPException) as exc:
                pi_api.resolve_workspace_file(workspace, attempt)
            assert exc.value.status_code == 403

    def test_resolve_workspace_file_returns_existing_file(self, tmp_path):
        workspace = tmp_path / "ws"
        (workspace / "sub").mkdir(parents=True)
        target = workspace / "sub" / "ok.html"
        target.write_text("hi", encoding="utf-8")

        assert pi_api.resolve_workspace_file(workspace, "sub/ok.html") == target.resolve()

    def test_resolve_workspace_file_missing_raises_404(self, tmp_path):
        from fastapi import HTTPException

        workspace = tmp_path / "ws"
        workspace.mkdir()

        with pytest.raises(HTTPException) as exc:
            pi_api.resolve_workspace_file(workspace, "nope.txt")
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_status_reports_disabled(self, async_client, auth_headers, monkeypatch):
        monkeypatch.setattr(settings, "PIAGENT_ENABLED", False)

        response = await async_client.get("/api/v1/pi/status", headers=auth_headers)

        assert response.status_code == 200
        assert response.json()["enabled"] is False

    @pytest.mark.asyncio
    async def test_stream_requires_enabled_flag(self, async_client, auth_headers, test_agent, monkeypatch):
        monkeypatch.setattr(settings, "PIAGENT_ENABLED", False)

        response = await async_client.post(
            f"/api/v1/pi/{test_agent.id}/stream",
            headers=auth_headers,
            json={"message": "hi"},
        )

        assert response.status_code == 503
        assert "PIAGENT_ENABLED" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_stream_forwards_events(self, async_client, auth_headers, test_agent, monkeypatch):
        monkeypatch.setattr(settings, "PIAGENT_ENABLED", True)
        monkeypatch.setattr(settings, "PIAGENT_WORKSPACE_ROOT", "")

        class FakeRunner:
            exe = "pi"
            timeout = 5

            async def stream(self, **_kwargs):
                yield {"type": "text", "content": "你好"}
                yield {"type": "done", "content": "你好", "files": [], "session_id": None}

        monkeypatch.setattr(pi_api, "pi_agent_runner", FakeRunner())

        response = await async_client.post(
            f"/api/v1/pi/{test_agent.id}/stream",
            headers=auth_headers,
            json={"message": "hi"},
        )

        assert response.status_code == 200
        body = response.text
        assert '"type": "text"' in body
        assert '"type": "done"' in body

    @pytest.mark.asyncio
    async def test_run_requires_agent_ownership(self, async_client, auth_headers, monkeypatch):
        monkeypatch.setattr(settings, "PIAGENT_ENABLED", True)

        response = await async_client.post(
            "/api/v1/pi/not-my-agent/run",
            headers=auth_headers,
            json={"message": "hi"},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_list_skills_helper_reads_skill_md(self, tmp_path, monkeypatch):
        (tmp_path / "excel").mkdir()
        (tmp_path / "excel" / "SKILL.md").write_text("# excel", encoding="utf-8")
        (tmp_path / "empty").mkdir()

        monkeypatch.setattr(pi_api, "pi_skills_root", lambda: tmp_path)

        assert pi_api._list_available_skills() == ["excel"]
