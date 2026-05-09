import { useCallback, useState } from 'react'
import {
  ReactFlow,
  MiniMap,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  addEdge,
  Connection,
  Node,
  Edge,
  BackgroundVariant,
  Panel,
  NodeProps,
} from 'reactflow'
import 'reactflow/dist/style.css'

import { Button } from '../ui/Button'
import { Input, Select } from '../ui/Input'
import { Card } from '../ui/Card'
import {
  Play,
  Save,
  Undo2,
  Redo2,
  ZoomIn,
  ZoomOut,
  Download,
  Upload,
  Plus,
  MessageSquare,
  Cpu,
  Database,
  Wrench,
  GitBranch,
  Send,
  Settings,
} from 'lucide-react'
import { TriggerNode } from './nodes/TriggerNode'
import { LLMNode } from './nodes/LLMNode'
import { KnowledgeNode } from './nodes/KnowledgeNode'
import { ToolNode } from './nodes/ToolNode'
import { ConditionNode } from './nodes/ConditionNode'
import { ResponseNode } from './nodes/ResponseNode'

const nodeTypes = {
  trigger: TriggerNode,
  llm: LLMNode,
  knowledge: KnowledgeNode,
  tool: ToolNode,
  condition: ConditionNode,
  response: ResponseNode,
}

const defaultNodes: Node[] = [
  {
    id: 'trigger-1',
    type: 'trigger',
    position: { x: 250, y: 0 },
    data: { label: '消息触发', description: '用户发送消息时触发' },
  },
  {
    id: 'llm-1',
    type: 'llm',
    position: { x: 250, y: 150 },
    data: { 
      label: '意图识别', 
      model: 'gpt-4',
      prompt: '分析用户意图，从以下类别中选择：客服咨询、产品购买、技术支持、其他'
    },
  },
]

const defaultEdges: Edge[] = [
  { id: 'e1-2', source: 'trigger-1', target: 'llm-1', animated: true },
]

const nodeCategories = [
  {
    name: '触发器',
    nodes: [
      { type: 'trigger', label: '消息触发', icon: MessageSquare, color: 'from-blue-500 to-cyan-500' },
    ],
  },
  {
    name: 'AI 能力',
    nodes: [
      { type: 'llm', label: 'LLM 对话', icon: Cpu, color: 'from-purple-500 to-violet-500' },
      { type: 'knowledge', label: '知识库', icon: Database, color: 'from-emerald-500 to-green-500' },
    ],
  },
  {
    name: '流程控制',
    nodes: [
      { type: 'condition', label: '条件分支', icon: GitBranch, color: 'from-amber-500 to-orange-500' },
      { type: 'tool', label: '工具调用', icon: Wrench, color: 'from-pink-500 to-rose-500' },
    ],
  },
  {
    name: '输出',
    nodes: [
      { type: 'response', label: '回复用户', icon: Send, color: 'from-indigo-500 to-purple-500' },
    ],
  },
]

interface WorkflowEditorProps {
  initialNodes?: Node[]
  initialEdges?: Edge[]
  onSave?: (nodes: Node[], edges: Edge[]) => void
}

