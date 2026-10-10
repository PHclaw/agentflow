"""
测试 AgentNode —— 在工作流里调用 Agent，并为其指定技能

Agent 是行为的单元，技能是它的能力；这里与对话页「选 Agent + 勾技能」
保持同一套语义，走的都是 AI Agent 引擎。
"""
import pytest

from app.services import workflow_runtime as wr
from app.services.workflow_runtime import (
    AgentNode,
    NodeStatus,
    WorkflowRuntime,
)


class FakeAgent:
    def __init__(self, agent_id="agent-1", name="测试 Agent"):
        self.id = agent_id
        self.name = name
        self.description = "用于测试"
        self.model_config = {"model": "gpt-4o-mini"}
        self.settings = {}


class FakeDB:
    """只需支持 db.get(Agent, id)"""

    def __init__(self, agents=None):
        self._agents = agents or {}

    async def get(self, model, pk):
        return self._agents.get(pk)


def make_state(db=None, **ctx):
    state = wr.WorkflowState(workflow_id="t", nodes={}, edges=[], context=dict(ctx))
    if db is not None:
        state.context["db_session"] = db
    return state


@pytest.fixture
def pi_env(monkeypatch):
    """开启 AI Agent 引擎，并替换掉真实的子进程调用"""
    monkeypatch.setattr("app.core.config.settings.PIAGENT_ENABLED", True, raising=False)

    captured = {}

    async def fake_run(message, agent_id, agent, session_id=None, skills=None, timeout=None):
        captured.update(
            message=message,
            agent_id=agent_id,
            agent=agent,
            session_id=session_id,
            skills=skills,
            timeout=timeout,
        )
        return {
            "success": True,
            "error": None,
            "content": "Agent 的回答",
            "files": [
                {"name": "out.xlsx", "path": "out.xlsx", "size": 1024, "url": "/api/v1/pi/x/files/out.xlsx"}
            ],
        }

    monkeypatch.setattr("app.services.pi_agent.pi_agent_runner.run", fake_run)
    return captured


