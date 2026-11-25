import { memo } from 'react'
import { Handle, Position, NodeProps } from 'reactflow'
import { GitBranch } from 'lucide-react'
import { NodeMeta, NodeShell, NodeTitle } from './NodeShell'

/** 条件分支节点。有左右两个出边（是 / 否），不用 NodeShell 的底部连接点。 */
export const ConditionNode = memo(({ id, data, selected }: NodeProps) => {
  return (
    <NodeShell
      id={id}
      selected={selected}
      accent="bg-amber-500"
      icon={<GitBranch className="w-3.5 h-3.5" />}
      typeLabel="条件"
      hasSource={false}
    >
      <NodeTitle>{data.label}</NodeTitle>
      {data.description && <NodeMeta>{data.description}</NodeMeta>}

      <div className="mt-2 flex gap-2">
        <span className="text-2xs px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400">
          是
        </span>
        <span className="text-2xs px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400">
          否
        </span>
      </div>

      {/* 条件节点的两个出口在左右两侧，父组件的 hasSource={false} 已经
          避开了底部连接点，这里单独补上 */}
      <Handle
        type="source"
        position={Position.Right}
        id="true"
        className="!w-2.5 !h-2.5 !bg-slate-300 dark:!bg-slate-600 !border-2 !border-white dark:!border-slate-900"
      />
      <Handle
        type="source"
        position={Position.Left}
        id="false"
        className="!w-2.5 !h-2.5 !bg-slate-300 dark:!bg-slate-600 !border-2 !border-white dark:!border-slate-900"
      />
    </NodeShell>
  )
})

ConditionNode.displayName = 'ConditionNode'
