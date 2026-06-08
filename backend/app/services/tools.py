"""
工具服务 - Agent 工具调用
"""
from typing import Callable, Dict, Any, List
from pydantic import BaseModel
import httpx
import json


class ToolDefinition(BaseModel):
    """工具定义"""
    name: str
    description: str
    parameters: dict  # JSON Schema
    function: Callable = None


class ToolService:
    """工具服务"""
    
    def __init__(self):
        self.tools: Dict[str, ToolDefinition] = {}
        self._register_builtin_tools()
    
    def _register_builtin_tools(self):
        """注册内置工具"""
        # 搜索工具
        self.register(ToolDefinition(
            name="search",
            description="搜索互联网获取信息",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"}
                },
                "required": ["query"]
            },
            function=self._search,
        ))
        
        # 计算工具
        self.register(ToolDefinition(
            name="calculate",
            description="执行数学计算",
            parameters={
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "数学表达式"}
                },
                "required": ["expression"]
            },
            function=self._calculate,
        ))
        
        # 天气工具
        self.register(ToolDefinition(
            name="get_weather",
            description="获取天气信息",
            parameters={
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名称"}
                },
                "required": ["city"]
            },
            function=self._get_weather,
        ))
        
        # API 调用工具
        self.register(ToolDefinition(
            name="http_request",
            description="发起 HTTP 请求",
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "method": {"type": "string", "enum": ["GET", "POST"]},
                    "body": {"type": "object"},
                },
                "required": ["url"]
            },
            function=self._http_request,
        ))

        # 浏览器自动化工具
        self.register(ToolDefinition(
            name="browser_control",
            description="控制浏览器执行自动化任务，如打开网页、点击、输入、截图",
            parameters={
                "type": "object",
                "properties": {
                    "task": {"type": "string", "description": "任务描述，自然语言"},
                    "max_steps": {"type": "integer", "description": "最大步数，默认10", "default": 10},
                    "session_id": {"type": "string", "description": "会话ID，可选", "default": "default"},
                },
                "required": ["task"]
            },
            function=self._browser_control,
        ))
    
    def register(self, tool: ToolDefinition):
        """注册工具"""
        self.tools[tool.name] = tool
    
    def get_tool_definitions(self) -> List[dict]:
        """获取工具定义列表（用于 LLM）"""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                }
            }
            for tool in self.tools.values()
        ]
    
    async def execute(self, name: str, arguments: dict) -> Any:
        """执行工具"""
        tool = self.tools.get(name)
        
        if not tool:
            return {"error": f"Tool not found: {name}"}
        
        try:
            if tool.function:
                result = await tool.function(**arguments)
                return result
            else:
                return {"error": f"Tool function not implemented: {name}"}
        except Exception as e:
            return {"error": str(e)}
    
    async def _search(self, query: str) -> dict:
        """搜索"""
        # 简化实现，实际应调用搜索 API
        return {
            "query": query,
            "results": [
                {"title": "搜索结果示例", "snippet": "这是搜索结果的内容..."}
            ]
        }
    
    async def _calculate(self, expression: str) -> dict:
        """计算 - 使用 ast 安全解析"""
        import ast
        import operator
        
        try:
            # 安全计算：仅允许基本数学运算
            allowed_chars = set("0123456789+-*/(). ")
            if not all(c in allowed_chars for c in expression):
                return {"error": "Invalid expression: only digits and +-*/(). allowed"}
            
            # 使用 ast.literal_eval 不支持运算符，改用手动解析
            # 用 operator 映射实现安全计算
            tree = ast.parse(expression, mode='eval')
            
            def _eval(node):
                if isinstance(node, ast.Constant):
                    return node.value
                elif isinstance(node, ast.BinOp):
                    left = _eval(node.left)
                    right = _eval(node.right)
                    ops = {
                        ast.Add: operator.add,
                        ast.Sub: operator.sub,
                        ast.Mult: operator.mul,
                        ast.Div: operator.truediv,
                        ast.Pow: operator.pow,
                        ast.Mod: operator.mod,
                    }
                    return ops[type(node.op)](left, right)
                elif isinstance(node, ast.UnaryOp):
                    operand = _eval(node.operand)
                    if isinstance(node.op, ast.USub):
                        return -operand
                    elif isinstance(node.op, ast.UAdd):
                        return operand
                elif isinstance(node, ast.Call):
                    raise ValueError("Function calls not allowed")
                raise ValueError(f"Unsupported expression: {ast.dump(node)}")
            
            result = _eval(tree.body)
            return {"expression": expression, "result": result}
        except Exception as e:
            return {"error": str(e)}
    
    async def _get_weather(self, city: str) -> dict:
        """获取天气"""
        # 简化实现
        return {
            "city": city,
            "weather": "晴",
            "temperature": "25°C",
        }
    
    async def _http_request(
        self,
        url: str,
        method: str = "GET",
        body: dict = None,
    ) -> dict:
        """HTTP 请求"""
        async with httpx.AsyncClient() as client:
            if method == "GET":
                response = await client.get(url, timeout=30)
            else:
                response = await client.post(url, json=body, timeout=30)
            
            return {
                "status_code": response.status_code,
                "body": response.text[:1000],  # 限制长度
            }


    async def _browser_control(self, task: str, max_steps: int = 10, session_id: str = "default") -> dict:
        """浏览器自动化"""
        try:
            from .browser import browser_tool_service
            result = await browser_tool_service.execute_browser_task(
                task=task,
                max_steps=max_steps,
                session_id=session_id,
            )
            return {
                "success": result.success,
                "steps": result.steps_executed,
                "result": result.final_result,
                "screenshots": result.screenshots,
                "error": result.error,
            }
        except Exception as e:
            return {"success": False, "error": str(e), "result": "", "steps": 0}


# 全局工具服务实例
tool_service = ToolService()
