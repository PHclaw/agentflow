"""
测试工作流运行时的节点行为与数据传递

覆盖 app/services/workflow_runtime.py：
- BaseNode 的输入/输出存取
- TriggerNode / LLMNode / ConditionNode / ToolNode / ResponseNode
- WorkflowRuntime 的拓扑排序、分支选择与端到端执行
"""
import pytest

from app.services import workflow_runtime as wr
from app.services.workflow_runtime import (
    BaseNode,
    ConditionNode,
    LLMNode,
    NodeStatus,
    ResponseNode,
    ToolNode,
    TriggerNode,
    WorkflowRuntime,
    WorkflowState,
)


def make_state(context=None, node_outputs=None) -> WorkflowState:
    state = WorkflowState(workflow_id="wf-test")
    if context:
        state.context = dict(context)
    if node_outputs:
        state.node_outputs = dict(node_outputs)
    return state


class TestBaseNode:
    """节点基类的数据存取"""

    def test_set_output_writes_node_cache_and_context(self):
        node = BaseNode("n1", {})
        state = make_state()

        node.set_output(state, "answer", "42")

        assert state.node_outputs["n1"]["answer"] == "42"
        assert state.context["n1.answer"] == "42"

    def test_get_input_prefers_node_output_cache(self):
        node = BaseNode("n1", {})
        state = make_state(
            context={"value": "from-context"},
            node_outputs={"value": {"nested": "from-cache"}},
        )

        assert node.get_input(state, "value") == {"nested": "from-cache"}

    def test_get_input_falls_back_to_context(self):
        node = BaseNode("n1", {})
        state = make_state(context={"value": "from-context"})

        assert node.get_input(state, "value") == "from-context"

    def test_get_input_returns_none_when_missing(self):
        node = BaseNode("n1", {})
        assert node.get_input(state=make_state(), input_key="missing") is None

    @pytest.mark.asyncio
    async def test_base_execute_is_abstract(self):
        with pytest.raises(NotImplementedError):
            await BaseNode("n1", {}).execute(make_state())


class TestTriggerNode:
    """触发器节点"""

    @pytest.mark.asyncio
    async def test_message_trigger(self):
        node = TriggerNode("t1", {"trigger_type": "message"})
        state = make_state(context={"user_message": "你好"})

        result = await node.execute(state)

        assert result.status == NodeStatus.SUCCESS
        assert state.node_outputs["t1"]["message"] == "你好"
        assert state.node_outputs["t1"]["message_length"] == 2

    @pytest.mark.asyncio
    async def test_webhook_trigger(self):
        node = TriggerNode("t1", {"trigger_type": "webhook"})
        state = make_state(context={"webhook_data": {"event": "push"}})

        result = await node.execute(state)

        assert result.status == NodeStatus.SUCCESS
        assert state.node_outputs["t1"]["data"] == {"event": "push"}

    @pytest.mark.asyncio
    async def test_schedule_trigger(self):
        node = TriggerNode("t1", {"trigger_type": "schedule"})
        state = make_state()

        result = await node.execute(state)

        assert result.status == NodeStatus.SUCCESS
        assert "T" in state.node_outputs["t1"]["timestamp"]

    @pytest.mark.asyncio
    async def test_unknown_trigger_type_still_succeeds(self):
        node = TriggerNode("t1", {"trigger_type": "unknown"})
        state = make_state()

        result = await node.execute(state)

        assert result.status == NodeStatus.SUCCESS
        assert state.node_outputs.get("t1") is None


