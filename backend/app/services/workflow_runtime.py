"""
工作流运行时 - 节点数据传递与执行
基于 LangGraph 实现工作流节点的数据流动
"""
from typing import Dict, List, Any, Optional, Callable, AsyncIterator
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import json
import uuid
from datetime import datetime

from .llm import LLMService
from .knowledge import KnowledgeService
from ..core.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession


class NodeStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class NodeInput:
    """节点输入"""
    key: str
    value: Any
    source_node_id: Optional[str] = None


@dataclass
class NodeOutput:
    """节点输出"""
    key: str
    value: Any
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NodeResult:
    """节点执行结果"""
    node_id: str
    status: NodeStatus
    outputs: List[NodeOutput] = field(default_factory=list)
    error: Optional[str] = None
    execution_time: float = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


@dataclass
class WorkflowState:
    """工作流状态"""
    workflow_id: str
    nodes: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    edges: List[Dict[str, str]] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)  # 全局上下文
    node_outputs: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # 节点输出缓存
    execution_history: List[NodeResult] = field(default_factory=list)
    current_node: Optional[str] = None


class BaseNode:
    """节点基类"""
    
    def __init__(self, node_id: str, config: Dict[str, Any]):
        self.node_id = node_id
        self.config = config
        self.input_schema = {}
        self.output_schema = {}
    
    def get_input(self, state: WorkflowState, input_key: str) -> Any:
        """从状态中获取输入"""
        # 优先从节点输出缓存中获取
        if input_key in state.node_outputs:
            return state.node_outputs[input_key]
        
        # 从全局上下文获取
        if input_key in state.context:
            return state.context[input_key]
        
        return None
    
    def set_output(self, state: WorkflowState, key: str, value: Any, metadata: Dict = None):
        """设置输出到状态"""
        if self.node_id not in state.node_outputs:
            state.node_outputs[self.node_id] = {}
        
        state.node_outputs[self.node_id][key] = value
        
        # 同时存入全局上下文，供后续节点使用
        state.context[f"{self.node_id}.{key}"] = value
    
    async def execute(self, state: WorkflowState) -> NodeResult:
        """执行节点 - 子类实现"""
        raise NotImplementedError


class TriggerNode(BaseNode):
    """触发器节点 - 工作流入口"""
    
    async def execute(self, state: WorkflowState) -> NodeResult:
        result = NodeResult(node_id=self.node_id, status=NodeStatus.RUNNING, start_time=datetime.now())
        
        try:
            # 获取触发配置
            trigger_type = self.config.get("trigger_type", "message")
            
            if trigger_type == "message":
                # 从上下文获取用户消息
                user_message = state.context.get("user_message", "")
                self.set_output(state, "message", user_message)
                self.set_output(state, "message_length", len(user_message))
                
            elif trigger_type == "webhook":
                webhook_data = state.context.get("webhook_data", {})
                self.set_output(state, "data", webhook_data)
                
            elif trigger_type == "schedule":
                self.set_output(state, "timestamp", datetime.now().isoformat())
            
            result.status = NodeStatus.SUCCESS
            return result
            
        except Exception as e:
            result.status = NodeStatus.FAILED
            result.error = str(e)
            return result
        finally:
            result.end_time = datetime.now()


