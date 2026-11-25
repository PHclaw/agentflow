import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { MessageSquare, RefreshCw } from 'lucide-react'
import { chat as chatApi, type ChatSessionItem } from '../services/api'

/** 把 ISO 时间显示成「刚刚 / 3 小时前 / 昨天 / 10-08」 */
function relativeTime(iso: string | null): string {
  if (!iso) return ''
  const then = new Date(iso.endsWith('Z') || iso.includes('+') ? iso : `${iso}Z`)
  if (Number.isNaN(then.getTime())) return ''
  const diff = Date.now() - then.getTime()
  const min = Math.floor(diff / 60000)
  if (min < 1) return '刚刚'
  if (min < 60) return `${min} 分钟前`
  const hour = Math.floor(min / 60)
  if (hour < 24) return `${hour} 小时前`
  const day = Math.floor(hour / 24)
  if (day === 1) return '昨天'
  if (day < 7) return `${day} 天前`
  const d = new Date(then.getTime())
  return `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export default function ConversationListPage() {
  const [sessions, setSessions] = useState<ChatSessionItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [keyword, setKeyword] = useState('')
  const navigate = useNavigate()

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await chatApi.allSessions({ limit: 100 })
      setSessions(data?.sessions ?? [])
    } catch (e: any) {
      setError(e?.message || '加载对话记录失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  // 标题与 Agent 名都参与搜索，方便按其中任一维度找
  const filtered = keyword.trim()
    ? sessions.filter((s) =>
        `${s.title}${s.agent_name}`.toLowerCase().includes(keyword.trim().toLowerCase())
      )
    : sessions

  /** 打开指定的一段对话：带 session 参数，对话页会加载它并接着聊 */
  const open = (s: ChatSessionItem) => {
    navigate(`/agents/${s.agent_id}/chat?session=${s.id}`)
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-slate-900 dark:text-white">对话记录</h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            共 {sessions.length} 段对话，点任意一段可以接着聊
          </p>
        </div>
        <button
          onClick={load}
          title="刷新"
          className="p-2 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 dark:hover:bg-slate-900 transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      <input
        value={keyword}
        onChange={(e) => setKeyword(e.target.value)}
        placeholder="搜索对话内容或 Agent 名称"
        className="w-full max-w-md px-3.5 py-2 mb-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 text-sm text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:border-brand-400 dark:focus:border-brand-500 transition-colors"
      />

      {error && (
        <div className="mb-4 px-4 py-3 rounded-xl bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-900 text-sm text-red-600 dark:text-red-400">
          {error}
        </div>
      )}

      {!loading && filtered.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <div className="w-14 h-14 rounded-2xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center mb-4">
            <MessageSquare className="w-6 h-6 text-slate-400" />
          </div>
          <p className="text-slate-500 dark:text-slate-400 text-sm">
            {keyword ? '没有匹配的对话' : '还没有对话记录，去和某个 Agent 聊几句吧'}
          </p>
        </div>
      )}

      <div className="space-y-2">
        {filtered.map((s) => (
          <button
            key={s.id}
            onClick={() => open(s)}
            className="w-full flex items-start gap-3 px-4 py-3 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 hover:border-brand-300 dark:hover:border-brand-700 hover:shadow-sm transition-all text-left"
          >
            <div className="w-8 h-8 flex-shrink-0 rounded-lg bg-gradient-to-br from-brand-500 to-brand-600 text-white text-xs font-medium flex items-center justify-center mt-0.5">
              {s.agent_name.slice(0, 1)}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm text-slate-900 dark:text-white truncate">
                {s.title || '（空对话）'}
              </p>
              <p className="mt-0.5 text-xs text-slate-400 dark:text-slate-500 truncate">
                {s.agent_name} · {s.message_count} 条消息
                {s.updated_at ? ` · ${relativeTime(s.updated_at)}` : ''}
              </p>
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}