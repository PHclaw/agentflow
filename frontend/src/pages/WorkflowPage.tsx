import React, { useState, useEffect, useCallback, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
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
  ReactFlowInstance,
} from 'reactflow'
import 'reactflow/dist/style.css'

import { Button } from '../components/ui/Button'
import { Input, Select } from '../components/ui/Input'
import { Card } from '../components/ui/Card'
import { api } from '../services/api'
import { useToastStore } from '../stores'
import {
  ArrowLeft,
  Save,
  Play,
  Undo2,
  Redo2,
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
  ChevronDown,
  ChevronRight,
  Loader2,
  CheckCircle,
  XCircle,
  AlertCircle,
  Trash2,
  Copy,
  Eye,
  EyeOff,
  Zap,
} from 'lucide-react'

// 节点组件
import { TriggerNode } from '../components/workflow/nodes/TriggerNode'
import { LLMNode } from '../components/workflow/nodes/LLMNode'
import { KnowledgeNode } from '../components/workflow/nodes/KnowledgeNode'
import { ToolNode } from '../components/workflow/nodes/ToolNode'
import { ConditionNode } from '../components/workflow/nodes/ConditionNode'
import { ResponseNode } from '../components/workflow/nodes/ResponseNode'

const nodeTypes = {
  trigger: TriggerNode,
  llm: LLMNode,
  knowledge: KnowledgeNode,
  tool: ToolNode,
  condition: ConditionNode,
  response: ResponseNode,
}

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
      { type: 'knowledge', label: '知识库检索', icon: Database, color: 'from-emerald-500 to-green-500' },
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

// 节点执行状态
interface NodeExecutionState {
  nodeId: string
  status: 'idle' | 'running' | 'success' | 'failed'
  inputs: Record<string, any>
  outputs: Record<string, any>
  error?: string
  executionTime?: number
}

