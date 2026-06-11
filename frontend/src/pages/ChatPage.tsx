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
} from 'lucide-react'
import { api } from '../services/api'
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
}

interface AgentInfo {
  id: string
  name: string
  description: string
  model: string
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

  useEffect(() => {
    loadAgent()
    loadHistory()
  }, [id])

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

  const handleSend = async () => {
    if (!inputMessage.trim() || isLoading) return

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: inputMessage,
      timestamp: new Date().toISOString(),
    }

    setMessages((prev) => [...prev, userMessage])
    setInputMessage('')
    setIsLoading(true)
    setStreamingContent('')

    try {
      const response = await fetch(`/api/v1/chat/${id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: inputMessage,
          conversation_id: conversationId,
          stream: true,
        }),
      })

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()
      let fullContent = ''

      if (reader) {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          const chunk = decoder.decode(value)
          const lines = chunk.split('\n')

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6))
                if (data.content) {
                  fullContent += data.content
                  setStreamingContent(fullContent)
                }
              } catch {}
            }
          }
        }
      }

      // 添加完整回复
      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: fullContent || '抱歉，我暂时无法回答这个问题。',
        timestamp: new Date().toISOString(),
      }

      setMessages((prev) => [...prev, assistantMessage])
    } catch (error) {
      console.error('Chat error:', error)
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: '抱歉，发生了错误。请稍后重试。',
        timestamp: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
      setStreamingContent('')
    }
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
                  {agent?.model || 'gpt-4o-mini'}
                </p>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
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
                    >
                      <Copy className="w-4 h-4" />
                    </button>
                    {message.role === 'assistant' && (
                      <>
                        <button className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 dark:hover:bg-slate-800">
                          <ThumbsUp className="w-4 h-4" />
                        </button>
                        <button className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 dark:hover:bg-slate-800">
                          <ThumbsDown className="w-4 h-4" />
                        </button>
                        <button className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 dark:hover:bg-slate-800">
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

            {/* Streaming indicator */}
            {streamingContent && (
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

            {/* Loading indicator */}
            {isLoading && !streamingContent && (
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
              onClick={handleSend}
              disabled={!inputMessage.trim() || isLoading}
              className="absolute right-2 top-1/2 -translate-y-1/2 p-2 rounded-xl bg-indigo-500 text-white disabled:opacity-50 disabled:cursor-not-allowed hover:bg-indigo-600 transition-colors"
            >
              <Send className="w-5 h-5" />
            </button>
          </div>
          <p className="text-xs text-slate-400 mt-2 text-center">
            {agent?.name} 可能会产生不准确的信息，请斟酌参考。
          </p>
        </div>
      </footer>
    </div>
  )
}