export function WorkflowEditor({
  initialNodes: propNodes,
  initialEdges: propEdges,
  onSave,
}: WorkflowEditorProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState(propNodes || defaultNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(propEdges || defaultEdges)
  const [selectedNode, setSelectedNode] = useState<Node | null>(null)

  const onConnect = useCallback(
    (params: Connection) => setEdges((eds: Edge[]) => addEdge({ ...params, animated: true }, eds)),
    [setEdges]
  )

  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    setSelectedNode(node)
  }, [])

  const handleAddNode = (type: string, label: string) => {
    const newNode: Node = {
      id: `${type}-${Date.now()}`,
      type,
      position: { x: 250, y: (nodes.length + 1) * 150 },
      data: { label, description: '' },
    }
    setNodes((nds: Node[]) => [...nds, newNode])
  }

  const handleSave = useCallback(() => {
    if (onSave) {
      onSave(nodes, edges)
    }
  }, [nodes, edges, onSave])

  return (
    <div className="h-full flex flex-col bg-slate-100">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-3 bg-white border-b border-slate-200">
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" leftIcon={<Undo2 className="w-4 h-4" />}>
            撤销
          </Button>
          <Button variant="ghost" size="sm" leftIcon={<Redo2 className="w-4 h-4" />}>
            重做
          </Button>
          <div className="w-px h-6 bg-slate-200 mx-2" />
          <Button variant="ghost" size="sm" leftIcon={<ZoomOut className="w-4 h-4" />}>
            缩小
          </Button>
          <Button variant="ghost" size="sm" leftIcon={<ZoomIn className="w-4 h-4" />}>
            放大
          </Button>
        </div>

        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" leftIcon={<Download className="w-4 h-4" />}>
            导出
          </Button>
          <Button variant="outline" size="sm" leftIcon={<Upload className="w-4 h-4" />}>
            导入
          </Button>
          <Button variant="outline" size="sm" leftIcon={<Play className="w-4 h-4" />}>
            测试
          </Button>
          <Button size="sm" leftIcon={<Save className="w-4 h-4" />} onClick={handleSave} className="shadow-lg shadow-indigo-500/20">
            保存
          </Button>
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Left sidebar - Node palette */}
        <div className="w-64 bg-white border-r border-slate-200 overflow-y-auto">
          <div className="p-4">
            <h3 className="text-sm font-semibold text-slate-700 mb-4">节点组件</h3>
            
            {nodeCategories.map((category) => (
              <div key={category.name} className="mb-6">
                <h4 className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">
                  {category.name}
                </h4>
                <div className="space-y-2">
                  {category.nodes.map((node) => (
                    <button
                      key={node.type}
                      onClick={() => handleAddNode(node.type, node.label)}
                      className="w-full flex items-center gap-3 p-3 rounded-xl bg-slate-50 hover:bg-slate-100 border border-transparent hover:border-slate-200 transition-all group"
                    >
                      <div className={`p-2 rounded-lg bg-gradient-to-br ${node.color} shadow-sm group-hover:scale-110 transition-transform`}>
                        <node.icon className="w-4 h-4 text-white" />
                      </div>
                      <span className="text-sm font-medium text-slate-700">{node.label}</span>
                      <Plus className="w-4 h-4 text-slate-400 ml-auto opacity-0 group-hover:opacity-100 transition-opacity" />
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Main canvas */}
        <div className="flex-1">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={onNodeClick}
            nodeTypes={nodeTypes}
            fitView
            snapToGrid
            snapGrid={[16, 16]}
            className="bg-slate-50"
          >
            <Background
              variant={BackgroundVariant.Dots}
              gap={16}
              size={1}
              color="#cbd5e1"
            />
            <Controls className="bg-white border border-slate-200 rounded-xl shadow-lg" />
            <MiniMap
              className="bg-white border border-slate-200 rounded-xl shadow-lg"
              nodeColor={(node: Node) => {
                switch (node.type) {
                  case 'trigger':
                    return '#3b82f6'
                  case 'llm':
                    return '#8b5cf6'
                  case 'knowledge':
                    return '#10b981'
                  case 'tool':
                    return '#ec4899'
                  case 'condition':
                    return '#f59e0b'
                  case 'response':
                    return '#6366f1'
                  default:
                    return '#64748b'
                }
              }}
            />

            {/* Empty state */}
            {nodes.length === 0 && (
              <Panel position="top-center" className="mt-20">
                <Card className="p-8 text-center shadow-xl">
                  <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center mx-auto mb-4 shadow-lg shadow-indigo-500/30">
                    <Plus className="w-8 h-8 text-white" />
                  </div>
                  <h3 className="text-lg font-semibold text-slate-900 mb-2">
                    从这里开始构建你的工作流
                  </h3>
                  <p className="text-sm text-slate-500 mb-4">
                    拖拽左侧的节点到画布上，或点击添加节点
                  </p>
                  <div className="flex items-center justify-center gap-2 text-xs text-slate-400">
                    <span className="px-2 py-1 rounded bg-slate-100">支持</span>
                    <span className="px-2 py-1 rounded bg-slate-100">拖拽</span>
                    <span className="px-2 py-1 rounded bg-slate-100">缩放</span>
                    <span className="px-2 py-1 rounded bg-slate-100">连接</span>
                  </div>
                </Card>
              </Panel>
            )}
          </ReactFlow>
        </div>

        {/* Right sidebar - Properties */}
        <div className="w-80 bg-white border-l border-slate-200 overflow-y-auto">
          <div className="p-4 border-b border-slate-100">
            <h3 className="text-sm font-semibold text-slate-700">节点配置</h3>
          </div>
          
          {selectedNode ? (
            <div className="p-4 space-y-4">
              <div className="flex items-center gap-3 p-3 rounded-xl bg-gradient-to-r from-indigo-50 to-purple-50">
                <div className="p-2 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600">
                  <Settings className="w-4 h-4 text-white" />
                </div>
                <div>
                  <div className="font-medium text-slate-900">{selectedNode.data.label}</div>
                  <div className="text-xs text-slate-500 capitalize">{selectedNode.type} 节点</div>
                </div>
              </div>

              <Input
                label="节点名称"
                value={selectedNode.data.label}
                onChange={(e) => {
                  setNodes((nds: Node[]) =>
                    nds.map((n: Node) =>
                      n.id === selectedNode.id ? { ...n, data: { ...n.data, label: e.target.value } } : n
                    )
                  )
                }}
              />

              <Input
                label="描述"
                value={selectedNode.data.description || ''}
                onChange={(e) => {
                  setNodes((nds: Node[]) =>
                    nds.map((n: Node) =>
                      n.id === selectedNode.id ? { ...n, data: { ...n.data, description: e.target.value } } : n
                    )
                  )
                }}
                placeholder="简要描述这个节点的作用"
              />

              {selectedNode.type === 'llm' && (
                <>
                  <Select
                    label="模型"
                    value={selectedNode.data.model || 'gpt-4'}
                    onChange={(e) => {
                      setNodes((nds: Node[]) =>
                        nds.map((n: Node) =>
                          n.id === selectedNode.id ? { ...n, data: { ...n.data, model: e.target.value } } : n
                        )
                      )
                    }}
                    options={[
                      { value: 'gpt-4', label: 'GPT-4' },
                      { value: 'gpt-3.5-turbo', label: 'GPT-3.5 Turbo' },
                      { value: 'claude-3', label: 'Claude 3' },
                    ]}
                  />
                </>
              )}
            </div>
          ) : (
            <div className="p-8 text-center">
              <div className="w-12 h-12 rounded-xl bg-slate-100 flex items-center justify-center mx-auto mb-4">
                <Settings className="w-6 h-6 text-slate-400" />
              </div>
              <p className="text-sm text-slate-500">
                选择一个节点以查看和编辑配置
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
