import { memo } from 'react'
import { Handle, Position, NodeProps } from 'reactflow'
import { Send } from 'lucide-react'

export const ResponseNode = memo(({ data, selected }: NodeProps) => {
  return (
    <div className={`relative group ${selected ? 'scale-105' : ''} transition-transform`}>
      {/* Glow effect */}
      <div className="absolute -inset-1 bg-gradient-to-r from-indigo-500 to-purple-500 rounded-2xl blur opacity-20 group-hover:opacity-40 transition-opacity" />
      
      {/* Main card */}
      <div className="relative bg-white rounded-2xl border-2 border-indigo-200 shadow-lg overflow-hidden min-w-[180px]">
        {/* Gradient header */}
        <div className="bg-gradient-to-r from-indigo-500 to-purple-500 px-4 py-3">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-white/20">
              <Send className="w-4 h-4 text-white" />
            </div>
            <span className="text-sm font-semibold text-white">响应</span>
          </div>
        </div>

        {/* Content */}
        <div className="p-4">
          <div className="font-medium text-slate-900 mb-1">{data.label}</div>
          <div className="text-xs text-slate-500 mb-2">{data.description}</div>
          <div className="text-xs text-indigo-600 bg-indigo-50 px-2 py-1 rounded-lg inline-block">
            回复用户
          </div>
        </div>

        {/* Handles */}
        <Handle
          type="target"
          position={Position.Top}
          className="!w-3 !h-3 !bg-indigo-500 !border-2 !border-white !top-[-6px]"
        />
      </div>
    </div>
  )
})

ResponseNode.displayName = 'ResponseNode'
