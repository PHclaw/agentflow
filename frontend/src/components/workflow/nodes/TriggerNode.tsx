import { memo } from 'react'
import { NodeProps } from 'reactflow'
import { MessageSquare } from 'lucide-react'
import { NodeMeta, NodeShell, NodeTitle } from './NodeShell'

/** 触发器节点：画布的起点。 */
export const TriggerNode = memo(({ id, data, selected }: NodeProps) => {
  return (
    <NodeShell
      id={id}
      selected={selected}
      accent="bg-blue-500"
      icon={<MessageSquare className="w-3.5 h-3.5" />}
      typeLabel="触发器"
      hasSource
    >
      <NodeTitle>{data.label}</NodeTitle>
      {data.description && <NodeMeta>{data.description}</NodeMeta>}
    </NodeShell>
  )
})

TriggerNode.displayName = 'TriggerNode'
