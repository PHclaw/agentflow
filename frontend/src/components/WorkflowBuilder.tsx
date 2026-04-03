import React, { useState, useCallback } from 'react'
import ReactFlow, {
  Node,
  Edge,
  addEdge,
  Connection,
  useNodesState,
  useEdgesState,
  Controls,
  Background,
  MiniMap,
  Panel,
} from 'reactflow'
import 'reactflow/dist/style.css'

// 节点类型
const nodeTypes = {
  llm: LLMNode,
  condition: ConditionNode,
  tool: ToolNode,
  knowledge: KnowledgeNode,
  output: OutputNode,
}

// 初始节点
const initialNodes: Node[] = [
  {
    id: 'start',
    type: 'condition',
    position: { x: 250, y: 50 },
    data: { label: '开始', condition: 'intent' },
  },
  {
    id: 'llm',
    type: 'llm',
    position: { x: 250, y: 150 },
    data: { label: 'AI 处理', model: 'gpt-4o-mini' },
  },
  {
    id: 'output',
    type: 'output',
    position: { x: 250, y: 250 },
    data: { label: '输出' },
  },
]

const initialEdges: Edge[] = [
  { id: 'e1', source: 'start', target: 'llm', animated: true },
  { id: 'e2', source: 'llm', target: 'output' },
]

export default function WorkflowBuilder() {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges)
  const [selectedNode, setSelectedNode] = useState<Node | null>(null)

  const onConnect = useCallback(
    (params: Connection) => setEdges((eds) => addEdge(params, eds)),
    [setEdges]
  )

  const onNodeClick = useCallback((event: React.MouseEvent, node: Node) => {
    setSelectedNode(node)
  }, [])

  const addNode = (type: string) => {
    const newNode: Node = {
      id: `${type}-${Date.now()}`,
      type,
      position: { x: Math.random() * 400, y: Math.random() * 400 },
      data: { label: type === 'llm' ? 'AI 处理' : type === 'tool' ? '工具' : type === 'knowledge' ? '知识库' : '条件' },
    }
    setNodes((nds) => [...nds, newNode])
  }

  const deleteSelectedNode = () => {
    if (selectedNode) {
      setNodes((nds) => nds.filter((n) => n.id !== selectedNode.id))
      setEdges((eds) => eds.filter((e) => e.source !== selectedNode.id && e.target !== selectedNode.id))
      setSelectedNode(null)
    }
  }

  return (
    <div className="h-screen flex">
      {/* 左侧工具栏 */}
      <div className="w-64 bg-gray-50 border-r p-4">
        <h3 className="font-semibold text-gray-700 mb-4">节点类型</h3>
        <div className="space-y-2">
          <button
            onClick={() => addNode('llm')}
            className="w-full p-3 bg-blue-50 text-blue-700 rounded-lg hover:bg-blue-100 transition flex items-center gap-2"
          >
            <span className="text-xl">🤖</span>
            <span>AI 处理</span>
          </button>
          <button
            onClick={() => addNode('condition')}
            className="w-full p-3 bg-yellow-50 text-yellow-700 rounded-lg hover:bg-yellow-100 transition flex items-center gap-2"
          >
            <span className="text-xl">🔀</span>
            <span>条件分支</span>
          </button>
          <button
            onClick={() => addNode('tool')}
            className="w-full p-3 bg-green-50 text-green-700 rounded-lg hover:bg-green-100 transition flex items-center gap-2"
          >
            <span className="text-xl">🔧</span>
            <span>工具调用</span>
          </button>
          <button
            onClick={() => addNode('knowledge')}
            className="w-full p-3 bg-purple-50 text-purple-700 rounded-lg hover:bg-purple-100 transition flex items-center gap-2"
          >
            <span className="text-xl">📚</span>
            <span>知识库</span>
          </button>
        </div>

        {selectedNode && (
          <div className="mt-8 p-4 bg-white rounded-lg border">
            <h4 className="font-semibold text-gray-700 mb-2">选中节点</h4>
            <p className="text-sm text-gray-500 mb-3">{selectedNode.data.label}</p>
            <button
              onClick={deleteSelectedNode}
              className="w-full py-2 bg-red-50 text-red-600 rounded hover:bg-red-100 transition text-sm"
            >
              删除节点
            </button>
          </div>
        )}
      </div>

      {/* 画布 */}
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
        >
          <Background />
          <Controls />
          <MiniMap />
          <Panel position="top-right">
            <div className="bg-white p-2 rounded-lg shadow flex gap-2">
              <button className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">
                保存
              </button>
              <button className="px-4 py-2 bg-gray-100 text-gray-700 rounded hover:bg-gray-200">
                测试运行
              </button>
            </div>
          </Panel>
        </ReactFlow>
      </div>
    </div>
  )
}

// 自定义节点组件
function LLMNode({ data }: { data: any }) {
  return (
    <div className="px-4 py-2 shadow-md rounded-lg bg-blue-500 text-white border-2 border-blue-600">
      <div className="flex items-center gap-2">
        <span>🤖</span>
        <span className="font-medium">{data.label}</span>
      </div>
      <div className="text-xs text-blue-100 mt-1">{data.model || 'gpt-4o-mini'}</div>
    </div>
  )
}

function ConditionNode({ data }: { data: any }) {
  return (
    <div className="px-4 py-2 shadow-md rounded-lg bg-yellow-500 text-white border-2 border-yellow-600">
      <div className="flex items-center gap-2">
        <span>🔀</span>
        <span className="font-medium">{data.label}</span>
      </div>
      <div className="text-xs text-yellow-100 mt-1">{data.condition || '条件判断'}</div>
    </div>
  )
}

function ToolNode({ data }: { data: any }) {
  return (
    <div className="px-4 py-2 shadow-md rounded-lg bg-green-500 text-white border-2 border-green-600">
      <div className="flex items-center gap-2">
        <span>🔧</span>
        <span className="font-medium">{data.label}</span>
      </div>
      <div className="text-xs text-green-100 mt-1">{data.tool || '工具'}</div>
    </div>
  )
}

function KnowledgeNode({ data }: { data: any }) {
  return (
    <div className="px-4 py-2 shadow-md rounded-lg bg-purple-500 text-white border-2 border-purple-600">
      <div className="flex items-center gap-2">
        <span>📚</span>
        <span className="font-medium">{data.label}</span>
      </div>
      <div className="text-xs text-purple-100 mt-1">RAG 检索</div>
    </div>
  )
}

function OutputNode({ data }: { data: any }) {
  return (
    <div className="px-4 py-2 shadow-md rounded-lg bg-gray-500 text-white border-2 border-gray-600">
      <div className="flex items-center gap-2">
        <span>📤</span>
        <span className="font-medium">{data.label}</span>
      </div>
    </div>
  )
}
