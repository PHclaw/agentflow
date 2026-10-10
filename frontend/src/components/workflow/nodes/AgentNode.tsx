import { memo } from 'react'
import { Handle, Position, NodeProps } from 'reactflow'
import { Bot } from 'lucide-react'

export const AgentNode = memo(({ data, selected }: NodeProps) => {
  const skills: string[] = Array.isArray(data.skills) ? data.skills : []

  return (
    <div className={`relative group ${selected ? 'scale-105' : ''} transition-transform`}>
      {/* Glow effect */}
      <div className="absolute -inset-1 bg-gradient-to-r from-sky-500 to-brand-500 rounded-2xl blur opacity-20 group-hover:opacity-40 transition-opacity" />

      {/* Main card */}
      <div className="relative bg-white rounded-2xl border-2 border-sky-200 shadow-lg overflow-hidden min-w-[200px]">
        {/* Gradient header */}
        <div className="bg-gradient-to-r from-sky-500 to-brand-500 px-4 py-3">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-white/20">
              <Bot className="w-4 h-4 text-white" />
            </div>
            <span className="text-sm font-semibold text-white">智能体</span>
          </div>
        </div>

        {/* Content */}
        <div className="p-4">
          <div className="font-medium text-slate-900 mb-1">{data.label}</div>
          <div className="text-xs text-slate-500 mb-2">
            {data.agent_name ||
              (data.agent_id ? `Agent ${String(data.agent_id).slice(0, 8)}` : '当前 Agent')}
          </div>
          {skills.length > 0 ? (
            <div className="flex flex-wrap gap-1">
              {skills.slice(0, 3).map((s) => (
                <span
                  key={s}
                  className="text-[11px] px-1.5 py-0.5 rounded-md bg-sky-50 text-sky-700"
                >
                  {s}
                </span>
              ))}
              {skills.length > 3 && (
                <span className="text-[11px] px-1.5 py-0.5 rounded-md bg-slate-100 text-slate-500">
                  +{skills.length - 3}
                </span>
              )}
            </div>
          ) : (
            <div className="text-xs text-slate-400 bg-slate-50 px-2 py-1 rounded-lg inline-block">
              未指定技能
            </div>
          )}
        </div>

        {/* Handles */}
        <Handle
          type="target"
          position={Position.Top}
          className="!w-3 !h-3 !bg-sky-500 !border-2 !border-white !top-[-6px]"
        />
        <Handle
          type="source"
          position={Position.Bottom}
          className="!w-3 !h-3 !bg-sky-500 !border-2 !border-white !bottom-[-6px]"
        />
      </div>
    </div>
  )
})

AgentNode.displayName = 'AgentNode'