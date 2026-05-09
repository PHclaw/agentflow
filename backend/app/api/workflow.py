"""
工作流执行 API
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional, AsyncIterator
from sqlalchemy.ext.asyncio import AsyncSession
import json

from ..core.database import get_db
from ..services.workflow_runtime import workflow_runtime, NodeStatus

router = APIRouter(prefix="/api/v1/workflow", tags=["工作流"])


class WorkflowExecutionRequest(BaseModel):
    workflow_definition: Dict[str, Any]
    input_data: Dict[str, Any] = {}


class NodeExecutionRequest(BaseModel):
    workflow_definition: Dict[str, Any]
    node_id: str
    input_data: Dict[str, Any] = {}


class WorkflowTestRequest(BaseModel):
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    input_data: Dict[str, Any] = {}


@router.post("/execute")
async def execute_workflow(
    request: WorkflowExecutionRequest,
    db: AsyncSession = Depends(get_db)
):
    """执行完整工作流"""
    try:
        state = await workflow_runtime.execute_workflow(
            workflow_def=request.workflow_definition,
            input_data=request.input_data,
            db_session=db,
        )
        
        # 获取最终结果
        final_output = None
        for node_result in reversed(state.execution_history):
            if node_result.status == NodeStatus.SUCCESS.value:
                outputs = state.node_outputs.get(node_result.node_id, {})
                if "final_response" in outputs:
                    final_output = outputs["final_response"]
                    break
                elif "response" in outputs:
                    final_output = outputs["response"]
                    break
        
        return {
            "success": True,
            "workflow_id": state.workflow_id,
            "final_output": final_output,
            "context": state.context,
            "node_outputs": state.node_outputs,
            "execution_history": [
                {
                    "node_id": r.node_id,
                    "status": r.status.value,
                    "execution_time": r.execution_time,
                    "error": r.error,
                }
                for r in state.execution_history
            ],
        }
        
    except Exception as e:
        raise HTTPException(500, f"工作流执行失败: {str(e)}")


@router.post("/execute/node")
async def execute_single_node(
    request: NodeExecutionRequest,
    db: AsyncSession = Depends(get_db)
):
    """执行单个节点"""
    try:
        result = await workflow_runtime.execute_node(
            workflow_def=request.workflow_definition,
            node_id=request.node_id,
            input_data=request.input_data,
            db_session=db,
        )
        
        return {
            "success": result.status == NodeStatus.SUCCESS,
            "node_id": result.node_id,
            "status": result.status.value,
            "outputs": {
                out.key: out.value for out in result.outputs
            } if hasattr(result, 'outputs') else {},
            "error": result.error,
            "execution_time": result.execution_time,
        }
        
    except Exception as e:
        raise HTTPException(500, f"节点执行失败: {str(e)}")


@router.post("/execute/stream")
async def execute_workflow_stream(
    request: WorkflowExecutionRequest,
    db: AsyncSession = Depends(get_db)
):
    """执行工作流 - 流式输出"""
    async def generate():
        try:
            # 执行工作流
            state = await workflow_runtime.execute_workflow(
                workflow_def=request.workflow_definition,
                input_data=request.input_data,
                db_session=db,
            )
            
            # 逐个发送节点执行结果
            for node_result in state.execution_history:
                outputs = state.node_outputs.get(node_result.node_id, {})
                
                yield f"data: {json.dumps({
                    'type': 'node_complete',
                    'node_id': node_result.node_id,
                    'status': node_result.status.value,
                    'outputs': outputs,
                    'execution_time': node_result.execution_time,
                })}\n\n"
                
                # 模拟流式输出（如果是 LLM 节点）
                if "response" in outputs and isinstance(outputs["response"], str):
                    # 逐字符发送（模拟）
                    for i in range(0, len(outputs["response"]), 10):
                        chunk = outputs["response"][i:i+10]
                        yield f"data: {json.dumps({
                            'type': 'llm_chunk',
                            'node_id': node_result.node_id,
                            'chunk': chunk,
                        })}\n\n"
                        await asyncio.sleep(0.01)
            
            # 最终结果
            final_output = None
            for node_result in reversed(state.execution_history):
                if node_result.status == NodeStatus.SUCCESS.value:
                    outputs = state.node_outputs.get(node_result.node_id, {})
                    if "final_response" in outputs:
                        final_output = outputs["final_response"]
                        break
                    elif "response" in outputs:
                        final_output = outputs["response"]
                        break
            
            yield f"data: {json.dumps({
                'type': 'complete',
                'final_output': final_output,
            })}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
        
        yield "data: [DONE]\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.post("/test")
async def test_workflow(
    request: WorkflowTestRequest,
    db: AsyncSession = Depends(get_db)
):
    """测试工作流配置"""
    workflow_def = {
        "nodes": request.nodes,
        "edges": request.edges,
    }
    
    try:
        state = await workflow_runtime.execute_workflow(
            workflow_def=workflow_def,
            input_data=request.input_data,
            db_session=db,
        )
        
        return {
            "success": True,
            "execution_order": workflow_runtime.get_execution_order(
                request.nodes, request.edges
            ),
            "node_outputs": state.node_outputs,
            "execution_history": [
                {
                    "node_id": r.node_id,
                    "status": r.status.value,
                    "error": r.error,
                }
                for r in state.execution_history
            ],
        }
        
    except Exception as e:
        raise HTTPException(500, f"测试失败: {str(e)}")


@router.get("/execution-order")
async def get_execution_order(
    nodes: str,  # JSON string
    edges: str,  # JSON string
):
    """获取节点执行顺序"""
    try:
        nodes_list = json.loads(nodes)
        edges_list = json.loads(edges)
        
        order = workflow_runtime.get_execution_order(nodes_list, edges_list)
        
        return {
            "order": order,
        }
        
    except Exception as e:
        raise HTTPException(400, f"解析失败: {str(e)}")


# 添加 asyncio 导入
import asyncio
