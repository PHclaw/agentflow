"""
测试 SkillNode —— 技能作为工作流节点被编排执行

此前技能只能由 AI Agent 引擎在对话时旁路调用，无法参与编排。
这些用例不真实执行技能，而是替换掉 get_skill / call_agent。
"""
import pytest

from app.services import workflow_runtime as wr
from app.services.workflow_runtime import (
    NodeStatus,
    SkillNode,
    WorkflowRuntime,
)


def make_state(**ctx):
    state = wr.WorkflowState(workflow_id="t", nodes={}, edges=[], context=dict(ctx))
    state.context.setdefault("db_session", object())
    return state


class TestSkillNodeRegistration:
    def test_runtime_knows_skill_node(self):
        assert WorkflowRuntime().node_types["skill"] is SkillNode


class TestSkillNodeConfig:
    @pytest.mark.asyncio
    async def test_missing_skill_fails(self):
        result = await SkillNode("s1", {}).execute(make_state())

        assert result.status == NodeStatus.FAILED
        assert "未配置技能" in result.error

    @pytest.mark.asyncio
    async def test_unknown_skill_fails(self, monkeypatch):
        monkeypatch.setattr("app.services.skill.store.get_skill", lambda sid: None)

        result = await SkillNode("s1", {"skill": "not-exist"}).execute(make_state())

        assert result.status == NodeStatus.FAILED
        assert "技能不存在" in result.error

    @pytest.mark.asyncio
    async def test_missing_db_session_fails(self):
        state = wr.WorkflowState(workflow_id="t", nodes={}, edges=[], context={})

        result = await SkillNode("s1", {"skill": "excel"}).execute(state)

        assert result.status == NodeStatus.FAILED
        assert "数据库会话不可用" in result.error


class TestSkillNodeExecution:
    @pytest.fixture
    def skill_env(self, monkeypatch):
        """替换技能加载与调用，记录传入参数"""
        captured = {}

        class FakeSkill:
            name = "Excel 表格助手"

        class FakeResponse:
            output = "已生成表格"
            latency_ms = 123
            tool_trace = {
                "downloadUrl": "/static/a.xlsx",
                "downloadUrls": ["/static/a.xlsx", "/static/b.png"],
            }

        async def fake_call(db, skill, caller_id, variables, conversation_id=None):
            captured.update(
                db=db,
                skill=skill,
                caller_id=caller_id,
                variables=variables,
                conversation_id=conversation_id,
            )
            return FakeResponse()

        monkeypatch.setattr("app.services.skill.store.get_skill", lambda sid: FakeSkill())
        monkeypatch.setattr("app.services.skill_service.call_agent", fake_call)
        return captured

    @pytest.mark.asyncio
    async def test_successful_call_sets_outputs(self, skill_env):
        state = make_state(user_message="帮我做个表", caller_id="user-1")

        result = await SkillNode("s1", {"skill": "excel"}).execute(state)

        assert result.status == NodeStatus.SUCCESS
        outputs = state.node_outputs["s1"]
        assert outputs["result"] == "已生成表格"
        assert outputs["output"] == "已生成表格"
        assert outputs["skill_name"] == "Excel 表格助手"
        assert outputs["latency_ms"] == 123
        # 调用者身份要传下去，技能侧据此鉴权
        assert skill_env["caller_id"] == "user-1"
        assert skill_env["variables"]["input"] == "帮我做个表"

    @pytest.mark.asyncio
    async def test_download_urls_are_deduped(self, skill_env):
        state = make_state(user_message="做个表")

        await SkillNode("s1", {"skill": "excel"}).execute(state)

        urls = state.node_outputs["s1"]["download_urls"]
        assert urls == ["/static/a.xlsx", "/static/b.png"]

    @pytest.mark.asyncio
    async def test_input_priority_config_over_upstream_over_message(self, skill_env):
        # 1) 节点配置的 input 优先
        state = make_state(user_message="用户消息")
        state.node_outputs["l1"] = {"response": "上游回复"}
        state.edges = [{"source": "l1", "target": "s1"}]
        await SkillNode("s1", {"skill": "excel", "input": "配置里的输入"}).execute(state)
        assert skill_env["variables"]["input"] == "配置里的输入"

        # 2) 没配 input 时取上游节点输出
        state2 = make_state(user_message="用户消息")
        state2.node_outputs["l1"] = {"response": "上游回复"}
        state2.edges = [{"source": "l1", "target": "s1"}]
        await SkillNode("s1", {"skill": "excel"}).execute(state2)
        assert skill_env["variables"]["input"] == "上游回复"

        # 3) 都没有时回落到本轮用户消息
        state3 = make_state(user_message="用户消息")
        await SkillNode("s1", {"skill": "excel"}).execute(state3)
        assert skill_env["variables"]["input"] == "用户消息"

    @pytest.mark.asyncio
    async def test_extra_variables_support_dollar_reference(self, skill_env):
        state = make_state(user_message="原始消息")

        await SkillNode(
            "s1",
            {"skill": "excel", "variables": {"topic": "$user_message", "fixed": "常量"}},
        ).execute(state)

        assert skill_env["variables"]["topic"] == "原始消息"
        assert skill_env["variables"]["fixed"] == "常量"

    @pytest.mark.asyncio
    async def test_skill_exception_marks_node_failed(self, skill_env, monkeypatch):
        async def boom(*args, **kwargs):
            raise RuntimeError("技能执行炸了")

        monkeypatch.setattr("app.services.skill_service.call_agent", boom)

        result = await SkillNode("s1", {"skill": "excel"}).execute(make_state(user_message="x"))

        assert result.status == NodeStatus.FAILED
        assert "技能执行炸了" in result.error


class TestSkillNodeInWorkflow:
    @pytest.mark.asyncio
    async def test_skill_node_runs_in_a_workflow(self, monkeypatch):
        """技能节点应能串进 trigger -> skill -> response 的编排"""

        class FakeSkill:
            name = "Excel 表格助手"

        class FakeResponse:
            output = "技能产出"
            latency_ms = 1
            tool_trace = None

        async def fake_call(db, skill, caller_id, variables, conversation_id=None):
            return FakeResponse()

        monkeypatch.setattr("app.services.skill.store.get_skill", lambda sid: FakeSkill())
        monkeypatch.setattr("app.services.skill_service.call_agent", fake_call)

        workflow_def = {
            "nodes": [
                {"id": "t1", "type": "trigger", "data": {"trigger_type": "message"}},
                {"id": "s1", "type": "skill", "data": {"skill": "excel"}},
                {"id": "r1", "type": "response", "data": {"template": "结果：{{s1.output}}"}},
            ],
            "edges": [
                {"source": "t1", "target": "s1"},
                {"source": "s1", "target": "r1"},
            ],
        }

        state = await WorkflowRuntime().execute_workflow(
            workflow_def=workflow_def,
            input_data={"user_message": "做个表", "caller_id": "u1"},
            db_session=object(),
        )

        assert state.node_outputs["s1"]["output"] == "技能产出"
        # 响应节点应能把技能产出拼进最终回复
        assert wr.extract_final_response(state) == "结果：技能产出"