export default function WorkflowPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { addToast } = useToastStore()
  const reactFlowWrapper = useRef<HTMLDivElement>(null)
  const [reactFlowInstance, setReactFlowInstance] = useState<any>(null)
  const isNewWorkflow = id === 'new'

  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  const [selectedNode, setSelectedNode] = useState<Node | null>(null)
  const [loading, setLoading] = useState(false)
  const [agentId, setAgentId] = useState<string | null>(null)
  
  // 测试执行相关
  const [testInput, setTestInput] = useState('')
  const [testRunning, setTestRunning] = useState(false)
  const [testOutput, setTestOutput] = useState('')
  const [nodeExecutionStates, setNodeExecutionStates] = useState<Record<string, NodeExecutionState>>({})
  const [showTestPanel, setShowTestPanel] = useState(false)
  
  // 节点配置面板
  const [expandedCategory, setExpandedCategory] = useState<string | null>('AI 能力')

  // 如果有 agent id，加载现有工作流
  useEffect(() => {
    if (id && id !== 'new') {
      loadWorkflow(id)
    } else {
      // 新工作流 - 添加默认触发器
      const defaultNodes: Node[] = [
        {
          id: 'trigger-1',
          type: 'trigger',
          position: { x: 250, y: 50 },
          data: { label: '消息触发', description: '用户发送消息时触发', trigger_type: 'message' },
        },
      ]
      setNodes(defaultNodes)
    }
  }, [id])

  const loadWorkflow = async (agentId: string) => {
    try {
      const agent = await api.get(`/agents/${agentId}`)
      const workflowDef = agent.workflow_definition
      
      if (workflowDef && workflowDef.nodes && workflowDef.nodes.length > 0) {
        const loadedNodes: Node[] = workflowDef.nodes.map((node: any, idx: number) => ({
          id: node.id || `node-${idx}`,
          type: node.type || 'llm',
          position: node.position || { x: 250, y: 150 + idx * 150 },
          data: {
            label: node.data?.label || node.type,
            description: node.data?.description || '',
            model: node.data?.model || 'gpt-4o-mini',
            prompt: node.data?.prompt || '',
            temperature: node.data?.temperature || 0.7,
            system_prompt: node.data?.system_prompt || '',
            kb_id: node.data?.kb_id || '',
            top_k: node.data?.top_k || 5,
            tool_name: node.data?.tool_name || 'calculator',
            tool_params: node.data?.tool_params || {},
            condition_type: node.data?.condition_type || 'contains',
            condition_value: node.data?.condition_value || '',
            response_template: node.data?.response_template || '',
            trigger_type: node.data?.trigger_type || 'message',
            ...node.data,
          },
        }))
        
        const loadedEdges: Edge[] = (workflowDef.edges || []).map((edge: any, idx: number) => ({
          id: `edge-${idx}`,
          source: edge.source,
          target: edge.target,
          sourceHandle: edge.sourceHandle,
          animated: true,
          style: { stroke: '#6366f1' },
        }))
        
        setNodes(loadedNodes)
        setEdges(loadedEdges)
      }
      setAgentId(agentId)
    } catch (error) {
      addToast({ type: 'error', message: '加载工作流失败' })
    }
  }

  const onConnect = useCallback(
    (params: Connection) => {
      setEdges((eds: Edge[]) => addEdge({
        ...params,
        animated: true,
        style: { stroke: '#6366f1' },
      }, eds))
    },
    [setEdges]
  )

  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    setSelectedNode(node)
  }, [])

  const handleAddNode = (type: string, label: string) => {
    const bounds = reactFlowInstance.getViewport()
    const position = {
      x: (-bounds.x + 400) / bounds.zoom,
      y: (-bounds.y + 200) / bounds.zoom,
    }
    
    const newNode: Node = {
      id: `${type}-${Date.now()}`,
      type,
      position,
      data: {
        label,
        description: '',
        model: 'gpt-4o-mini',
        prompt: '',
        temperature: 0.7,
        system_prompt: '',
        kb_id: '',
        top_k: 5,
        tool_name: 'calculator',
        tool_params: {},
        condition_type: 'contains',
        condition_value: '',
        response_template: '',
        trigger_type: 'message',
      },
    }
    setNodes((nds: Node[]) => [...nds, newNode])
  }

  const handleSave = async () => {
    const workflowNodes = nodes.map(node => ({
      id: node.id,
      type: node.type,
      position: node.position,
      data: node.data,
    }))
    
    const workflowEdges = edges.map(edge => ({
      source: edge.source,
      target: edge.target,
      sourceHandle: edge.sourceHandle,
    }))

    if (isNewWorkflow || !agentId) {
      setLoading(true)
      try {
        const newAgent = await api.post('/agents', {
          name: '未命名工作流',
          description: '从工作流编辑器创建',
          workflow_definition: {
            nodes: workflowNodes,
            edges: workflowEdges,
          },
          llm_config: {
            provider: 'openai',
            model: 'gpt-4o-mini',
            temperature: 0.7,
          },
        })
        setAgentId(newAgent.id)
        addToast({ type: 'success', message: '工作流已保存' })
        window.history.replaceState({}, '', `/workflow/${newAgent.id}`)
      } catch (error: any) {
        addToast({ type: 'error', message: error.message || '保存失败' })
      } finally {
        setLoading(false)
      }
    } else {
      setLoading(true)
      try {
        await api.put(`/agents/${agentId}`, {
          workflow_definition: {
            nodes: workflowNodes,
            edges: workflowEdges,
          },
        })
        addToast({ type: 'success', message: '工作流已保存' })
      } catch (error: any) {
        addToast({ type: 'error', message: error.message || '保存失败' })
      } finally {
        setLoading(false)
      }
    }
  }

  const handleExport = () => {
    const data = { nodes, edges, exportedAt: new Date().toISOString() }
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `workflow-${Date.now()}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleImport = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = (e) => {
      try {
        const data = JSON.parse(e.target?.result as string)
        if (data.nodes) setNodes(data.nodes)
        if (data.edges) setEdges(data.edges)
        addToast({ type: 'success', message: '工作流已导入' })
      } catch {
        addToast({ type: 'error', message: '导入失败，文件格式错误' })
      }
    }
    reader.readAsText(file)
  }

  // 测试工作流
  const handleTestWorkflow = async () => {
    if (!testInput.trim()) {
      addToast({ type: 'warning', message: '请输入测试内容' })
      return
    }

    setTestRunning(true)
    setTestOutput('')
    setShowTestPanel(true)
    
    const newStates: Record<string, NodeExecutionState> = {}
    nodes.forEach(node => {
      newStates[node.id] = {
        nodeId: node.id,
        status: 'idle',
        inputs: {},
        outputs: {},
      }
    })
    setNodeExecutionStates(newStates)

    try {
      const response = await fetch('/api/v1/workflow/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workflow_definition: {
            nodes: nodes.map(n => ({ id: n.id, type: n.type, data: n.data })),
            edges: edges.map(e => ({ source: e.source, target: e.target, sourceHandle: e.sourceHandle })),
          },
          input_data: { user_message: testInput },
        }),
      })

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()
      let output = ''

      while (reader) {
        const { done, value } = await reader.read()
        if (done) break
        const chunk = decoder.decode(value)
        const lines = chunk.split('\n')
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))
              if (data.type === 'node_complete') {
                setNodeExecutionStates(prev => ({
                  ...prev,
                  [data.node_id]: {
                    nodeId: data.node_id,
                    status: data.status === 'success' ? 'success' : 'failed',
                    inputs: data.inputs || {},
                    outputs: data.outputs || {},
                    executionTime: data.execution_time,
                    error: data.error,
                  },
                }))
              } else if (data.type === 'llm_chunk') {
                output += data.chunk
                setTestOutput(output)
              } else if (data.type === 'complete') {
                setTestOutput(data.final_output || '执行完成')
              }
            } catch {}
          }
        }
      }
    } catch (error: any) {
      addToast({ type: 'error', message: error.message || '测试执行失败' })
    } finally {
      setTestRunning(false)
    }
  }

  const handleDeleteNode = (nodeId: string) => {
    setNodes(nds => nds.filter(n => n.id !== nodeId))
    setEdges(eds => eds.filter(e => e.source !== nodeId && e.target !== nodeId))
    if (selectedNode?.id === nodeId) setSelectedNode(null)
  }

  const handleCopyNode = (node: Node) => {
    const newNode: Node = {
      ...node,
      id: `${node.type}-${Date.now()}`,
      position: { x: node.position.x + 50, y: node.position.y + 50 },
      selected: false,
    }
    setNodes(nds => [...nds, newNode])
  }

  return (
    <div className="h-screen flex flex-col bg-slate-100">
      {/* Header */}
      <div className="bg-white border-b border-slate-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button variant="ghost" size="sm" onClick={() => navigate(-1)}>
              <ArrowLeft className="w-5 h-5" />
            </Button>
            <div>
              <h1 className="text-xl font-bold text-slate-900">
                {isNewWorkflow ? '新建工作流' : '编辑工作流'}
              </h1>
              <p className="text-sm text-slate-500">
                {nodes.length} 个节点，{edges.length} 条连接
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Button variant="outline" size="sm" leftIcon={<Zap className="w-4 h-4" />} onClick={() => setShowTestPanel(!showTestPanel)}>
              测试
            </Button>
            <Button variant="outline" size="sm" leftIcon={<Undo2 className="w-4 h-4" />}>撤销</Button>
            <Button variant="outline" size="sm" leftIcon={<Redo2 className="w-4 h-4" />}>重做</Button>
            <div className="w-px h-6 bg-slate-200 mx-1" />
            <Button variant="outline" size="sm" leftIcon={<Download className="w-4 h-4" />} onClick={handleExport}>导出</Button>
            <label>
              <Button variant="outline" size="sm" leftIcon={<Upload className="w-4 h-4" />} as="span">导入</Button>
              <input type="file" accept=".json" onChange={handleImport} className="hidden" />
            </label>
            <Button size="sm" leftIcon={<Save className="w-4 h-4" />} onClick={handleSave} loading={loading} className="shadow-lg shadow-indigo-500/20">
              保存
            </Button>
          </div>
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Left sidebar */}
        <div className="w-64 bg-white border-r border-slate-200 overflow-y-auto">
          <div className="p-4">
            <h3 className="text-sm font-semibold text-slate-700 mb-4">节点组件</h3>
            {nodeCategories.map((category) => (
              <div key={category.name} className="mb-4">
                <button
                  onClick={() => setExpandedCategory(expandedCategory === category.name ? null : category.name)}
                  className="w-full flex items-center justify-between text-xs font-medium text-slate-400 uppercase tracking-wider mb-2 hover:text-slate-600"
                >
                  {category.name}
                  {expandedCategory === category.name ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                </button>
                {expandedCategory === category.name && (
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
                )}
              </div>
            ))}
          </div>
          
          {/* Test Panel */}
          {showTestPanel && (
            <div className="p-4 border-t border-slate-200">
              <h3 className="text-sm font-semibold text-slate-700 mb-3">测试运行</h3>
              <div className="space-y-3">
                <Input
                  placeholder="输入测试内容..."
                  value={testInput}
                  onChange={(e) => setTestInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleTestWorkflow()}
                />
                <Button className="w-full" leftIcon={testRunning ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />} onClick={handleTestWorkflow} disabled={testRunning}>
                  {testRunning ? '执行中...' : '运行测试'}
                </Button>
                
                {Object.values(nodeExecutionStates).length > 0 && (
                  <div className="space-y-2 mt-4">
                    <h4 className="text-xs font-medium text-slate-500">执行状态</h4>
                    {nodes.map(node => {
                      const state = nodeExecutionStates[node.id]
                      return (
                        <div key={node.id} className={`flex items-center gap-2 p-2 rounded-lg text-xs ${
                          state?.status === 'success' ? 'bg-green-50 text-green-700' :
                          state?.status === 'failed' ? 'bg-red-50 text-red-700' :
                          state?.status === 'running' ? 'bg-blue-50 text-blue-700' :
                          'bg-slate-50 text-slate-500'
                        }`}>
                          {state?.status === 'success' && <CheckCircle className="w-3 h-3" />}
                          {state?.status === 'failed' && <XCircle className="w-3 h-3" />}
                          {state?.status === 'running' && <Loader2 className="w-3 h-3 animate-spin" />}
                          {state?.status === 'idle' && <AlertCircle className="w-3 h-3" />}
                          <span className="truncate">{node.data.label}</span>
                          {state?.executionTime && <span className="ml-auto">{state.executionTime.toFixed(2)}s</span>}
                        </div>
                      )
                    })}
                  </div>
                )}
                
                {testOutput && (
                  <div className="mt-4">
                    <h4 className="text-xs font-medium text-slate-500 mb-2">输出结果</h4>
                    <div className="p-3 bg-slate-50 rounded-lg text-sm whitespace-pre-wrap max-h-40 overflow-y-auto">
                      {testOutput}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Main canvas */}
        <div className="flex-1 relative">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={onNodeClick}
            onInit={(instance: ReactFlowInstance) => setReactFlowInstance(instance)}
            nodeTypes={nodeTypes}
            fitView
            snapToGrid
            snapGrid={[16, 16]}
            className="bg-slate-50"
          >
            <Background variant={BackgroundVariant.Dots} gap={16} size={1} color="#cbd5e1" />
            <Controls className="bg-white border border-slate-200 rounded-xl shadow-lg" />
            <MiniMap
              className="bg-white border border-slate-200 rounded-xl shadow-lg"
              nodeColor={(node: Node) => {
                const state = nodeExecutionStates[node.id]
                if (state?.status === 'success') return '#10b981'
                if (state?.status === 'failed') return '#ef4444'
                if (state?.status === 'running') return '#3b82f6'
                switch (node.type) {
                  case 'trigger': return '#3b82f6'
                  case 'llm': return '#8b5cf6'
                  case 'knowledge': return '#10b981'
                  case 'tool': return '#ec4899'
                  case 'condition': return '#f59e0b'
                  case 'response': return '#6366f1'
                  default: return '#64748b'
                }
              }}
            />
            {nodes.length === 0 && (
              <Panel position="top-center" className="mt-20">
                <Card className="p-8 text-center shadow-xl">
                  <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center mx-auto mb-4 shadow-lg shadow-indigo-500/30">
                    <Plus className="w-8 h-8 text-white" />
                  </div>
                  <h3 className="text-lg font-semibold text-slate-900 mb-2">从这里开始构建你的工作流</h3>
                  <p className="text-sm text-slate-500 mb-4">点击左侧的节点按钮添加节点</p>
                </Card>
              </Panel>
            )}
          </ReactFlow>
        </div>

        {/* Right sidebar */}
        <div className="w-80 bg-white border-l border-slate-200 overflow-y-auto">
          <div className="p-4 border-b border-slate-100 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-700">节点配置</h3>
            {selectedNode && (
              <div className="flex items-center gap-1">
                <button onClick={() => handleCopyNode(selectedNode)} className="p-1.5 hover:bg-slate-100 rounded-lg text-slate-500" title="复制">
                  <Copy className="w-4 h-4" />
                </button>
                <button onClick={() => handleDeleteNode(selectedNode.id)} className="p-1.5 hover:bg-red-50 rounded-lg text-slate-500 hover:text-red-500" title="删除">
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            )}
          </div>
          
          {selectedNode ? (
            <NodeConfigPanel 
              node={selectedNode} 
              nodes={nodes}
              onUpdate={(data) => {
                setNodes(nds => nds.map(n => 
                  n.id === selectedNode.id ? { ...n, data: { ...n.data, ...data } } : n
                ))
              }}
              executionState={nodeExecutionStates[selectedNode.id]}
            />
          ) : (
            <div className="p-8 text-center">
              <div className="w-12 h-12 rounded-xl bg-slate-100 flex items-center justify-center mx-auto mb-4">
                <Settings className="w-6 h-6 text-slate-400" />
              </div>
              <p className="text-sm text-slate-500">选择一个节点以查看和编辑配置</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// 节点配置面板
interface NodeConfigPanelProps {
  node: Node
  nodes: Node[]
  onUpdate: (data: any) => void
  executionState?: NodeExecutionState
}

function NodeConfigPanel({ node, onUpdate, executionState }: NodeConfigPanelProps) {
  const [showOutputs, setShowOutputs] = useState(false)
  
  const renderConfig = () => {
    switch (node.type) {
      case 'trigger':
        return (
          <>
            <Input label="节点名称" value={node.data.label} onChange={(e) => onUpdate({ label: e.target.value })} />
            <Input label="触发类型" value={node.data.trigger_type} onChange={(e) => onUpdate({ trigger_type: e.target.value })} placeholder="message / webhook / schedule" />
            <Input label="描述" value={node.data.description} onChange={(e) => onUpdate({ description: e.target.value })} placeholder="简要描述" />
          </>
        )
      
      case 'llm':
        return (
          <>
            <Input label="节点名称" value={node.data.label} onChange={(e) => onUpdate({ label: e.target.value })} />
            <Select label="模型" value={node.data.model} onChange={(e) => onUpdate({ model: e.target.value })}
              options={[
                { value: 'gpt-4o-mini', label: 'GPT-4o Mini' },
                { value: 'gpt-4o', label: 'GPT-4o' },
                { value: 'gpt-4-turbo', label: 'GPT-4 Turbo' },
                { value: 'claude-3-sonnet', label: 'Claude 3 Sonnet' },
              ]}
            />
            <Input label="系统提示词" value={node.data.system_prompt} onChange={(e) => onUpdate({ system_prompt: e.target.value })} placeholder="设置 AI 角色..." />
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700">提示词模板</label>
              <textarea
                value={node.data.prompt}
                onChange={(e) => onUpdate({ prompt: e.target.value })}
                placeholder="使用 {{变量名}} 引用上下文..."
                rows={4}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
              <p className="text-xs text-slate-400">支持: {'{{user_message}}'}, {'{{knowledge.context}}'}, {'{{tool.result}}'}</p>
            </div>
            <Input label="温度" type="number" value={node.data.temperature} onChange={(e) => onUpdate({ temperature: parseFloat(e.target.value) })} min={0} max={2} step={0.1} />
          </>
        )
      
      case 'knowledge':
        return (
          <>
            <Input label="节点名称" value={node.data.label} onChange={(e) => onUpdate({ label: e.target.value })} />
            <Input label="知识库 ID" value={node.data.kb_id} onChange={(e) => onUpdate({ kb_id: e.target.value })} placeholder="输入知识库 ID" />
            <Input label="检索数量" type="number" value={node.data.top_k} onChange={(e) => onUpdate({ top_k: parseInt(e.target.value) })} min={1} max={20} />
            <div className="p-3 bg-emerald-50 rounded-lg text-xs text-emerald-700">
              输出: <code>knowledge.results</code>, <code>knowledge.context</code>
            </div>
          </>
        )
      
      case 'condition':
        return (
          <>
            <Input label="节点名称" value={node.data.label} onChange={(e) => onUpdate({ label: e.target.value })} />
            <Select label="条件类型" value={node.data.condition_type} onChange={(e) => onUpdate({ condition_type: e.target.value })}
              options={[
                { value: 'equals', label: '等于' },
                { value: 'not_equals', label: '不等于' },
                { value: 'contains', label: '包含' },
                { value: 'not_contains', label: '不包含' },
                { value: 'starts_with', label: '开头是' },
                { value: 'ends_with', label: '结尾是' },
                { value: 'greater_than', label: '大于' },
                { value: 'less_than', label: '小于' },
                { value: 'is_empty', label: '为空' },
                { value: 'is_not_empty', label: '不为空' },
                { value: 'regex', label: '正则匹配' },
              ]}
            />
            <Input label="比较值" value={node.data.condition_value} onChange={(e) => onUpdate({ condition_value: e.target.value })} placeholder="输入比较值" />
            <div className="text-xs text-slate-400">真走 <span className="text-green-600">是</span> 分支，假走 <span className="text-red-600">否</span> 分支</div>
          </>
        )
      
      case 'tool':
        return (
          <>
            <Input label="节点名称" value={node.data.label} onChange={(e) => onUpdate({ label: e.target.value })} />
            <Select label="工具" value={node.data.tool_name} onChange={(e) => onUpdate({ tool_name: e.target.value })}
              options={[
                { value: 'calculator', label: '计算器' },
                { value: 'formatter', label: '格式化' },
                { value: 'text_process', label: '文本处理' },
                { value: 'date_time', label: '日期时间' },
              ]}
            />
            {node.data.tool_name === 'calculator' && (
              <Input label="表达式" value={node.data.tool_params?.expression || ''} onChange={(e) => onUpdate({ tool_params: { ...node.data.tool_params, expression: e.target.value } })} placeholder="如: 100 + 200" />
            )}
            {node.data.tool_name === 'formatter' && (
              <Input label="模板" value={node.data.tool_params?.template || ''} onChange={(e) => onUpdate({ tool_params: { ...node.data.tool_params, template: e.target.value } })} placeholder='如: "结果: {input}"' />
            )}
          </>
        )
      
      case 'response':
        return (
          <>
            <Input label="节点名称" value={node.data.label} onChange={(e) => onUpdate({ label: e.target.value })} />
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700">响应模板</label>
              <textarea
                value={node.data.response_template}
                onChange={(e) => onUpdate({ response_template: e.target.value })}
                placeholder="使用 {{变量}} 引用上下文..."
                rows={4}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            <div className="text-xs text-slate-400">可用: {'{{llm.response}}'}, {'{{knowledge.context}}'}, {'{{tool.result}}'}</div>
          </>
        )
      
      default:
        return <Input label="节点名称" value={node.data.label} onChange={(e) => onUpdate({ label: e.target.value })} />
    }
  }

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center gap-3 p-3 rounded-xl bg-gradient-to-r from-indigo-50 to-purple-50">
        <div className="p-2 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600">
          <Settings className="w-4 h-4 text-white" />
        </div>
        <div>
          <div className="font-medium text-slate-900">{node.data.label}</div>
          <div className="text-xs text-slate-500 capitalize">{node.type} 节点</div>
        </div>
        {executionState && (
          <div className={`ml-auto px-2 py-0.5 rounded text-xs ${
            executionState.status === 'success' ? 'bg-green-100 text-green-700' :
            executionState.status === 'failed' ? 'bg-red-100 text-red-700' :
            executionState.status === 'running' ? 'bg-blue-100 text-blue-700' :
            'bg-slate-100 text-slate-500'
          }`}>
            {executionState.status}
          </div>
        )}
      </div>

      {renderConfig()}

      {executionState && (executionState.inputs || executionState.outputs) && (
        <div className="border-t border-slate-100 pt-4">
          <button onClick={() => setShowOutputs(!showOutputs)} className="flex items-center gap-2 text-sm font-medium text-slate-700 mb-3">
            {showOutputs ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            {showOutputs ? '隐藏' : '查看'} 执行数据
          </button>
          
          {showOutputs && (
            <div className="space-y-4">
              {executionState.inputs && Object.keys(executionState.inputs).length > 0 && (
                <div>
                  <h4 className="text-xs font-medium text-slate-500 mb-2">输入数据</h4>
                  <div className="p-3 bg-slate-50 rounded-lg text-xs font-mono max-h-32 overflow-y-auto">
                    <pre>{JSON.stringify(executionState.inputs, null, 2)}</pre>
                  </div>
                </div>
              )}
              {executionState.outputs && Object.keys(executionState.outputs).length > 0 && (
                <div>
                  <h4 className="text-xs font-medium text-slate-500 mb-2">输出数据</h4>
                  <div className="p-3 bg-slate-50 rounded-lg text-xs font-mono max-h-32 overflow-y-auto">
                    <pre>{JSON.stringify(executionState.outputs, null, 2)}</pre>
                  </div>
                </div>
              )}
              {executionState.error && (
                <div className="p-3 bg-red-50 rounded-lg text-xs text-red-700"><strong>错误:</strong> {executionState.error}</div>
              )}
              {executionState.executionTime && (
                <div className="text-xs text-slate-400">执行时间: {executionState.executionTime.toFixed(3)}s</div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
