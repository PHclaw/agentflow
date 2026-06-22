"""
工作流引擎 - 基于 LangGraph
"""
from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
import json


class WorkflowState(TypedDict):
    """工作流状态"""
    messages: list
    current_node: str
    context: dict
    memory: dict


class WorkflowEngine:
    """工作流引擎"""
    
    def __init__(self, workflow_definition: dict = None, llm_service=None):
        self.definition = workflow_definition or {}
        self.llm_service = llm_service
        self.graph = None
        
        if workflow_definition:
            self.graph = StateGraph(WorkflowState)
            self._build_graph()
    
    def validate(self, workflow: dict = None) -> tuple[bool, list[str]]:
        """验证工作流定义"""
        definition = workflow or self.definition
        errors = []
        
        if not definition:
            return False, ["工作流定义为空"]
        
        nodes = definition.get("nodes", [])
        edges = definition.get("edges", [])
        
        # 检查开始节点
        has_start = any(n.get("type") == "start" for n in nodes)
        if not has_start:
            errors.append("缺少开始节点 (type: start)")
        
        # 检查结束节点
        has_end = any(n.get("type") in ["end", "output"] for n in nodes)
        if not has_end:
            errors.append("缺少结束节点 (type: end 或 output)")
        
        # 检查边的引用是否存在
        node_ids = {n["id"] for n in nodes}
        for edge in edges:
            source = edge.get("from") or edge.get("source")
            target = edge.get("to") or edge.get("target")
            
            if source and source not in node_ids:
                errors.append(f"边引用了不存在的源节点: {source}")
            if target and target not in node_ids:
                errors.append(f"边引用了不存在的目标节点: {target}")
        
        return len(errors) == 0, errors
    
    def get_execution_order(self, workflow: dict = None) -> list[str]:
        """获取执行顺序（拓扑排序）"""
        definition = workflow or self.definition
        
        if not definition:
            return []
        
        nodes = definition.get("nodes", [])
        edges = definition.get("edges", [])
        
        # 构建邻接表
        graph = {n["id"]: [] for n in nodes}
        in_degree = {n["id"]: 0 for n in nodes}
        
        for edge in edges:
            source = edge.get("from") or edge.get("source")
            target = edge.get("to") or edge.get("target")
            
            if source and target:
                graph[source].append(target)
                in_degree[target] += 1
        
        # Kahn 算法
        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        order = []
        
        while queue:
            current = queue.pop(0)
            order.append(current)
            
            for neighbor in graph[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        return order
    
    def _build_graph(self):
        """构建工作流图"""
        # 添加节点
        for node in self.definition.get("nodes", []):
            node_id = node["id"]
            node_type = node["type"]
            config = node.get("config", {})
            
            self.graph.add_node(node_id, self._create_node_handler(node_type, config))
        
        # 添加边
        for edge in self.definition.get("edges", []):
            source = edge["source"]
            target = edge["target"]
            condition = edge.get("condition")
            
            if condition:
                # 条件边
                self.graph.add_conditional_edges(
                    source,
                    self._create_condition_router(condition),
                    {target: target}
                )
            else:
                self.graph.add_edge(source, target)
        
        # 设置入口
        entry = self.definition.get("entry", "start")
        self.graph.set_entry_point(entry)
        
        # 设置结束点
        for node_id in self.definition.get("nodes", []):
            if not self._has_outgoing_edges(node_id):
                self.graph.add_edge(node_id, END)
    
    def _has_outgoing_edges(self, node_id: str) -> bool:
        """检查是否有出边"""
        return any(edge["source"] == node_id for edge in self.definition.get("edges", []))
    
    def _create_node_handler(self, node_type: str, config: dict):
        """创建节点处理器"""
        async def handler(state: WorkflowState) -> dict:
            if node_type == "llm":
                return await self._llm_node(state, config)
            elif node_type == "condition":
                return await self._condition_node(state, config)
            elif node_type == "tool":
                return await self._tool_node(state, config)
            elif node_type == "template":
                return await self._template_node(state, config)
            else:
                return {"current_node": node_type}
        
        return handler
    
    async def _llm_node(self, state: WorkflowState, config: dict) -> dict:
        """LLM 节点 - 真正调用 LLM"""
        messages = state.get("messages", [])
        
        # 如果没有注入 LLM 服务，返回占位响应
        if not self.llm_service:
            last_message = messages[-1] if messages else None
            return {
                "messages": messages + [AIMessage(
                    content=f"[Placeholder] Response to: {last_message.content if last_message else 'start'}"
                )],
                "current_node": "llm_response"
            }
        
        # 转换消息格式
        llm_messages = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                llm_messages.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                llm_messages.append({"role": "assistant", "content": msg.content})
            elif isinstance(msg, SystemMessage):
                llm_messages.append({"role": "system", "content": msg.content})
        
        # 合并节点级配置
        node_config = {**config}
        provider = node_config.pop("provider", None)
        model = node_config.pop("model", None)
        temperature = node_config.pop("temperature", 0.7)
        max_tokens = node_config.pop("max_tokens", 2000)
        
        # 如果节点指定了不同的 provider/model，临时创建 LLM 服务
        if provider or model:
            from ..services.llm import LLMService
            temp_llm = LLMService(
                provider=provider or self.llm_service.provider,
                model=model or self.llm_service.model,
            )
            response_text = await temp_llm.chat(
                messages=llm_messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        else:
            response_text = await self.llm_service.chat(
                messages=llm_messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        
        return {
            "messages": messages + [AIMessage(content=response_text)],
            "current_node": "llm_response"
        }
    
    async def _condition_node(self, state: WorkflowState, config: dict) -> dict:
        """条件节点"""
        condition = config.get("condition", "")
        value = config.get("value", "")
        
        return {
            "context": {**state.get("context", {}), "condition_result": value in condition}
        }
    
    async def _tool_node(self, state: WorkflowState, config: dict) -> dict:
        """工具节点"""
        tool_name = config.get("tool", "search")
        
        return {
            "context": {**state.get("context", {}), "tool_called": tool_name}
        }
    
    async def _template_node(self, state: WorkflowState, config: dict) -> dict:
        """模板节点"""
        template = config.get("template", "")
        
        return {
            "context": {**state.get("context", {}), "template": template}
        }
    
    def _create_condition_router(self, condition: dict):
        """创建条件路由"""
        def router(state: WorkflowState) -> str:
            return condition.get("then", END)
        return router
    
    async def run(self, input_message: str) -> str:
        """执行工作流"""
        app = self.graph.compile()
        
        initial_state = {
            "messages": [HumanMessage(content=input_message)],
            "current_node": "start",
            "context": {},
            "memory": {}
        }
        
        result = await app.ainvoke(initial_state)
        
        # 返回最后一条 AI 消息
        for msg in reversed(result.get("messages", [])):
            if isinstance(msg, AIMessage):
                return msg.content
        
        return "No response"