@pytest.fixture
def disabled_pi(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.PIAGENT_ENABLED", False, raising=False)


class TestAgentNodeRegistration:
    def test_runtime_knows_agent_node(self):
        assert WorkflowRuntime().node_types["agent"] is AgentNode


class TestAgentNodeGuards:
    @pytest.mark.asyncio
    async def test_disabled_engine_fails_with_hint(self, disabled_pi):
        result = await AgentNode("a1", {}).execute(make_state(FakeDB(), agent_id="agent-1"))

        assert result.status == NodeStatus.FAILED
        assert "PIAGENT_ENABLED" in result.error

    @pytest.mark.asyncio
    async def test_missing_db_session_fails(self, pi_env):
        result = await AgentNode("a1", {"agent_id": "agent-1"}).execute(make_state())

        assert result.status == NodeStatus.FAILED
        assert "数据库会话不可用" in result.error

    @pytest.mark.asyncio
    async def test_no_agent_target_fails(self, pi_env):
        result = await AgentNode("a1", {}).execute(make_state(FakeDB()))

        assert result.status == NodeStatus.FAILED
        assert "未指定 Agent" in result.error

    @pytest.mark.asyncio
    async def test_agent_not_found_fails(self, pi_env):
        result = await AgentNode("a1", {"agent_id": "ghost"}).execute(
            make_state(FakeDB(), agent_id="agent-1")
        )

        assert result.status == NodeStatus.FAILED
        assert "Agent 不存在" in result.error


class TestAgentNodeExecution:
    @pytest.mark.asyncio
    async def test_calls_agent_and_sets_outputs(self, pi_env):
        db = FakeDB({"agent-1": FakeAgent(name="客服助手")})
        state = make_state(db, agent_id="agent-1")

        result = await AgentNode("a1", {}).execute(state)

        assert result.status == NodeStatus.SUCCESS
        outputs = state.node_outputs["a1"]
        assert outputs["result"] == "Agent 的回答"
        assert outputs["output"] == "Agent 的回答"
        assert outputs["agent_id"] == "agent-1"
        assert outputs["agent_name"] == "客服助手"
        # 工作区产物要透出，供后续响应节点展示
        assert outputs["files"][0]["name"] == "out.xlsx"
        assert pi_env["agent_id"] == "agent-1"

    @pytest.mark.asyncio
    async def test_node_config_overrides_agent(self, pi_env):
        db = FakeDB({"agent-1": FakeAgent(), "agent-2": FakeAgent("agent-2", "销售助手")})

        await AgentNode("a1", {"agent_id": "agent-2"}).execute(make_state(db, agent_id="agent-1"))

        assert pi_env["agent_id"] == "agent-2"

    @pytest.mark.asyncio
    async def test_skills_passed_through(self, pi_env):
        db = FakeDB({"agent-1": FakeAgent()})

        await AgentNode("a1", {"agent_id": "agent-1", "skills": ["excel", "pdf"]}).execute(
            make_state(db, agent_id="agent-1")
        )

        assert pi_env["skills"] == ["excel", "pdf"]

    @pytest.mark.asyncio
    async def test_skills_accept_comma_string(self, pi_env):
        db = FakeDB({"agent-1": FakeAgent()})

        await AgentNode("a1", {"agent_id": "agent-1", "skills": "excel, pdf"}).execute(
            make_state(db, agent_id="agent-1")
        )

        assert pi_env["skills"] == ["excel", "pdf"]

    @pytest.mark.asyncio
    async def test_no_skills_means_none(self, pi_env):
        db = FakeDB({"agent-1": FakeAgent()})

        await AgentNode("a1", {"agent_id": "agent-1"}).execute(make_state(db, agent_id="agent-1"))

        assert pi_env["skills"] is None

    @pytest.mark.asyncio
    async def test_input_priority(self, pi_env):
        db = FakeDB({"agent-1": FakeAgent()})

        # 1) 节点配置优先
        state = make_state(db, agent_id="agent-1", user_message="用户消息")
        state.node_outputs["l1"] = {"response": "上游回复"}
        state.edges = [{"source": "l1", "target": "a1"}]
        await AgentNode("a1", {"input": "配置输入"}).execute(state)
        assert pi_env["message"] == "配置输入"

        # 2) 其次取上游输出
        state2 = make_state(db, agent_id="agent-1", user_message="用户消息")
        state2.node_outputs["l1"] = {"response": "上游回复"}
        state2.edges = [{"source": "l1", "target": "a1"}]
        await AgentNode("a1", {}).execute(state2)
        assert pi_env["message"] == "上游回复"

        # 3) 最后回落到用户消息
        await AgentNode("a1", {}).execute(make_state(db, agent_id="agent-1", user_message="用户消息"))
        assert pi_env["message"] == "用户消息"

    @pytest.mark.asyncio
    async def test_runner_failure_marks_node_failed(self, pi_env, monkeypatch):
        async def boom(*args, **kwargs):
            return {"success": False, "error": "模型密钥无效", "content": "", "files": []}

        monkeypatch.setattr("app.services.pi_agent.pi_agent_runner.run", boom)

        result = await AgentNode("a1", {"agent_id": "agent-1"}).execute(
            make_state(FakeDB({"agent-1": FakeAgent()}), agent_id="agent-1")
        )

        assert result.status == NodeStatus.FAILED
        assert "模型密钥无效" in result.error

    @pytest.mark.asyncio
    async def test_timeout_is_coerced_to_int(self, pi_env):
        db = FakeDB({"agent-1": FakeAgent()})

        await AgentNode("a1", {"agent_id": "agent-1", "timeout": "300"}).execute(
            make_state(db, agent_id="agent-1")
        )
        assert pi_env["timeout"] == 300

        # 非法值不应让节点崩掉，按未设置处理
        await AgentNode("a1", {"agent_id": "agent-1", "timeout": "abc"}).execute(
            make_state(db, agent_id="agent-1")
        )
        assert pi_env["timeout"] is None


class TestAgentNodeInWorkflow:
    @pytest.mark.asyncio
    async def test_agent_node_in_a_workflow(self, pi_env):
        """trigger -> agent(带技能) -> response 串起来"""
        db = FakeDB({"agent-1": FakeAgent(name="表格助手")})

        workflow_def = {
            "nodes": [
                {"id": "t1", "type": "trigger", "data": {"trigger_type": "message"}},
                {
                    "id": "a1",
                    "type": "agent",
                    "data": {"agent_id": "agent-1", "skills": ["excel"]},
                },
                {"id": "r1", "type": "response", "data": {"template": "结果：{{a1.output}}"}},
            ],
            "edges": [
                {"source": "t1", "target": "a1"},
                {"source": "a1", "target": "r1"},
            ],
        }

        state = await WorkflowRuntime().execute_workflow(
            workflow_def=workflow_def,
            input_data={"user_message": "做个表", "agent_id": "agent-1"},
            db_session=db,
        )

        assert state.node_outputs["a1"]["output"] == "Agent 的回答"
        assert state.node_outputs["a1"]["skills"] == ["excel"]
        assert wr.extract_final_response(state) == "结果：Agent 的回答"