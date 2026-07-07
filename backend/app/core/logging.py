"""日志系统 - 结构化日志记录"""
import logging
import sys
from datetime import datetime
from typing import Optional
from pathlib import Path
import json

# 配置日志格式
class JSONFormatter(logging.Formatter):
    """JSON 格式日志"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # 添加额外字段
        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        if hasattr(record, "agent_id"):
            log_data["agent_id"] = record.agent_id
        if hasattr(record, "duration"):
            log_data["duration_ms"] = record.duration
        
        # 添加异常信息
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)


class ColoredFormatter(logging.Formatter):
    """带颜色的日志格式"""
    
    COLORS = {
        "DEBUG": "\033[36m",    # 青色
        "INFO": "\033[32m",     # 绿色
        "WARNING": "\033[33m",  # 黄色
        "ERROR": "\033[31m",    # 红色
        "CRITICAL": "\033[35m", # 紫色
    }
    RESET = "\033[0m"
    
    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


def setup_logging(level: str = "INFO", log_file: Optional[str] = None):
    """配置日志系统"""
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    
    # 清除现有处理器
    root_logger.handlers.clear()
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_formatter = ColoredFormatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%H:%M:%S"
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # 文件处理器（JSON 格式）
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(file_handler)


# 便捷的日志记录器
def get_logger(name: str) -> logging.Logger:
    """获取日志记录器"""
    return logging.getLogger(name)


class RequestLogger:
    """请求日志中间件"""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
    
    async def log_request(self, request, response=None, error=None, duration_ms: float = None):
        """记录请求"""
        log_data = {
            "method": request.method,
            "path": request.url.path,
            "client": request.client.host if request.client else "unknown",
        }
        
        if duration_ms is not None:
            log_data["duration_ms"] = round(duration_ms, 2)
        
        if response:
            log_data["status_code"] = response.status_code
        
        if error:
            log_data["error"] = str(error)
        
        if error:
            self.logger.error(f"Request failed: {json.dumps(log_data)}")
        else:
            self.logger.info(f"Request: {json.dumps(log_data)}")


# 全局日志记录器实例
logger = get_logger("agentflow")


class WorkflowLogger:
    """工作流执行日志"""
    
    def __init__(self, workflow_id: str, user_id: str = None):
        self.workflow_id = workflow_id
        self.user_id = user_id
        self.logger = get_logger(f"workflow.{workflow_id}")
        self.events: list = []
    
    def log_node_start(self, node_id: str, node_type: str, inputs: dict):
        """记录节点开始"""
        event = {
            "type": "node_start",
            "node_id": node_id,
            "node_type": node_type,
            "inputs": inputs,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.events.append(event)
        self.logger.info(f"Node started: {node_id} ({node_type})")
    
    def log_node_complete(self, node_id: str, outputs: dict, duration_ms: float):
        """记录节点完成"""
        event = {
            "type": "node_complete",
            "node_id": node_id,
            "outputs": outputs,
            "duration_ms": duration_ms,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.events.append(event)
        self.logger.info(f"Node completed: {node_id} in {duration_ms:.2f}ms")
    
    def log_node_error(self, node_id: str, error: str):
        """记录节点错误"""
        event = {
            "type": "node_error",
            "node_id": node_id,
            "error": error,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.events.append(event)
        self.logger.error(f"Node error: {node_id} - {error}")
    
    def get_events(self) -> list:
        """获取所有事件"""
        return self.events
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "workflow_id": self.workflow_id,
            "user_id": self.user_id,
            "events": self.events,
            "total_events": len(self.events)
        }
