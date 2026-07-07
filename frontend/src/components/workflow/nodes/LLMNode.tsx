import { memo } from 'react'
import { Handle, Position, NodeProps } from 'reactflow'
import { Cpu } from 'lucide-react'

export const LLMNode = memo(({ data, selected }: NodeProps) => {
  return (
    <div className={`relative group ${selected ? 'scale-105' : ''} transition-transform`}>
      {/* Glow effect */}
      <div className="absolute -inset-1 bg-gradient-to-r from-purple-500 to-violet-500 rounded-2xl blur opacity-20 group-hover:opacity-40 transition-opacity" />
      
      {/* Main card */}
      <div className="relative bg-white rounded-2xl border-2 border-purple-200 shadow-lg overflow-hidden min-w-[180px]">
        {/* Gradient header */}
        <div className="bg-gradient-to-r from-purple-500 to-violet-500 px-4 py-3">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-white/20">
              <Cpu className="w-4 h-4 text-white" />
            </div>
            <span className="text-sm font-semibold text-white">LLM</span>
          </div>
        </div>

        {/* Content */}
        <div className="p-4">
          <div className="font-medium text-slate-900 mb-1">{data.label}</div>
          <div className="text-xs text-slate-500 mb-2">
            {data.model || 'gpt-4'}
          </div>
          <div className="text-xs text-purple-600 bg-purple-50 px-2 py-1 rounded-lg inline-block">
            {data.prompt ? '已配置提示词' : '未配置提示词'}
          </div>
        </div>

        {/* Handles */}
        <Handle
          type="target"
          position={Position.Top}
          className="!w-3 !h-3 !bg-purple-500 !border-2 !border-white !top-[-6px]"
        />
        <Handle
          type="source"
          position={Position.Bottom}
          className="!w-3 !h-3 !bg-purple-500 !border-2 !border-white !bottom-[-6px]"
        />
      </div>
    </div>
  )
})

LLMNode.displayName = 'LLMNode'
