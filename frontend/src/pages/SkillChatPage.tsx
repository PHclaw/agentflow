import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  ArrowLeft,
  Send,
  Bot,
  User,
  Paperclip,
  Loader2,
  Download,
  X,
} from 'lucide-react'
import { skills as skillsApi, type SkillCallResponse } from '../services/api'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
}

interface SkillInfo {
  id: string
  name: string
  description: string
  specialty?: string
}

function renderMarkdownLinks(text: string) {
  const urlRe = /(https?:\/\/[^\s)]+|\/static\/[^\s)]+)/g
  const parts = text.split(urlRe)
  return parts.map((part, i) => {
    if (urlRe.test(part) || part.startsWith('/static/')) {
      return (
        <a
          key={i}
          href={part}
          target="_blank"
          rel="noreferrer"
          className="text-indigo-600 underline break-all"
        >
          {part}
        </a>
      )
    }
    return <span key={i}>{part}</span>
  })
}

export default function SkillChatPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [skill, setSkill] = useState<SkillInfo | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState('')
  const [sessionId, setSessionId] = useState<string | undefined>()
  const [downloads, setDownloads] = useState<string[]>([])

  useEffect(() => {
    if (!id) return
    setLoadError('')
    skillsApi
      .get(id)
      .then((data) =>
        setSkill({
          id: data.id,
          name: data.name,
          description: data.description || '',
          specialty: data.specialty,
        })
      )
      .catch((e: { message?: string }) => {
        const msg = e?.message || '加载 Skill 失败'
        setLoadError(msg)
        if (msg.includes('登录') || msg.includes('401') || msg.includes('未登录')) {
          setTimeout(() => navigate('/login'), 1500)
        }
      })
  }, [id, navigate])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const collectDownloads = (res: SkillCallResponse) => {
    const urls: string[] = []
    const trace = res.toolTrace
    if (trace?.downloadUrl) urls.push(trace.downloadUrl)
    if (trace?.downloadUrls) urls.push(...trace.downloadUrls)
    if (trace?.imageUrl) urls.push(trace.imageUrl)
    setDownloads(Array.from(new Set(urls)))
  }

  const sendMessage = async () => {
    if (!id || (!input.trim() && files.length === 0) || loading) return

    const userText = input.trim() || '请处理上传的文件'
    setMessages((prev) => [
      ...prev,
      { id: `u-${Date.now()}`, role: 'user', content: userText },
    ])
    setInput('')
    setLoading(true)

    try {
      const res =
        files.length > 0
          ? await skillsApi.callWithFiles(id, userText, files, sessionId)
          : await skillsApi.call(id, { input: userText }, sessionId)

      if (res.sessionId) setSessionId(res.sessionId)
      collectDownloads(res)
      setMessages((prev) => [
        ...prev,
        {
          id: `a-${Date.now()}`,
          role: 'assistant',
          content: res.output || '（无回复）',
        },
      ])
      setFiles([])
    } catch (e: any) {
      setMessages((prev) => [
        ...prev,
        {
          id: `e-${Date.now()}`,
          role: 'assistant',
          content: `调用失败：${e?.message || '未知错误'}`,
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <header className="bg-white border-b border-slate-200 px-4 py-3 flex items-center gap-3">
        <Button variant="ghost" size="sm" onClick={() => navigate('/skills')}>
          <ArrowLeft className="w-4 h-4" />
        </Button>
        <div className="flex-1 min-w-0">
          <h1 className="font-semibold text-slate-900 truncate">
            {skill?.name || 'Skill 对话'}
          </h1>
          {skill?.specialty && (
            <p className="text-xs text-slate-500">{skill.specialty}</p>
          )}
        </div>
      </header>

      {loadError && (
        <div className="px-4 pt-4 max-w-4xl mx-auto w-full">
          <Card className="p-4 border-red-200 bg-red-50 text-red-700 text-sm">
            {loadError}
          </Card>
        </div>
      )}

      <div className="flex-1 overflow-y-auto p-4 max-w-4xl mx-auto w-full space-y-4">
        {skill?.description && messages.length === 0 && (
          <Card className="p-4 text-sm text-slate-600 whitespace-pre-line">
            {skill.description}
          </Card>
        )}

        {messages.map((m) => (
          <div
            key={m.id}
            className={`flex gap-3 ${m.role === 'user' ? 'justify-end' : ''}`}
          >
            {m.role === 'assistant' && (
              <div className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center">
                <Bot className="w-4 h-4 text-indigo-600" />
              </div>
            )}
            <div
              className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm whitespace-pre-wrap ${
                m.role === 'user'
                  ? 'bg-indigo-600 text-white'
                  : 'bg-white border border-slate-200 text-slate-800'
              }`}
            >
              {m.role === 'assistant' ? renderMarkdownLinks(m.content) : m.content}
            </div>
            {m.role === 'user' && (
              <div className="w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center">
                <User className="w-4 h-4 text-slate-600" />
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex items-center gap-2 text-slate-500 text-sm">
            <Loader2 className="w-4 h-4 animate-spin" />
            Skill 正在处理...
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {downloads.length > 0 && (
        <div className="px-4 pb-2 max-w-4xl mx-auto w-full">
          <Card className="p-4 border-indigo-200 bg-indigo-50/50">
            <p className="text-sm font-medium text-slate-700 mb-2">生成文件</p>
            <div className="flex flex-wrap gap-2">
            {downloads.map((url) => (
              <a
                key={url}
                href={url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-2 text-sm px-3 py-2 rounded-lg bg-white border border-indigo-200 text-indigo-700 hover:bg-indigo-50 transition-colors"
              >
                <Download className="w-4 h-4" />
                {url.split('/').pop() || '下载'}
              </a>
            ))}
            </div>
          </Card>
        </div>
      )}

      {files.length > 0 && (
        <div className="px-4 pb-2 max-w-4xl mx-auto w-full flex flex-wrap gap-2">
          {files.map((f) => (
            <span
              key={f.name}
              className="inline-flex items-center gap-1 text-xs bg-white border rounded-full px-3 py-1"
            >
              {f.name}
              <button
                type="button"
                onClick={() => setFiles((prev) => prev.filter((x) => x !== f))}
              >
                <X className="w-3 h-3" />
              </button>
            </span>
          ))}
        </div>
      )}

      <div className="border-t bg-white p-4">
        <div className="max-w-4xl mx-auto flex gap-2 items-end">
          <input
            ref={fileInputRef}
            type="file"
            multiple
            className="hidden"
            onChange={(e) => {
              const picked = Array.from(e.target.files || [])
              if (picked.length) setFiles((prev) => [...prev, ...picked])
              e.target.value = ''
            }}
          />
          <Button
            variant="ghost"
            size="sm"
            onClick={() => fileInputRef.current?.click()}
            title="上传文件"
          >
            <Paperclip className="w-4 h-4" />
          </Button>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                sendMessage()
              }
            }}
            rows={2}
            placeholder="输入问题，或上传 Excel/PDF 后描述需求..."
            className="flex-1 resize-none rounded-xl border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
          <Button onClick={sendMessage} disabled={loading}>
            <Send className="w-4 h-4" />
          </Button>
        </div>
      </div>
    </div>
  )
}
