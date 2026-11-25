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
    """构造测试用状态。

    db_session 属于运行时管线，存放在 ``internal`` 而不是 ``context``：
    放进 context 会让 /workflow/execute 的响应序列化失败
    （'AsyncEngine' object is not iterable → 整个接口 500）。
    """
    state = wr.WorkflowState(workflow_id="t", nodes={}, edges=[], context=dict(ctx))
    if db is not None:
        state.internal["db_session"] = db
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


class TestAgentModelInjection:
    """Agent 的模型配置注入工作流节点的行为。

    ``build_workflow_for_agent`` 会把 Agent 上的模型填进没配模型的 LLM 节点。
    这个设计本身合理（Agent 级设置作为节点默认值），但前提是
    ``model_config.model`` 真的是用户设的 —— 它曾经是硬编码的 ``gpt-4o-mini``，
    于是把节点里清干净的模型名又填了回去，用户在本地端点上照样吃 404。
    """

    def _agent(self, model_config):
        """``build_workflow_for_agent`` 只读这四个属性，用轻量对象即可。"""
        from types import SimpleNamespace

        return SimpleNamespace(
            workflow_definition={
                "nodes": [
                    {"id": "l1", "type": "llm", "data": {"prompt": ""}},
                    {"id": "l2", "type": "llm", "data": {"prompt": "", "model": "qwen2.5:7b"}},
                ],
                "edges": [],
            },
            model_config=model_config,
            knowledge_base_id=None,
            settings={},
        )

    def test_empty_agent_model_is_not_injected(self):
        """空模型名 = 跟随生效配置，绝不能注入节点。"""
        from app.services.agent_turn import build_workflow_for_agent

        out = build_workflow_for_agent(self._agent({"model": "", "temperature": 0.7}))

        nodes = {n["id"]: n["data"] for n in out["nodes"]}
        assert "model" not in nodes["l1"], "空模型名被注入了，节点会退回 .env 的 gpt-4o-mini"
        # 节点自己配了就保持不动
        assert nodes["l2"]["model"] == "qwen2.5:7b"

    def test_missing_model_key_is_not_injected(self):
        from app.services.agent_turn import build_workflow_for_agent

        out = build_workflow_for_agent(self._agent({"temperature": 0.7}))

        assert "model" not in {n["id"]: n["data"] for n in out["nodes"]}["l1"]

    def test_explicit_agent_model_is_injected(self):
        """真的设了模型时仍要注入 —— 这是 Agent 级设置的既有语义。"""
        from app.services.agent_turn import build_workflow_for_agent

        out = build_workflow_for_agent(self._agent({"model": "glm4:latest", "temperature": 0.7}))

        nodes = {n["id"]: n["data"] for n in out["nodes"]}
        assert nodes["l1"]["model"] == "glm4:latest"
        # 节点显式配的优先级更高，不被覆盖
        assert nodes["l2"]["model"] == "qwen2.5:7b"


class TestCreateAgentDoesNotPersistStaleModel:
    """新建 Agent 时不能把陈旧默认值写进库。"""

    @pytest.mark.asyncio
    async def test_created_agent_model_is_empty(self, async_client, auth_headers):
        resp = await async_client.post(
            "/api/v1/agents", json={"name": "不带模型配置"}, headers=auth_headers
        )
        assert resp.status_code == 200, resp.text

        assert resp.json()["model"] == "", (
            "新建 Agent 不该默认写入 gpt-4o-mini —— 它会被注入工作流节点，"
            "在非 OpenAI 端点必然 404"
        )

    @pytest.mark.asyncio
    async def test_explicit_model_is_kept(self, async_client, auth_headers):
        resp = await async_client.post(
            "/api/v1/agents",
            json={"name": "指定模型", "llm_config": {"model": "qwen2.5:7b"}},
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["model"] == "qwen2.5:7b"


def _workflow(model: str) -> dict:
    """最小可执行工作流：trigger → llm。

    model 由调用方给，这样「显式指定」与「留空回退」两种情形能共用同一份结构。
    """
    return {
        "nodes": [
            {"id": "t1", "type": "trigger", "data": {"label": "消息触发"}},
            {"id": "l1", "type": "llm", "data": {
                "label": "LLM",
                "model": model,
                "prompt": "",
                "system_prompt": "你是一个简洁的助手。",
                "temperature": 0.7,
            }},
        ],
        "edges": [{"id": "e1", "source": "t1", "target": "l1"}],
    }


class TestWorkflowExecuteApi:
    """``/workflow/execute`` 的 API 层行为。

    这里盯两个真实故障：

    1. 接口曾**恒定 500** —— ``WorkflowState.context`` 里存着 ``db_session``
       （节点执行要用），而接口把 context 原样返回，FastAPI 序列化时炸出
       ``'AsyncEngine' object is not iterable``。整个接口不可用。
    2. 节点里钉死的模型名（模板里的 ``gpt-4``）在非 OpenAI 端点上必然 404。
    """

    @pytest.mark.asyncio
    async def test_response_is_serializable(
        self, async_client, auth_headers, monkeypatch
    ):
        async def fake_chat(self, messages, temperature=0.7, **kw):
            return "ok"

        monkeypatch.setattr(wr.LLMService, "chat", fake_chat)

        resp = await async_client.post(
            "/api/v1/workflow/execute",
            json={
                "workflow_definition": _workflow("test-model"),
                "input_data": {"user_message": "hi"},
            },
            headers=auth_headers,
        )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        # 运行时管线不能出现在对外响应里
        assert "db_session" not in body["context"]
        assert body["node_outputs"]["l1"]["response"] == "ok"

    @pytest.mark.asyncio
    async def test_node_without_model_uses_effective_config(
        self, async_client, auth_headers, monkeypatch
    ):
        """端到端确认：model 留空 → 回退到生效配置的模型。"""
        used = {}

        async def fake_chat(self, messages, temperature=0.7, **kw):
            used["model"] = self.model
            return "ok"

        monkeypatch.setattr(wr.LLMService, "chat", fake_chat)
        monkeypatch.setattr(wr, "_effective_model_name", lambda: "glm4:latest")

        resp = await async_client.post(
            "/api/v1/workflow/execute",
            json={
                "workflow_definition": _workflow(""),
                "input_data": {"user_message": "hi"},
            },
            headers=auth_headers,
        )

        assert resp.status_code == 200, resp.text
        assert used["model"] == "glm4:latest"
        assert resp.json()["node_outputs"]["l1"]["model_used"] == "glm4:latest"

    @pytest.mark.asyncio
    async def test_requires_authentication(self, async_client):
        resp = await async_client.post(
            "/api/v1/workflow/execute",
            json={"workflow_definition": _workflow("m"), "input_data": {}},
        )
        assert resp.status_code == 401