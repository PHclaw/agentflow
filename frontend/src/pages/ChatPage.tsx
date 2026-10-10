import React, { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeft,
  ArrowUp,
  Bot,
  BookOpen,
  Brain,
  Check,
  ChevronDown,
  Copy,
  Download,
  MessageSquare,
  Paperclip,
  Plus,
  RefreshCw,
  Settings,
  Sparkles,
  Square,
  Terminal,
  ThumbsDown,
  ThumbsUp,
  Wrench,
  X,
  Zap,
} from 'lucide-react'
import { api } from '../services/api'
import { chat as chatApi, pi, type PiArtifact, type PiStatus } from '../services/api'
import { Markdown } from '../components/ui/Markdown'
import { Modal } from '../components/ui/Modal'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: string
  sources?: any[]
  thinking?: string
  /** PiAgent 引擎生成的可下载附件 */
  files?: PiArtifact[]
  /** PiAgent 引擎执行过程中的工具调用记录 */
  toolCalls?: string[]
}

interface AgentInfo {
  id: string
  name: string
  description: string
  model: string
}

type Engine = 'builtin' | 'pi'

/** PiAgent 运行过程中的实时事件状态 */
interface PiLiveState {
  logs: string[]
  toolCalls: string[]
  thinking: string
  text: string
}

/** 输入框上方附挂的功能项 */
interface PanelItem {
  key: string
  icon: React.ComponentType<{ className?: string }>
  label: string
  hint?: string
  active?: boolean
  disabled?: boolean
  onClick: () => void
}

const EMPTY_PI_LIVE: PiLiveState = { logs: [], toolCalls: [], thinking: '', text: '' }

interface ChatSessionProps {
  /** Agent id */
  id: string
  /** 从技能广场进入时携带的技能 id：自动启用该技能 */
  skillId?: string
  /** 技能流程下切换 Agent 的回调（不传则不显示切换入口） */
  onSwitchAgent?: () => void
}

