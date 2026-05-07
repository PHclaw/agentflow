"""
整合模块测试
"""
import pytest


class TestConfigIntegration:
    """配置整合测试"""
    
    def test_config_import(self):
        """测试配置导入"""
        from ..integrations import config
        
        assert config is not None
    
    def test_config_get(self):
        """测试配置获取"""
        from ..integrations import config
        
        # 测试默认值
        value = config.get("NON_EXISTENT_KEY", "default_value")
        
        assert value == "default_value"


class TestTracerIntegration:
    """追踪整合测试"""
    
    def test_tracer_import(self):
        """测试追踪器导入"""
        from ..integrations import tracer
        
        assert tracer is not None
    
    def test_start_span(self):
        """测试开始追踪"""
        from ..integrations import tracer
        
        span_id = tracer.start_span(
            name="test_span",
            agent_id="test-agent",
            session_id="test-session",
        )
        
        assert span_id is not None
        
        # 结束追踪
        tracer.end_span(span_id)
    
    def test_get_stats(self):
        """测试获取统计"""
        from ..integrations import tracer
        
        stats = tracer.get_stats()
        
        assert isinstance(stats, dict)
