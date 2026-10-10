import React, { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeft,
  Send,
  Bot,
  User,
  Settings,
  Copy,
  ThumbsUp,
  ThumbsDown,
  RefreshCw,
  MoreVertical,
  MessageSquare,
  Sparkles,
  BookOpen,
  Zap,
  Check,
  X,
  Paperclip,
  Download,
  Terminal,
  Brain,
  ChevronDown,
} from 'lucide-react'
import { api } from '../services/api'
import { chat as chatApi, pi, type PiArtifact, type PiStatus } from '../services/api'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Card } from '../components/ui/Card'

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

export default function ChatPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  
  const [agent, setAgent] = useState<AgentInfo | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [inputMessage, setInputMessage] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [streamingContent, setStreamingContent] = useState('')
  const [showSettings, setShowSettings] = useState(false)
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
  const [piLive, setPiLive] = useState<PiLiveState>({
    logs: [],
    toolCalls: [],
    thinking: '',
    text: '',
  })
  const [showThinking, setShowThinking] = useState(false)
  const [piSessionId, setPiSessionId] = useState<string | null>(null)
  const [selectedSkills, setSelectedSkills] = useState<string[]>([])
  const abortRef = useRef<AbortController | null>(null)

  const piReady = Boolean(piStatus?.enabled && piStatus?.available)

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

  const loadAgent = async () => {
    try {
      const data = await api.get(`/agents/${id}`)
      setAgent({
        id: data.id,
        name: data.name,
        description: data.description || '',
        model: data.model || 'gpt-4o-mini',
      })
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
      // No chat history yet
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

  /** 下载 PiAgent 工作区产物 */
  const handleDownloadArtifact = async (file: PiArtifact) => {
    try {
      const blob = await pi.downloadArtifact(id!, file.path)
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

  /** 内置链路：直连大模型（SSE：session / chunk / done / error） */
  const sendWithBuiltin = async (message: string, signal: AbortSignal): Promise<string> => {
    let fullContent = ''

    for await (const event of chatApi.stream(id!, message, conversationId, signal)) {
      if (event.type === 'session' && event.session_id) {
        setConversationId(event.session_id)
      } else if (event.type === 'chunk' && event.content) {
        fullContent += event.content
        setStreamingContent(fullContent)
      } else if (event.type === 'done') {
        if (event.content) fullContent = event.content
        if (event.session_id) setConversationId(event.session_id)
      } else if (event.type === 'error') {
        throw new Error(event.error || '对话失败')
      }
    }

    return fullContent || '抱歉，我暂时无法回答这个问题。'
  }

  /** PiAgent 链路：外部 agent CLI，带思考/工具调用/产物 */
  const sendWithPi = async (message: string, signal: AbortSignal) => {
    let text = ''
    let thinking = ''
    const toolCalls: string[] = []
    const logs: string[] = []
    let files: PiArtifact[] = []

    setPiLive({ logs: [], toolCalls: [], thinking: '', text: '' })

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

    const controller = new AbortController()
    abortRef.current = controller

    try {
      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: '',
        timestamp: new Date().toISOString(),
      }

      if (engine === 'pi') {
        const result = await sendWithPi(currentInput, controller.signal)
        assistantMessage.content = result.content
        assistantMessage.files = result.files
        assistantMessage.toolCalls = result.toolCalls
        assistantMessage.thinking = result.thinking
      } else {
        assistantMessage.content = await sendWithBuiltin(currentInput, controller.signal)
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
      setPiLive({ logs: [], toolCalls: [], thinking: '', text: '' })
      abortRef.current = null
    }
  }

  return (
    <div className="h-screen flex flex-col bg-slate-50 dark:bg-slate-900">
      {/* Header */}
      <header className="bg-white dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700 px-6 py-4">
        <div className="flex items-center justify-between max-w-4xl mx-auto">
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate(-1)}
              className="p-2 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-500"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600">
                <Bot className="w-5 h-5 text-white" />
              </div>
              <div>
                <h1 className="font-semibold text-slate-900 dark:text-white">
                  {agent?.name || 'AI Assistant'}
                </h1>
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  {engine === 'pi' ? 'AI Agent 引擎' : agent?.model || 'gpt-4o-mini'}
                </p>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {/* 引擎切换 */}
            <div className="flex items-center rounded-xl bg-slate-100 dark:bg-slate-700 p-0.5">
              <button
                onClick={() => setEngine('builtin')}
                className={`px-3 py-1.5 text-xs font-medium rounded-[10px] transition-colors ${
                  engine === 'builtin'
                    ? 'bg-white dark:bg-slate-800 text-slate-900 dark:text-white shadow-sm'
                    : 'text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
                }`}
              >
                内置模型
              </button>
              <button
                onClick={() => piReady && setEngine('pi')}
                disabled={!piReady}
                title={
                  piReady
                    ? 'AI Agent 引擎：可读写工作区文件、调用技能'
                    : 'AI Agent 引擎未启用（配置方式见 README）'
                }
                className={`px-3 py-1.5 text-xs font-medium rounded-[10px] transition-colors ${
                  engine === 'pi'
                    ? 'bg-white dark:bg-slate-800 text-slate-900 dark:text-white shadow-sm'
                    : 'text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
                } ${piReady ? '' : 'opacity-40 cursor-not-allowed'}`}
              >
                AI Agent
                {piReady && piStatus?.skills?.length ? ` · ${piStatus.skills.length} 技能` : ''}
              </button>
            </div>
            <button
              onClick={() => setShowSettings(!showSettings)}
              className="p-2 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-500"
            >
              <Settings className="w-5 h-5" />
            </button>
            <button className="p-2 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-500">
              <MoreVertical className="w-5 h-5" />
            </button>
          </div>
        </div>
      </header>

      {/* Messages */}
      <main className="flex-1 overflow-y-auto">
        {/* Settings Panel */}
        {showSettings && (
          <div className="bg-white dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700 px-6 py-4">
            <div className="max-w-4xl mx-auto">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-semibold text-slate-900 dark:text-white">对话设置</h3>
                <button onClick={() => setShowSettings(false)} className="p-1 rounded hover:bg-slate-100 dark:hover:bg-slate-700">
                  <X className="w-4 h-4 text-slate-500" />
                </button>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">模型</label>
                  <select
                    value={settings.model}
                    onChange={(e) => setSettings({ ...settings, model: e.target.value })}
                    className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 text-sm"
                  >
                    <option value="gpt-4o-mini">GPT-4o Mini</option>
                    <option value="gpt-4o">GPT-4o</option>
                    <option value="claude-sonnet-4-20250514">Claude Sonnet 4</option>
                    <option value="deepseek-chat">DeepSeek V3</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">温度: {settings.temperature}</label>
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
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">系统提示词</label>
                  <input
                    type="text"
                    value={settings.systemPrompt}
                    onChange={(e) => setSettings({ ...settings, systemPrompt: e.target.value })}
                    placeholder="（Agent 侧配置优先）"
                    className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 text-sm"
                  />
                </div>
              </div>

              {engine === 'pi' && (
                <div className="mt-4 pt-4 border-t border-slate-200 dark:border-slate-700">
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                    启用技能
                    <span className="ml-2 text-xs font-normal text-slate-400">
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
                            className={`inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs border transition-colors ${
                              active
                                ? 'bg-indigo-500 border-indigo-500 text-white'
                                : 'bg-white dark:bg-slate-700 border-slate-200 dark:border-slate-600 text-slate-600 dark:text-slate-300 hover:border-indigo-300'
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
            </div>
          </div>
        )}

        <div className="max-w-4xl mx-auto px-6 py-8">
          {messages.length === 0 && !isLoading && (
            <div className="text-center py-16">
              <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center mx-auto mb-6 shadow-xl shadow-indigo-500/20">
                <Sparkles className="w-10 h-10 text-white" />
              </div>
              <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-3">
                开始与 {agent?.name || 'AI'} 对话
              </h2>
              <p className="text-slate-500 dark:text-slate-400 max-w-md mx-auto mb-8">
                {agent?.description || '我是您的智能助手，可以回答问题、帮助完成任务。'}
              </p>
              
              {/* Quick suggestions */}
              <div className="flex flex-wrap justify-center gap-3">
                {[
                  { icon: BookOpen, text: '知识问答' },
                  { icon: Zap, text: '快速生成' },
                  { icon: MessageSquare, text: '对话咨询' },
                ].map((suggestion, i) => (
                  <button
                    key={i}
                    onClick={() => setInputMessage(suggestion.text)}
                    className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:border-indigo-300 dark:hover:border-indigo-600 transition-colors"
                  >
                    <suggestion.icon className="w-4 h-4" />
                    {suggestion.text}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Message list */}
          <div className="space-y-6">
            {messages.map((message) => (
              <div
                key={message.id}
                className={`flex gap-4 ${
                  message.role === 'user' ? 'flex-row-reverse' : ''
                }`}
              >
                {/* Avatar */}
                <div
                  className={`flex-shrink-0 w-10 h-10 rounded-xl flex items-center justify-center ${
                    message.role === 'user'
                      ? 'bg-indigo-500'
                      : 'bg-gradient-to-br from-emerald-500 to-green-600'
                  }`}
                >
                  {message.role === 'user' ? (
                    <User className="w-5 h-5 text-white" />
                  ) : (
                    <Bot className="w-5 h-5 text-white" />
                  )}
                </div>

                {/* Content */}
                <div
                  className={`flex-1 max-w-2xl ${
                    message.role === 'user' ? 'text-right' : ''
                  }`}
                >
                  <div
                    className={`inline-block p-4 rounded-2xl text-left ${
                      message.role === 'user'
                        ? 'bg-indigo-500 text-white rounded-tr-md'
                        : 'bg-white dark:bg-slate-800 text-slate-900 dark:text-white rounded-tl-md shadow-sm'
                    }`}
                  >
                    <p className="whitespace-pre-wrap">{message.content}</p>

                    {/* 工具调用记录 */}
                    {message.role === 'assistant' && message.toolCalls?.length ? (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {message.toolCalls.map((tool, i) => (
                          <span
                            key={i}
                            className="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-slate-100 dark:bg-slate-700 text-xs text-slate-600 dark:text-slate-300"
                          >
                            <Terminal className="w-3 h-3" />
                            {tool}
                          </span>
                        ))}
                      </div>
                    ) : null}

                    {/* 生成的文件附件 */}
                    {message.role === 'assistant' && message.files?.length ? (
                      <div className="mt-3 space-y-2">
                        {message.files.map((file) => (
                          <button
                            key={file.path}
                            onClick={() => handleDownloadArtifact(file)}
                            className="flex items-center gap-2 w-full px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-600 hover:border-indigo-300 dark:hover:border-indigo-500 text-sm text-left transition-colors"
                          >
                            <Paperclip className="w-4 h-4 text-indigo-500 flex-shrink-0" />
                            <span className="flex-1 truncate">{file.name}</span>
                            <span className="text-xs text-slate-400">{formatSize(file.size)}</span>
                            <Download className="w-4 h-4 text-slate-400 flex-shrink-0" />
                          </button>
                        ))}
                      </div>
                    ) : null}
                  </div>

                  {/* Actions */}
                  <div
                    className={`flex items-center gap-2 mt-2 ${
                      message.role === 'user' ? 'justify-end' : 'justify-start'
                    }`}
                  >
                    <button
                      onClick={() => copyMessage(message.content)}
                      className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 dark:hover:bg-slate-800"
                      title="复制"
                    >
                      <Copy className="w-4 h-4" />
                    </button>
                    {message.role === 'assistant' && (
                      <>
                        <button
                          onClick={() => handleFeedback(message.id, 'up')}
                          className={`p-1.5 rounded-lg ${
                            feedbackGiven[message.id] === 'up'
                              ? 'text-emerald-500 bg-emerald-50 dark:bg-emerald-900/20'
                              : 'text-slate-400 hover:text-emerald-500 hover:bg-slate-100 dark:hover:bg-slate-800'
                          }`}
                          title="赞同"
                        >
                          <ThumbsUp className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleFeedback(message.id, 'down')}
                          className={`p-1.5 rounded-lg ${
                            feedbackGiven[message.id] === 'down'
                              ? 'text-red-500 bg-red-50 dark:bg-red-900/20'
                              : 'text-slate-400 hover:text-red-500 hover:bg-slate-100 dark:hover:bg-slate-800'
                          }`}
                          title="反对"
                        >
                          <ThumbsDown className="w-4 h-4" />
                        </button>
                        <button
                          onClick={handleRegenerate}
                          className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 dark:hover:bg-slate-800"
                          title="重新生成"
                        >
                          <RefreshCw className="w-4 h-4" />
                        </button>
                      </>
                    )}
                    <span className="text-xs text-slate-400 ml-2">
                      {new Date(message.timestamp).toLocaleTimeString('zh-CN', {
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </span>
                  </div>
                </div>
              </div>
            ))}

            {/* 内置链路：流式正文 */}
            {engine === 'builtin' && streamingContent && (
              <div className="flex gap-4">
                <div className="flex-shrink-0 w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-green-600 flex items-center justify-center">
                  <Bot className="w-5 h-5 text-white" />
                </div>
                <div className="flex-1 max-w-2xl">
                  <div className="inline-block p-4 rounded-2xl rounded-tl-md bg-white dark:bg-slate-800 shadow-sm">
                    <div className="flex items-center gap-2">
                      <span className="whitespace-pre-wrap">{streamingContent}</span>
                      <span className="w-2 h-5 bg-indigo-500 animate-pulse rounded" />
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* 内置链路：等待中 */}
            {engine === 'builtin' && isLoading && !streamingContent && (
              <div className="flex gap-4">
                <div className="flex-shrink-0 w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-green-600 flex items-center justify-center">
                  <Bot className="w-5 h-5 text-white" />
                </div>
                <div className="flex-1 max-w-2xl">
                  <div className="inline-block p-4 rounded-2xl rounded-tl-md bg-white dark:bg-slate-800 shadow-sm">
                    <div className="flex items-center gap-2 text-slate-500">
                      <RefreshCw className="w-4 h-4 animate-spin" />
                      <span>思考中...</span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* PiAgent 引擎：实时过程（工具调用 / 思考 / 正文） */}
            {engine === 'pi' && isLoading && (
              <div className="flex gap-4">
                <div className="flex-shrink-0 w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-green-600 flex items-center justify-center">
                  <Bot className="w-5 h-5 text-white" />
                </div>
                <div className="flex-1 max-w-2xl space-y-2">
                  {piLive.toolCalls.length > 0 && (
                    <div className="flex flex-wrap gap-2">
                      {piLive.toolCalls.map((tool, i) => (
                        <span
                          key={i}
                          className="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-slate-100 dark:bg-slate-700 text-xs text-slate-600 dark:text-slate-300"
                        >
                          <Terminal className="w-3 h-3" />
                          {tool}
                        </span>
                      ))}
                    </div>
                  )}

                  {piLive.thinking && (
                    <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 overflow-hidden">
                      <button
                        onClick={() => setShowThinking(!showThinking)}
                        className="flex items-center gap-2 w-full px-4 py-2 text-xs text-slate-500 hover:bg-slate-50 dark:hover:bg-slate-700/50"
                      >
                        <Brain className="w-3.5 h-3.5" />
                        <span>思考过程</span>
                        <ChevronDown
                          className={`w-3.5 h-3.5 ml-auto transition-transform ${
                            showThinking ? 'rotate-180' : ''
                          }`}
                        />
                      </button>
                      {showThinking && (
                        <p className="px-4 pb-3 text-xs text-slate-500 whitespace-pre-wrap max-h-48 overflow-y-auto">
                          {piLive.thinking}
                        </p>
                      )}
                    </div>
                  )}

                  <div className="inline-block p-4 rounded-2xl rounded-tl-md bg-white dark:bg-slate-800 shadow-sm">
                    {piLive.text ? (
                      <div className="flex items-center gap-2">
                        <span className="whitespace-pre-wrap">{piLive.text}</span>
                        <span className="w-2 h-5 bg-indigo-500 animate-pulse rounded" />
                      </div>
                    ) : (
                      <div className="flex items-center gap-2 text-slate-500">
                        <RefreshCw className="w-4 h-4 animate-spin" />
                        <span>{piLive.logs[piLive.logs.length - 1] || 'AI Agent 启动中...'}</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>

          <div ref={messagesEndRef} />
        </div>
      </main>

      {/* Input */}
      <footer className="bg-white dark:bg-slate-800 border-t border-slate-200 dark:border-slate-700 px-6 py-4">
        <div className="max-w-4xl mx-auto">
          <div className="relative">
            <textarea
              ref={inputRef}
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="输入消息... (Enter 发送, Shift+Enter 换行)"
              rows={1}
              className="w-full px-4 py-3 pr-12 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-white placeholder-slate-400 resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500"
              style={{
                maxHeight: '120px',
                minHeight: '48px',
              }}
            />
            <button
              onClick={isLoading ? handleStop : handleSend}
              disabled={!isLoading && !inputMessage.trim()}
              title={isLoading ? '停止生成' : '发送'}
              className={`absolute right-2 top-1/2 -translate-y-1/2 p-2 rounded-xl text-white disabled:opacity-50 disabled:cursor-not-allowed transition-colors ${
                isLoading ? 'bg-slate-400 hover:bg-slate-500' : 'bg-indigo-500 hover:bg-indigo-600'
              }`}
            >
              {isLoading ? <X className="w-5 h-5" /> : <Send className="w-5 h-5" />}
            </button>
          </div>
          <p className="text-xs text-slate-400 mt-2 text-center">
            {engine === 'pi' ? 'AI Agent 引擎会实际读写工作区文件。' : ''}
            {agent?.name} 可能会产生不准确的信息，请斟酌参考。
          </p>
        </div>
      </footer>
    </div>
  )
}