class TestLLMNode:
    """LLM 节点（使用假的 LLMService，不发起真实请求）"""

    @pytest.fixture
    def fake_llm(self, monkeypatch):
        captured = {}

        class FakeLLMService:
            def __init__(self, provider="openai", model=None):
                captured["provider"] = provider
                captured["model"] = model

            async def chat(self, messages, temperature=0.7, max_tokens=2000, **kwargs):
                captured["messages"] = messages
                captured["temperature"] = temperature
                return "fake-reply"

        monkeypatch.setattr(wr, "LLMService", FakeLLMService)
        return captured

    @pytest.mark.asyncio
    async def test_llm_node_success(self, fake_llm):
        node = LLMNode("l1", {"model": "gpt-4o-mini", "temperature": 0.2})
        state = make_state(context={"user_message": "问题"})

        result = await node.execute(state)

        assert result.status == NodeStatus.SUCCESS
        assert state.node_outputs["l1"]["response"] == "fake-reply"
        assert state.node_outputs["l1"]["model_used"] == "gpt-4o-mini"
        assert fake_llm["messages"][-1]["content"] == "问题"
        assert fake_llm["temperature"] == 0.2

    @pytest.mark.asyncio
    async def test_llm_node_renders_prompt_template(self, fake_llm):
        node = LLMNode("l1", {"prompt": "请回答：{{user_message}}"})
        state = make_state(context={"user_message": "什么是 RAG"})

        await node.execute(state)

        assert fake_llm["messages"][-1]["content"] == "请回答：什么是 RAG"

    @pytest.mark.asyncio
    async def test_llm_node_renders_node_reference(self, fake_llm):
        node = LLMNode("l1", {"prompt": "总结：{{t1.message}}"})
        state = make_state(node_outputs={"t1": {"message": "原文"}})

        await node.execute(state)

        assert fake_llm["messages"][-1]["content"] == "总结：原文"

    @pytest.mark.asyncio
    async def test_llm_node_includes_system_prompt(self, fake_llm):
        node = LLMNode("l1", {"system_prompt": "你是助手"})
        state = make_state(context={"user_message": "hi"})

        await node.execute(state)

        assert fake_llm["messages"][0] == {"role": "system", "content": "你是助手"}

    @pytest.mark.asyncio
    async def test_llm_node_failure_is_captured(self, monkeypatch):
        class BoomLLMService:
            def __init__(self, provider="openai", model=None):
                pass

            async def chat(self, *args, **kwargs):
                raise RuntimeError("上游不可用")

        monkeypatch.setattr(wr, "LLMService", BoomLLMService)

        node = LLMNode("l1", {})
        result = await node.execute(make_state(context={"user_message": "hi"}))

        assert result.status == NodeStatus.FAILED
        assert "上游不可用" in result.error


class TestConditionNode:
    """条件节点"""

    @pytest.mark.parametrize(
        "condition_type,value,expected,expected_result",
        [
            ("equals", "Yes", "yes", True),
            ("equals", "Yes", "no", False),
            ("not_equals", "Yes", "no", True),
            ("contains", "hello world", "lo w", True),
            ("not_contains", "hello world", "zzz", True),
            ("starts_with", "hello", "he", True),
            ("ends_with", "hello", "lo", True),
            ("greater_than", 10, 5, True),
            ("greater_than", "abc", 5, False),
            ("less_than", 3, 5, True),
            ("less_than", "abc", 5, False),
            ("is_empty", "", None, True),
            ("is_not_empty", "x", None, True),
            ("is_not_empty", "  ", None, False),
            ("regex", "abc123", r"\d+", True),
            ("in_list", "b", "a,b,c", True),
            ("in_list", "z", "a,b,c", False),
            ("unknown_type", "anything", None, True),
        ],
    )
    def test_evaluate_condition(self, condition_type, value, expected, expected_result):
        node = ConditionNode("c1", {})
        assert (
            node._evaluate_condition(value, condition_type, expected, make_state())
            is expected_result
        )

    @pytest.mark.asyncio
    async def test_execute_sets_outputs(self):
        node = ConditionNode("c1", {
            "condition_type": "contains",
            "condition_value": "退款",
            "true_label": "走退款流程",
            "false_label": "转人工",
        })
        state = make_state(context={"value": "我要退款"})

        result = await node.execute(state)

        assert result.status == NodeStatus.SUCCESS
        outputs = state.node_outputs["c1"]
        assert outputs["condition_met"] is True
        assert outputs["true_branch"] == "走退款流程"
        assert outputs["false_branch"] == "转人工"


