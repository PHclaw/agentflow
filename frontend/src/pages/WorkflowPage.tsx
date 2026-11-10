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
  NodeChange,
  EdgeChange,
  BackgroundVariant,
  Panel,
  ReactFlowInstance,
} from 'reactflow'
import 'reactflow/dist/style.css'

import { Button } from '../components/ui/Button'
import { Input, Select } from '../components/ui/Input'
import { Card } from '../components/ui/Card'
import { useWorkflowHistory } from '../components/workflow/useWorkflowHistory'
import { api, llmConfigs, pi, connectors } from '../services/api'
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
  Bot,
  Check,
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
  MoreVertical,
  X,
} from 'lucide-react'

// 节点组件
import { TriggerNode } from '../components/workflow/nodes/TriggerNode'
import { LLMNode } from '../components/workflow/nodes/LLMNode'
import { KnowledgeNode } from '../components/workflow/nodes/KnowledgeNode'
import { ToolNode } from '../components/workflow/nodes/ToolNode'
import { AgentNode } from '../components/workflow/nodes/AgentNode'
import { ConditionNode } from '../components/workflow/nodes/ConditionNode'
import { ResponseNode } from '../components/workflow/nodes/ResponseNode'
import { PixelEdge } from '../components/workflow/pixel/PixelEdge'
import { PixelMotionProvider } from '../components/workflow/pixel/PixelMotion'
import { PixelGlyph } from '../components/pixel/PixelGlyph'
// 像素动效的统一节拍。所有跟它相关的等待时长都写成它的整数倍
import { PIXEL_BEAT_MS } from '../components/pixel/pixelKit'

const nodeTypes = {
  trigger: TriggerNode,
  llm: LLMNode,
  knowledge: KnowledgeNode,
  tool: ToolNode,
  agent: AgentNode,
  condition: ConditionNode,
  response: ResponseNode,
}

/*
  连线也换成自定义组件（见 pixel/PixelEdge）：它会在原来的细线之上叠一条
  会走像素方块的虚线，用来表达"数据正沿着这条边往下走"。

  和 nodeTypes 一样必须是**模块级常量**：ReactFlow 是拿这个对象的引用做
  比较的，每次渲染新建一个对象会让画布上所有边卸载重建 —— 每次改节点配置
  都重挂一遍 DOM，动画会不停从头开始。
*/
const edgeTypes = { pixel: PixelEdge }

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
      { type: 'llm', label: 'LLM 对话', icon: Cpu, color: 'from-brand-500 to-brand-500' },
      { type: 'knowledge', label: '知识库检索', icon: Database, color: 'from-emerald-500 to-green-500' },
      { type: 'agent', label: '智能体调用', icon: Bot, color: 'from-sky-500 to-brand-500' },
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
      { type: 'response', label: '回复用户', icon: Send, color: 'from-brand-500 to-brand-500' },
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

/**
 * 视口是否窄于 lg（1024px）。
 *
 * 为什么用一个 JS 判断，而不是两边都渲染再用 `hidden lg:block` 藏一个：
 * 右栏里的 `NodeConfigPanel` 挂载时会去拉一次模型列表，测试面板里还有一个
 * 受控输入框 —— 渲染两份就是两份请求、两个输入框。这类「看起来只是藏了一个」
 * 的写法，代价往往是静默多出来的副作用。
 */
