import { memo } from 'react'
import { NodeProps } from 'reactflow'
import { Cpu } from 'lucide-react'
import { NodeBadge, NodeMeta, NodeShell, NodeTitle } from './NodeShell'

/**
 * LLM 节点。
 *
 * `data.model` 留空表示「跟随生效配置的模型」，所以这里不能拿它跟某个
 * 硬编码默认值比较 —— 只判断有没有配。
 */
export const LLMNode = memo(({ id, data, selected }: NodeProps) => {
  return (
    <NodeShell
      id={id}
      selected={selected}
      accent="bg-purple-500"
      icon={<Cpu className="w-3.5 h-3.5" />}
      typeLabel="LLM"
    >
      <NodeTitle>{data.label}</NodeTitle>
      <NodeMeta>{data.model || '跟随生效配置'}</NodeMeta>
      <div>
        <NodeBadge>{data.prompt ? '已配置提示词' : '未配置提示词'}</NodeBadge>
      </div>
    </NodeShell>
  )
})

LLMNode.displayName = 'LLMNode'