class LLMNode(BaseNode):
    """LLM 节点 - AI 对话处理"""
    
    async def execute(self, state: WorkflowState) -> NodeResult:
        result = NodeResult(node_id=self.node_id, status=NodeStatus.RUNNING, start_time=datetime.now())
        
        try:
            # 获取输入
            input_text = self.get_input(state, "message") or self.config.get("input_field", "")
            if not input_text:
                input_text = state.context.get("user_message", "")
            
            # 获取配置
            model = self.config.get("model", "gpt-4o-mini")
            temperature = float(self.config.get("temperature", 0.7))
            prompt_template = self.config.get("prompt", "")
            system_prompt = self.config.get("system_prompt", "")
            
            # 构建消息
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            
            # 处理 prompt 模板 - 替换变量
            if prompt_template:
                processed_prompt = self._process_template(prompt_template, state)
                messages.append({"role": "user", "content": processed_prompt})
            else:
                messages.append({"role": "user", "content": input_text})
            
            # 调用 LLM
            llm = LLMService()
            response = await llm.chat(messages, temperature=temperature, model=model)
            
            # 设置输出
            self.set_output(state, "response", response)
            self.set_output(state, "response_length", len(response))
            self.set_output(state, "model_used", model)
            self.set_output(state, "tokens_used", len(input_text) + len(response))  # 粗略估算
            
            result.status = NodeStatus.SUCCESS
            
        except Exception as e:
            result.status = NodeStatus.FAILED
            result.error = str(e)
            
        finally:
            result.end_time = datetime.now()
        
        return result
    
    def _process_template(self, template: str, state: WorkflowState) -> str:
        """处理模板变量"""
        import re
        # 替换 {{variable}} 格式的变量
        def replace_var(match):
            var_path = match.group(1)
            # 支持 node_id.key 格式
            if "." in var_path:
                parts = var_path.split(".")
                node_id = parts[0]
                key = parts[1]
                return str(state.node_outputs.get(node_id, {}).get(key, match.group(0)))
            # 从全局上下文获取
            return str(state.context.get(var_path, match.group(0)))
        
        return re.sub(r'\{\{([^}]+)\}\}', replace_var, template)


class KnowledgeNode(BaseNode):
    """知识库节点 - RAG 检索"""
    
    async def execute(self, state: WorkflowState) -> NodeResult:
        result = NodeResult(node_id=self.node_id, status=NodeStatus.RUNNING, start_time=datetime.now())
        
        try:
            # 获取输入
            query = self.get_input(state, "message") or self.config.get("query", "")
            if not query:
                query = state.context.get("user_message", "")
            
            # 获取配置
            kb_id = self.config.get("kb_id", "")
            top_k = int(self.config.get("top_k", 5))
            include_context = self.config.get("include_context", True)
            
            if not kb_id:
                result.status = NodeStatus.FAILED
                result.error = "未配置知识库 ID"
                return result
            
            # 执行 RAG 搜索
            db = state.context.get("db_session")
            if not db:
                result.status = NodeStatus.FAILED
                result.error = "数据库会话不可用"
                return result
            
            service = KnowledgeService(db, kb_id)
            
            # 搜索相关文档
            search_results = await service.search(query, [kb_id], top_k=top_k)
            
            # 设置输出
            self.set_output(state, "results", search_results)
            self.set_output(state, "result_count", len(search_results))
            
            if include_context and search_results:
                context = await service.get_context(query, [kb_id])
                self.set_output(state, "context", context)
            else:
                self.set_output(state, "context", "")
            
            # 提取关键信息
            relevant_info = "\n".join([
                f"- {r.get('content', '')[:200]}..."
                for r in search_results[:3]
            ])
            self.set_output(state, "relevant_info", relevant_info)
            
            result.status = NodeStatus.SUCCESS
            
        except Exception as e:
            result.status = NodeStatus.FAILED
            result.error = f"RAG 检索失败: {str(e)}"
            
        finally:
            result.end_time = datetime.now()
        
        return result


