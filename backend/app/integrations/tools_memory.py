"""
AgentFlow 整合 agent-tool-registry 和 agent-memory-store

Phase 3: 工具注册 + 记忆管理
"""
from typing import Dict, Any, List, Optional, Callable
from abc import ABC, abstractmethod
import json
import asyncio

# agent-tool-registry 整合
try:
    from agent_tool_registry import ToolRegistry, Tool
    HAS_TOOL_REGISTRY = True
except ImportError:
    HAS_TOOL_REGISTRY = False

# agent-memory-store 整合
try:
    from agent_memory_store import MemoryStore, MemoryConfig
    HAS_MEMORY_STORE = True
except ImportError:
    HAS_MEMORY_STORE = False


class ToolManager:
    """
    整合 agent-tool-registry 的工具管理
    
    支持工具类型：
    - search: 搜索
    - calculator: 计算
    - weather: 天气
    - browser: 浏览器自动化
    - api: API 调用
    - custom: 自定义
    """
    
    def __init__(self):
        if HAS_TOOL_REGISTRY:
            self._registry = ToolRegistry()
        else:
            self._registry = None
        
        self._tools: Dict[str, Callable] = {}
        self._tool_configs: Dict[str, Dict] = {}
        
        self._register_builtin_tools()
    
    def _register_builtin_tools(self):
        """注册内置工具"""
        # 搜索工具
        self.register(
            name="search",
            handler=self._search_tool,
            description="搜索信息",
            parameters={
                "query": {"type": "string", "description": "搜索关键词"}
            }
        )
        
        # 计算工具
        self.register(
            name="calculator",
            handler=self._calculator_tool,
            description="数学计算",
            parameters={
                "expression": {"type": "string", "description": "数学表达式"}
            }
        )
        
        # 天气工具
        self.register(
            name="weather",
            handler=self._weather_tool,
            description="查询天气",
            parameters={
                "location": {"type": "string", "description": "地点"}
            }
        )
        
        # 浏览器工具
        self.register(
            name="browser",
            handler=self._browser_tool,
            description="浏览器自动化",
            parameters={
                "action": {"type": "string", "description": "操作类型"},
                "url": {"type": "string", "description": "URL"}
            }
        )
    
    def register(
        self,
        name: str,
        handler: Callable,
        description: str = "",
        parameters: Dict = None
    ):
        """注册工具"""
        self._tools[name] = handler
        self._tool_configs[name] = {
            "name": name,
            "description": description,
            "parameters": parameters or {}
        }
        
        if HAS_TOOL_REGISTRY and self._registry:
            tool = Tool(
                name=name,
                description=description,
                parameters_schema=parameters or {},
                handler=handler
            )
            self._registry.register(tool)
    
    async def execute(
        self,
        tool_name: str,
        **kwargs
    ) -> Dict[str, Any]:
        """执行工具"""
        if tool_name not in self._tools:
            return {"error": f"Tool not found: {tool_name}"}
        
        handler = self._tools[tool_name]
        
        try:
            if asyncio.iscoroutinefunction(handler):
                result = await handler(**kwargs)
            else:
                result = handler(**kwargs)
            
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_tool_schemas(self) -> List[Dict]:
        """获取工具 schema（用于 LLM function calling）"""
        schemas = []
        
        for name, config in self._tool_configs.items():
            schemas.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": config["description"],
                    "parameters": {
                        "type": "object",
                        "properties": config["parameters"],
                        "required": list(config["parameters"].keys())
                    }
                }
            })
        
        return schemas
    
    # 内置工具实现
    async def _search_tool(self, query: str) -> str:
        """搜索工具"""
        # TODO: 实现搜索逻辑
        return f"搜索结果：{query}"
    
    def _calculator_tool(self, expression: str) -> float:
        """计算工具"""
        try:
            return eval(expression)
        except Exception:
            return 0.0
    
    async def _weather_tool(self, location: str) -> str:
        """天气工具"""
        # TODO: 调用天气 API
        return f"{location} 天气：晴，25°C"
    
    async def _browser_tool(self, action: str, url: str = None) -> str:
        """浏览器工具"""
        # TODO: 调用 browser-use
        return f"浏览器操作：{action} {url or ''}"


