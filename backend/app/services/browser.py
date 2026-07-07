"""
Browser-Use 工具 - 浏览器自动化控制
集成 browser-use 实现 AI 控制浏览器
"""
import os
import json
import asyncio
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

# browser-use 核心组件
try:
    from browser_use import Agent, Browser
    from langchain_openai import ChatOpenAI
    BROWSER_USE_AVAILABLE = True
except ImportError:
    BROWSER_USE_AVAILABLE = False


class BrowserToolConfig(BaseModel):
    """浏览器工具配置"""
    task: str
    max_steps: int = 10
    model_name: str = "gpt-4o"
    api_key: Optional[str] = None


class BrowserResult(BaseModel):
    """浏览器操作结果"""
    success: bool
    steps_executed: int
    final_result: str
    screenshots: List[str] = []
    error: Optional[str] = None


class BrowserToolService:
    """浏览器自动化工具服务"""

    def __init__(self):
        self.active_agents: Dict[str, Any] = {}
        self._browser: Optional[Browser] = None

    async def execute_browser_task(
        self,
        task: str,
        max_steps: int = 10,
        model_name: str = "gpt-4o",
        api_key: Optional[str] = None,
        session_id: str = "default",
    ) -> BrowserResult:
        """
        执行浏览器自动化任务
        
        Args:
            task: 任务描述，如 "帮我打开知乎，搜索 AI Agent，截图"
            max_steps: 最大步数限制
            model_name: 使用的模型
            api_key: API Key（如果为空则使用环境变量）
            session_id: 会话 ID，支持并发多个浏览器实例
        """
        if not BROWSER_USE_AVAILABLE:
            return BrowserResult(
                success=False,
                steps_executed=0,
                final_result="",
                error="browser-use 未安装，请运行: pip install browser-use playwright && playwright install chromium"
            )

        try:
            # 初始化 LLM
            import os
            key = api_key or os.getenv("OPENAI_API_KEY")
            if not key:
                return BrowserResult(
                    success=False,
                    steps_executed=0,
                    final_result="",
                    error="需要设置 OPENAI_API_KEY 或传入 api_key"
                )

            llm = ChatOpenAI(model=model_name, api_key=key)

            # 创建/复用浏览器实例
            if session_id not in self.active_agents:
                self.active_agents[session_id] = None

            # 创建 Agent
            agent = Agent(
                task=task,
                llm=llm,
                browser=self._get_or_create_browser(session_id),
                max_steps=max_steps,
            )

            self.active_agents[session_id] = agent

            # 执行任务
            result = await agent.run()

            # 提取结果
            steps = result.steps if hasattr(result, 'steps') else max_steps
            final = result.final_result if hasattr(result, 'final_result') else str(result)

            return BrowserResult(
                success=True,
                steps_executed=steps,
                final_result=final,
                screenshots=[],
            )

        except Exception as e:
            return BrowserResult(
                success=False,
                steps_executed=0,
                final_result="",
                error=str(e)
            )

    def _get_or_create_browser(self, session_id: str) -> Browser:
        """获取或创建浏览器实例"""
        if self._browser is None:
            self._browser = Browser(
                headless=True,
                extra_chromium_args=["--disable-blink-features=AutomationControlled"],
            )
        return self._browser

    async def close_browser(self, session_id: str = "default"):
        """关闭指定会话的浏览器"""
        if session_id in self.active_agents:
            del self.active_agents[session_id]
        if not self.active_agents and self._browser:
            await self._browser.close()
            self._browser = None

    def get_tool_definition(self) -> dict:
        """获取工具定义（用于 LLM）"""
        return {
            "type": "function",
            "function": {
                "name": "browser_control",
                "description": """控制浏览器执行自动化任务。可以打开网页、点击元素、输入文字、滚动页面、截图等。
适用场景：需要获取网页信息、自动化填写表单、自动发帖、数据采集等。
输入任务描述即可，如：'打开Google搜索 AI Agent' 或 '登录知乎找到热帖并截图'。""",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task": {
                            "type": "string",
                            "description": "任务描述，用自然语言描述你想让浏览器做什么"
                        },
                        "max_steps": {
                            "type": "integer",
                            "description": "最大操作步数，默认10步",
                            "default": 10
                        },
                        "session_id": {
                            "type": "string",
                            "description": "浏览器会话ID，可选，支持多会话并发",
                            "default": "default"
                        }
                    },
                    "required": ["task"]
                }
            }
        }


# 全局实例
browser_tool_service = BrowserToolService()
