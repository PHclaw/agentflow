"""
工作流执行 API
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
import json
import asyncio

from ..core.database import get_db
from ..models.subscription import Subscription
from ..services.entitlement import (
    Resource,
    check as check_quota,
    consume as consume_quota,
)
from ..services.workflow_runtime import (
    workflow_runtime,
    NodeStatus,
    extract_final_response,
    normalize_workflow_definition,
)
from app.api.auth import get_current_user_id
from app.api.deps import current_subscription

router = APIRouter(dependencies=[Depends(get_current_user_id)])


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


def _with_caller(input_data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """把登录用户注入为 caller_id，供 erp_read 等工具做归属校验。

    聊天链路（run_workflow_turn）本就会带 caller_id；编辑器的 /workflow/*
    此前直接透传 input_data、没有这个字段，导致连接器工具在测试运行时
    拿不到调用者身份。这里统一补齐，两条入口口径一致。
    已有 caller_id（如内部调用）不覆盖。
    """
    merged = {**(input_data or {})}
    merged.setdefault("caller_id", user_id)
    return merged


@router.post("/execute")
async def execute_workflow(
    request: WorkflowExecutionRequest,
    db: AsyncSession = Depends(get_db),
    sub: Subscription = Depends(current_subscription),
    user_id: str = Depends(get_current_user_id),
):
    """执行完整工作流"""
    # 画布上的 LLM / 智能体节点会真的调模型，跑一次就该记一次
    await check_quota(db, sub, Resource.MESSAGES)

    try:
        state = await workflow_runtime.execute_workflow(
            workflow_def=request.workflow_definition,
            input_data=_with_caller(request.input_data, user_id),
            db_session=db,
        )
        
        # 取最终结果（原实现用枚举与字符串比较，恒为假，final_output 一直是 null）
        final_output = extract_final_response(state)
        
        result = {
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

    await consume_quota(db, sub, Resource.MESSAGES)
    await db.commit()
    return result


@router.post("/execute/node")
async def execute_single_node(
    request: NodeExecutionRequest,
    db: AsyncSession = Depends(get_db),
    sub: Subscription = Depends(current_subscription),
    user_id: str = Depends(get_current_user_id),
):
    """执行单个节点"""
    await check_quota(db, sub, Resource.MESSAGES)

    try:
        result = await workflow_runtime.execute_node(
            workflow_def=request.workflow_definition,
            node_id=request.node_id,
            input_data=_with_caller(request.input_data, user_id),
            db_session=db,
        )
        
        payload = {
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

    await consume_quota(db, sub, Resource.MESSAGES)
    await db.commit()
    return payload


@router.post("/execute/stream")
async def execute_workflow_stream(
    request: WorkflowExecutionRequest,
    db: AsyncSession = Depends(get_db),
    sub: Subscription = Depends(current_subscription),
    user_id: str = Depends(get_current_user_id),
):
    """执行工作流 - 流式输出"""
    # 与 /execute 一致：额度检查放在返回 StreamingResponse 之前，
    # 这样超额是个正常的 402 响应，而不是变成流里的一个 error 事件
    await check_quota(db, sub, Resource.MESSAGES)

    async def generate():
        # 执行放进后台任务，事件通过队列回传。
        #
        # 之前的写法是先把 execute_workflow 整个 await 完，再回头遍历
        # execution_history 一条条 yield —— 那只是"分几次写出去"，事件在
        # 时间上仍然全部发生在执行结束之后。编辑器的节点进度因此永远停在
        # 起点，跑完才齐刷刷变绿。用队列之后，每推进一步就能立刻发出去。
        queue: "asyncio.Queue[Optional[dict]]" = asyncio.Queue()

        async def on_event(evt: dict):
            await queue.put(evt)

        async def run():
            try:
                state = await workflow_runtime.execute_workflow(
                    workflow_def=request.workflow_definition,
                    input_data=_with_caller(request.input_data, user_id),
                    db_session=db,
                    on_event=on_event,
                )

                # 跑完才计数：中途抛异常的那次不算
                await consume_quota(db, sub, Resource.MESSAGES)
                await db.commit()

                # 最终结果用一条哨兵事件带出来，避免再往队列里塞一个大对象
                await queue.put({"_final_output": extract_final_response(state)})
            except Exception as e:  # noqa: BLE001 - 任何异常都要变成流里的 error 事件
                await queue.put({"type": "error", "error": str(e)})
            finally:
                # 结束哨兵。放 finally 里，异常路径也不能让外面一直等着
                await queue.put(None)

        task = asyncio.create_task(run())

        try:
            while True:
                evt = await queue.get()
                if evt is None:
                    break

                if "_final_output" in evt:
                    yield f"data: {json.dumps({
                        'type': 'complete',
                        'final_output': evt['_final_output'],
                    })}\n\n"
                    continue

                yield f"data: {json.dumps(evt)}\n\n"

                # 节点产出里有文字的话，再按小块吐一遍，做出"边生成边显示"的
                # 观感（真正的逐 token 需要模型层支持回调，这里只能做到这样）
                if evt.get("type") == "node_complete":
                    text = (evt.get("outputs") or {}).get("response")
                    if isinstance(text, str) and text:
                        for i in range(0, len(text), 10):
                            yield f"data: {json.dumps({
                                'type': 'llm_chunk',
                                'node_id': evt.get('node_id'),
                                'chunk': text[i:i + 10],
                            })}\n\n"
                            await asyncio.sleep(0.01)
        finally:
            # 客户端中途断开时别把任务留在后台空转。
            # 代价是这次不计额度 —— 流式接口本来就有这个缺口。
            if not task.done():
                task.cancel()

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
    db: AsyncSession = Depends(get_db),
    sub: Subscription = Depends(current_subscription),
    user_id: str = Depends(get_current_user_id),
):
    """测试工作流配置"""
    # 编辑器里的「测试运行」同样是真跑一遍，一样消耗模型额度
    await check_quota(db, sub, Resource.MESSAGES)

    workflow_def = normalize_workflow_definition(
        {"nodes": request.nodes, "edges": request.edges}
    )
    
    try:
        state = await workflow_runtime.execute_workflow(
            workflow_def=workflow_def,
            input_data=_with_caller(request.input_data, user_id),
            db_session=db,
        )
        
        payload = {
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

    await consume_quota(db, sub, Resource.MESSAGES)
    await db.commit()
    return payload


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
