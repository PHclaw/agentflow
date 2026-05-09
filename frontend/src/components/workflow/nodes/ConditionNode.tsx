import { memo } from 'react'
import { Handle, Position, NodeProps } from 'reactflow'
import { GitBranch } from 'lucide-react'

export const ConditionNode = memo(({ data, selected }: NodeProps) => {
  return (
    <div className={`relative group ${selected ? 'scale-105' : ''} transition-transform`}>
      {/* Glow effect */}
      <div className="absolute -inset-1 bg-gradient-to-r from-amber-500 to-orange-500 rounded-2xl blur opacity-20 group-hover:opacity-40 transition-opacity" />
      
      {/* Main card */}
      <div className="relative bg-white rounded-2xl border-2 border-amber-200 shadow-lg overflow-hidden min-w-[180px]">
        {/* Gradient header */}
        <div className="bg-gradient-to-r from-amber-500 to-orange-500 px-4 py-3">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-white/20">
              <GitBranch className="w-4 h-4 text-white" />
            </div>
            <span className="text-sm font-semibold text-white">条件</span>
          </div>
        </div>

        {/* Content */}
        <div className="p-4">
          <div className="font-medium text-slate-900 mb-1">{data.label}</div>
          <div className="text-xs text-slate-500 mb-2">{data.description}</div>
          <div className="flex gap-2">
            <span className="text-xs px-2 py-0.5 rounded bg-green-50 text-green-600">是</span>
            <span className="text-xs px-2 py-0.5 rounded bg-red-50 text-red-600">否</span>
          </div>
        </div>

        {/* Handles */}
        <Handle
          type="target"
          position={Position.Top}
          className="!w-3 !h-3 !bg-amber-500 !border-2 !border-white !top-[-6px]"
        />
        <Handle
          type="source"
          position={Position.Bottom}
          id="yes"
          style={{ left: '30%' }}
          className="!w-3 !h-3 !bg-green-500 !border-2 !border-white !bottom-[-6px]"
        />
        <Handle
          type="source"
          position={Position.Bottom}
          id="no"
          style={{ left: '70%' }}
          className="!w-3 !h-3 !bg-red-500 !border-2 !border-white !bottom-[-6px]"
        />
      </div>
    </div>
  )
})

ConditionNode.displayName = 'ConditionNode'
