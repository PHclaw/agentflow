"""数据库种子数据"""
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.agent import WorkflowTemplate


DEFAULT_TEMPLATES = [
    {
        "name": "智能客服",
        "category": "customer_service",
        "description": "自动回答常见问题，支持多轮对话和工单创建。包含 FAQ 匹配、意图识别、工单生成三个节点。",
        "icon": "💬",
        "color": "from-green-500 to-emerald-600",
        "features": ["FAQ 自动回答", "多轮对话", "工单创建", "满意度调查"],
        "workflow_definition": {
            "nodes": [
                {"id": "start", "type": "start", "label": "用户输入"},
                {"id": "classify", "type": "llm", "label": "意图分类", "config": {"model": "gpt-4", "prompt": "判断用户意图：FAQ问答/工单/转人工", "temperature": 0.1}},
                {"id": "faq", "type": "knowledge", "label": "FAQ 检索", "config": {"top_k": 3}},
                {"id": "ticket", "type": "llm", "label": "工单生成", "config": {"model": "gpt-4", "prompt": "提取工单信息：标题、描述、优先级"}},
                {"id": "end", "type": "output", "label": "回复用户"},
            ],
            "edges": [
                {"from": "start", "to": "classify"},
                {"from": "classify", "to": "faq", "condition": "intent == 'faq'"},
                {"from": "classify", "to": "ticket", "condition": "intent == 'ticket'"},
                {"from": "faq", "to": "end"},
                {"from": "ticket", "to": "end"},
            ],
        },
        "is_public": True,
    },
    {
        "name": "销售助手",
        "category": "sales",
        "description": "帮助销售跟进客户、生成报价、安排会议。集成 CRM 数据查询节点。",
        "icon": "💰",
        "color": "from-blue-500 to-indigo-600",
        "features": ["客户跟进", "报价生成", "会议安排", "CRM 集成"],
        "workflow_definition": {
            "nodes": [
                {"id": "start", "type": "start", "label": "客户输入"},
                {"id": "analyze", "type": "llm", "label": "需求分析", "config": {"model": "gpt-4", "prompt": "分析客户需求：产品兴趣、预算范围、决策阶段"}},
                {"id": "quote", "type": "tool", "label": "生成报价", "config": {"tool": "generate_quote"}},
                {"id": "schedule", "type": "tool", "label": "安排会议", "config": {"tool": "schedule_meeting"}},
                {"id": "end", "type": "output", "label": "回复客户"},
            ],
            "edges": [
                {"from": "start", "to": "analyze"},
                {"from": "analyze", "to": "quote", "condition": "need_quote == true"},
                {"from": "analyze", "to": "schedule", "condition": "need_meeting == true"},
                {"from": "quote", "to": "end"},
                {"from": "schedule", "to": "end"},
            ],
        },
        "is_public": True,
    },
    {
        "name": "HR 助手",
        "category": "hr",
        "description": "回答员工关于假期、薪资、福利等 HR 政策问题，支持政策文档 RAG 检索。",
        "icon": "👥",
        "color": "from-purple-500 to-violet-600",
        "features": ["政策查询", "假期申请", "薪资咨询", "培训推荐"],
        "workflow_definition": {
            "nodes": [
                {"id": "start", "type": "start", "label": "员工提问"},
                {"id": "retrieve", "type": "knowledge", "label": "政策检索", "config": {"top_k": 5, "kb_name": "hr_policies"}},
                {"id": "answer", "type": "llm", "label": "生成回答", "config": {"model": "gpt-4", "prompt": "基于检索到的 HR 政策回答员工问题。如果不确定，请引导员工联系 HR 部门。"}},
                {"id": "end", "type": "output", "label": "回复员工"},
            ],
            "edges": [
                {"from": "start", "to": "retrieve"},
                {"from": "retrieve", "to": "answer"},
                {"from": "answer", "to": "end"},
            ],
        },
        "is_public": True,
    },
    {
        "name": "知识库问答",
        "category": "general",
        "description": "基于企业知识库的智能问答系统，支持多文档格式检索和 LLM 摘要回答。",
        "icon": "📚",
        "color": "from-pink-500 to-rose-600",
        "features": ["文档导入", "智能检索", "多格式支持", "权限管理"],
        "workflow_definition": {
            "nodes": [
                {"id": "start", "type": "start", "label": "用户提问"},
                {"id": "search", "type": "knowledge", "label": "文档检索", "config": {"top_k": 5, "score_threshold": 0.7}},
                {"id": "rerank", "type": "llm", "label": "重排序", "config": {"model": "gpt-4", "prompt": "根据问题相关性重排序检索结果，保留最相关的3条"}},
                {"id": "summarize", "type": "llm", "label": "摘要回答", "config": {"model": "gpt-4", "prompt": "基于检索内容生成简洁准确的回答，引用来源"}},
                {"id": "end", "type": "output", "label": "回答用户"},
            ],
            "edges": [
                {"from": "start", "to": "search"},
                {"from": "search", "to": "rerank"},
                {"from": "rerank", "to": "summarize"},
                {"from": "summarize", "to": "end"},
            ],
        },
        "is_public": True,
    },
]


async def seed_templates(db: AsyncSession):
    """初始化模板数据（仅当表为空时）"""
    result = await db.execute(select(func.count()).select_from(WorkflowTemplate))
    count = result.scalar()
    if count and count > 0:
        return  # 已存在数据，跳过

    for tpl in DEFAULT_TEMPLATES:
        template = WorkflowTemplate(
            id=str(uuid.uuid4()),
            name=tpl["name"],
            category=tpl["category"],
            description=tpl["description"],
            icon=tpl.get("icon", "template"),
            color=tpl.get("color", "from-blue-500 to-indigo-600"),
            features=tpl.get("features", []),
            workflow_definition=tpl["workflow_definition"],
            is_public=tpl["is_public"],
        )
        db.add(template)

    await db.commit()
    print(f"Seeded {len(DEFAULT_TEMPLATES)} workflow templates")
