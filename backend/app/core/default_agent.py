"""新账号的默认 Agent。

开源 / 自托管场景下，别人注册完不应该面对一个空列表 —— 点「对话」就得能
直接聊起来，而不是先被引导去「创建 Agent」。

这里只造一个不带工作流的普通 Agent（走内置或 PiAgent 对话链路），不预置任何
业务模板；模板市场由 ``app.core.seed.seed_templates`` 单独负责。默认 Agent 也
计入免费版配额（``FREE_AGENTS``），否则用户能白拿两个。
"""
from app.models.agent import Agent

DEFAULT_AGENT_NAME = "Alagent"
DEFAULT_AGENT_DESCRIPTION = "我是您的智能助手，可以回答问题、帮助完成任务。"

DEFAULT_AGENT_SYSTEM_PROMPT = """你是 AgentFlow 的通用工作助手，目标是帮用户把任务推进到可交付的结果。

工作方式：
1. 先确认目标与约束，信息不足时只问最关键的一个问题
2. 输出可直接执行的结论、步骤或草稿，必要时用列表或表格组织
3. 涉及数据、引用、法规时明确标注不确定性，不编造事实

风格：简体中文、简洁、专业，不使用空泛的客套话。"""


def build_default_agent(user_external_id: str) -> Agent:
    """构造注册时附带的默认 Agent（字段与 ``POST /agents`` 保持一致）。

    ``model`` 留空表示「跟随当前生效的模型配置」，避免把某个具体型号钉死 ——
    本地 Ollama / DeepSeek 用户拿到 gpt-4o-mini 会直接报模型不存在。
    """
    return Agent(
        user_id=user_external_id,
        name=DEFAULT_AGENT_NAME,
        description=DEFAULT_AGENT_DESCRIPTION,
        workflow_definition={"nodes": [], "edges": [], "entry": "start"},
        model_config={"provider": "openai", "model": "", "temperature": 0.7},
        settings={"system_prompt": DEFAULT_AGENT_SYSTEM_PROMPT},
        is_active=True,
    )
