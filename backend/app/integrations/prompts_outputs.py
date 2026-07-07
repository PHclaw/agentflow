"""
AgentFlow 整合 agent-prompt-templates 和 agent-output-parser

Phase 2: Prompt 模板 + 输出解析
"""
from typing import Dict, Any, List, Optional
import json
import re

# agent-prompt-templates 整合
try:
    from agent_prompt_templates import (
        ChainOfThoughtPrompt,
        ReActPrompt,
        FewShotPrompt,
        SystemPrompt
    )
    HAS_PROMPT_TEMPLATES = True
except ImportError:
    HAS_PROMPT_TEMPLATES = False

# agent-output-parser 整合
try:
    from agent_output_parser import (
        JSONParser,
        MarkdownParser,
        PydanticParser,
        RegexParser
    )
    HAS_OUTPUT_PARSER = True
except ImportError:
    HAS_OUTPUT_PARSER = False


class PromptManager:
    """
    整合 agent-prompt-templates 的提示词管理
    
    支持模板类型：
    - chain_of_thought: CoT 推理
    - react: ReAct 框架
    - few_shot: Few-shot 示例
    - system: 系统提示
    """
    
    def __init__(self):
        self._templates: Dict[str, Any] = {}
        self._load_default_templates()
    
    def _load_default_templates(self):
        """加载默认模板"""
        # 客服模板
        self._templates["customer_service"] = self._build_customer_service_template()
        
        # 销售助手模板
        self._templates["sales_assistant"] = self._build_sales_template()
        
        # HR 助手模板
        self._templates["hr_assistant"] = self._build_hr_template()
        
        # 通用问答模板
        self._templates["qa"] = self._build_qa_template()
    
    def _build_customer_service_template(self) -> Dict[str, Any]:
        """客服模板"""
        if HAS_PROMPT_TEMPLATES:
            return {
                "system": SystemPrompt(
                    role="customer_service",
                    instructions=[
                        "你是专业的客服代表",
                        "礼貌、耐心地回答用户问题",
                        "遇到无法解决的问题，引导用户转人工",
                    ]
                ),
                "react": ReActPrompt(
                    tools=["search_knowledge", "create_ticket", "transfer_human"]
                )
            }
        else:
            return {
                "system": {
                    "role": "system",
                    "content": """你是一名专业的客服代表。请遵循以下原则：
1. 礼貌、耐心地回答用户问题
2. 准确提供产品和服务信息
3. 遇到无法解决的问题，引导用户转人工客服
4. 保护用户隐私，不泄露敏感信息"""
                }
            }
    
    def _build_sales_template(self) -> Dict[str, Any]:
        """销售模板"""
        if HAS_PROMPT_TEMPLATES:
            return {
                "system": SystemPrompt(
                    role="sales_assistant",
                    instructions=[
                        "你是销售助手",
                        "帮助客户了解产品",
                        "生成报价和方案",
                    ]
                ),
                "cot": ChainOfThoughtPrompt(
                    reasoning_steps=[
                        "分析客户需求",
                        "匹配产品方案",
                        "生成报价",
                    ]
                )
            }
        else:
            return {
                "system": {
                    "role": "system",
                    "content": """你是一名销售助手。请遵循以下原则：
1. 了解客户需求，提供针对性方案
2. 清晰介绍产品优势和价格
3. 生成准确的报价单
4. 安排跟进和会议"""
                }
            }
    
    def _build_hr_template(self) -> Dict[str, Any]:
        """HR 模板"""
        return {
            "system": {
                "role": "system",
                "content": """你是一名 HR 助手。请遵循以下原则：
1. 准确回答公司政策和流程问题
2. 帮助员工办理假期、报销等事务
3. 保护员工隐私信息
4. 引导复杂问题联系 HR 部门"""
            }
        }
    
    def _build_qa_template(self) -> Dict[str, Any]:
        """通用问答模板"""
        if HAS_PROMPT_TEMPLATES:
            return {
                "few_shot": FewShotPrompt(
                    examples=[
                        {
                            "question": "产品价格是多少？",
                            "answer": "让我查询一下产品价格信息..."
                        },
                        {
                            "question": "如何退款？",
                            "answer": "退款流程如下：1. 登录账户 2. 进入订单 3. 申请退款..."
                        }
                    ]
                )
            }
        else:
            return {
                "system": {
                    "role": "system",
                    "content": "你是一个智能问答助手，请准确、简洁地回答用户问题。"
                }
            }
    
    def get_template(self, template_name: str) -> Dict[str, Any]:
        """获取模板"""
        return self._templates.get(template_name, self._templates["qa"])
    
    def build_messages(
        self,
        template_name: str,
        user_message: str,
        history: List[Dict] = None,
        context: str = None
    ) -> List[Dict]:
        """构建消息列表"""
        template = self.get_template(template_name)
        messages = []
        
        # 添加系统消息
        if "system" in template:
            system_content = template["system"]
            if HAS_PROMPT_TEMPLATES and hasattr(system_content, "render"):
                messages.append({"role": "system", "content": system_content.render()})
            elif isinstance(system_content, dict):
                messages.append(system_content)
            else:
                messages.append({"role": "system", "content": str(system_content)})
        
        # 添加上下文（RAG）
        if context:
            messages.append({
                "role": "system",
                "content": f"参考信息：\n{context}"
            })
        
        # 添加历史
        if history:
            messages.extend(history)
        
        # 添加用户消息
        messages.append({"role": "user", "content": user_message})
        
        return messages
    
    def register_template(self, name: str, template: Dict[str, Any]):
        """注册自定义模板"""
        self._templates[name] = template