function useIsNarrow() {
  const [narrow, setNarrow] = useState(
    () =>
      typeof window !== 'undefined' &&
      window.matchMedia('(max-width: 1023px)').matches
  )
  useEffect(() => {
    const mq = window.matchMedia('(max-width: 1023px)')
    const onChange = () => setNarrow(mq.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])
  return narrow
}

export default function WorkflowPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { addToast } = useToastStore()
  const isNarrow = useIsNarrow()
  const reactFlowWrapper = useRef<HTMLDivElement>(null)
  /** 导入用的隐藏 file input。桌面按钮和手机菜单都靠它触发，所以提到外面来 */
  const importInputRef = useRef<HTMLInputElement>(null)
  const [reactFlowInstance, setReactFlowInstance] = useState<any>(null)
  const isNewWorkflow = id === 'new'

  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])

  /*
    撤销 / 重做。

    这两个按钮在页头和手机「更多」里都摆了挺久，但一直没接逻辑 —— 桌面端两个
    Button 没有 onClick，手机菜单里写的是 `run: () => {}`。点了没反应的按钮
    比没有按钮更糟：用户会以为自己误触了，然后反复点。

    记历史的时机见 useWorkflowHistory 的说明：只在「一步操作」的边界拍快照，
    拖拽和连续编辑都只占一格。
  */
  const applySnapshot = useCallback(
    (snap: { nodes: Node[]; edges: Edge[] }) => {
      setNodes(snap.nodes)
      setEdges(snap.edges)
      /*
        撤销/重做可能把**正在配置的那个节点**一起撤掉。selection 要跟着清：

        不清的话右栏还挂着一个已经不在画布上的节点的配置，连它的「删除」按钮
        都还在 —— 点一下就是对着一个不存在的节点发号施令，而画布上什么都没变，
        用户完全看不出发生了什么。
      */
      setSelectedNode((cur) =>
        cur && snap.nodes.some((n) => n.id === cur.id) ? cur : null
      )
    },
    [setNodes, setEdges]
  )
  const history = useWorkflowHistory(nodes, edges, applySnapshot)

  /*
    删除也会走 ReactFlow 的 change 流：选中节点按 Delete、选中连线按
    Backspace，送进来的都是 type === 'remove' 的变化。这种变化的「之前」
    状态在回调里已经拿不到了，所以在检测到 remove 时**先拍一张**，
    再把变化交给 ReactFlow 应用。

    拖拽同理，见下面 onNodeDragStart。
  */
  const handleNodesChange = (changes: NodeChange[]) => {
    if (changes.some((c) => c.type === 'remove')) history.mark()
    onNodesChange(changes)
  }

  const handleEdgesChange = (changes: EdgeChange[]) => {
    if (changes.some((c) => c.type === 'remove')) history.mark()
    onEdgesChange(changes)
  }

  /** 拖动开始时拍快照 —— 拖拽过程中每帧都会变，只有起点值得记。 */
  const handleNodeDragStart = () => history.mark()

  /*
    Ctrl+Z / Ctrl+Shift+Z。编辑器的通用约定，没有它用户只能去找右上角那两个
    小按钮。在输入框里不抢 —— 那里 Ctrl+Z 是撤销文字，归浏览器和输入框管。
  */
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!(e.ctrlKey || e.metaKey) || e.key.toLowerCase() !== 'z') return
      const tag = (e.target as HTMLElement | null)?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
      e.preventDefault()
      if (e.shiftKey) history.redo()
      else history.undo()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [history.undo, history.redo])
  const [selectedNode, setSelectedNode] = useState<Node | null>(null)
  const [loading, setLoading] = useState(false)
  const [agentId, setAgentId] = useState<string | null>(null)
  
  // 测试执行相关
  const [testInput, setTestInput] = useState('')
  const [testRunning, setTestRunning] = useState(false)
  const [testOutput, setTestOutput] = useState('')
  const [nodeExecutionStates, setNodeExecutionStates] = useState<Record<string, NodeExecutionState>>({})
  const [showTestPanel, setShowTestPanel] = useState(false)
  /**
   * 刚从左侧面板添加、正在播放「像素聚合」出现动画的节点。
   *
   * 为什么存在这里而不是写进 `node.data`：data 会被 handleSave /
   * handleExport 一起序列化进数据库 —— 那样刷新页面时，一个早就不"新"的
   * 节点还会再"出现"一次。这类**只属于这一刻 UI 的**标记，不能进数据模型。
   */
  const [freshNodes, setFreshNodes] = useState<ReadonlySet<string>>(new Set())
  /**
   * 移动端底部面板，一次只开一个。
   *
   * 为什么必须有它：编辑器原本是三栏并排 —— 左栏 256px（节点组件）+ 画布 +
   * 右栏 320px（节点配置）。两者合计 576px，**比手机屏幕还宽**，画布宽度被
   * 挤成负数，整个页面在手机上等于不可用。手机上只能让画布独占宽度，
   * 两侧的栏收进这个底部面板。
   */
  const [mobileSheet, setMobileSheet] = useState<null | 'palette' | 'config' | 'test'>(null)
  /** 移动端页头的「更多」下拉（撤销/重做/导出/导入/测试） */
  const [mobileMoreOpen, setMobileMoreOpen] = useState(false)
  
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
          // 模板节点没有坐标（归一化会丢掉不合法的 position），这里兜底排布。
          // 步长必须大于节点卡片高度，否则卡片会互相压住；交错 x 让链路更易读
          position: node.position || { x: 250 + (idx % 2) * 56, y: 120 + idx * 178 },
          data: {
            label: node.data?.label || node.type,
            description: node.data?.description || '',
            model: node.data?.model || '',
            prompt: node.data?.prompt || '',
            temperature: node.data?.temperature || 0.7,
            system_prompt: node.data?.system_prompt || '',
            kb_id: node.data?.kb_id || '',
            top_k: node.data?.top_k || 5,
            tool_name: node.data?.tool_name || 'calculator',
            tool_params: node.data?.tool_params || {},
            agent_id: node.data?.agent_id || '',
            agent_name: node.data?.agent_name || '',
            skills: Array.isArray(node.data?.skills) ? node.data.skills : [],
            input: node.data?.input || '',
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
          // 存量工作流的边上没有 type，这里补上，否则新老连线长得不一样
          type: 'pixel',
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
      // 连线也是一步操作：先把连线前的状态记进历史，再应用新边
      history.mark()
      setEdges((eds: Edge[]) => addEdge({
        ...params,
        type: 'pixel',
        animated: true,
        style: { stroke: '#6366f1' },
      }, eds))
    },
    [setEdges, history]
  )

  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    setSelectedNode(node)
    // 手机上点节点 = 想改它的配置，直接弹出底部面板 —— 那里已经没有空间
    // 再摆一个常驻的右侧栏了。桌面端右侧栏本来就常驻，不需要这一步。
    //
    // 显式判断视口而不是只靠 `lg:hidden`：面板虽然隐藏了，状态却会被设上，
    // 用户把窗口拖窄时就会莫名弹出一个面板。
    if (typeof window !== 'undefined' && window.matchMedia('(max-width: 1023px)').matches) {
      setMobileSheet('config')
    }
  }, [])

  const handleAddNode = (type: string, label: string) => {
    // 落在**可视区域中心**，而不是写死的 (400, 200) 偏移。
    //
    // 手机上画布只有 300 多像素宽，固定偏移会把新节点丢到屏幕外 ——
    // 用户点完「添加节点」面板收起、画布上什么也没多出来，看起来就是功能坏了。
    //
    // reactFlowInstance 在 onInit 之前是 null，视口尺寸也取不到（容器 ref
    // 没挂上时），两条都给了兜底值，不让它抛。
    const bounds = reactFlowInstance?.getViewport?.() ?? { x: 0, y: 0, zoom: 1 }
    const rect = reactFlowWrapper.current?.getBoundingClientRect()
    const centerX = (-bounds.x + (rect?.width ?? 800) / 2) / bounds.zoom
    const centerY = (-bounds.y + (rect?.height ?? 600) / 2) / bounds.zoom
    // 连加多个时错开一点：完全重叠的话看起来像只加了一个
    const cascade = (nodes.length % 5) * 24
    const position = {
      x: centerX - 100 + cascade,
      y: centerY - 40 + cascade,
    }
    
    const newNode: Node = {
      id: `${type}-${Date.now()}`,
      type,
      position,
      data: {
        label,
        description: '',
        // 留空表示「跟随当前生效配置的模型」。
        // 写死 gpt-4o-mini 的话，生效端点是本地 Ollama 时必然报「模型不存在」。
        model: '',
        prompt: '',
        temperature: 0.7,
        system_prompt: '',
        kb_id: '',
        top_k: 5,
        tool_name: 'calculator',
        tool_params: {},
        agent_id: '',
        agent_name: '',
        skills: [],
        input: '',
        condition_type: 'contains',
        condition_value: '',
        response_template: '',
        trigger_type: 'message',
      },
    }
    history.commit({ nodes: [...nodes, newNode], edges })

    /*
      播一次"从像素里拼出来"的出现动画（见 NodeShell）。360ms 是动画时长，
      这里等 5 拍（450ms）再摘掉标记，留一点余量 —— 卡在动画刚好结束的那一帧
      摘，会因为主线程忙而把它截断。
    */
    setFreshNodes((prev) => new Set(prev).add(newNode.id))
    window.setTimeout(() => {
      setFreshNodes((prev) => {
        if (!prev.has(newNode.id)) return prev
        const next = new Set(prev)
        next.delete(newNode.id)
        return next
      })
    }, PIXEL_BEAT_MS * 5)

    // 顺手选中：桌面右栏会直接显示它的配置，手机上新出现的「配置」浮层按钮
    // 也才能亮出来 —— 否则用户加完节点看不出下一步该干嘛。
    setSelectedNode(newNode)
    // 手机上从「添加节点」面板里选完就该收起来 —— 否则它一直盖着刚加的那个节点
    setMobileSheet(null)
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
            // 留空 = 跟随生效配置的模型。写死 gpt-4o-mini 会被 agent_turn
            // 注入到所有未指定模型的节点上，在非 OpenAI 端点必然 404。
            model: '',
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
    // 清空 value，否则连续导入同一个文件时第二次不会触发 change。
    // 现在这个 input 还会被手机菜单里的「导入」以编程方式点开，更需要清。
    event.target.value = ''
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
    // 手机上没有左栏，得把面板弹出来才看得到执行进度和输出
    if (isNarrow) setMobileSheet('test')
    
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
      const token = localStorage.getItem('token')
      /*
        走 /execute/stream，而不是 /execute。

        /execute 返回的是一整个 JSON（跑完才有响应），前端却按 SSE 在解析 ——
        一个 `data:` 帧都读不到，于是执行期间画布上没有任何反馈，参数面板和控制台
        也拿不到任何节点结果。stream 这条才会逐节点推事件，节点上的像素进度带
        才有东西可放。
      */
      const response = await fetch('/api/v1/workflow/execute/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          workflow_definition: {
            nodes: nodes.map(n => ({ id: n.id, type: n.type, data: n.data })),
            edges: edges.map(e => ({ source: e.source, target: e.target, sourceHandle: e.sourceHandle })),
          },
          input_data: { user_message: testInput },
        }),
      })

      // 额度不够之类的情况会是一个正常的 JSON 错误响应，而不是事件流。
      // 不显式拦下来，用户看到的就只是"点了没反应"。
      if (!response.ok) {
        throw new Error(
          response.status === 402 ? '本月额度已用完' : `执行失败（HTTP ${response.status}）`
        )
      }

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()
      let output = ''
      /*
        按 SSE 的**帧边界**切，而不是按 chunk 切。

        一个 `data:` 帧可能被拆到两个 chunk 里（模型边生成边吐字时尤其容易），
        对每个 chunk 单独 split('\n') 会把 JSON 截断，然后被 catch 吞掉 ——
        表现出来就是"某个节点的状态一直不亮"，而且极难复现。
        这里留一个 buffer，只处理以空行结束的完整帧。
      */
      let buffer = ''

      while (reader) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        const frames = buffer.split('\n\n')
        buffer = frames.pop() ?? ''

        for (const frame of frames) {
          const line = frame.trim()
          if (!line.startsWith('data: ')) continue
          const payload = line.slice(6)
          if (payload === '[DONE]') continue

          let data: any
          try {
            data = JSON.parse(payload)
          } catch {
            continue
          }

          if (data.type === 'node_start') {
            // 一个节点真正开始跑了。像素进度带和光晕就挂在这个状态上
            setNodeExecutionStates(prev => ({
              ...prev,
              [data.node_id]: {
                ...(prev[data.node_id] ?? { nodeId: data.node_id, inputs: {}, outputs: {} }),
                nodeId: data.node_id,
                status: 'running',
              },
            }))
          } else if (data.type === 'node_complete') {
            setNodeExecutionStates(prev => ({
              ...prev,
              [data.node_id]: {
                nodeId: data.node_id,
                status: data.status === 'success' ? 'success' : 'failed',
                inputs: data.inputs || prev[data.node_id]?.inputs || {},
                outputs: data.outputs || {},
                executionTime: data.execution_time,
                error: data.error,
              },
            }))
          } else if (data.type === 'llm_chunk') {
            output += data.chunk
            setTestOutput(output)
          } else if (data.type === 'error') {
            addToast({ type: 'error', message: data.error || '执行失败' })
          } else if (data.type === 'complete') {
            // final_output 可能是 null（比如工作流里没有回复节点），
            // 这时退回已经收到的流式文本，而不是显示"执行完成"把内容盖掉
            setTestOutput(data.final_output || output || '执行完成')
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
    history.commit({
      nodes: nodes.filter((n) => n.id !== nodeId),
      edges: edges.filter((e) => e.source !== nodeId && e.target !== nodeId),
    })
    if (selectedNode?.id === nodeId) {
      setSelectedNode(null)
      // 面板里删掉正在配置的那个节点，面板必须一起收 —— 留着一个空壳
      // 面板会让用户以为还有东西没配完
      setMobileSheet(null)
    }
  }

  const handleCopyNode = (node: Node) => {
    const newNode: Node = {
      ...node,
      id: `${node.type}-${Date.now()}`,
      position: { x: node.position.x + 50, y: node.position.y + 50 },
      selected: false,
    }
    history.commit({ nodes: [...nodes, newNode], edges })
  }

  /**
   * 面板内容抽出来复用。
   *
   * 桌面端它们摆在左右两栏；手机上那两栏（256px + 320px）合计比屏幕还宽，
   * 没有立足之地，改由底部面板承载。同一视口只渲染其中一处 —— 见 useIsNarrow
   * 的说明，不是两边都渲染再藏一个。
   */
  const nodePaletteBody = (
    <>
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
                  className="w-full flex items-center gap-3 p-3 rounded-xl bg-slate-50 hover:bg-slate-100
                    active:bg-slate-200 border border-transparent hover:border-slate-200 transition-all group"
                >
                  <div className={`p-2 rounded-lg bg-gradient-to-br ${node.color} shadow-sm group-hover:scale-110 transition-transform`}>
                    <node.icon className="w-4 h-4 text-white" />
                  </div>
                  <span className="text-sm font-medium text-slate-700">{node.label}</span>
                  {/* 手机上没有 hover，这个「+」要常显，否则看不出这一整行是可点的 */}
                  <Plus className="w-4 h-4 text-slate-400 ml-auto opacity-100 lg:opacity-0 lg:group-hover:opacity-100 transition-opacity" />
                </button>
              ))}
            </div>
          )}
        </div>
      ))}
    </>
  )

  const testPanelBody = (
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
  )

  /**
   * 配置面板的复制 / 删除。
   *
   * 只包含按钮、不含标题：桌面端它挂在右栏标题行，手机端挂在底部面板标题行
   * —— 标题各写各的语义才对（桌面是「节点配置」，手机面板的标题还兼作
   * 添加节点 / 测试运行两种状态）。
   */
  const configNodeActions = selectedNode ? (
    <div className="flex items-center gap-1">
      <button onClick={() => handleCopyNode(selectedNode)} className="p-1.5 hover:bg-slate-100 rounded-lg text-slate-500" title="复制">
        <Copy className="w-4 h-4" />
      </button>
      <button onClick={() => handleDeleteNode(selectedNode.id)} className="p-1.5 hover:bg-red-50 rounded-lg text-slate-500 hover:text-red-500" title="删除">
        <Trash2 className="w-4 h-4" />
      </button>
    </div>
  ) : null

  const configPanelBody = selectedNode ? (
    /*
      onFocus 在 React 里是按 focusin 语义冒泡的：面板里任何一个输入框获得
      焦点，就拍一张「改动前」的快照。这样连续改几个字段只占一格历史，
      撤销一次回到刚点进来时的样子，而不是每个字符一格。
    */
    <div onFocus={history.mark}>
      <NodeConfigPanel
        node={nodes.find((n) => n.id === selectedNode.id) || selectedNode}
        nodes={nodes}
        onUpdate={(data) => {
          setNodes(nds => nds.map(n =>
            n.id === selectedNode.id ? { ...n, data: { ...n.data, ...data } } : n
          ))
        }}
        executionState={nodeExecutionStates[selectedNode.id]}
      />
    </div>
  ) : (
    <div className="p-8 text-center">
      <div className="w-12 h-12 rounded-xl bg-slate-100 flex items-center justify-center mx-auto mb-4">
        <Settings className="w-6 h-6 text-slate-400" />
      </div>
      <p className="text-sm text-slate-500">选择一个节点以查看和编辑配置</p>
    </div>
  )

  return (
    /* h-full 而不是 h-screen：见 ChatPage 的说明，h-screen 会被顶栏和底部导航切掉 */
    <div className="h-full flex flex-col bg-slate-100">
      {/*
        页头。

        原本这一行是「返回 + 标题 + 6 个带文字按钮」（测试/撤销/重做/导出/导入/
        保存），没有换行也没有收起 —— 在 375px 手机上约 700px 宽，必然横向
        溢出、按钮被挤出屏幕外。

        分两档：桌面保留全部按钮平铺；手机只留「保存」（最高频，且是唯一的
        不可逆操作）和一个「更多」，其余四项收进下拉。
      */}
      <div className="bg-white border-b border-slate-200 px-3 py-2 sm:px-6 sm:py-4 shrink-0">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 sm:gap-4 min-w-0">
            <Button variant="ghost" size="sm" onClick={() => navigate(-1)} aria-label="返回">
              <ArrowLeft className="w-5 h-5" />
            </Button>
            <div className="min-w-0">
              <h1 className="text-base sm:text-xl font-bold truncate text-slate-900">
                {isNewWorkflow ? '新建工作流' : '编辑工作流'}
              </h1>
              <p className="text-xs sm:text-sm text-slate-500 truncate">
                {nodes.length} 个节点，{edges.length} 条连接
              </p>
            </div>
          </div>

          {/* 桌面：全部操作平铺 */}
          <div className="hidden lg:flex items-center gap-3 shrink-0">
            <Button variant="outline" size="sm" leftIcon={<Zap className="w-4 h-4" />} onClick={() => setShowTestPanel(!showTestPanel)}>
              测试
            </Button>
            {/* 撤销/重做：没得可撤时置灰。摆一个永远亮着但按了没反应的按钮，
                比不摆更糟 —— 用户会以为自己误触，然后反复点 */}
            <Button
              variant="outline"
              size="sm"
              leftIcon={<Undo2 className="w-4 h-4" />}
              onClick={history.undo}
              disabled={!history.canUndo}
              title="撤销（Ctrl+Z）"
            >
              撤销
            </Button>
            <Button
              variant="outline"
              size="sm"
              leftIcon={<Redo2 className="w-4 h-4" />}
              onClick={history.redo}
              disabled={!history.canRedo}
              title="重做（Ctrl+Shift+Z）"
            >
              重做
            </Button>
            <div className="w-px h-6 bg-slate-200 mx-1" />
            <Button variant="outline" size="sm" leftIcon={<Download className="w-4 h-4" />} onClick={handleExport}>导出</Button>
            <Button variant="outline" size="sm" leftIcon={<Upload className="w-4 h-4" />} onClick={() => importInputRef.current?.click()}>
              导入
            </Button>
            <Button size="sm" leftIcon={<Save className="w-4 h-4" />} onClick={handleSave} loading={loading} className="shadow-lg shadow-brand-500/20">
              保存
            </Button>
          </div>

          {/* 手机：保存 + 更多 */}
          <div className="flex lg:hidden items-center gap-2 shrink-0 relative">
            <Button size="sm" leftIcon={<Save className="w-4 h-4" />} onClick={handleSave} loading={loading}>
              保存
            </Button>
            <button
              type="button"
              onClick={() => setMobileMoreOpen(v => !v)}
              aria-label="更多操作"
              aria-expanded={mobileMoreOpen}
              className="p-2.5 rounded-xl border border-slate-200 text-slate-600 hover:bg-slate-50 transition-colors"
            >
              {mobileMoreOpen ? <X className="w-4 h-4" /> : <MoreVertical className="w-4 h-4" />}
            </button>

            {mobileMoreOpen && (
              <>
                {/* 点外面关掉。z-[90] 夹在页面内容之上、菜单之下 */}
                <div
                  className="fixed inset-0 z-[90]"
                  onClick={() => setMobileMoreOpen(false)}
                  aria-hidden="true"
                />
                <div className="absolute right-0 top-full mt-2 z-[95] w-44 py-1 rounded-xl
                  bg-white border border-slate-200 shadow-large">
                  {[
                    { icon: Zap, label: '测试运行', run: () => setMobileSheet('test'), off: false },
                    { icon: Undo2, label: '撤销', run: history.undo, off: !history.canUndo },
                    { icon: Redo2, label: '重做', run: history.redo, off: !history.canRedo },
                    { icon: Download, label: '导出', run: handleExport, off: false },
                    { icon: Upload, label: '导入', run: () => importInputRef.current?.click(), off: false },
                  ].map((item) => (
                    <button
                      key={item.label}
                      type="button"
                      disabled={item.off}
                      onClick={() => {
                        item.run()
                        setMobileMoreOpen(false)
                      }}
                      className="w-full flex items-center gap-3 px-3 py-2.5 text-sm text-slate-700
                        hover:bg-slate-50 active:bg-slate-100 transition-colors
                        disabled:opacity-40 disabled:pointer-events-none"
                    >
                      <item.icon className="w-4 h-4 text-slate-500" />
                      {item.label}
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {/*
        导入用的隐藏 input。提到页头外面：桌面按钮和手机菜单都要触发它，
        放在原来的 <label> 里手机就够不着了。
      */}
      <input
        ref={importInputRef}
        type="file"
        accept=".json"
        onChange={handleImport}
        className="hidden"
      />

      <div className="flex-1 flex overflow-hidden relative">
        {/*
          左栏（节点组件 + 测试运行）。

          桌面常驻；**手机整栏不渲染** —— 它 256px 宽，在 375px 的屏幕上直接
          吃掉三分之二，画布被挤到剩下不到 120px，等于不能用。手机的等价入口
          是画布右下角的「＋」浮层按钮，点了弹出底部面板（见本文件末尾的
          mobileSheet）。
        */}
        {!isNarrow && (
          <div className="w-64 shrink-0 bg-white border-r border-slate-200 overflow-y-auto">
            <div className="p-4">
              <h3 className="text-sm font-semibold text-slate-700 mb-4">节点组件</h3>
              {nodePaletteBody}
            </div>

            {showTestPanel && (
              <div className="p-4 border-t border-slate-200">
                <h3 className="text-sm font-semibold text-slate-700 mb-3">测试运行</h3>
                {testPanelBody}
              </div>
            )}
          </div>
        )}

        {/* Main canvas */}
        {/* ref 之前声明了却没挂到任何元素上 —— 新增节点要按容器尺寸算落点，接上它 */}
        <div ref={reactFlowWrapper} className="flex-1 relative">
          {/*
            像素动效的状态从这里下发到每个节点和每条连线。
            Provider 不产生 DOM 节点，所以这一层的包裹不影响 ReactFlow
            靠容器尺寸算布局的机制（它仍然是那个 flex-1 的 div 的直接内容）。
          */}
          <PixelMotionProvider fresh={freshNodes} run={nodeExecutionStates}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={handleNodesChange}
            onEdgesChange={handleEdgesChange}
            onConnect={onConnect}
            onNodeClick={onNodeClick}
            onNodeDragStart={handleNodeDragStart}
            onInit={(instance: ReactFlowInstance) => setReactFlowInstance(instance)}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            // 兜底：任何没显式写 type 的新边也走像素边
            defaultEdgeOptions={{ type: 'pixel' }}
            fitView
            snapToGrid
            snapGrid={[16, 16]}
            className="bg-slate-50"
          >
            <Background variant={BackgroundVariant.Dots} gap={16} size={1} color="#cbd5e1" />
            <Controls className="bg-white border border-slate-200 rounded-xl shadow-lg" />
            {/*
              小地图。手机上不渲染：画布本身还不到 400px 宽，一张缩略图既看不了
              什么、又盖住右下角的操作区，纯粹占地方。
            */}
            {!isNarrow && (
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
                  case 'agent': return '#0ea5e9'
                  case 'condition': return '#f59e0b'
                  case 'response': return '#6366f1'
                  default: return '#64748b'
                }
              }}
            />
            )}

            {nodes.length === 0 && (
              <Panel position="top-center" className="mt-6 lg:mt-20">
                <Card className="p-6 sm:p-8 text-center shadow-xl">
                  {/*
                    加号换成像素图形（PixelGlyph）。
                    原来是一块品牌色渐变 + 彩色光晕的方块 —— 那是全站唯一一处
                    "彩色发光"，跟设计系统里"细描边、不要彩色光晕"的取向冲突；
                    换成中性底 + 像素加号之后，它和画布上那些像素块成了一家人。
                  */}
                  <div className="mx-auto mb-4 grid h-14 w-14 place-items-center rounded-2xl border border-slate-200 bg-slate-50 text-indigo-600 sm:h-16 sm:w-16 dark:border-slate-800 dark:bg-slate-900 dark:text-indigo-400">
                    <PixelGlyph name="plus" cell={5} />
                  </div>
                  <h3 className="text-base sm:text-lg font-semibold text-slate-900 mb-2">从这里开始构建你的工作流</h3>
                  {/* 手机上不提「左侧」—— 那一栏已经收进底部面板了 */}
                  <p className="text-sm text-slate-500">点右下角的「＋」添加节点，拖动节点可以移动位置</p>
                </Card>
              </Panel>
            )}
          </ReactFlow>
          </PixelMotionProvider>

          {/* 手机浮层操作按钮。桌面侧栏常驻，不需要这一层 */}
          {isNarrow && (
            <div className="absolute right-3 bottom-3 z-10 flex flex-col items-end gap-2">
              {selectedNode && (
                <button
                  type="button"
                  onClick={() => setMobileSheet('config')}
                  aria-label="编辑节点配置"
                  className="w-11 h-11 rounded-full bg-white border border-slate-200 shadow-large
                    flex items-center justify-center text-slate-600 active:scale-95 transition-transform"
                >
                  <Settings className="w-5 h-5" />
                </button>
              )}
              <button
                type="button"
                onClick={() => setMobileSheet('palette')}
                aria-label="添加节点"
                className="w-14 h-14 rounded-full bg-brand-600 text-white shadow-large
                  flex items-center justify-center active:scale-95 transition-transform"
              >
                <Plus className="w-6 h-6" />
              </button>
            </div>
          )}
        </div>

        {/*
          右栏（节点配置）。桌面常驻；手机上收进底部面板 —— 它 320px 宽，
          加上左栏 256px 就是 576px，比手机屏幕还宽，画布宽度会变成负数。
        */}
        {!isNarrow && (
          <div className="w-80 shrink-0 bg-white border-l border-slate-200 overflow-y-auto">
            <div className="p-4 border-b border-slate-100 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-slate-700">节点配置</h3>
              {configNodeActions}
            </div>
            {configPanelBody}
          </div>
        )}

        {/*
          移动端底部面板。三种内容共用一套外壳：添加节点 / 节点配置 / 测试运行。
          用一个状态而不是三个布尔，是因为它们互斥 —— 同时开两个只会互相叠住。
        */}
        {isNarrow && mobileSheet && (
          <>
            <div
              className="fixed inset-0 z-[75] bg-black/40 animate-fade-in"
              onClick={() => setMobileSheet(null)}
              aria-hidden="true"
            />
            <div
              className="fixed inset-x-0 bottom-0 z-[80] flex flex-col max-h-[78dvh]
                rounded-t-2xl bg-white shadow-2xl pb-[env(safe-area-inset-bottom)]"
            >
              <div className="relative shrink-0 px-4 pt-1.5 pb-2 border-b border-slate-100">
                {/* 拖拽把手，暗示这块可以往下收 */}
                <span
                  className="absolute left-1/2 -translate-x-1/2 top-1.5 w-9 h-1 rounded-full bg-slate-300"
                  aria-hidden="true"
                />
                <div className="flex items-center justify-between pt-2.5">
                  <h3 className="text-sm font-semibold text-slate-700">
                    {mobileSheet === 'palette' ? '添加节点'
                      : mobileSheet === 'config' ? '节点配置'
                      : '测试运行'}
                  </h3>
                  <div className="flex items-center gap-1">
                    {mobileSheet === 'config' && configNodeActions}
                    <button
                      type="button"
                      onClick={() => setMobileSheet(null)}
                      aria-label="关闭"
                      className="p-2 -mr-1 rounded-lg text-slate-500 hover:bg-slate-100"
                    >
                      <X className="w-5 h-5" />
                    </button>
                  </div>
                </div>
              </div>
              <div className="flex-1 min-h-0 overflow-y-auto p-4">
                {mobileSheet === 'palette' && nodePaletteBody}
                {mobileSheet === 'config' && configPanelBody}
                {mobileSheet === 'test' && testPanelBody}
              </div>
            </div>
          </>
        )}
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
  const [modelOptions, setModelOptions] = useState<{value: string, label: string}[]>([])
  const [effectiveModel, setEffectiveModel] = useState<string | null>(null)
  const [modelsLoading, setModelsLoading] = useState(true)
  const [modelsError, setModelsError] = useState<string | null>(null)

  useEffect(() => {
    const fetchModels = async () => {
      setModelsLoading(true)
      setModelsError(null)
      try {
        // 用「用户实际能用的模型」，而不是 /templates/models/list 那份静态目录。
        //
        // 两处旧问题：
        // 1. 这个接口返回 {models: [...]}，旧代码取 res.data || res 后直接 .map()，
        //    抛 TypeError 被 catch 吞掉，于是永远只剩写死的两个模型；
        // 2. 静态目录里全是 OpenAI / Anthropic 的型号名，生效端点若是本地
        //    Ollama，选中它们只会得到「模型不存在」。
        const res = await llmConfigs.models()
        const list = res?.models || []
        setEffectiveModel(res?.effective?.model || null)
        setModelOptions(
          list.map((m) => ({
            value: m.id,
            label: m.is_effective
              ? `${m.label}（当前生效 · ${m.provider}）`
              : `${m.label} · ${m.provider}`,
          }))
        )
        if (list.length === 0) {
          setModelsError('还没有可用的模型，请先到「设置 → 模型配置」里添加')
        }
      } catch (error: any) {
        setModelsError(error.message || '加载模型列表失败')
        setModelOptions([])
      } finally {
        setModelsLoading(false)
      }
    }
    fetchModels()
  }, [])

  // 节点里存的模型可能已不在可用列表中（例如换过生效配置）。
  // 直接拿 node.data.model 当 value 的话，下拉会显示成第一项、但存的值没变，
  // 执行时发出去的仍是一个该端点上不存在的模型名。
  // 这里统一按「可用则用、不可用则回落到生效模型」来渲染。
  const nodeModel = node.data.model || ''
  const modelAvailable = modelOptions.some((o) => o.value === nodeModel)
  const selectedModel = modelAvailable ? nodeModel : effectiveModel || ''

  // 智能体 / 技能下拉：只有打开该节点时才拉取，避免每次进编辑器都请求
  const [agentOptions, setAgentOptions] = useState<{ value: string; label: string }[]>([])
  const [skillOptions, setSkillOptions] = useState<{ value: string; label: string }[]>([])
  const [agentOptsLoading, setAgentOptsLoading] = useState(false)
  const [skillOptsLoading, setSkillOptsLoading] = useState(false)
  const [agentOptsError, setAgentOptsError] = useState<string | null>(null)
  const [skillOptsError, setSkillOptsError] = useState<string | null>(null)

  // 外部数据连接器下拉（仅 erp_read 工具节点用）
  const [connectorOptions, setConnectorOptions] = useState<{ value: string; label: string }[]>([])
  const [connectorTables, setConnectorTables] = useState<Record<string, string[]>>({})
  const [connectorOptsLoading, setConnectorOptsLoading] = useState(false)
  const [connectorOptsError, setConnectorOptsError] = useState<string | null>(null)

  useEffect(() => {
    if (node.type !== 'tool' || node.data?.tool_name !== 'erp_read') return
    if (connectorOptions.length > 0 || connectorOptsLoading) return

    setConnectorOptsLoading(true)
    connectors
      .list()
      .then((list) => {
        setConnectorOptions(list.map((c) => ({ value: c.id, label: c.alias })))
        const tables: Record<string, string[]> = {}
        list.forEach((c) => { tables[c.id] = c.allowed_tables || [] })
        setConnectorTables(tables)
      })
      .catch((e: any) => setConnectorOptsError(e?.message || '连接器列表加载失败'))
      .finally(() => setConnectorOptsLoading(false))
  }, [node.type, node.data?.tool_name, connectorOptions.length, connectorOptsLoading])

  useEffect(() => {
    if (node.type !== 'agent' || agentOptions.length > 0 || agentOptsLoading) return

    setAgentOptsLoading(true)
    api
      .get('/agents')
      .then((list: any) => {
        const arr = Array.isArray(list) ? list : list?.items ?? []
        setAgentOptions(arr.map((a: any) => ({ value: a.id, label: a.name })))
      })
      .catch((e: any) => setAgentOptsError(e?.message || 'Agent 列表加载失败'))
      .finally(() => setAgentOptsLoading(false))
  }, [node.type, agentOptions.length, agentOptsLoading])

  useEffect(() => {
    if (node.type !== 'agent' || skillOptions.length > 0 || skillOptsLoading) return

    setSkillOptsLoading(true)
    // 取 AI Agent 引擎实际可用的技能：节点最终传给引擎的就是这一份
    pi.status()
      .then((st: any) => {
        const names: string[] = Array.isArray(st?.skills) ? st.skills : []
        setSkillOptions(names.map((s: string) => ({ value: s, label: s })))
      })
      .catch((e: any) => setSkillOptsError(e?.message || '技能列表加载失败'))
      .finally(() => setSkillOptsLoading(false))
  }, [node.type, skillOptions.length, skillOptsLoading])

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
            <Select label="模型" value={selectedModel} onChange={(e) => onUpdate({ model: e.target.value })}
              options={modelOptions}
              disabled={modelsLoading || modelOptions.length === 0}
            />
            {modelsLoading && (
              <p className="text-xs text-slate-400 mt-1">加载模型中...</p>
            )}
            {modelsError && (
              <p className="text-xs text-red-500 mt-1">{modelsError}</p>
            )}
            {/* 字段里存了模型、但它不在可用列表里（比如换过生效配置）：
                必须显式提示 —— 否则界面看着是选中了某项，实际执行时
                发出去的还是那个该端点上不存在的旧模型名 */}
            {!modelsLoading && modelOptions.length > 0 && !!nodeModel && !modelAvailable && (
              <p className="text-xs text-amber-600 mt-1">
                原模型「{nodeModel}」不在当前可用列表中，执行时会使用「{selectedModel}」。
                重新选择一次并保存即可固定下来。
              </p>
            )}
            {!modelsLoading && modelOptions.length > 0 && !nodeModel && (
              <p className="text-xs text-slate-400 mt-1">
                未指定时跟随「设置 → 模型配置」里当前生效的模型
                {effectiveModel ? `（${effectiveModel}）` : ''}
              </p>
            )}
            <Input label="系统提示词" value={node.data.system_prompt} onChange={(e) => onUpdate({ system_prompt: e.target.value })} placeholder="设置 AI 角色..." />
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700">提示词模板</label>
              <textarea
                value={node.data.prompt}
                onChange={(e) => onUpdate({ prompt: e.target.value })}
                placeholder="使用 {{变量名}} 引用上下文..."
                rows={4}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
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
      
      case 'agent':
        return (
          <>
            <Input label="节点名称" value={node.data.label} onChange={(e) => onUpdate({ label: e.target.value })} />
            <Select
              label="目标 Agent"
              value={node.data.agent_id || ''}
              onChange={(e) => {
                const picked = agentOptions.find((o) => o.value === e.target.value)
                onUpdate({ agent_id: e.target.value, agent_name: picked?.label || '' })
              }}
              options={agentOptions}
              disabled={agentOptsLoading}
              placeholder="留空则使用当前 Agent"
            />
            {agentOptsLoading && <p className="text-xs text-slate-400 mt-1">加载 Agent 中...</p>}
            {agentOptsError && <p className="text-xs text-red-500 mt-1">{agentOptsError}</p>}

            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700">
                启用技能
                <span className="ml-2 text-xs font-normal text-slate-400">
                  不选则不加载任何技能
                </span>
              </label>
              {skillOptsLoading ? (
                <p className="text-xs text-slate-400">加载技能中...</p>
              ) : skillOptions.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {skillOptions.map((option) => {
                    const selected: string[] = Array.isArray(node.data.skills)
                      ? node.data.skills
                      : []
                    const active = selected.includes(option.value)
                    return (
                      <button
                        key={option.value}
                        type="button"
                        onClick={() =>
                          onUpdate({
                            skills: active
                              ? selected.filter((s) => s !== option.value)
                              : [...selected, option.value],
                          })
                        }
                        className={`inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-xs border transition-colors ${
                          active
                            ? 'bg-slate-900 border-slate-900 text-white dark:bg-white dark:text-slate-900 dark:border-white'
                            : 'border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:border-slate-400'
                        }`}
                      >
                        {active && <Check className="w-3 h-3" />}
                        {option.label}
                      </button>
                    )
                  })}
                </div>
              ) : (
                <p className="text-xs text-slate-400">
                  {skillOptsError || 'AI Agent 引擎未启用，没有可用技能'}
                </p>
              )}
            </div>

            <Input
              label="输入内容"
              value={node.data.input || ''}
              onChange={(e) => onUpdate({ input: e.target.value })}
              placeholder="留空则自动取上游节点的输出"
            />
            <Input
              label="超时（秒，可选）"
              value={node.data.timeout || ''}
              onChange={(e) => onUpdate({ timeout: e.target.value })}
              placeholder="留空用引擎默认值"
            />
            <p className="text-xs text-slate-400">
              Agent 产出可在响应节点用{' '}
              <code className="px-1 rounded bg-slate-100">{'{{节点ID.output}}'}</code> 引用
            </p>
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
                { value: 'erp_read', label: 'ERP 数据读取（只读）' },
              ]}
            />
            {node.data.tool_name === 'calculator' && (
              <Input label="表达式" value={node.data.tool_params?.expression || ''} onChange={(e) => onUpdate({ tool_params: { ...node.data.tool_params, expression: e.target.value } })} placeholder="如: 100 + 200" />
            )}
            {node.data.tool_name === 'formatter' && (
              <Input label="模板" value={node.data.tool_params?.template || ''} onChange={(e) => onUpdate({ tool_params: { ...node.data.tool_params, template: e.target.value } })} placeholder='如: "结果: {input}"' />
            )}
            {node.data.tool_name === 'erp_read' && (
              <>
                <Select
                  label="连接器"
                  value={node.data.tool_params?.connector_id || ''}
                  onChange={(e) => onUpdate({ tool_params: { ...node.data.tool_params, connector_id: e.target.value, resource: '' } })}
                  options={connectorOptions}
                  disabled={connectorOptsLoading || connectorOptions.length === 0}
                  placeholder="请选择连接器"
                />
                {connectorOptsLoading && <p className="text-xs text-slate-400">加载连接器中…</p>}
                {connectorOptsError && <p className="text-xs text-red-500">{connectorOptsError}</p>}
                {!connectorOptsLoading && connectorOptions.length === 0 && (
                  <p className="text-xs text-amber-600">还没有连接器，请先到「设置 → 数据连接器」新建。</p>
                )}
                {(connectorTables[node.data.tool_params?.connector_id] || []).length > 0 ? (
                  <Select
                    label="表名（resource）"
                    value={node.data.tool_params?.resource || ''}
                    onChange={(e) => onUpdate({ tool_params: { ...node.data.tool_params, resource: e.target.value } })}
                    options={connectorTables[node.data.tool_params?.connector_id].map((t) => ({ value: t, label: t }))}
                    placeholder="选择表"
                  />
                ) : (
                  <Input label="表名（resource）" value={node.data.tool_params?.resource || ''} onChange={(e) => onUpdate({ tool_params: { ...node.data.tool_params, resource: e.target.value } })} placeholder="须在连接器白名单内，如 customers" />
                )}
                <Input label="行数上限（可选）" value={node.data.tool_params?.limit ?? ''} onChange={(e) => onUpdate({ tool_params: { ...node.data.tool_params, limit: e.target.value ? Number(e.target.value) : undefined } })} placeholder="留空则用连接器的默认行限" />
                <p className="text-xs text-slate-400">读到的数据会经连接器脱敏后，自动作为下游智能体节点（PiAgent）的输入。</p>
              </>
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
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
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
      <div className="flex items-center gap-3 p-3 rounded-xl bg-gradient-to-r from-brand-50 to-brand-50">
        <div className="p-2 rounded-lg bg-gradient-to-br from-brand-500 to-brand-600">
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
