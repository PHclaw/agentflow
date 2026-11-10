import { useCallback, useRef, useState } from 'react'
import type { Edge, Node } from 'reactflow'

/**
 * 工作流画布的撤销 / 重做。
 *
 * 为什么不用现成的撤销库：ReactFlow 的 `onNodesChange` 会把**拖拽中间帧**、
 * **选中态变化**这类不该进历史的细碎改动一起送进来，直接拿它当触发器的话，
 * 撤销栈里会塞满"往左挪了 3 像素"这种条目，点一次撤销几乎看不出变化。
 *
 * 所以入口刻意收窄，只有这几类算「一次操作」：
 *
 *   加节点 / 删节点 / 复制 / 连线 / 断线 / 拖动节点 / 改动配置项
 *
 * 后两类用「**开始前拍快照**」的方式记：`onNodeDragStart` 时拍一张、
 * 配置面板获得焦点时拍一张。于是"一次拖拽""一次连续编辑"都只占一格，
 * 而不是每帧一格、每个字符一格。
 *
 * 另外 `mark` 会做去重：快照和栈顶完全一样就不压栈。否则用户在输入框上
 * 点来点去却不改内容，也会攒出一串空条目，撤销时要连点几下才看到变化。
 */

export interface WorkflowSnapshot {
  nodes: Node[]
  edges: Edge[]
}

/** 栈容量。50 步足够回溯，也够小 —— 每格都是整张图的浅拷贝。 */
const LIMIT = 50

function signature(snap: WorkflowSnapshot): string {
  return (
    `${snap.nodes.length}|${snap.edges.length}|` +
    snap.nodes
      .map(
        (n) =>
          `${n.id}@${Math.round(n.position.x)},${Math.round(n.position.y)}:` +
          `${JSON.stringify(n.data)}`
      )
      .join(';')
  )
}

export function useWorkflowHistory(
  nodes: Node[],
  edges: Edge[],
  apply: (snap: WorkflowSnapshot) => void
) {
  const past = useRef<WorkflowSnapshot[]>([])
  const future = useRef<WorkflowSnapshot[]>([])
  const [, bump] = useState(0)

  const snapshot = useCallback((): WorkflowSnapshot => ({ nodes, edges }), [nodes, edges])

  /**
   * 记一格历史，**不改变当前内容**。
   * 用于拖拽开始、输入框获得焦点这类"接下来要改了"的时刻。
   */
  const mark = useCallback(() => {
    const last = past.current[past.current.length - 1]
    if (last && signature(last) === signature(snapshot())) return
    past.current.push(snapshot())
    if (past.current.length > LIMIT) past.current.shift()
    future.current = []
    bump((v) => v + 1)
  }, [snapshot])

  /** 记一格历史，同时应用新状态。用于加/删/连线这类一步完成的操作。 */
  const commit = useCallback(
    (next: WorkflowSnapshot) => {
      mark()
      apply(next)
    },
    [mark, apply]
  )

  const undo = useCallback(() => {
    const prev = past.current.pop()
    if (!prev) return
    future.current.push(snapshot())
    apply(prev)
    bump((v) => v + 1)
  }, [snapshot, apply])

  const redo = useCallback(() => {
    const next = future.current.pop()
    if (!next) return
    past.current.push(snapshot())
    apply(next)
    bump((v) => v + 1)
  }, [snapshot, apply])

  return {
    mark,
    commit,
    undo,
    redo,
    canUndo: past.current.length > 0,
    canRedo: future.current.length > 0,
  }
}