class OutputParser:
    """
    整合 agent-output-parser 的输出解析
    
    支持解析：
    - JSON: 结构化数据
    - Markdown: 格式化文本
    - Tool Call: 工具调用
    - Action: 动作指令
    """
    
    def __init__(self):
        self._parsers = {}
        self._init_parsers()
    
    def _init_parsers(self):
        """初始化解析器"""
        if HAS_OUTPUT_PARSER:
            self._parsers["json"] = JSONParser()
            self._parsers["markdown"] = MarkdownParser()
            self._parsers["regex"] = RegexParser()
        else:
            self._parsers["json"] = self._fallback_json_parser
            self._parsers["markdown"] = self._fallback_markdown_parser
            self._parsers["tool_call"] = self._parse_tool_call
            self._parsers["action"] = self._parse_action
    
    def _fallback_json_parser(self, text: str) -> Dict[str, Any]:
        """回退 JSON 解析器"""
        # 尝试提取 JSON 块
        json_match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # 尝试直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"raw": text}
    
    def _fallback_markdown_parser(self, text: str) -> Dict[str, Any]:
        """回退 Markdown 解析器"""
        # 提取标题
        headers = re.findall(r'^#+\s+(.+)$', text, re.MULTILINE)
        
        # 提取列表
        lists = re.findall(r'^[-*]\s+(.+)$', text, re.MULTILINE)
        
        # 提取代码块
        code_blocks = re.findall(r'```(\w+)?\s*(.*?)\s*```', text, re.DOTALL)
        
        return {
            "headers": headers,
            "lists": lists,
            "code_blocks": [{"lang": lang, "code": code} for lang, code in code_blocks],
            "raw": text
        }
    
    def _parse_tool_call(self, text: str) -> Optional[Dict[str, Any]]:
        """解析工具调用"""
        # 格式: Action: tool_name\nAction Input: {...}
        action_match = re.search(r'Action:\s*(\w+)', text)
        input_match = re.search(r'Action Input:\s*(.+?)(?:\n|$)', text, re.DOTALL)
        
        if action_match:
            tool_name = action_match.group(1)
            tool_input = {}
            
            if input_match:
                try:
                    tool_input = json.loads(input_match.group(1).strip())
                except json.JSONDecodeError:
                    tool_input = {"raw": input_match.group(1).strip()}
            
            return {
                "tool": tool_name,
                "input": tool_input
            }
        
        return None
    
    def _parse_action(self, text: str) -> Optional[Dict[str, Any]]:
        """解析动作指令"""
        # 格式: [ACTION: type] content
        action_match = re.search(r'\[ACTION:\s*(\w+)\]\s*(.+)', text)
        
        if action_match:
            return {
                "type": action_match.group(1),
                "content": action_match.group(2).strip()
            }
        
        return None
    
    def parse(
        self,
        text: str,
        format: str = "auto"
    ) -> Dict[str, Any]:
        """
        解析输出
        
        Args:
            text: LLM 输出文本
            format: 解析格式 (json/markdown/tool_call/action/auto)
        
        Returns:
            解析结果字典
        """
        if format == "auto":
            # 自动检测格式
            if text.strip().startswith("{") or "```json" in text:
                format = "json"
            elif "Action:" in text:
                format = "tool_call"
            elif "[ACTION:" in text:
                format = "action"
            elif "#" in text or "```" in text:
                format = "markdown"
            else:
                format = "markdown"
        
        parser = self._parsers.get(format)
        
        if callable(parser):
            return parser(text)
        elif HAS_OUTPUT_PARSER and hasattr(parser, "parse"):
            return parser.parse(text)
        else:
            return {"raw": text}
    
    def validate_json(
        self,
        data: Dict[str, Any],
        schema: Dict[str, Any]
    ) -> bool:
        """验证 JSON 数据"""
        if HAS_OUTPUT_PARSER:
            try:
                parser = PydanticParser(schema=schema)
                parser.validate(data)
                return True
            except Exception:
                return False
        else:
            # 简单验证
            required = schema.get("required", [])
            return all(key in data for key in required)


# 全局实例
prompt_manager = PromptManager()
output_parser = OutputParser()
