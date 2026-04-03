"""
预置模板
"""
from typing import List, Dict

# 客服机器人模板
CUSTOMER_SERVICE_TEMPLATE = {
    "name": "智能客服机器人",
    "category": "customer_service",
    "description": "自动回答客户常见问题，支持多轮对话和工单创建",
    "workflow_definition": {
        "nodes": [
            {
                "id": "start",
                "type": "condition",
                "config": {
                    "condition": "intent",
                    "branches": ["faq", "complaint", "order", "other"]
                }
            },
            {
                "id": "faq",
                "type": "knowledge",
                "config": {
                    "kb_id": "faq_kb",
                    "fallback": "llm"
                }
            },
            {
                "id": "complaint",
                "type": "tool",
                "config": {
                    "tool": "create_ticket",
                    "priority": "high"
                }
            },
            {
                "id": "order",
                "type": "tool",
                "config": {
                    "tool": "query_order"
                }
            },
            {
                "id": "llm",
                "type": "llm",
                "config": {
                    "system_prompt": "你是一个专业的客服助手，请友好、专业地回答用户问题。"
                }
            },
            {
                "id": "end",
                "type": "output",
                "config": {}
            }
        ],
        "edges": [
            {"source": "start", "target": "faq", "condition": {"intent": "faq"}},
            {"source": "start", "target": "complaint", "condition": {"intent": "complaint"}},
            {"source": "start", "target": "order", "condition": {"intent": "order"}},
            {"source": "start", "target": "llm", "condition": {"intent": "other"}},
            {"source": "faq", "target": "end"},
            {"source": "complaint", "target": "end"},
            {"source": "order", "target": "end"},
            {"source": "llm", "target": "end"},
        ],
        "entry": "start"
    },
    "model_config": {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "temperature": 0.7
    }
}

# 销售助手模板
SALES_ASSISTANT_TEMPLATE = {
    "name": "销售助手",
    "category": "sales",
    "description": "帮助销售跟进客户、生成报价、安排会议",
    "workflow_definition": {
        "nodes": [
            {
                "id": "start",
                "type": "llm",
                "config": {
                    "system_prompt": "你是一个销售助手，帮助销售人员进行客户跟进和报价。"
                }
            },
            {
                "id": "check_crm",
                "type": "tool",
                "config": {
                    "tool": "query_crm",
                    "action": "get_customer"
                }
            },
            {
                "id": "generate_response",
                "type": "llm",
                "config": {}
            },
            {
                "id": "end",
                "type": "output",
                "config": {}
            }
        ],
        "edges": [
            {"source": "start", "target": "check_crm"},
            {"source": "check_crm", "target": "generate_response"},
            {"source": "generate_response", "target": "end"}
        ],
        "entry": "start"
    }
}

# HR 助手模板
HR_ASSISTANT_TEMPLATE = {
    "name": "HR 助手",
    "category": "hr",
    "description": "回答员工关于假期、薪资、福利等问题",
    "workflow_definition": {
        "nodes": [
            {
                "id": "start",
                "type": "knowledge",
                "config": {
                    "kb_id": "hr_policy"
                }
            },
            {
                "id": "llm",
                "type": "llm",
                "config": {
                    "system_prompt": "你是 HR 助手，根据公司政策回答员工问题。回答要准确、友好。"
                }
            },
            {
                "id": "end",
                "type": "output",
                "config": {}
            }
        ],
        "edges": [
            {"source": "start", "target": "llm"},
            {"source": "llm", "target": "end"}
        ],
        "entry": "start"
    }
}

# 财务助手模板
FINANCE_ASSISTANT_TEMPLATE = {
    "name": "财务助手",
    "category": "finance",
    "description": "处理报销审批、发票查询、预算咨询",
    "workflow_definition": {
        "nodes": [
            {
                "id": "start",
                "type": "condition",
                "config": {
                    "condition": "task_type",
                    "branches": ["reimbursement", "invoice", "budget"]
                }
            },
            {
                "id": "reimbursement",
                "type": "tool",
                "config": {
                    "tool": "submit_reimbursement"
                }
            },
            {
                "id": "invoice",
                "type": "tool",
                "config": {
                    "tool": "query_invoice"
                }
            },
            {
                "id": "budget",
                "type": "tool",
                "config": {
                    "tool": "query_budget"
                }
            },
            {
                "id": "end",
                "type": "output",
                "config": {}
            }
        ],
        "edges": [
            {"source": "start", "target": "reimbursement", "condition": {"task_type": "reimbursement"}},
            {"source": "start", "target": "invoice", "condition": {"task_type": "invoice"}},
            {"source": "start", "target": "budget", "condition": {"task_type": "budget"}},
            {"source": "reimbursement", "target": "end"},
            {"source": "invoice", "target": "end"},
            {"source": "budget", "target": "end"}
        ],
        "entry": "start"
    }
}

# 所有模板
ALL_TEMPLATES = [
    CUSTOMER_SERVICE_TEMPLATE,
    SALES_ASSISTANT_TEMPLATE,
    HR_ASSISTANT_TEMPLATE,
    FINANCE_ASSISTANT_TEMPLATE,
]


def get_templates_by_category(category: str = None) -> List[Dict]:
    """按分类获取模板"""
    if not category:
        return ALL_TEMPLATES
    
    return [t for t in ALL_TEMPLATES if t["category"] == category]


def get_template_by_name(name: str) -> Dict:
    """按名称获取模板"""
    for template in ALL_TEMPLATES:
        if template["name"] == name:
            return template
    return None
