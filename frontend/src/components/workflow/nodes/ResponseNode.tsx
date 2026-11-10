import { memo } from 'react'
import { NodeProps } from 'reactflow'
import { Send } from 'lucide-react'
import { NodeBadge, NodeMeta, NodeShell, NodeTitle } from './NodeShell'

/**
 * 回复节点：工作流的终点。
 *
 * 色条用**中性灰**而不是 2.0.2 的 `indigo-500` —— 2.0.2 的 LLM 节点用的是
 * `purple-500`，而它的配置把 indigo / purple 映射到同一个色阶，两种节点会
 * 长得一模一样。终点节点本来就「不再加工」，用中性表达比再占一个彩色更准。
 */
export const ResponseNode = memo(({ id, data, selected }: NodeProps) => {
  return (
    <NodeShell
      id={id}
      selected={selected}
      accent="bg-slate-500"
      icon={<Send className="w-3.5 h-3.5" />}
      typeLabel="回复"
      hasTarget
      hasSource={false}
    >
      <NodeTitle>{data.label}</NodeTitle>
      {data.description && <NodeMeta>{data.description}</NodeMeta>}
      <div>
        <NodeBadge>回复用户</NodeBadge>
      </div>
    </NodeShell>
  )
})

ResponseNode.displayName = 'ResponseNode'