class TestToolNode:
    """工具节点"""

    @pytest.mark.asyncio
    async def test_calculator(self):
        node = ToolNode("tool1", {"tool_name": "calculator", "params": {"expression": "2+3*4"}})
        state = make_state()

        result = await node.execute(state)

        assert result.status == NodeStatus.SUCCESS
        assert state.node_outputs["tool1"]["result"] == "14"

    @pytest.mark.asyncio
    async def test_calculator_rejects_unsafe_expression(self):
        node = ToolNode("tool1", {"tool_name": "calculator", "params": {"expression": "__import__('os')"}})
        state = make_state()

        await node.execute(state)

        assert state.node_outputs["tool1"]["result"] == "表达式包含非法字符"

    @pytest.mark.asyncio
    async def test_text_process_operations(self):
        cases = {
            "uppercase": ("abc", "ABC"),
            "lowercase": ("ABC", "abc"),
            "trim": ("  x  ", "x"),
            "length": ("abcd", "4"),
            "word_count": ("a b c", "3"),
        }
        for operation, (raw, expected) in cases.items():
            node = ToolNode("t", {"tool_name": "text_process", "params": {"operation": operation}})
            state = make_state()
            state.context["input"] = raw
            await node.execute(state)
            assert state.node_outputs["t"]["result"] == expected, operation

    @pytest.mark.asyncio
    async def test_formatter(self):
        node = ToolNode("t", {"tool_name": "formatter", "params": {"template": "结果：{input}"}})
        state = make_state()
        state.context["input"] = "42"

        await node.execute(state)

        assert state.node_outputs["t"]["result"] == "结果：42"

    @pytest.mark.asyncio
    async def test_datetime_uses_format(self):
        node = ToolNode("t", {"tool_name": "date_time", "params": {"format": "%Y"}})
        state = make_state()

        await node.execute(state)

        assert len(state.node_outputs["t"]["result"]) == 4

    @pytest.mark.asyncio
    async def test_search_and_weather_return_structured_mock(self):
        search_node = ToolNode("s", {"tool_name": "search", "params": {"query": "AgentFlow"}})
        state = make_state()
        await search_node.execute(state)
        assert "搜索 API 未配置" in state.node_outputs["s"]["result"]

        weather_node = ToolNode("w", {"tool_name": "weather", "params": {"city": "上海"}})
        state2 = make_state()
        await weather_node.execute(state2)
        assert "天气 API 未配置" in state2.node_outputs["w"]["result"]

    @pytest.mark.asyncio
    async def test_unknown_tool_fails(self):
        node = ToolNode("t", {"tool_name": "not_exist"})
        state = make_state()

        result = await node.execute(state)

        assert result.status == NodeStatus.FAILED
        assert "未知工具" in result.error
        assert state.node_outputs["t"]["success"] is False

    def test_resolve_variable(self):
        node = ToolNode("t", {})
        state = make_state(
            context={"city": "北京"},
            node_outputs={"n1": {"value": 7}},
        )

        assert node._resolve_variable("$city", state) == "北京"
        assert node._resolve_variable("$n1.value", state) == 7
        assert node._resolve_variable("$missing", state) == "$missing"
        assert node._resolve_variable("plain", state) == "plain"

    @pytest.mark.asyncio
    async def test_params_are_resolved(self):
        node = ToolNode("t", {
            "tool_name": "formatter",
            "params": {"template": "城市={input}", "unused": "$city"},
        })
        state = make_state()
        state.context["input"] = "上海"
        state.context["city"] = "上海"

        await node.execute(state)

        assert state.node_outputs["t"]["result"] == "城市=上海"


class TestResponseNode:
    """响应节点"""

    @pytest.mark.asyncio
    async def test_plain_response(self):
        node = ResponseNode("r1", {"response": "你好"})
        state = make_state()

        result = await node.execute(state)

        assert result.status == NodeStatus.SUCCESS
        assert state.node_outputs["r1"]["final_response"] == "你好"

    @pytest.mark.asyncio
    async def test_template_response(self):
        node = ResponseNode("r1", {"template": "回答：{{l1.response}}"})
        state = make_state(node_outputs={"l1": {"response": "内容"}})

        await node.execute(state)

        assert state.node_outputs["r1"]["final_response"] == "回答：内容"

    @pytest.mark.asyncio
    async def test_missing_variable_keeps_placeholder(self):
        node = ResponseNode("r1", {"template": "{{unknown}}"})
        state = make_state()

        await node.execute(state)

        assert state.node_outputs["r1"]["final_response"] == "{{unknown}}"