class ConditionNode(BaseNode):
    """条件节点 - 分支判断"""
    
    async def execute(self, state: WorkflowState) -> NodeResult:
        result = NodeResult(node_id=self.node_id, status=NodeStatus.RUNNING, start_time=datetime.now())
        
        try:
            # 获取输入
            input_value = self.get_input(state, "value") or self.config.get("value", "")
            condition_type = self.config.get("condition_type", "equals")
            condition_value = self.config.get("condition_value", "")
            
            # 执行条件判断
            condition_met = self._evaluate_condition(
                input_value, condition_type, condition_value, state
            )
            
            # 设置输出
            self.set_output(state, "condition_met", condition_met)
            self.set_output(state, "condition_type", condition_type)
            self.set_output(state, "true_branch", self.config.get("true_label", "是"))
            self.set_output(state, "false_branch", self.config.get("false_label", "否"))
            
            result.status = NodeStatus.SUCCESS
            
        except Exception as e:
            result.status = NodeStatus.FAILED
            result.error = str(e)
            
        finally:
            result.end_time = datetime.now()
        
        return result
    
    def _evaluate_condition(
        self, value: Any, condition_type: str, condition_value: Any, state: WorkflowState
    ) -> bool:
        """评估条件"""
        if condition_type == "equals":
            return str(value).lower() == str(condition_value).lower()
        elif condition_type == "not_equals":
            return str(value).lower() != str(condition_value).lower()
        elif condition_type == "contains":
            return str(condition_value) in str(value)
        elif condition_type == "not_contains":
            return str(condition_value) not in str(value)
        elif condition_type == "starts_with":
            return str(value).startswith(str(condition_value))
        elif condition_type == "ends_with":
            return str(value).endswith(str(condition_value))
        elif condition_type == "greater_than":
            try:
                return float(value) > float(condition_value)
            except:
                return False
        elif condition_type == "less_than":
            try:
                return float(value) < float(condition_value)
            except:
                return False
        elif condition_type == "is_empty":
            return not value or str(value).strip() == ""
        elif condition_type == "is_not_empty":
            return value and str(value).strip() != ""
        elif condition_type == "regex":
            import re
            return bool(re.search(str(condition_value), str(value)))
        elif condition_type == "in_list":
            items = [i.strip() for i in str(condition_value).split(",")]
            return str(value) in items
        else:
            return True


class ToolNode(BaseNode):
    """工具节点 - 调用外部工具"""
    
    async def execute(self, state: WorkflowState) -> NodeResult:
        result = NodeResult(node_id=self.node_id, status=NodeStatus.RUNNING, start_time=datetime.now())
        
        try:
            # 获取输入
            tool_name = self.config.get("tool_name", "")
            tool_input = self.get_input(state, "input") or self.config.get("input", "")
            
            # 获取工具参数
            tool_params = self.config.get("params", {})
            
            # 处理参数中的变量引用
            processed_params = {}
            for key, value in tool_params.items():
                processed_params[key] = self._resolve_variable(value, state)
            
            # 调用工具
            tool_result = await self._call_tool(tool_name, processed_params, tool_input, state)
            
            # 设置输出
            self.set_output(state, "result", tool_result)
            self.set_output(state, "tool_name", tool_name)
            self.set_output(state, "success", True)
            
            result.status = NodeStatus.SUCCESS
            
        except Exception as e:
            self.set_output(state, "error", str(e))
            self.set_output(state, "success", False)
            result.status = NodeStatus.FAILED
            result.error = str(e)
            
        finally:
            result.end_time = datetime.now()
        
        return result
    
    def _resolve_variable(self, value: Any, state: WorkflowState) -> Any:
        """解析变量引用"""
        if isinstance(value, str) and value.startswith("$"):
            var_path = value[1:]
            if "." in var_path:
                parts = var_path.split(".")
                return state.node_outputs.get(parts[0], {}).get(parts[1], value)
            return state.context.get(var_path, value)
        return value
    
    async def _call_tool(
        self, tool_name: str, params: Dict, input_data: Any, state: WorkflowState
    ) -> Any:
        """调用工具"""
        # 预定义工具
        tools = {
            "calculator": self._tool_calculator,
            "search": self._tool_search,
            "weather": self._tool_weather,
            "formatter": self._tool_formatter,
            "text_process": self._tool_text_process,
            "date_time": self._tool_datetime,
        }
        
        if tool_name in tools:
            return await tools[tool_name](params, input_data, state)
        else:
            raise ValueError(f"未知工具: {tool_name}")
    
    async def _tool_calculator(self, params: Dict, input_data: Any, state: WorkflowState) -> str:
        """计算器工具"""
        operation = params.get("operation", "calculate")
        expression = params.get("expression", input_data)
        
        try:
            # 安全计算
            allowed_chars = set("0123456789+-*/()., ")
            if all(c in allowed_chars for c in expression):
                result = eval(expression)
                return str(result)
            return "表达式包含非法字符"
        except Exception as e:
            return f"计算错误: {str(e)}"
    
    async def _tool_search(self, params: Dict, input_data: Any, state: WorkflowState) -> str:
        """搜索工具"""
        query = params.get("query", input_data)
        engine = params.get("engine", "duckduckgo")
        
        # 实际项目中这里会调用真实搜索 API
        return f"搜索结果 for '{query}': 暂无结果（需要配置搜索 API）"
    
    async def _tool_weather(self, params: Dict, input_data: Any, state: WorkflowState) -> str:
        """天气查询工具"""
        city = params.get("city", input_data)
        return f"{city} 天气：晴，温度 25°C（需要配置天气 API）"
    
    async def _tool_formatter(self, params: Dict, input_data: Any, state: WorkflowState) -> str:
        """格式化工具"""
        template = params.get("template", "{input}")
        return template.replace("{input}", str(input_data))
    
    async def _tool_text_process(self, params: Dict, input_data: Any, state: WorkflowState) -> str:
        """文本处理工具"""
        operation = params.get("operation", "uppercase")
        
        if operation == "uppercase":
            return str(input_data).upper()
        elif operation == "lowercase":
            return str(input_data).lower()
        elif operation == "trim":
            return str(input_data).strip()
        elif operation == "length":
            return str(len(str(input_data)))
        elif operation == "word_count":
            return str(len(str(input_data).split()))
        else:
            return str(input_data)
    
    async def _tool_datetime(self, params: Dict, input_data: Any, state: WorkflowState) -> str:
        """日期时间工具"""
        format_str = params.get("format", "%Y-%m-%d %H:%M:%S")
        return datetime.now().strftime(format_str)


