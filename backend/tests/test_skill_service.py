"""
测试 Skill 服务的接口层

覆盖 app/services/skill_service.py 中不落盘、不发起模型调用的部分：
- 版本号递增、默认工作流、工作流模型同步
- 标签/触发器归一化
- 列表可见性过滤、更新、下架、删除
- 工具已产出文件时调用失败的兜底文案

持久化相关函数通过 monkeypatch 替换 store 层，避免真实写盘。
"""
import pytest

from app.schemas import AgentUpdate
from app.services import skill_service as ss
from app.services.skill.store import FileSkill


def make_skill(**overrides) -> FileSkill:
    defaults = {
        "id": "skill-1",
        "name": "示例 Skill",
        "author_id": "user-a",
    }
    defaults.update(overrides)
    return FileSkill(**defaults)


class TestVersionAndWorkflow:
    """版本号与工作流辅助函数"""

    @pytest.mark.parametrize(
        "current,expected",
        [
            (None, "v1.0.0"),
            ("", "v1.0.0"),
            ("v0.0.0", "v1.0.0"),
            ("0.0.0", "v1.0.0"),
            ("v1.2.3", "v1.3.0"),
            ("1.2.3", "v1.3.0"),
            ("not-a-version", "v1.0.0"),
        ],
    )
    def test_bump_version(self, current, expected):
        assert ss._bump_version(current) == expected

    def test_default_workflow_shape(self):
        wf = ss.default_workflow("gpt-4o-mini", agent_id="a1", version="v2.0.0")

        assert wf["agentId"] == "a1"
        assert wf["version"] == "v2.0.0"
        assert [s["action"] for s in wf["steps"]] == [
            "injectVariables",
            "callModel",
            "formatOutput",
        ]
        assert wf["steps"][1]["model"] == "gpt-4o-mini"

    def test_sync_workflow_model_updates_call_model_step(self):
        wf = {
            "agentId": "a1",
            "version": "v1.0.0",
            "steps": [
                {"action": "injectVariables"},
                {"action": "callModel", "model": "old-model"},
                {"action": "formatOutput"},
            ],
        }

        result = ss._sync_workflow_model(wf, "new-model")

        assert result["steps"][1]["model"] == "new-model"
        # 其余步骤保持原样
        assert result["steps"][0] == {"action": "injectVariables"}
        assert result["agentId"] == "a1"

    def test_sync_workflow_model_on_empty_steps_falls_back_to_default(self):
        result = ss._sync_workflow_model({"steps": []}, "m")

        assert result["steps"][1]["model"] == "m"

    def test_sync_workflow_model_on_none(self):
        result = ss._sync_workflow_model(None, "m")

        assert result["steps"][1]["model"] == "m"
        assert result["agentId"] == ""


class TestNormalization:
    """标签与触发器归一化"""

    def test_with_specialty_tag_prepends(self):
        assert ss._with_specialty_tag(["x"], "数据分析") == ["数据分析", "x"]

    def test_with_specialty_tag_dedupes(self):
        assert ss._with_specialty_tag(["数据分析", "x"], "数据分析") == ["数据分析", "x"]

    def test_with_specialty_tag_ignores_blank(self):
        assert ss._with_specialty_tag(["x"], "  ") == ["x"]
        assert ss._with_specialty_tag(None, "") == []

    def test_normalize_triggers_strips_and_dedupes(self):
        assert ss._normalize_triggers([" 退款 ", "退款", "", "发票"]) == ["退款", "发票"]

    def test_normalize_triggers_truncates_long_value(self):
        result = ss._normalize_triggers(["x" * 100])
        assert len(result[0]) == 64

    def test_normalize_triggers_caps_at_16(self):
        result = ss._normalize_triggers([f"t{i}" for i in range(30)])
        assert len(result) == 16

    def test_normalize_triggers_handles_none(self):
        assert ss._normalize_triggers(None) == []


