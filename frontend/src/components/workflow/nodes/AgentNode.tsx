import { memo } from 'react'
import { NodeProps } from 'reactflow'
import { Bot } from 'lucide-react'
import { NodeBadge, NodeMeta, NodeShell, NodeTitle } from './NodeShell'

/** Agent 节点：调用另一个 Agent（pi Agent 执行）。 */
export const AgentNode = memo(({ id, data, selected }: NodeProps) => {
  const skills: string[] = Array.isArray(data.skills) ? data.skills : []

  return (
    <NodeShell
      id={id}
      selected={selected}
      accent="bg-sky-500"
      icon={<Bot className="w-3.5 h-3.5" />}
      typeLabel="Agent"
    >
      <NodeTitle>{data.label}</NodeTitle>
      <NodeMeta>
        {data.agent_name ||
          (data.agent_id ? `Agent ${String(data.agent_id).slice(0, 8)}` : '当前 Agent')}
      </NodeMeta>
      {skills.length > 0 ? (
        <div>
          <NodeBadge>{skills.join('、')}</NodeBadge>
        </div>
      ) : null}
    </NodeShell>
  )
})

AgentNode.displayName = 'AgentNode'