class ResponseNode(BaseNode):
    """响应节点 - 回复用户"""
    
    async def execute(self, state: WorkflowState) -> NodeResult:
        result = NodeResult(node_id=self.node_id, status=NodeStatus.RUNNING, start_time=datetime.now())
        
        try:
            # 获取输入
            response_content = self.get_input(state, "response") or self.config.get("response", "")
            template = self.config.get("template", "")
            
            # 处理模板
            if template:
                response_content = self._process_template(template, state)
            
            # 设置输出
            self.set_output(state, "response_content", response_content)
            self.set_output(state, "final_response", response_content)
            self.set_output(state, "response_time", datetime.now().isoformat())
            
            result.status = NodeStatus.SUCCESS
            
        except Exception as e:
            result.status = NodeStatus.FAILED
            result.error = str(e)
            
        finally:
            result.end_time = datetime.now()
        
        return result
    
    def _process_template(self, template: str, state: WorkflowState) -> str:
        """处理响应模板"""
        import re
        
        def replace_var(match):
            var_path = match.group(1)
            if "." in var_path:
                parts = var_path.split(".")
                value = state.node_outputs.get(parts[0], {}).get(parts[1], "")
                return str(value)
            return str(state.context.get(var_path, match.group(0)))
        
        return re.sub(r'\{\{([^}]+)\}\}', replace_var, template)