class TestListing:
    """列表可见性"""

    @pytest.mark.asyncio
    async def test_get_agent_delegates_to_store(self, monkeypatch):
        skill = make_skill()
        monkeypatch.setattr(ss, "get_skill", lambda agent_id: skill)

        assert await ss.get_agent(db=None, agent_id="skill-1") is skill

    @pytest.mark.asyncio
    async def test_list_agents_includes_own_and_open_published(self, monkeypatch):
        mine = make_skill(id="s1", author_id="user-a", visibility="private", status="draft")
        others_public = make_skill(id="s2", author_id="user-b", visibility="public", status="published")
        others_private = make_skill(id="s3", author_id="user-b", visibility="private", status="published")
        monkeypatch.setattr(ss, "list_skills", lambda **kw: [mine, others_public, others_private])

        result = await ss.list_agents(db=None, user_id="user-a")

        assert [s.id for s in result] == ["s1", "s2"]

    @pytest.mark.asyncio
    async def test_list_agents_deduplicates_by_id(self, monkeypatch):
        skill = make_skill(id="s1", author_id="user-a")
        monkeypatch.setattr(ss, "list_skills", lambda **kw: [skill, skill])

        result = await ss.list_agents(db=None, user_id="user-a")

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_list_my_agents_passes_author_filter(self, monkeypatch):
        captured = {}

        def fake_list_skills(**kwargs):
            captured.update(kwargs)
            return [make_skill()]

        monkeypatch.setattr(ss, "list_skills", fake_list_skills)

        await ss.list_my_agents(db=None, user_id="user-a")

        assert captured == {"author_id": "user-a", "include_deprecated": False}


class TestMutation:
    """更新 / 下架 / 删除"""

    @pytest.mark.asyncio
    async def test_update_agent_applies_fields_and_saves(self, monkeypatch):
        skill = make_skill()
        saved = {}

        def fake_save(s):
            saved["skill"] = s
            return s

        monkeypatch.setattr(ss, "save_skill", fake_save)

        result = await ss.update_agent(
            db=None,
            agent=skill,
            payload=AgentUpdate(name="新名字", description="新描述"),
        )

        assert result.name == "新名字"
        assert result.description == "新描述"
        assert saved["skill"] is skill

    @pytest.mark.asyncio
    async def test_update_agent_ignores_unset_fields(self, monkeypatch):
        skill = make_skill(name="原名", system_prompt_enc="原提示词")
        monkeypatch.setattr(ss, "save_skill", lambda s: s)

        await ss.update_agent(db=None, agent=skill, payload=AgentUpdate(description="只改描述"))

        assert skill.name == "原名"
        assert skill.system_prompt_enc == "原提示词"
        assert skill.description == "只改描述"

    @pytest.mark.asyncio
    async def test_update_agent_recomputes_variables(self, monkeypatch):
        skill = make_skill()
        monkeypatch.setattr(ss, "save_skill", lambda s: s)

        await ss.update_agent(
            db=None,
            agent=skill,
            payload=AgentUpdate(user_prompt="请分析 {{city}} 的 {{metric}}"),
        )

        assert [v["name"] for v in skill.variables] == ["city", "metric"]

    @pytest.mark.asyncio
    async def test_deprecate_agent_sets_status(self, monkeypatch):
        skill = make_skill(status="published")
        monkeypatch.setattr(ss, "save_skill", lambda s: s)

        result = await ss.deprecate_agent(db=None, agent=skill)

        assert result.status == "deprecated"

    @pytest.mark.asyncio
    async def test_delete_agent_purges(self, monkeypatch):
        skill = make_skill()
        captured = {}
        monkeypatch.setattr(ss, "delete_skill", lambda skill_id, purge=False: captured.update(id=skill_id, purge=purge))

        await ss.delete_agent(db=None, agent=skill)

        assert captured == {"id": "skill-1", "purge": True}


class TestToolFallback:
    """工具已产出文件时的兜底输出"""

    def test_returns_none_without_trace(self):
        assert ss._fallback_output_from_tools(None, RuntimeError("boom")) is None

    def test_returns_none_when_tool_failed(self):
        assert ss._fallback_output_from_tools({"exitCode": 1, "downloadUrl": "/x"}, RuntimeError()) is None

    def test_returns_none_without_download(self):
        assert ss._fallback_output_from_tools({"exitCode": 0}, RuntimeError()) is None

    def test_builds_markdown_when_tool_succeeded(self):
        text = ss._fallback_output_from_tools(
            {"exitCode": 0, "downloadUrl": "/static/generated/a.xlsx", "downloadName": "结果.xlsx"},
            RuntimeError("模型失败"),
        )

        assert "结果.xlsx" in text
        assert "/static/generated/a.xlsx" in text
        assert "## 下载" in text

    def test_missing_exit_code_is_treated_as_failure(self):
        """exitCode 缺失时按非零处理，即使带了下载链接也不产出兜底文案"""
        assert ss._fallback_output_from_tools({"downloadUrls": ["/a", "/b"]}, RuntimeError()) is None

    def test_supports_multiple_download_urls(self):
        text = ss._fallback_output_from_tools(
            {"exitCode": 0, "downloadUrls": ["/a", "/b"]}, RuntimeError()
        )
        assert "/a" in text and "/b" in text

    def test_invalid_exit_code_is_treated_as_failure(self):
        assert ss._fallback_output_from_tools({"exitCode": "abc", "downloadUrl": "/x"}, RuntimeError()) is None
