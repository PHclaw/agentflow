import { memo } from 'react'
import { NodeProps } from 'reactflow'
import { Wrench } from 'lucide-react'
import { NodeBadge, NodeMeta, NodeShell, NodeTitle } from './NodeShell'

/** 工具调用节点。 */
export const ToolNode = memo(({ id, data, selected }: NodeProps) => {
  return (
    <NodeShell
      id={id}
      selected={selected}
      accent="bg-pink-500"
      icon={<Wrench className="w-3.5 h-3.5" />}
      typeLabel="工具"
    >
      <NodeTitle>{data.label}</NodeTitle>
      {data.description && <NodeMeta>{data.description}</NodeMeta>}
      <div>
        <NodeBadge>{data.tools || '0'} 个工具</NodeBadge>
      </div>
    </NodeShell>
  )
})

ToolNode.displayName = 'ToolNode'