class WorkflowRuntime:
    """工作流运行时"""
    
    def __init__(self):
        self.node_types = {
            "trigger": TriggerNode,
            "llm": LLMNode,
            "knowledge": KnowledgeNode,
            "condition": ConditionNode,
            "tool": ToolNode,
            "response": ResponseNode,
        }
    
    def create_node(self, node_type: str, node_id: str, config: Dict) -> BaseNode:
        """创建节点实例"""
        node_class = self.node_types.get(node_type, BaseNode)
        return node_class(node_id, config)
    
    def get_execution_order(self, nodes: List[Dict], edges: List[Dict]) -> List[str]:
        """获取执行顺序（拓扑排序）"""
        # 构建邻接表
        in_degree = {n["id"]: 0 for n in nodes}
        adjacency = {n["id"]: [] for n in nodes}
        
        for edge in edges:
            source = edge.get("source")
            target = edge.get("target")
            if source and target:
                adjacency[source].append(target)
                in_degree[target] = in_degree.get(target, 0) + 1
        
        # Kahn's algorithm
        queue = [n for n, d in in_degree.items() if d == 0]
        order = []
        
        while queue:
            node_id = queue.pop(0)
            order.append(node_id)
            
            for neighbor in adjacency[node_id]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        return order
    
    def get_next_nodes(
        self, current_node_id: str, edges: List[Dict], condition_result: bool = None
    ) -> List[str]:
        """获取下一个节点"""
        next_nodes = []

        for edge in edges:
            if edge.get("source") != current_node_id:
                continue

            source_handle = edge.get("sourceHandle")
            target = edge.get("target")

            if not target:
                continue

            # 检查是否是条件分支
            if source_handle in ["yes", "true"]:
                # 条件为真时的分支
                if condition_result is True:
                    next_nodes.append(target)
            elif source_handle in ["no", "false"]:
                # 条件为假时的分支
                if condition_result is False:
                    next_nodes.append(target)
            elif source_handle is None or source_handle == "":
                # 无条件边 - 总是执行
                next_nodes.append(target)
            else:
                # 其他情况（如标签边）- 总是执行
                next_nodes.append(target)

        return next_nodes
    
    async def execute_workflow(
        self,
        workflow_def: Dict,
        input_data: Dict,
        db_session: AsyncSession,
    ) -> WorkflowState:
        """执行工作流 - 使用 BFS 遍历"""
        workflow_id = str(uuid.uuid4())

        # 初始化状态
        state = WorkflowState(
            workflow_id=workflow_id,
            nodes={n["id"]: n for n in workflow_def.get("nodes", [])},
            edges=workflow_def.get("edges", []),
            context=input_data,
        )
        state.context["db_session"] = db_session

        # 记录已执行的节点
        executed = set()

        # 找到触发器节点作为起点
        start_nodes = [
            n["id"] for n in workflow_def.get("nodes", [])
            if n.get("type") == "trigger"
        ]

        if not start_nodes:
            # 如果没有触发器节点，使用拓扑排序的第一个节点
            execution_order = self.get_execution_order(
                workflow_def.get("nodes", []),
                workflow_def.get("edges", [])
            )
            if execution_order:
                start_nodes = [execution_order[0]]
            else:
                raise ValueError("工作流没有有效的起始节点")

        # 使用队列进行 BFS 执行
        from collections import deque
        queue = deque(start_nodes)

        while queue:
            node_id = queue.popleft()

            if node_id in executed:
                continue

            node_def = state.nodes.get(node_id, {})
            node_type = node_def.get("type", "")

            if not node_type:
                executed.add(node_id)
                continue

            # 创建节点实例
            node = self.create_node(node_type, node_id, node_def.get("data", {}))

            # 设置当前节点
            state.current_node = node_id

            # 执行节点
            result = await node.execute(state)
            result.execution_time = (
                (result.end_time - result.start_time).total_seconds()
                if result.end_time and result.start_time else 0
            )

            state.execution_history.append(result)
            executed.add(node_id)

            # 如果节点失败且是关键节点，停止执行
            if result.status == NodeStatus.FAILED:
                if node_type in ["trigger", "llm", "response"]:
                    break

            # 获取下一个节点
            condition_result = None
            if node_type == "condition":
                condition_result = state.node_outputs.get(node_id, {}).get("condition_met", True)

            next_nodes = self.get_next_nodes(node_id, state.edges, condition_result)

            # 添加下一个节点到队列
            for next_id in next_nodes:
                if next_id not in executed:
                    queue.append(next_id)

        return state
    
    async def execute_node(
        self,
        workflow_def: Dict,
        node_id: str,
        input_data: Dict,
        db_session: AsyncSession,
    ) -> NodeResult:
        """单独执行某个节点"""
        state = WorkflowState(
            workflow_id="single",
            nodes={n["id"]: n for n in workflow_def.get("nodes", [])},
            edges=workflow_def.get("edges", []),
            context=input_data,
        )
        state.context["db_session"] = db_session
        
        node_def = state.nodes.get(node_id, {})
        node_type = node_def.get("type", "")
        
        node = self.create_node(node_type, node_id, node_def.get("data", {}))
        return await node.execute(state)


# 全局运行时实例
workflow_runtime = WorkflowRuntime()
