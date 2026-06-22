"""
测试工作流引擎
"""
import pytest

from ..workflows.engine import WorkflowEngine


class TestWorkflowEngine:
    """工作流引擎测试"""
    
    def test_validate_workflow_valid(self):
        """测试有效工作流验证"""
        engine = WorkflowEngine()
        
        workflow = {
            "nodes": [
                {"id": "start", "type": "start", "label": "开始"},
                {"id": "llm1", "type": "llm", "label": "LLM 节点"},
                {"id": "end", "type": "output", "label": "结束"},
            ],
            "edges": [
                {"from": "start", "to": "llm1"},
                {"from": "llm1", "to": "end"},
            ],
        }
        
        is_valid, errors = engine.validate(workflow)
        assert is_valid is True
        assert len(errors) == 0
    
    def test_validate_workflow_missing_start(self):
        """测试缺少开始节点"""
        engine = WorkflowEngine()
        
        workflow = {
            "nodes": [
                {"id": "llm1", "type": "llm", "label": "LLM 节点"},
                {"id": "end", "type": "output", "label": "结束"},
            ],
            "edges": [
                {"from": "llm1", "to": "end"},
            ],
        }
        
        is_valid, errors = engine.validate(workflow)
        assert is_valid is False
        assert any("start" in e.lower() for e in errors)
    
    def test_validate_workflow_missing_end(self):
        """测试缺少结束节点"""
        engine = WorkflowEngine()
        
        workflow = {
            "nodes": [
                {"id": "start", "type": "start", "label": "开始"},
                {"id": "llm1", "type": "llm", "label": "LLM 节点"},
            ],
            "edges": [
                {"from": "start", "to": "llm1"},
            ],
        }
        
        is_valid, errors = engine.validate(workflow)
        assert is_valid is False
        assert any("end" in e.lower() or "output" in e.lower() for e in errors)
    
    def test_validate_workflow_invalid_edge(self):
        """测试无效边"""
        engine = WorkflowEngine()
        
        workflow = {
            "nodes": [
                {"id": "start", "type": "start", "label": "开始"},
                {"id": "end", "type": "output", "label": "结束"},
            ],
            "edges": [
                {"from": "start", "to": "nonexistent"},
            ],
        }
        
        is_valid, errors = engine.validate(workflow)
        assert is_valid is False
    
    def test_get_execution_order(self):
        """测试执行顺序"""
        engine = WorkflowEngine()
        
        workflow = {
            "nodes": [
                {"id": "start", "type": "start"},
                {"id": "a", "type": "llm"},
                {"id": "b", "type": "llm"},
                {"id": "end", "type": "output"},
            ],
            "edges": [
                {"from": "start", "to": "a"},
                {"from": "a", "to": "b"},
                {"from": "b", "to": "end"},
            ],
        }
        
        order = engine.get_execution_order(workflow)
        assert order[0] == "start"
        assert order[-1] == "end"
        assert "a" in order
        assert "b" in order
