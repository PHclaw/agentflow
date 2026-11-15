import { memo } from 'react'
import { NodeProps } from 'reactflow'
import { Database } from 'lucide-react'
import { NodeBadge, NodeShell, NodeTitle } from './NodeShell'

/** 知识库检索节点。 */
export const KnowledgeNode = memo(({ id, data, selected }: NodeProps) => {
  return (
    <NodeShell
      id={id}
      selected={selected}
      accent="bg-emerald-500"
      icon={<Database className="w-3.5 h-3.5" />}
      typeLabel="知识库"
    >
      <NodeTitle>{data.label}</NodeTitle>
      <div>
        <NodeBadge>{data.documents || '0'} 个文档</NodeBadge>
      </div>
    </NodeShell>
  )
})

KnowledgeNode.displayName = 'KnowledgeNode'