export function ChatSession({ id, skillId, onSwitchAgent }: ChatSessionProps) {
  const navigate = useNavigate()
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  const [agent, setAgent] = useState<AgentInfo | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [inputMessage, setInputMessage] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [streamingContent, setStreamingContent] = useState('')
  const [showSettings, setShowSettings] = useState(false)
  const [showPanel, setShowPanel] = useState(false)
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [feedbackGiven, setFeedbackGiven] = useState<Record<string, string>>({})
  const [settings, setSettings] = useState({
    model: 'gpt-4o-mini',
    temperature: 0.7,
    systemPrompt: '',
  })

  // PiAgent 引擎相关状态
  const [engine, setEngine] = useState<Engine>('builtin')
  const [piStatus, setPiStatus] = useState<PiStatus | null>(null)
  const [piLive, setPiLive] = useState<PiLiveState>(EMPTY_PI_LIVE)
  const [expandedThinking, setExpandedThinking] = useState<Record<string, boolean>>({})
  const [piSessionId, setPiSessionId] = useState<string | null>(null)
  const [selectedSkills, setSelectedSkills] = useState<string[]>([])
  /** 该 Agent 是否配置了工作流（配了则由工作流编排执行） */
  const [hasWorkflow, setHasWorkflow] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  const piReady = Boolean(piStatus?.enabled && piStatus?.available)

  /**
   * 实际生效的引擎。
   *
   * 配了工作流的 Agent 只能走内置链路（后端只在 /chat 上按编排执行，
   * AI Agent 引擎不读工作流）。
   *
   * 这里用派生值而不是用 effect 去改 engine：loadPiStatus 会在拿到状态后
   * 无条件 setEngine('pi')，而 React 严格模式下 effect 会执行两次，第二个
   * 请求返回时 piReady 值没变、依赖不触发，兜底的 effect 不会重跑，
   * 引擎就会停在 pi。派生值不受这个竞态影响。
   */
  const effectiveEngine: Engine = hasWorkflow ? 'builtin' : engine
  const isEmptyState = messages.length === 0 && !isLoading && !streamingContent

  useEffect(() => {
    loadAgent()
    loadHistory()
    loadPiStatus()
  }, [id])

  const loadPiStatus = async () => {
    try {
      const status = await pi.status()
      setPiStatus(status)
      // pi 引擎就绪时默认使用它
      if (status.enabled && status.available) setEngine('pi')
    } catch {
      setPiStatus(null)
    }
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages, streamingContent])

  // 从技能广场进入：自动启用该技能。
  // 技能只有 AI Agent 引擎支持（内置链路不传 skills），因此同时把引擎切过去。
  useEffect(() => {
    if (!skillId) return
    setSelectedSkills((prev) => (prev.includes(skillId) ? prev : [...prev, skillId]))
    if (piReady && !hasWorkflow) setEngine('pi')
  }, [skillId, piReady, hasWorkflow])

  // 输入框随内容增高（上限 200px），与参考实现的告示输入区一致
  useEffect(() => {
    const el = inputRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`
  }, [inputMessage])

  const loadAgent = async () => {
    try {
      const data = await api.get(`/agents/${id}`)
      setAgent({
        id: data.id,
        name: data.name,
        description: data.description || '',
        model: data.model || 'gpt-4o-mini',
      })
      const nodes = data.workflow_definition?.nodes ?? []
      setHasWorkflow(nodes.length > 0)
    } catch (error) {
      console.error('Failed to load agent:', error)
    }
  }

  const loadHistory = async () => {
    try {
      const data = await api.get(`/chat/${id}/history`)
      if (data?.messages) {
        setMessages(data.messages)
      }
    } catch (error) {
      // 尚无历史会话，不算错误
    }
  }

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const copyMessage = (content: string) => {
    navigator.clipboard.writeText(content)
  }

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  }

  const toggleThinking = (key: string) =>
    setExpandedThinking((prev) => ({ ...prev, [key]: !prev[key] }))

  /** 下载 PiAgent 工作区产物 */
  const handleDownloadArtifact = async (file: PiArtifact) => {
    try {
      // 优先用产物自带的 url：工作流里的智能体节点可能指向另一个 Agent，
      // 它的 url 里带的是真正持有该工作区的 agent id，
      // 若一律用当前 id 拼路径会 404
      const blob = file.url
        ? await api.getBlob(file.url)
        : await pi.downloadArtifact(id!, file.path)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = file.name
      a.click()
      URL.revokeObjectURL(url)
    } catch (error: any) {
      alert(error?.message || '下载失败')
    }
  }

  const handleFeedback = async (messageId: string, rating: string) => {
    try {
      await chatApi.feedback(id!, messageId, rating)
      setFeedbackGiven(prev => ({ ...prev, [messageId]: rating }))
    } catch (error) {
      console.error('Feedback error:', error)
    }
  }

  const handleRegenerate = async () => {
    // 找到最后一条用户消息并重新发送
    const lastUserMsg = [...messages].reverse().find(m => m.role === 'user')
    if (!lastUserMsg || isLoading) return

    // 删除最后一条 assistant 消息
    setMessages(prev => {
      const idx = prev.map(m => m.id).lastIndexOf(lastUserMsg.id)
      return prev.slice(0, idx + 1)
    })

    // 重新发送
    setInputMessage(lastUserMsg.content)
    setTimeout(() => handleSend(), 100)
  }

  const handleStop = () => {
    abortRef.current?.abort()
    abortRef.current = null
    setIsLoading(false)
  }

  const handleNewChat = () => {
    setMessages([])
    setConversationId(null)
    setPiSessionId(null)
    setStreamingContent('')
    setPiLive(EMPTY_PI_LIVE)
    setInputMessage('')
    inputRef.current?.focus()
  }

  /** 内置链路：直连大模型或按工作流编排执行
   *  （SSE：session / chunk / done / error，done 可能带 files）
   */
  const sendWithBuiltin = async (
    message: string,
    signal: AbortSignal
  ): Promise<{ content: string; files: PiArtifact[] }> => {
    let fullContent = ''
    let files: PiArtifact[] = []

    for await (const event of chatApi.stream(id!, message, conversationId, signal)) {
      if (event.type === 'session' && event.session_id) {
        setConversationId(event.session_id)
      } else if (event.type === 'chunk' && event.content) {
        fullContent += event.content
        setStreamingContent(fullContent)
      } else if (event.type === 'done') {
        if (event.content) fullContent = event.content
        if (event.session_id) setConversationId(event.session_id)
        // 工作流里的智能体节点生成的产物要作为附件展示
        if (event.files?.length) files = event.files
      } else if (event.type === 'error') {
        throw new Error(event.error || '对话失败')
      }
    }

    return {
      content: fullContent || '抱歉，我暂时无法回答这个问题。',
      files,
    }
  }

  /** PiAgent 链路：外部 agent CLI，带思考/工具调用/产物 */
  const sendWithPi = async (message: string, signal: AbortSignal) => {
    let text = ''
    let thinking = ''
    const toolCalls: string[] = []
    const logs: string[] = []
    let files: PiArtifact[] = []

    setPiLive(EMPTY_PI_LIVE)

    for await (const event of pi.stream(
      id!,
      {
        message,
        session_id: piSessionId,
        skills: selectedSkills.length ? selectedSkills : undefined,
      },
      signal
    )) {
      switch (event.type) {
        case 'log':
          if (event.content) {
            logs.push(event.content)
            setPiLive((prev) => ({ ...prev, logs: [...logs] }))
          }
          break
        case 'thinking':
          thinking += event.content || ''
          setPiLive((prev) => ({ ...prev, thinking }))
          break
        case 'tool_call':
          if (event.content) {
            toolCalls.push(event.content)
            setPiLive((prev) => ({ ...prev, toolCalls: [...toolCalls] }))
          }
          break
        case 'text':
          text += event.content || ''
          setPiLive((prev) => ({ ...prev, text }))
          break
        case 'done':
          if (event.content) text = event.content
          files = event.files || []
          if (event.session_id) setPiSessionId(event.session_id)
          break
        case 'error':
          throw new Error(event.content || 'AI Agent 执行失败')
      }
    }

    return {
      content: text || '（AI Agent 未返回内容）',
      files,
      toolCalls,
      thinking,
    }
  }

  const handleSend = async () => {
    if (!inputMessage.trim() || isLoading) return

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: inputMessage,
      timestamp: new Date().toISOString(),
    }

    setMessages((prev) => [...prev, userMessage])
    const currentInput = inputMessage
    setInputMessage('')
    setIsLoading(true)
    setStreamingContent('')
    setShowPanel(false)

    const controller = new AbortController()
    abortRef.current = controller

    try {
      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: '',
        timestamp: new Date().toISOString(),
      }

      if (effectiveEngine === 'pi') {
        const result = await sendWithPi(currentInput, controller.signal)
        assistantMessage.content = result.content
        assistantMessage.files = result.files
        assistantMessage.toolCalls = result.toolCalls
        assistantMessage.thinking = result.thinking
      } else {
        const result = await sendWithBuiltin(currentInput, controller.signal)
        assistantMessage.content = result.content
        if (result.files.length) assistantMessage.files = result.files
      }

      setMessages((prev) => [...prev, assistantMessage])
    } catch (error: any) {
      // 用户主动停止不算错误
      if (error?.name !== 'AbortError') {
        console.error('Chat error:', error)
        setMessages((prev) => [
          ...prev,
          {
            id: (Date.now() + 1).toString(),
            role: 'assistant',
            content: error?.message || '抱歉，发生了错误。请稍后重试。',
            timestamp: new Date().toISOString(),
          },
        ])
      }
    } finally {
      setIsLoading(false)
      setStreamingContent('')
      setPiLive(EMPTY_PI_LIVE)
      abortRef.current = null
    }
  }

  // ---------------------------------------------------------------- 输入区

  /** 输入框上方附挂的功能项。全部对应真实可用的能力，不放占位按钮。 */
  const panelItems: PanelItem[] = [
    {
      key: 'engine',
      icon: Sparkles,
      label: hasWorkflow ? '工作流编排' : engine === 'pi' ? 'AI Agent 引擎' : '内置模型',
      hint: hasWorkflow
        ? '该 Agent 已配置工作流，按画布编排执行'
        : piReady
          ? '点击切换引擎'
          : '仅内置模型可用',
      active: true,
      // 配了工作流就不能切换引擎：工作流只在编排链路上生效
      disabled: !piReady || hasWorkflow,
      onClick: () => setEngine((prev) => (prev === 'pi' ? 'builtin' : 'pi')),
    },
  ]

  if (effectiveEngine === 'pi' && piStatus?.skills?.length) {
    const count = selectedSkills.length
    panelItems.push({
      key: 'skills',
      icon: Wrench,
      label: count ? `已选 ${count} 项技能` : '选择技能',
      hint: '来自仓库 skills/ 目录',
      active: count > 0,
      onClick: () => {
        setShowPanel(false)
        setShowSettings(true)
      },
    })
  }

  const renderComposer = (variant: 'hero' | 'docked') => (
    <div className={variant === 'hero' ? 'w-full max-w-2xl' : 'w-full max-w-2xl mx-auto'}>
      {/* 已启用的技能：会随每次请求带给 AI Agent 引擎 */}
      {selectedSkills.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-2">
          {selectedSkills.map((name) => (
            <span
              key={name}
              className="inline-flex items-center gap-1.5 pl-2.5 pr-1.5 py-1 rounded-full bg-slate-100 dark:bg-slate-800 text-xs text-slate-600 animate-fade-in"
            >
              <Wrench className="w-3 h-3" />
              {name}
              <button
                type="button"
                onClick={() => setSelectedSkills((prev) => prev.filter((s) => s !== name))}
                title="取消使用该技能"
                className="p-0.5 rounded-full hover:bg-slate-200 dark:hover:bg-slate-700"
              >
                <X className="w-3 h-3" />
              </button>
            </span>
          ))}
        </div>
      )}

      {hasWorkflow && (
        <p className="mb-2 text-xs text-slate-400">
          该 Agent 已配置工作流，对话按工作流编排执行。
        </p>
      )}

      {hasWorkflow && selectedSkills.length > 0 && (
        <p className="mb-2 text-xs text-amber-600 dark:text-amber-500">
          工作流编排优先，已选技能不会随本次对话执行；清空工作流后技能才生效。
        </p>
      )}

      {skillId && !piReady && !hasWorkflow && (
        <p className="mb-2 text-xs text-amber-600 dark:text-amber-500">
          该技能依赖 AI Agent 引擎，当前未启用；对话仍可继续，但技能不会被执行。
        </p>
      )}

      {/* 附挂功能项 */}
      {showPanel && panelItems.length > 0 && (
        <div className="mb-2 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-1.5 shadow-sm">
          {panelItems.map((item) => (
            <button
              key={item.key}
              onClick={item.onClick}
              disabled={item.disabled}
              className={`flex items-center gap-2.5 w-full px-3 py-2 rounded-xl text-left text-sm transition-colors ${
                item.disabled
                  ? 'opacity-40 cursor-not-allowed text-slate-400'
                  : 'text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800'
              }`}
            >
              <item.icon className="w-4 h-4 flex-shrink-0 text-slate-400" />
              <span className="font-medium">{item.label}</span>
              {item.hint && (
                <span className="text-xs font-normal text-slate-400">{item.hint}</span>
              )}
              {item.active && <Check className="w-4 h-4 ml-auto text-slate-900 dark:text-white" />}
            </button>
          ))}
        </div>
      )}

      {/* 输入卡片 */}
      <div className="rounded-[26px] border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-[0_2px_20px_rgba(15,23,42,0.06)] dark:shadow-none focus-within:border-slate-300 dark:focus-within:border-slate-700 transition-colors">
        <textarea
          ref={inputRef}
          value={inputMessage}
          onChange={(e) => setInputMessage(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="尽管问，带图也行"
          rows={1}
          /*
           * 这里要显式清掉焦点环：
           * index.css 有一条全局 *:focus-visible { ring-2 ring-indigo-500 }，
           * ring 是 box-shadow 而非 outline，所以只写 focus:outline-none 挡不住它，
           * 会在输入框四周描出一圈紫色方框（且不跟随卡片圆角）。
           * 聚焦反馈由外层卡片的 focus-within:border-* 承担。
           */
          className="w-full bg-transparent px-5 pt-4 pb-1 text-[15px] text-slate-900 dark:text-white placeholder-slate-400 resize-none focus:outline-none focus-visible:outline-none focus-visible:ring-0 focus-visible:ring-offset-0"
          style={{ maxHeight: '200px' }}
        />

        <div className="flex items-center justify-between px-3.5 pb-3 pt-1">
          {panelItems.length > 0 ? (
            <button
              onClick={() => setShowPanel((v) => !v)}
              title="更多能力"
              className={`p-2 rounded-full transition-colors ${
                showPanel
                  ? 'bg-slate-900 text-white dark:bg-white dark:text-slate-900'
                  : 'text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800'
              }`}
            >
              <Plus
                className={`w-4 h-4 transition-transform ${showPanel ? 'rotate-45' : ''}`}
              />
            </button>
          ) : (
            <span />
          )}

          <button
            onClick={isLoading ? handleStop : handleSend}
            disabled={!isLoading && !inputMessage.trim()}
            title={isLoading ? '停止生成' : '发送'}
            className={`w-9 h-9 flex items-center justify-center rounded-full transition-colors ${
              isLoading
                ? 'bg-slate-900 text-white dark:bg-white dark:text-slate-900'
                : inputMessage.trim()
                  ? 'bg-slate-900 text-white hover:bg-slate-700 dark:bg-white dark:text-slate-900'
                  : 'bg-slate-100 text-slate-400 dark:bg-slate-800 dark:text-slate-600 cursor-not-allowed'
            }`}
          >
            {isLoading ? <Square className="w-3.5 h-3.5 fill-current" /> : <ArrowUp className="w-4 h-4" />}
          </button>
        </div>
      </div>
    </div>
  )

  // ---------------------------------------------------------------- 消息渲染

  const renderThinking = (key: string, thinking: string, streaming = false) => {
    const open = Boolean(expandedThinking[key])
    return (
      <button
        onClick={() => toggleThinking(key)}
        className="flex items-center gap-1.5 mb-2 text-sm text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 transition-colors"
      >
        <Brain className={`w-4 h-4 ${streaming ? 'animate-pulse' : ''}`} />
        <span>{streaming ? '思考中…' : '思考已完成'}</span>
        <ChevronDown className={`w-3.5 h-3.5 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
    )
  }

  const assistantAvatar = (
    <div className="flex-shrink-0 w-7 h-7 rounded-full bg-gradient-to-br from-sky-400 to-blue-500 flex items-center justify-center">
      <Sparkles className="w-3.5 h-3.5 text-white" />
    </div>
  )

  const renderArtifacts = (files: PiArtifact[]) => (
    <div className="mt-3 space-y-2">
      {files.map((file) => (
        <button
          key={file.path}
          onClick={() => handleDownloadArtifact(file)}
          className="flex items-center gap-2 w-full px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-700 hover:border-slate-300 dark:hover:border-slate-600 text-sm text-left transition-colors"
        >
          <Paperclip className="w-4 h-4 text-slate-400 flex-shrink-0" />
          <span className="flex-1 truncate">{file.name}</span>
          <span className="text-xs text-slate-400">{formatSize(file.size)}</span>
          <Download className="w-4 h-4 text-slate-400 flex-shrink-0" />
        </button>
      ))}
    </div>
  )

  const renderToolCalls = (toolCalls: string[]) => (
    <div className="mt-3 flex flex-wrap gap-2">
      {toolCalls.map((tool, i) => (
        <span
          key={i}
          className="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 text-xs text-slate-600 dark:text-slate-300"
        >
          <Terminal className="w-3 h-3" />
          {tool}
        </span>
      ))}
    </div>
  )

  /** 助手消息下方的操作条；只放已实现的能力 */
  const renderActions = (message: Message, extra?: React.ReactNode) => (
    <div className="flex items-center gap-1 mt-2 -ml-1.5 text-slate-400">
      <button
        onClick={() => copyMessage(message.content)}
        title="复制"
        className="p-1.5 rounded-lg hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
      >
        <Copy className="w-3.5 h-3.5" />
      </button>
      {extra}
      {message.role === 'assistant' && (
        <>
          <button
            onClick={handleRegenerate}
            title="重新生成"
            className="p-1.5 rounded-lg hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => handleFeedback(message.id, 'up')}
            title="赞同"
            className={`p-1.5 rounded-lg ${
              feedbackGiven[message.id] === 'up'
                ? 'text-emerald-500 bg-emerald-50 dark:bg-emerald-900/20'
                : 'hover:text-emerald-500 hover:bg-slate-100 dark:hover:bg-slate-800'
            }`}
          >
            <ThumbsUp className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => handleFeedback(message.id, 'down')}
            title="反对"
            className={`p-1.5 rounded-lg ${
              feedbackGiven[message.id] === 'down'
                ? 'text-red-500 bg-red-50 dark:bg-red-900/20'
                : 'hover:text-red-500 hover:bg-slate-100 dark:hover:bg-slate-800'
            }`}
          >
            <ThumbsDown className="w-3.5 h-3.5" />
          </button>
        </>
      )}
    </div>
  )

  // ---------------------------------------------------------------- 页面

  return (
    <div className="h-screen flex flex-col bg-white dark:bg-slate-950">
      {/* 顶栏：保持极简，仅保留导航与必要控制 */}
      <header className="flex-shrink-0 px-4 py-3">
        <div className="flex items-center justify-between max-w-3xl mx-auto">
          <div className="flex items-center gap-2 min-w-0">
            <button
              onClick={() => navigate(-1)}
              title="返回"
              className="p-2 rounded-full text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-900 transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
            </button>
            <button
              onClick={() => setShowSettings((v) => !v)}
              title="对话设置"
              className="flex items-center gap-1 min-w-0 px-1 text-[15px] font-medium text-slate-900 dark:text-white hover:text-slate-600 dark:hover:text-slate-300 transition-colors"
            >
              <span className="truncate max-w-[40vw]">{agent?.name || '新对话'}</span>
              <ChevronDown
                className={`w-4 h-4 flex-shrink-0 transition-transform ${
                  showSettings ? 'rotate-180' : ''
                }`}
              />
            </button>
          </div>

          <div className="flex items-center gap-1">
            {onSwitchAgent && (
              <button
                onClick={onSwitchAgent}
                title="换一个 Agent 使用该技能"
                className="px-2.5 py-1.5 rounded-lg text-xs text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-900 transition-colors"
              >
                切换 Agent
              </button>
            )}
            {!isEmptyState && (
              <button
                onClick={handleNewChat}
                title="新对话"
                className="p-2 rounded-lg text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-900 transition-colors"
              >
                <Plus className="w-4 h-4" />
              </button>
            )}
            <button
              onClick={() => setShowSettings((v) => !v)}
              title="对话设置"
              className={`p-2 rounded-lg transition-colors ${
                showSettings
                  ? 'bg-slate-100 text-slate-900 dark:bg-slate-800 dark:text-white'
                  : 'text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-900'
              }`}
            >
              <Settings className="w-4 h-4" />
            </button>
          </div>
        </div>
      </header>

      {/* 对话设置：浮窗呈现。内容与之前的行内面板完全一致，
          只是容器换成 Modal（自带遮罩、ESC 关闭、点击遮罩关闭、锁定背景滚动） */}
      <Modal
        isOpen={showSettings}
        onClose={() => setShowSettings(false)}
        title="对话设置"
        size="full"
      >
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-500 mb-1">模型</label>
                <select
                  value={settings.model}
                  onChange={(e) => setSettings({ ...settings, model: e.target.value })}
                  className="w-full px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm"
                >
                  <option value="gpt-4o-mini">GPT-4o Mini</option>
                  <option value="gpt-4o">GPT-4o</option>
                  <option value="claude-sonnet-4-20250514">Claude Sonnet 4</option>
                  <option value="deepseek-chat">DeepSeek V3</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-500 mb-1">
                  温度: {settings.temperature}
                </label>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.1"
                  value={settings.temperature}
                  onChange={(e) => setSettings({ ...settings, temperature: parseFloat(e.target.value) })}
                  className="w-full"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-500 mb-1">系统提示词</label>
                <input
                  type="text"
                  value={settings.systemPrompt}
                  onChange={(e) => setSettings({ ...settings, systemPrompt: e.target.value })}
                  placeholder="（Agent 侧配置优先）"
                  className="w-full px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm"
                />
              </div>
            </div>

            {effectiveEngine === 'pi' && (
              <div className="mt-4 pt-4 border-t border-slate-100 dark:border-slate-800">
                <label className="block text-xs font-medium text-slate-500 mb-2">
                  启用技能
                  <span className="ml-2 font-normal text-slate-400">
                    来自仓库 skills/ 目录，不选则不加载任何技能
                  </span>
                </label>
                {piStatus?.skills?.length ? (
                  <div className="flex flex-wrap gap-2">
                    {piStatus.skills.map((name) => {
                      const active = selectedSkills.includes(name)
                      return (
                        <button
                          key={name}
                          onClick={() =>
                            setSelectedSkills((prev) =>
                              prev.includes(name) ? prev.filter((s) => s !== name) : [...prev, name]
                            )
                          }
                          className={`inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-xs border transition-colors ${
                            active
                              ? 'bg-slate-900 border-slate-900 text-white dark:bg-white dark:text-slate-900 dark:border-white'
                              : 'border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:border-slate-400'
                          }`}
                        >
                          {active && <Check className="w-3 h-3" />}
                          {name}
                        </button>
                      )
                    })}
                  </div>
                ) : (
                  <p className="text-sm text-slate-400">未发现可用技能</p>
                )}
              </div>
            )}
      </Modal>

      {isEmptyState ? (
        /* 空状态：大字标题 + 居中输入区 */
        <main className="flex-1 flex flex-col items-center justify-center px-6 pb-16 overflow-y-auto">
          <div className="w-full max-w-2xl text-center mb-8">
            <h1 className="text-5xl font-bold tracking-tight text-slate-900 dark:text-white mb-4">
              {agent?.name || 'AI Agent'}
            </h1>
            <p className="text-slate-500 dark:text-slate-400">
              {agent?.description || '我是您的智能助手，可以回答问题、帮助完成任务。'}
            </p>
          </div>

          {renderComposer('hero')}

          {/* 快捷入口 */}
          <div className="flex flex-wrap justify-center gap-2 mt-6">
            {[
              { icon: BookOpen, text: '知识问答' },
              { icon: Zap, text: '快速生成' },
              { icon: MessageSquare, text: '对话咨询' },
            ].map((suggestion, i) => (
              <button
                key={i}
                onClick={() => {
                  setInputMessage(suggestion.text)
                  inputRef.current?.focus()
                }}
                className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-full border border-slate-200 dark:border-slate-800 text-sm text-slate-600 dark:text-slate-300 hover:border-slate-400 dark:hover:border-slate-600 transition-colors"
              >
                <suggestion.icon className="w-3.5 h-3.5" />
                {suggestion.text}
              </button>
            ))}
          </div>
        </main>
      ) : (
        <>
          <main className="flex-1 overflow-y-auto">
            <div className="max-w-3xl mx-auto px-6 py-6 space-y-8">
              {messages.map((message) =>
                message.role === 'user' ? (
                  <div key={message.id} className="flex justify-end">
                    <div className="max-w-[80%]">
                      <div className="bg-slate-100 dark:bg-slate-800 rounded-2xl px-4 py-2.5 text-[15px] text-slate-900 dark:text-white whitespace-pre-wrap">
                        {message.content}
                      </div>
                      {renderActions(message)}
                    </div>
                  </div>
                ) : (
                  <div key={message.id} className="flex gap-3">
                    {assistantAvatar}
                    <div className="flex-1 min-w-0">
                      {message.thinking
                        ? renderThinking(message.id, message.thinking)
                        : null}
                      {message.thinking && expandedThinking[message.id] && (
                        <p className="mb-3 px-3 py-2.5 rounded-xl bg-slate-50 dark:bg-slate-900 text-xs text-slate-500 whitespace-pre-wrap max-h-64 overflow-y-auto">
                          {message.thinking}
                        </p>
                      )}

                      <Markdown
                        content={message.content}
                        className="text-[15px] text-slate-900 dark:text-white"
                      />

                      {message.toolCalls?.length ? renderToolCalls(message.toolCalls) : null}
                      {message.files?.length ? renderArtifacts(message.files) : null}

                      {renderActions(message)}
                    </div>
                  </div>
                )
              )}

              {/* 内置链路：流式正文 */}
              {effectiveEngine === 'builtin' && streamingContent && (
                <div className="flex gap-3">
                  {assistantAvatar}
                  <div className="flex-1 min-w-0">
                    <div className="text-[15px] text-slate-900 dark:text-white">
                      <Markdown content={streamingContent} />
                      <span className="inline-block w-1.5 h-3.5 bg-slate-900 dark:bg-white animate-pulse rounded-sm" />
                    </div>
                  </div>
                </div>
              )}

              {/* 内置链路：等待中 */}
              {effectiveEngine === 'builtin' && isLoading && !streamingContent && (
                <div className="flex gap-3">
                  {assistantAvatar}
                  <div className="flex items-center gap-2 text-sm text-slate-500">
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    <span>思考中…</span>
                  </div>
                </div>
              )}

              {/* PiAgent 引擎：实时过程 */}
              {effectiveEngine === 'pi' && isLoading && (
                <div className="flex gap-3">
                  {assistantAvatar}
                  <div className="flex-1 min-w-0">
                    {piLive.thinking ? renderThinking('live', piLive.thinking, true) : null}
                    {piLive.thinking && expandedThinking['live'] && (
                      <p className="mb-3 px-3 py-2.5 rounded-xl bg-slate-50 dark:bg-slate-900 text-xs text-slate-500 whitespace-pre-wrap max-h-64 overflow-y-auto">
                        {piLive.thinking}
                      </p>
                    )}

                    {piLive.toolCalls.length > 0 && renderToolCalls(piLive.toolCalls)}

                    <div className="mt-2 text-[15px] text-slate-900 dark:text-white whitespace-pre-wrap leading-relaxed">
                      {piLive.text ? (
                        <>
                          {piLive.text}
                          <span className="inline-block w-1.5 h-4 ml-0.5 align-middle bg-slate-900 dark:bg-white animate-pulse rounded-sm" />
                        </>
                      ) : (
                        <span className="flex items-center gap-2 text-sm text-slate-500">
                          <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                          {piLive.logs[piLive.logs.length - 1] || 'AI Agent 启动中…'}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          </main>

          <footer className="flex-shrink-0 px-6 pb-4 pt-2">
            {renderComposer('docked')}
            <p className="text-xs text-slate-400 mt-3 text-center">
              内容由 AI 生成，请仔细甄别
            </p>
          </footer>
        </>
      )}
    </div>
  )
}

/** 路由包装：/agents/:id/chat */
export default function ChatPage() {
  const { id } = useParams<{ id: string }>()
  return <ChatSession id={id ?? ''} />
}