class MemoryManager:
    """
    整合 agent-memory-store 的记忆管理
    
    支持后端：
    - in_memory: 内存（默认）
    - redis: Redis
    - postgresql: PostgreSQL
    - file: 文件
    """
    
    def __init__(self, backend: str = "in_memory", config: Dict = None):
        self.backend = backend
        self.config = config or {}
        
        if HAS_MEMORY_STORE:
            memory_config = MemoryConfig(
                backend=backend,
                **self.config
            )
            self._store = MemoryStore(memory_config)
        else:
            self._store = None
            self._memories: Dict[str, List[Dict]] = {}
    
    async def save(
        self,
        session_id: str,
        messages: List[Dict],
        metadata: Dict = None
    ):
        """保存记忆"""
        if HAS_MEMORY_STORE and self._store:
            await self._store.save(
                session_id=session_id,
                messages=messages,
                metadata=metadata
            )
        else:
            self._memories[session_id] = {
                "messages": messages,
                "metadata": metadata or {}
            }
    
    async def load(
        self,
        session_id: str,
        limit: int = None
    ) -> List[Dict]:
        """加载记忆"""
        if HAS_MEMORY_STORE and self._store:
            return await self._store.load(session_id, limit=limit)
        else:
            data = self._memories.get(session_id, {})
            messages = data.get("messages", [])
            return messages[-limit:] if limit else messages
    
    async def clear(self, session_id: str):
        """清空记忆"""
        if HAS_MEMORY_STORE and self._store:
            await self._store.clear(session_id)
        else:
            self._memories.pop(session_id, None)
    
    async def search(
        self,
        query: str,
        session_id: str = None,
        limit: int = 5
    ) -> List[Dict]:
        """搜索记忆（语义搜索）"""
        if HAS_MEMORY_STORE and self._store:
            return await self._store.search(
                query=query,
                session_id=session_id,
                limit=limit
            )
        else:
            # 简单关键词搜索
            results = []
            messages = await self.load(session_id) if session_id else []
            
            for msg in messages:
                if query.lower() in msg.get("content", "").lower():
                    results.append(msg)
            
            return results[:limit]
    
    async def summarize(
        self,
        session_id: str,
        max_tokens: int = 500
    ) -> str:
        """总结记忆"""
        messages = await self.load(session_id)
        
        if not messages:
            return ""
        
        # 简单总结（实际应调用 LLM）
        user_msgs = [m for m in messages if m["role"] == "user"]
        assistant_msgs = [m for m in messages if m["role"] == "assistant"]
        
        return f"对话历史：{len(user_msgs)} 个问题，{len(assistant_msgs)} 个回答"


class ConversationMemory:
    """
    对话记忆管理器
    
    整合到 AgentRuntime 中使用
    """
    
    def __init__(
        self,
        session_id: str,
        memory_manager: MemoryManager,
        max_history: int = 20
    ):
        self.session_id = session_id
        self.memory_manager = memory_manager
        self.max_history = max_history
    
    async def add_message(self, role: str, content: str):
        """添加消息"""
        messages = await self.memory_manager.load(self.session_id)
        messages.append({"role": role, "content": content})
        
        # 截断历史
        if len(messages) > self.max_history:
            messages = messages[-self.max_history:]
        
        await self.memory_manager.save(self.session_id, messages)
    
    async def get_history(self) -> List[Dict]:
        """获取历史"""
        return await self.memory_manager.load(self.session_id)
    
    async def get_context_window(
        self,
        max_tokens: int = 4000
    ) -> List[Dict]:
        """
        获取上下文窗口
        
        根据 token 限制返回合适的消息数量
        """
        messages = await self.get_history()
        
        # 简单估算：每条消息约 100 tokens
        max_messages = max_tokens // 100
        
        return messages[-max_messages:]


# 全局实例
tool_manager = ToolManager()
