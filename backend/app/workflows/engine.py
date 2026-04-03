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
    
    def __init__(self, workflow_definition: dict):
        self.definition = workflow_definition
        self.graph = StateGraph(WorkflowState)
        self._build_graph()
    
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
        """LLM 节点"""
        # 简化实现
        messages = state.get("messages", [])
        last_message = messages[-1] if messages else None
        
        return {
            "messages": messages + [AIMessage(content=f"Response to: {last_message.content if last_message else 'start'}")],
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