class TestWorkflowRuntime:
    """工作流运行时的编排能力"""

    def test_create_node_maps_types(self):
        runtime = WorkflowRuntime()
        assert isinstance(runtime.create_node("trigger", "t", {}), TriggerNode)
        assert isinstance(runtime.create_node("llm", "l", {}), LLMNode)
        assert isinstance(runtime.create_node("condition", "c", {}), ConditionNode)
        assert isinstance(runtime.create_node("tool", "tl", {}), ToolNode)
        assert isinstance(runtime.create_node("response", "r", {}), ResponseNode)

    def test_create_node_unknown_type_falls_back_to_base(self):
        runtime = WorkflowRuntime()
        node = runtime.create_node("mystery", "x", {})
        assert type(node) is BaseNode

    def test_execution_order_linear(self):
        runtime = WorkflowRuntime()
        nodes = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
        edges = [{"source": "a", "target": "b"}, {"source": "b", "target": "c"}]

        assert runtime.get_execution_order(nodes, edges) == ["a", "b", "c"]

    def test_execution_order_ignores_dangling_edge_target(self):
        runtime = WorkflowRuntime()
        nodes = [{"id": "a"}]
        edges = [{"source": "a", "target": "ghost"}]

        assert runtime.get_execution_order(nodes, edges) == ["a"]

    def test_execution_order_cycle_does_not_hang(self):
        runtime = WorkflowRuntime()
        nodes = [{"id": "a"}, {"id": "b"}]
        edges = [{"source": "a", "target": "b"}, {"source": "b", "target": "a"}]

        assert runtime.get_execution_order(nodes, edges) == []

    def test_get_next_nodes_plain_edge(self):
        runtime = WorkflowRuntime()
        edges = [{"source": "a", "target": "b"}]
        assert runtime.get_next_nodes("a", edges) == ["b"]

    def test_get_next_nodes_condition_branches(self):
        runtime = WorkflowRuntime()
        edges = [
            {"source": "c", "target": "yes_node", "sourceHandle": "yes"},
            {"source": "c", "target": "no_node", "sourceHandle": "no"},
        ]

        assert runtime.get_next_nodes("c", edges, True) == ["yes_node"]
        assert runtime.get_next_nodes("c", edges, False) == ["no_node"]
        # condition_result 为 None 时按 falsy 处理，走 no 分支
        assert runtime.get_next_nodes("c", edges, None) == ["no_node"]

    @pytest.mark.asyncio
    async def test_execute_workflow_end_to_end(self):
        """trigger -> response 全链路（不触碰 LLM）"""
        runtime = WorkflowRuntime()
        workflow_def = {
            "nodes": [
                {"id": "t1", "type": "trigger", "data": {"trigger_type": "message"}},
                {"id": "r1", "type": "response", "data": {"template": "收到：{{t1.message}}"}},
            ],
            "edges": [{"source": "t1", "target": "r1"}],
        }

        state = await runtime.execute_workflow(
            workflow_def, {"user_message": "你好"}, db_session=None
        )

        assert state.node_outputs["r1"]["final_response"] == "收到：你好"
        assert [r.node_id for r in state.execution_history] == ["t1", "r1"]
        assert all(r.status == NodeStatus.SUCCESS for r in state.execution_history)

    @pytest.mark.asyncio
    async def test_execute_workflow_continues_when_non_key_node_fails(self):
        runtime = WorkflowRuntime()
        workflow_def = {
            "nodes": [
                {"id": "t1", "type": "trigger", "data": {"trigger_type": "message"}},
                {"id": "tl", "type": "tool", "data": {"tool_name": "not_exist"}},
                {"id": "r1", "type": "response", "data": {"response": "不会执行"}},
            ],
            "edges": [
                {"source": "t1", "target": "tl"},
                {"source": "tl", "target": "r1"},
            ],
        }

        state = await runtime.execute_workflow(
            workflow_def, {"user_message": "hi"}, db_session=None
        )

        # tool 节点失败但非关键节点，流程继续；response 仍会执行
        assert any(r.node_id == "tl" and r.status == NodeStatus.FAILED for r in state.execution_history)
        assert state.node_outputs["r1"]["final_response"] == "不会执行"

    @pytest.mark.asyncio
    async def test_execute_node_single(self):
        runtime = WorkflowRuntime()
        workflow_def = {
            "nodes": [{"id": "t1", "type": "trigger", "data": {"trigger_type": "message"}}],
            "edges": [],
        }

        result = await runtime.execute_node(
            workflow_def, "t1", {"user_message": "abc"}, db_session=None
        )

        assert result.status == NodeStatus.SUCCESS
        assert result.node_id == "t1"

    @pytest.mark.asyncio
    async def test_execute_workflow_breaks_when_llm_fails(self, monkeypatch):
        """LLM 是关键节点，失败后应终止后续节点"""

        class BoomLLMService:
            def __init__(self, provider="openai", model=None):
                pass

            async def chat(self, *args, **kwargs):
                raise RuntimeError("模型不可用")

        monkeypatch.setattr(wr, "LLMService", BoomLLMService)

        runtime = WorkflowRuntime()
        workflow_def = {
            "nodes": [
                {"id": "t1", "type": "trigger", "data": {"trigger_type": "message"}},
                {"id": "l1", "type": "llm", "data": {"model": "gpt-4o-mini"}},
                {"id": "r1", "type": "response", "data": {"response": "不应执行"}},
            ],
            "edges": [
                {"source": "t1", "target": "l1"},
                {"source": "l1", "target": "r1"},
            ],
        }

        state = await runtime.execute_workflow(
            workflow_def, {"user_message": "hi"}, db_session=None
        )

        executed = [r.node_id for r in state.execution_history]
        assert executed == ["t1", "l1"]
        assert "r1" not in state.node_outputs

    @pytest.mark.asyncio
    async def test_execute_node_missing_id_raises(self):
        runtime = WorkflowRuntime()
        workflow_def = {"nodes": [], "edges": []}

        with pytest.raises(NotImplementedError):
            await runtime.execute_node(workflow_def, "ghost", {}, db_session=None)
