/**
 * 多智能体群聊
 *
 * 交互重点：
 * 1. 用户发任务 → 系统判断谁接 → 界面明确显示「谁接了 + 为什么」
 * 2. 被选中的智能体回复时 @ 回发起人，并带引用关系
 * 3. 其他人保持沉默，不让群里变成一堆人在说话
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { Markdown } from '../components/ui/Markdown'
import { downloadBlob } from '../lib/download'
import {
  agents as agentsApi,
  api,
  groups as groupsApi,
  pi,
  type GroupDetail,
  type GroupFileInfo,
  type GroupMessageItem,
  type GroupSummary,
  type PendingUpload,
  type PiArtifact,
} from '../services/api'

type Member = { id: string; name: string; description?: string | null }

type Bubble =
  | { kind: 'message'; data: GroupMessageItem }
  | { kind: 'pending'; agentName: string; text: string; replyToName: string }
  | { kind: 'routing' }

const ROUTE_MODE_LABEL: Record<string, string> = {
  auto: '自动指派',
  manual: '手动 @ 指定',
  off: '全员回复',
}

/** 执行方式的中文名。pi 内部仍叫 pi，只改对用户展示的字。 */
const EXEC_MODE_LABEL: Record<'llm' | 'pi', string> = {
  llm: '快速回答',
  pi: '工作模式',
}

function formatSize(bytes?: number): string {
  if (!bytes) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

const IMAGE_EXT = /\.(png|jpe?g|gif|webp|bmp|svg)$/i

/** 与服务端 ALLOWED_EXTENSIONS 对齐。前端先挡一次，
 *  用户不必等上传完才被告知「不支持这种文件」。 */
const ALLOWED_FILE_EXT = new Set([
  '.pdf', '.doc', '.docx', '.txt', '.md', '.rtf',
  '.ppt', '.pptx', '.xls', '.xlsx', '.csv', '.tsv',
  '.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.svg',
  '.json', '.yaml', '.yml', '.xml', '.toml', '.ini',
  '.py', '.js', '.ts', '.tsx', '.jsx', '.sql', '.html', '.css',
  '.zip',
])

const MAX_FILE_BYTES = 10 * 1024 * 1024
const MAX_FILES = 5
/** 同时上传的并发数。太少慢，太多会挤占浏览器连接（同域一般 6 条） */
const UPLOAD_CONCURRENCY = 3

const FILE_ICON: Record<string, string> = {
  image: '🖼️',
  sheet: '📊',
  slide: '📽️',
  pdf: '📕',
  archive: '🗜️',
  code: '🧾',
  doc: '📄',
}

function fileExt(name: string): string {
  const i = name.lastIndexOf('.')
  return i >= 0 ? name.slice(i).toLowerCase() : ''
}

/** 工作区文件要带 Bearer 头，`<img src>` / `<a href>` 直接访问会 401，
 *  所以统一走 blob：预览转 objectURL，下载调 downloadBlob。 */
async function fetchArtifact(file: PiArtifact, agentId?: string): Promise<Blob> {
  if (file.url) return api.getBlob(file.url)
  if (!agentId) throw new Error('缺少 agent 标识')
  return pi.downloadArtifact(agentId, file.path)
}

function ArtifactPreview({ file, agentId }: { file: PiArtifact; agentId?: string }) {
  const [src, setSrc] = useState<string | null>(null)

  useEffect(() => {
    if (!IMAGE_EXT.test(file.name)) return
    let alive = true
    let objectUrl: string | null = null
    ;(async () => {
      try {
        const blob = await fetchArtifact(file, agentId)
        if (!alive) return
        objectUrl = URL.createObjectURL(blob)
        setSrc(objectUrl)
      } catch {
        /* 预览失败不影响下载 */
      }
    })()
    return () => {
      alive = false
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [file, agentId])

  if (!src) return null
  return (
    <img
      src={src}
      alt={file.name}
      className="max-h-[320px] w-auto max-w-full rounded-lg border border-gray-200 bg-white"
    />
  )
}

/** 产物附件卡：文件名 + 大小 + 下载 */
function ArtifactCard({ file, agentId }: { file: PiArtifact; agentId?: string }) {
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const onDownload = async () => {
    if (busy) return
    setBusy(true)
    setErr(null)
    try {
      const blob = await fetchArtifact(file, agentId)
      downloadBlob(blob, file.name)
    } catch (e: any) {
      setErr(e?.message || '下载失败')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <button
        onClick={onDownload}
        disabled={busy}
        className="group/f flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-2.5 py-1.5 text-left transition hover:border-brand-300 hover:bg-brand-50/40 disabled:opacity-60"
        title={`下载 ${file.name}`}
      >
        <span className="text-[15px] leading-none">📎</span>
        <span className="min-w-0">
          <span className="block max-w-[220px] truncate text-[11.5px] font-medium text-gray-700">
            {file.name}
          </span>
          <span className="block text-[10px] text-gray-400">
            {busy ? '准备中…' : formatSize(file.size)}
          </span>
        </span>
        <span className="ml-1 text-[10.5px] text-brand-600 opacity-0 transition group-hover/f:opacity-100">
          下载
        </span>
      </button>
      {err && <p className="mt-1 text-[10px] text-red-500">{err}</p>}
    </div>
  )
}

/** 群聊文件卡：图片给缩略图，其余给图标 + 文件名 + 下载。
 *  下载必须带 token，所以是「取 blob 再保存」，不能直接给 <a href>。 */
function GroupFileCard({ file, groupId }: { file: GroupFileInfo; groupId: string }) {
  const [thumb, setThumb] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const isImage = file.kind === 'image'

  useEffect(() => {
    if (!isImage) return
    let alive = true
    let objectUrl: string | null = null
    ;(async () => {
      try {
        const blob = await groupsApi.downloadFile(groupId, file.stored_name)
        if (!alive) return
        objectUrl = URL.createObjectURL(blob)
        setThumb(objectUrl)
      } catch {
        /* 缩略图失败不影响下载 */
      }
    })()
    return () => {
      alive = false
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [file.stored_name, isImage, groupId])

  const onDownload = async () => {
    if (busy) return
    setBusy(true)
    setErr(null)
    try {
      const blob = await groupsApi.downloadFile(groupId, file.stored_name)
      downloadBlob(blob, file.name)
    } catch (e: any) {
      setErr(e?.message || '下载失败')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <button
        onClick={onDownload}
        disabled={busy}
        title={`下载 ${file.name}`}
        className="group/g flex items-center gap-2.5 rounded-lg border border-gray-200 bg-white p-1.5 pr-2.5 text-left transition hover:border-brand-300 hover:bg-brand-50/40 disabled:opacity-60"
      >
        {thumb ? (
          <img
            src={thumb}
            alt={file.name}
            className="h-10 w-10 shrink-0 rounded-md object-cover"
          />
        ) : (
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-gray-50 text-[17px]">
            {FILE_ICON[file.kind] || '📄'}
          </span>
        )}
        <span className="min-w-0">
          <span className="block max-w-[200px] truncate text-[11.5px] font-medium text-gray-700">
            {file.name}
          </span>
          <span className="block text-[10px] text-gray-400">
            {busy ? '准备中…' : formatSize(file.size)}
          </span>
        </span>
        <span className="ml-1 text-[10.5px] text-brand-600 opacity-0 transition group-hover/g:opacity-100">
          下载
        </span>
      </button>
      {err && <p className="mt-1 text-[10px] text-red-500">{err}</p>}
    </div>
  )
}

/** 待发送的附件：进度条 / 成功 / 失败重试 */
function UploadChip({
  item,
  onRetry,
  onRemove,
}: {
  item: PendingUpload
  onRetry: () => void
  onRemove: () => void
}) {
  const failed = item.status === 'error'
  return (
    <div
      className={`relative flex items-center gap-2 rounded-lg border px-2 py-1.5 ${
        failed ? 'border-red-200 bg-red-50' : 'border-gray-200 bg-white'
      }`}
    >
      <span className="text-[15px]">{FILE_ICON[item.result?.kind || 'doc'] || '📄'}</span>
      <span className="min-w-0">
        <span className="block max-w-[160px] truncate text-[11px] font-medium text-gray-700">
          {item.file.name}
        </span>
        <span className={`block text-[10px] ${failed ? 'text-red-500' : 'text-gray-400'}`}>
          {failed
            ? item.error || '上传失败'
            : item.status === 'done'
              ? formatSize(item.result?.size)
              : `上传中 ${item.percent}%`}
        </span>
        {item.status === 'uploading' && (
          <span className="mt-0.5 block h-0.5 w-24 overflow-hidden rounded-full bg-gray-100">
            <span
              className="block h-full bg-brand-500 transition-all"
              style={{ width: `${item.percent}%` }}
            />
          </span>
        )}
      </span>
      {failed && (
        <button
          onClick={onRetry}
          className="shrink-0 text-[10px] text-brand-600 underline"
          title="重新上传"
        >
          重试
        </button>
      )}
      <button
        onClick={onRemove}
        className="shrink-0 text-[11px] text-gray-400 hover:text-gray-700"
        title="移除"
      >
        ✕
      </button>
    </div>
  )
}

/** 把正文里的 @成员名 包成行内代码，交给 Markdown 渲染。
 *  长名字优先匹配，避免把 @文案编辑 里的 @文案 先切走。
 *
 *  为什么不直接插 <span>：正文要过 Markdown 渲染（模型输出带 ** 加粗、
 *  有序列表等），而 rehype-sanitize 会剥掉自定义 class 的 span，
 *  高亮会失效。行内代码是 Markdown 原生语法，渲染后自带底色，效果一致。
 */
/** 表情回应条：已有表情聚合显示，hover 出快捷表情 */
function ReactionBar({
  m,
  groupId,
  onReact,
}: {
  m: GroupMessageItem
  groupId: string
  onReact: (emoji: string) => Promise<void>
}) {
  const [open, setOpen] = useState(false)
  const counts = useMemo(() => {
    const map = new Map<string, { n: number; mine: boolean }>()
    for (const r of m.reactions || []) {
      const cur = map.get(r.emoji) || { n: 0, mine: false }
      map.set(r.emoji, { n: cur.n + 1, mine: cur.mine || r.mine })
    }
    return Array.from(map.entries())
  }, [m.reactions])

  if (!m.reactions?.length && !open) return null

  return (
    <div className="mt-1 flex flex-wrap items-center gap-1">
      {counts.map(([emoji, info]) => (
        <button
          key={emoji}
          onClick={() => void onReact(emoji)}
          className={`rounded-full border px-1.5 py-0.5 text-[11px] transition ${
            info.mine
              ? 'border-brand-400 bg-brand-50 text-brand-700'
              : 'border-gray-200 bg-gray-50 text-gray-600'
          }`}
          title={info.mine ? '取消我的回应' : '我的回应'}
        >
          {emoji} {info.n}
        </button>
      ))}
      <button
        onClick={() => setOpen((v) => !v)}
        className="rounded-full border border-dashed border-gray-300 px-1.5 py-0.5 text-[10px] text-gray-400 hover:border-brand-300 hover:text-brand-600"
      >
        {open ? '收起' : '+ 表情'}
      </button>
      {open && (
        <span className="flex gap-0.5">
          {['👍', '🎉', '❤️', '😂', '👀'].map((e) => (
            <button
              key={e}
              onClick={() => { void onReact(e); setOpen(false) }}
              className="rounded-md px-1 py-0.5 text-sm hover:bg-gray-100"
            >
              {e}
            </button>
          ))}
        </span>
      )}
    </div>
  )
}

/** 编辑消息 */
async function saveEdit(groupId: string, messageId: number, content: string) {
  const res = await groupsApi.editMessage(groupId, messageId, content)
  return res
}

/** 消息时间：飞书式 HH:MM，跨天的补日期 */
function formatMessageTime(iso?: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const hm = d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false })
  const today = new Date()
  const sameDay =
    d.getFullYear() === today.getFullYear() &&
    d.getMonth() === today.getMonth() &&
    d.getDate() === today.getDate()
  return sameDay ? hm : `${d.getMonth() + 1}/${d.getDate()} ${hm}`
}

function markMentions(text: string, names: string[]): string {
  if (!names.length) return text
  const sorted = [...names].sort((a, b) => b.length - a.length)
  const escaped = sorted.map((n) => n.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
  const re = new RegExp(`@(${escaped.join('|')})`, 'g')
  return text.replace(re, (m) => '`' + m + '`')
}

export default function GroupChatPage() {
  const [list, setList] = useState<GroupSummary[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [detail, setDetail] = useState<GroupDetail | null>(null)
  const [messages, setMessages] = useState<GroupMessageItem[]>([])
  const [bubbles, setBubbles] = useState<Bubble[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [routingHint, setRoutingHint] = useState<string | null>(null)

  // 飞书式交互：引用回复 + @ 选择器
  const [replyTo, setReplyTo] = useState<GroupMessageItem | null>(null)
  const [mentionQuery, setMentionQuery] = useState<string | null>(null)
  const [mentionIndex, setMentionIndex] = useState(0)
  const [explicitAgentId, setExplicitAgentId] = useState<string | null>(null)
  const [executionMode, setExecutionMode] = useState<'llm' | 'pi'>('llm')
  // 协作模式：single = 一人接活；chain = 成员之间接力补充
  const [collaborationMode, setCollaborationMode] = useState<'single' | 'chain'>('single')
  const [maxSpeakers, setMaxSpeakers] = useState(4)
  // 自动补人上限：群里没人能做时可以现场造几个成员
  const [recruitLimit, setRecruitLimit] = useState(3)
  const [highlightId, setHighlightId] = useState<number | null>(null)
  const messageRefs = useRef<Map<number, HTMLDivElement>>(new Map())

  // 飞书式交互增强：搜索 / 编辑 / 表情 / 已读 / @全体
  const [searchOpen, setSearchOpen] = useState(false)
  const [searchText, setSearchText] = useState('')
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editText, setEditText] = useState('')
  const [menuId, setMenuId] = useState<number | null>(null)
  const [mentionAll, setMentionAll] = useState(false)
  const QUICK_EMOJIS = ['👍', '🎉', '❤️', '😂', '👀']

  // 待发送附件：上传中/成功/失败都在这个列表里，发送成功后清空
  const [uploads, setUploads] = useState<PendingUpload[]>([])
  const fileInputRef = useRef<HTMLInputElement>(null)

  // 新建群
  const [showCreate, setShowCreate] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const [allAgents, setAllAgents] = useState<Member[]>([])
  const [newName, setNewName] = useState('')
  const [picked, setPicked] = useState<string[]>([])
  const [newMode, setNewMode] = useState('auto')

  const scrollRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)

  const scrollToBottom = useCallback(() => {
    requestAnimationFrame(() => {
      const el = scrollRef.current
      if (el) el.scrollTop = el.scrollHeight
    })
  }, [])

  const loadList = useCallback(async () => {
    try {
      const res = await groupsApi.list()
      setList(res.groups || [])
      if (!activeId && res.groups?.length) setActiveId(res.groups[0].id)
    } catch {
      // 列表加载失败时保持空态，不弹窗打断
    }
  }, [activeId])

  useEffect(() => {
    void loadList()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // 载入当前群
  useEffect(() => {
    if (!activeId) {
      setDetail(null)
      setMessages([])
      setBubbles([])
      return
    }
    let cancelled = false
    ;(async () => {
      try {
        const [g, m] = await Promise.all([
          groupsApi.get(activeId),
          groupsApi.messages(activeId, 100, searchText),
        ])
        if (cancelled) return
        setDetail(g)
        // 进群即标已读（不 await，避免拖慢首屏）
        void groupsApi.markAllRead(activeId).catch(() => {})
        // 群设置里的协作模式与人数上限要跟着群详情走
        const gs = (g as any).settings || {}
        setCollaborationMode(gs.collaboration_mode === 'chain' ? 'chain' : 'single')
        if (typeof gs.max_speakers === 'number') setMaxSpeakers(gs.max_speakers)
        if (typeof gs.auto_recruit_limit === 'number') setRecruitLimit(gs.auto_recruit_limit)
        setMessages(m.messages || [])
        setBubbles((m.messages || []).map((x) => ({ kind: 'message', data: x })))
        scrollToBottom()
      } catch {
        if (!cancelled) setDetail(null)
      }
    })()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeId, searchText, scrollToBottom])

  useEffect(() => {
    if (!showCreate || allAgents.length) return
    ;(async () => {
      try {
        const res: any = await agentsApi.list()
        const arr = res?.agents || res?.items || res || []
        setAllAgents(
          arr.map((a: any) => ({ id: a.id, name: a.name, description: a.description }))
        )
      } catch {
        setAllAgents([])
      }
    })()
  }, [showCreate, allAgents.length])

  const memberName = useCallback(
    (id?: string | null) => detail?.members.find((m) => m.id === id)?.name || '成员',
    [detail]
  )

  /** 点击引用块：滚到原消息并短暂高亮 */
  const jumpToMessage = useCallback((id: number) => {
    const el = messageRefs.current.get(id)
    if (!el) return
    el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    setHighlightId(id)
    window.setTimeout(() => setHighlightId(null), 1600)
  }, [])

  /** 根据输入框里最后一个 @ 后面的内容筛选成员 */
  const mentionOptions = useMemo(() => {
    if (mentionQuery === null || !detail) return []
    const q = mentionQuery.toLowerCase()
    return detail.members.filter((m) => m.name.toLowerCase().includes(q))
  }, [mentionQuery, detail])

  const updateInput = useCallback((value: string) => {
    setInput(value)
    const at = value.lastIndexOf('@')
    if (at < 0) {
      setMentionQuery(null)
      setMentionIndex(0)
      return
    }
    const after = value.slice(at + 1)
    // 出现空白说明已经写完 @名字，不再弹选择器
    if (/[\s\n]/.test(after)) {
      setMentionQuery(null)
      setMentionIndex(0)
      return
    }
    setMentionQuery(after)
    setMentionIndex(0)
  }, [])

  const pickMention = useCallback(
    (m: Member) => {
      const at = input.lastIndexOf('@')
      if (at < 0 || mentionQuery === null) return
      const head = input.slice(0, at)
      const tail = input.slice(at + mentionQuery.length + 1)
      setInput(`${head}@${m.name} ${tail}`)
      // 记下显式选中的人：正文里可能还有其他 @（引用/提到），
      // 不能靠后端从全文猜，否则会派错人。
      setExplicitAgentId(m.id)
      setMentionQuery(null)
      setMentionIndex(0)
    },
    [input, mentionQuery]
  )

  const handleCreate = async () => {
    if (!newName.trim()) return
    try {
      const g = await groupsApi.create({
        name: newName.trim(),
        agent_ids: picked,
        route_mode: newMode,
      })
      setShowCreate(false)
      setNewName('')
      setPicked([])
      setNewMode('auto')
      await loadList()
      setActiveId(g.id)
    } catch (e: any) {
      setRoutingHint(e?.message || '创建失败')
    }
  }

  /** 上传单个文件，失败只标记该条，不影响其它文件 */
  const uploadOne = useCallback(
    async (id: string, file: File) => {
      if (!activeId) return
      setUploads((prev) =>
        prev.map((u) =>
          u.id === id ? { ...u, status: 'uploading', percent: 0, error: undefined } : u
        )
      )
      try {
        const res = await groupsApi.uploadFile(activeId, file, (p) => {
          setUploads((prev) => prev.map((u) => (u.id === id ? { ...u, percent: p } : u)))
        })
        setUploads((prev) =>
          prev.map((u) => (u.id === id ? { ...u, status: 'done', percent: 100, result: res } : u))
        )
      } catch (e: any) {
        setUploads((prev) =>
          prev.map((u) => (u.id === id ? { ...u, status: 'error', error: e?.message } : u))
        )
      }
    },
    [activeId]
  )

  /** 选文件：先本地校验类型/大小/数量，再按并发上限排队上传 */
  const handlePickFiles = useCallback(
    (list: FileList | null) => {
      if (!list || !activeId) return
      const chosen = Array.from(list)
      const room = MAX_FILES - uploads.length
      const accepted: File[] = []
      const problems: string[] = []

      for (const f of chosen) {
        if (!ALLOWED_FILE_EXT.has(fileExt(f.name))) {
          problems.push(`${f.name} 类型不支持`)
          continue
        }
        if (f.size > MAX_FILE_BYTES) {
          problems.push(`${f.name} 超过 10MB`)
          continue
        }
        if (accepted.length >= room) {
          problems.push(`一条消息最多 ${MAX_FILES} 个文件`)
          break
        }
        accepted.push(f)
      }

      if (problems.length) setRoutingHint(problems.join('；'))
      if (!accepted.length) return

      const items = accepted.map((file) => ({
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        file,
      }))

      setUploads((prev) => [
        ...prev,
        ...items.map((it) => ({
          id: it.id,
          file: it.file,
          percent: 0,
          status: 'uploading' as const,
        })),
      ])

      // 简易并发池：固定 3 个 worker 轮流取任务
      let cursor = 0
      const workers = Array.from(
        { length: Math.min(UPLOAD_CONCURRENCY, items.length) },
        async () => {
          while (cursor < items.length) {
            const item = items[cursor]
            cursor += 1
            await uploadOne(item.id, item.file)
          }
        }
      )
      void Promise.all(workers)
    },
    [activeId, uploads.length, uploadOne]
  )

  /** 切换协作模式：单人接活 ↔ 成员接力补充 */
  const toggleCollaboration = useCallback(async () => {
    if (!activeId) return
    const next = collaborationMode === 'chain' ? 'single' : 'chain'
    const prev = collaborationMode
    setCollaborationMode(next)  // 先改 UI，失败再回滚
    try {
      await groupsApi.update(activeId, {
        settings: { collaboration_mode: next, max_speakers: maxSpeakers },
      })
      setRoutingHint(
        next === 'chain'
          ? `已开启协作接力：最多 ${maxSpeakers} 位成员依次补充`
          : '已切回单人接活'
      )
    } catch (e: any) {
      setCollaborationMode(prev)
      setRoutingHint(e?.message || '切换失败')
    }
  }, [activeId, collaborationMode, maxSpeakers])

  /** 调整接力人数上限 */
  const changeMaxSpeakers = useCallback(
    async (n: number) => {
      if (!activeId) return
      const prev = maxSpeakers
      setMaxSpeakers(n)
      try {
        await groupsApi.update(activeId, {
          settings: { collaboration_mode: collaborationMode, max_speakers: n },
        })
      } catch (e: any) {
        setMaxSpeakers(prev)
        setRoutingHint(e?.message || '保存失败')
      }
    },
    [activeId, maxSpeakers, collaborationMode]
  )

  /** 调整自动补人上限 */
  const changeRecruitLimit = useCallback(
    async (n: number) => {
      if (!activeId) return
      const prev = recruitLimit
      setRecruitLimit(n)
      try {
        await groupsApi.update(activeId, { settings: { auto_recruit_limit: n } })
        setRoutingHint(`自动补人上限已设为 ${n} 个`)
      } catch (e: any) {
        setRecruitLimit(prev)
        setRoutingHint(e?.message || '保存失败')
      }
    },
    [activeId, recruitLimit]
  )

  /** 移出成员。自动招募的会被彻底删除，需要明确提示。 */
  const handleRemoveMember = useCallback(
    async (agent: Member) => {
      if (!activeId) return
      const auto = !!(agent as any).auto_created
      const msg = auto
        ? `把「${agent.name}」移出群？它是自动招募的临时成员，会从账号里彻底删除。`
        : `把「${agent.name}」移出群？Agent 本身会保留，可以再加入别的群。`
      if (!window.confirm(msg)) return
      try {
        const res = await groupsApi.removeMember(activeId, agent.id)
        setDetail(res)
        setRoutingHint(
          res.removed_agent_purged
            ? `已移出「${agent.name}」，并删除了这个临时成员`
            : `已移出「${agent.name}」`
        )
        await loadList()
      } catch (e: any) {
        setRoutingHint(e?.message || '移出失败')
      }
    },
    [activeId, loadList]
  )

  /** 把账号里已有的 Agent 拉进群 */
  const handleAddMember = useCallback(
    async (agentId: string) => {
      if (!activeId || !detail) return
      if (detail.members.some((m) => m.id === agentId)) return
      try {
        const res = await groupsApi.addMembers(activeId, [
          ...detail.members.map((m) => m.id),
          agentId,
        ])
        setDetail(res)
        setRoutingHint(`已把「${res.members.find((m) => m.id === agentId)?.name}」拉进群`)
        await loadList()
      } catch (e: any) {
        setRoutingHint(e?.message || '添加失败')
      }
    },
    [activeId, detail, loadList]
  )

  /** 删除群聊。记录会一并删除，所以必须二次确认。 */
  const handleDeleteGroup = useCallback(
    async (g: { id: string; name: string }) => {
      if (!window.confirm(`删除群聊「${g.name}」？\n聊天记录会一并删除，无法恢复。`)) {
        return
      }
      try {
        await groupsApi.remove(g.id)
        if (activeId === g.id) {
          setActiveId(null)
          setDetail(null)
          setMessages([])
          setBubbles([])
        }
        await loadList()
        setRoutingHint(`已删除「${g.name}」`)
      } catch (e: any) {
        setRoutingHint(e?.message || '删除失败，请重试')
      }
    },
    [activeId, loadList]
  )

  const handleSend = async () => {
    const text = input.trim()
    if (!text || !activeId || sending) return

    // 有文件还在传就先等等，避免发出去一条「附件缺失」的消息
    if (uploads.some((u) => u.status === 'uploading')) {
      setRoutingHint('文件还在上传，请稍候…')
      return
    }
    if (uploads.some((u) => u.status === 'error')) {
      setRoutingHint('有文件上传失败，请重试或移除后再发送')
      return
    }

    const readyFiles: GroupFileInfo[] = uploads
      .filter((u) => u.status === 'done' && u.result)
      .map((u) => u.result as GroupFileInfo)

    setInput('')
    setMentionQuery(null)
    setMentionIndex(0)
    setExplicitAgentId(null)
    setSending(true)
    setRoutingHint(null)

    // 先把用户消息推到界面；临时 id 为负，等落库后用正式的 id
    const now = new Date().toISOString()
    const quoted = replyTo
    setReplyTo(null)
    setUploads([])
    setBubbles((prev) => [
      ...prev,
      {
        kind: 'message',
        data: {
          id: -Date.now(),
          sender_type: 'user',
          content: text,
          meta: {
            ...(quoted ? { reply_to: quoted.id } : {}),
            ...(readyFiles.length ? { files: readyFiles } : {}),
          },
          created_at: now,
        },
      },
      { kind: 'routing' },
    ])
    scrollToBottom()

    const ctrl = new AbortController()
    abortRef.current = ctrl
    let pendingAgent: { name: string; text: string } | null = null

    try {
      for await (const evt of groupsApi.stream(
        activeId,
        text,
        explicitAgentId || undefined,
        ctrl.signal,
        quoted?.id && quoted.id > 0 ? quoted.id : undefined,
        executionMode,
        readyFiles.map((f) => f.stored_name),
        mentionAll
      )) {
        // 群里没人能做，后端现场招了个人进来
        if (evt.type === 'member_joined') {
          setBubbles((prev) => [
            ...prev,
            {
              kind: 'message',
              data: {
                id: evt.id || -Date.now(),
                sender_type: 'system',
                content: evt.content || '已创建并拉入新成员',
                meta: { member_joined: evt.member?.id, reply_to: evt.reply_to },
                created_at: new Date().toISOString(),
              },
            },
          ])
          // 成员列表变了，重新拉一次群详情，顶部头像和人数要跟着更新
          if (activeId) {
            void groupsApi
              .get(activeId)
              .then((g) => setDetail(g))
              .catch(() => {})
          }
          scrollToBottom()
          continue
        }

        // 转交：把这一棒已确认的内容留在时间线，再显示「转给谁」
        if (evt.type === 'handoff') {
          const carriedText = evt.carried || ''
          const fromName = evt.from || pendingAgent?.name || '智能体'
          setBubbles((prev) => {
            const next = prev.filter((b) => b.kind !== 'pending')
            if (carriedText) {
              next.push({
                kind: 'message',
                data: {
                  // 用后端落库的正式 id，刷新前后能对上
                  id: evt.interim_id || -Date.now() - Math.floor(Math.random() * 1000),
                  sender_type: 'agent',
                  sender_id: evt.from_agent_id,
                  sender_name: fromName,
                  content: carriedText,
                  meta: { interim: true },
                  created_at: new Date().toISOString(),
                },
              })
            }
            // 转交说明本身落过库，这里用正式 id，刷新后能对上
            next.push({
              kind: 'message',
              data: {
                id: evt.id || -Date.now(),
                sender_type: 'system',
                content: evt.content || `${fromName} 转交给 ${evt.to || '同事'}`,
                meta: { handoff: true, reply_to: evt.reply_to },
                created_at: new Date().toISOString(),
              },
            })
            return next
          })
          pendingAgent = null
          scrollToBottom()
          continue
        }

        // 带附件时后端会自动升级到工作模式（只有它能真正读文件）
        if (evt.type === 'mode_switch') {
          if (evt.execution_mode === 'pi' || evt.execution_mode === 'llm') {
            setExecutionMode(evt.execution_mode)
          }
          setRoutingHint(evt.content || null)
          continue
        }

        if (evt.type === 'routing') {
          // 把临时负数 id 换成数据库正式 id，否则后续引用块找不到这条消息
          if (evt.user_message_id) {
            setBubbles((prev) =>
              prev.map((b) =>
                b.kind === 'message' && b.data.id < 0
                  ? { ...b, data: { ...b.data, id: evt.user_message_id! } }
                  : b
              )
            )
          }
          setRoutingHint('正在判断谁来接…')
          continue
        }

        if (evt.type === 'route_decision') {
          setRoutingHint(null)
          if (!evt.agent) {
            // 没人接：用系统消息展示原因
            setBubbles((prev) => prev.filter((b) => b.kind !== 'routing'))
            continue
          }
          continue
        }

        if (evt.type === 'system_message') {
          setBubbles((prev) => {
            const next = prev.filter((b) => b.kind !== 'routing')
            return [
              ...next,
              {
                kind: 'message',
                data: {
                  id: evt.id || -Date.now(),
                  sender_type: 'system',
                  content: evt.content || '',
                  meta: { reply_to: evt.reply_to, assignee: evt.assignee },
                  created_at: new Date().toISOString(),
                },
              },
            ]
          })
          scrollToBottom()
          continue
        }

        if (evt.type === 'agent_start' || (executionMode === 'pi' && !pendingAgent)) {
          pendingAgent = { name: (evt as any).agent || '智能体', text: '' }
          setBubbles((prev) => [
            ...prev,
            { kind: 'pending', agentName: pendingAgent!.name, text: '', replyToName: '你' },
          ])
          scrollToBottom()
          if (evt.type === 'agent_start') continue
        }

        // PiAgent 事件：把执行进度写进「正在输入」气泡，
        // 否则它整段只显示三个字，用户以为卡死了。
        if (evt.type === 'thinking' || evt.type === 'tool_call' || evt.type === 'log') {
          const label =
            evt.type === 'thinking' ? '思考中' : evt.type === 'tool_call' ? '调用工具' : '执行'
          const detail = String((evt as any).content || (evt as any).text || '').slice(0, 60)
          const line = detail ? `${label}：${detail}` : `${label}…`
          setRoutingHint(line)
          setBubbles((prev) => {
            const next = [...prev]
            for (let i = next.length - 1; i >= 0; i--) {
              const b = next[i]
              if (b.kind === 'pending') {
                // 累积最近几条，滚动看得到做过什么
                const merged = (b.text ? b.text + '\n' : '') + line
                next[i] = { ...b, text: merged.split('\n').slice(-6).join('\n') }
                break
              }
            }
            return next
          })
          scrollToBottom()
          continue
        }

        if (evt.type === 'agent_chunk') {
          const chunk = evt.text || ''
          if (!pendingAgent) {
            pendingAgent = { name: evt.agent || '智能体', text: '' }
            setBubbles((prev) => [
              ...prev,
              { kind: 'pending', agentName: pendingAgent!.name, text: '', replyToName: '你' },
            ])
          }
          pendingAgent.text += chunk
          const snapshot = pendingAgent.text
          setBubbles((prev) => {
            const next = [...prev]
            for (let i = next.length - 1; i >= 0; i--) {
              const b = next[i]
              if (b.kind === 'pending') {
                next[i] = { ...b, text: snapshot }
                break
              }
            }
            return next
          })
          scrollToBottom()
          continue
        }

        if (evt.type === 'agent_done') {
          // 必须先把文本抓到局部变量：setBubbles 的 updater 是延后执行的，
          // 而下面马上会把 pendingAgent 置空，直接闭包引用会拿到 null，
          // 表现为「智能体气泡是空的」（内容其实已经正常落库）。
          const finalText = (evt as any).content || pendingAgent?.text || ''
          const finalName = (evt as any).agent || pendingAgent?.name || '智能体'
          setBubbles((prev) => {
            const next = prev.filter((b) => b.kind !== 'pending')
            return [
              ...next,
              {
                kind: 'message',
                data: {
                  id: evt.id || -Date.now(),
                  sender_type: 'agent',
                  sender_id: evt.agent_id,
                  sender_name: finalName,
                  content: finalText,
                  meta: {
                    reply_to: evt.reply_to,
                    mentions: ['你'],
                    // 工作模式产出的文件必须带进 meta，否则气泡里没有下载入口
                    ...((evt as any).files?.length ? { files: (evt as any).files } : {}),
                    ...(evt.execution_mode ? { execution_mode: evt.execution_mode } : {}),
                  },
                  created_at: new Date().toISOString(),
                },
              },
            ]
          })
          pendingAgent = null
          // 产物已经在气泡里以附件卡呈现，不必再在输入框上方留一行提示
          setRoutingHint(null)
          scrollToBottom()
          continue
        }

        if (evt.type === 'error') {
          setRoutingHint(evt.content || '执行出错')
          continue
        }
      }
    } catch (e: any) {
      if (e?.name !== 'AbortError') setRoutingHint('连接中断，请重试')
    } finally {
      setSending(false)
      // 同时清掉 pending：PiAgent 模式下若中途失败或没收到 agent_done，
      // 「正在输入…」会永远留在界面上（之前就是这个表现）。
      setBubbles((prev) =>
        prev.filter((b) => b.kind !== 'routing' && b.kind !== 'pending')
      )
      abortRef.current = null
      void loadList()
    }
  }

  const activeGroup = useMemo(
    () => list.find((g) => g.id === activeId) || null,
    [list, activeId]
  )

  return (
    <div className="flex h-[calc(100vh-8.5rem)] gap-2 px-2 md:h-[calc(100vh-4rem)] md:gap-4 md:px-0">
      {/* 左：群列表（窄屏隐藏，改用聊天区头部的群选择） */}
      <aside className="hidden w-56 shrink-0 flex-col rounded-xl border border-gray-200 bg-white md:flex lg:w-64">
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
          <span className="text-sm font-semibold text-gray-900">群聊</span>
          <button
            onClick={() => setShowCreate((v) => !v)}
            className="text-xs px-2 py-1 rounded-md bg-brand-600 text-white hover:bg-brand-700"
          >
            新建
          </button>
        </div>

        {showCreate && (
          <div className="px-3 py-3 border-b border-gray-100 space-y-2">
            <input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="群名称，如「内容小组」"
              className="w-full text-xs px-2 py-1.5 border border-gray-200 rounded-md focus:outline-none focus:ring-1 focus:ring-brand-500"
            />
            <select
              value={newMode}
              onChange={(e) => setNewMode(e.target.value)}
              className="w-full text-xs px-2 py-1.5 border border-gray-200 rounded-md"
            >
              <option value="auto">自动指派（推荐）</option>
              <option value="manual">手动 @ 指定</option>
              <option value="off">全员回复</option>
            </select>
            <div className="max-h-40 overflow-y-auto space-y-1">
              {allAgents.length === 0 && (
                <p className="text-[11px] text-gray-400">还没有可加入的智能体</p>
              )}
              {allAgents.map((a) => {
                const on = picked.includes(a.id)
                return (
                  <button
                    key={a.id}
                    onClick={() =>
                      setPicked((p) => (on ? p.filter((x) => x !== a.id) : [...p, a.id]))
                    }
                    className={`w-full text-left text-[11px] px-2 py-1.5 rounded-md border transition ${
                      on
                        ? 'border-brand-500 bg-brand-50 text-brand-700'
                        : 'border-gray-200 text-gray-600 hover:border-gray-300'
                    }`}
                  >
                    {on ? '✓ ' : ''}
                    {a.name}
                  </button>
                )
              })}
            </div>
            <button
              onClick={handleCreate}
              disabled={!newName.trim()}
              className="w-full text-xs py-1.5 rounded-md bg-brand-600 text-white disabled:opacity-40"
            >
              创建并进入
            </button>
          </div>
        )}

        <div className="flex-1 overflow-y-auto">
          {list.length === 0 && !showCreate && (
            <p className="px-4 py-6 text-xs text-gray-400 leading-relaxed">
              还没有群聊。点「新建」，把几个智能体拉进同一个群，之后发任务由系统判断谁接。
            </p>
          )}
          {list.map((g) => (
            <div
              key={g.id}
              // 用 div 而不是 button：里面还要放删除按钮，button 不能嵌套
              role="button"
              tabIndex={0}
              onClick={() => setActiveId(g.id)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') setActiveId(g.id)
              }}
              className={`group/item w-full cursor-pointer px-4 py-3 border-b border-gray-50 transition ${
                g.id === activeId ? 'bg-brand-50' : 'hover:bg-gray-50'
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-medium text-gray-900 truncate">{g.name}</span>
                <span className="flex shrink-0 items-center gap-1.5">
                  <span className="text-[10px] text-gray-400">{g.member_count} 人</span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      void handleDeleteGroup(g)
                    }}
                    className="text-[11px] text-gray-300 opacity-0 transition hover:text-red-500 group-hover/item:opacity-100"
                    title="删除这个群聊"
                  >
                    ✕
                  </button>
                </span>
              </div>
              <p className="text-[11px] text-gray-400 truncate mt-0.5">
                {g.last_message || '还没有消息'}
              </p>
            </div>
          ))}
        </div>
      </aside>

      {/* 右：聊天区 */}
      <section className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-xl border border-gray-200 bg-white">
        {!detail ? (
          <div className="flex-1 flex items-center justify-center">
            <p className="text-sm text-gray-400">
              {list.length ? '选择左侧的群聊' : '先创建一个群聊'}
            </p>
          </div>
        ) : (
          <>
            {/* 头部 */}
            <header className="flex items-center justify-between gap-2 border-b border-gray-100 px-3 py-2.5 md:px-5 md:py-3">
              <div className="flex min-w-0 items-center gap-2">
                {/* 窄屏没有群列表，用下拉切群 */}
                <select
                  value={activeId || ''}
                  onChange={(e) => setActiveId(e.target.value)}
                  className="max-w-[96px] shrink-0 truncate rounded-md border border-gray-200 bg-white px-1.5 py-1 text-[11px] text-gray-700 md:hidden"
                >
                  {list.map((g) => (
                    <option key={g.id} value={g.id}>{g.name}</option>
                  ))}
                </select>
                <div className="min-w-0">
                <h2 className="truncate text-sm font-semibold text-gray-900">{detail.name}</h2>
                <p className="text-[11px] text-gray-400 mt-0.5">
                  {ROUTE_MODE_LABEL[detail.route_mode] || detail.route_mode} ·{' '}
                  {detail.members.length} 位成员
                  {collaborationMode === 'chain' && (
                    <> · <span className="text-brand-600">协作接力（最多 {maxSpeakers} 人）</span></>
                  )}
                </p>
                {detail.members.some((m) => !(m.description || '').trim()) && (
                  <p className="text-[10.5px] text-amber-600 mt-1">
                    有成员未填写能力描述（头像标黄），自动派发不可用 · 请到 Agent 设置补充
                  </p>
                )}
                </div>
              </div>
              <div className="flex shrink-0 -space-x-1.5">
                {detail.members.slice(0, 5).map((m) => {
                  const noDesc = !(m.description || '').trim()
                  return (
                    <div
                      key={m.id}
                      title={noDesc ? `${m.name}（未填写能力描述，无法自动派发）` : m.name}
                      className={`hidden w-7 h-7 rounded-full text-white text-[11px] items-center justify-center ring-2 ring-white sm:flex ${
                        noDesc
                          ? 'bg-amber-400 ring-amber-100'
                          : 'bg-gradient-to-br from-brand-500 to-blue-500'
                      }`}
                    >
                      {m.name.slice(0, 1)}
                    </div>
                  )
                })}
                <button
                  onClick={() => setShowSettings(true)}
                  className="ml-3 self-center rounded-md border border-gray-200 px-2 py-0.5 text-[10.5px] text-gray-500 transition hover:border-brand-300 hover:text-brand-600"
                  title="群设置：成员管理、协作模式、自动补人"
                >
                  群设置
                </button>
              </div>
            </header>

            {/* 搜索：按关键词过滤历史消息 */}
            {searchOpen && (
              <div className="mx-3 mt-3 flex items-center gap-2 rounded-lg border border-brand-200 bg-brand-50 px-3 py-2">
                <input
                  autoFocus
                  value={searchText}
                  onChange={(e) => setSearchText(e.target.value)}
                  placeholder="搜索聊天记录…"
                  className="flex-1 bg-transparent text-xs outline-none placeholder:text-brand-400"
                />
                <span className="text-[10px] text-brand-500">{messages.length} 条结果</span>
                <button
                  onClick={() => { setSearchOpen(false); setSearchText('') }}
                  className="text-xs text-brand-500 hover:text-brand-700"
                >
                  关闭
                </button>
              </div>
            )}

            {/* 消息流 */}
            <div ref={scrollRef} className="flex-1 overflow-y-auto px-5 py-4 space-y-3">
              {bubbles.length === 0 && (
                <div className="text-center py-10">
                  <p className="text-sm text-gray-400">发一条任务试试</p>
                  <p className="text-[11px] text-gray-400 mt-1">
                    系统会从 {detail.members.length} 位成员里挑一个最合适的来接手
                  </p>
                </div>
              )}

              {bubbles.map((b, idx) => {
                if (b.kind === 'routing') {
                  return (
                    <div key={`r-${idx}`} className="flex justify-center">
                      <span className="text-[11px] text-gray-400 animate-pulse">
                        {routingHint || '正在判断谁来接…'}
                      </span>
                    </div>
                  )
                }

                if (b.kind === 'pending') {
                  return (
                    <div key={`p-${idx}`} className="flex gap-2.5">
                      <div className="w-8 h-8 shrink-0 rounded-full bg-gradient-to-br from-brand-500 to-blue-500 text-white text-xs flex items-center justify-center">
                        {b.agentName.slice(0, 1)}
                      </div>
                      <div className="max-w-[75%]">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-xs font-medium text-gray-700">
                            {b.agentName}
                          </span>
                          <span className="text-[10px] text-gray-400">
                            回复 @{b.replyToName}
                          </span>
                        </div>
                        <div className="rounded-xl rounded-tl-sm bg-gray-50 border border-gray-100 px-3.5 py-2.5 text-sm text-gray-800 whitespace-pre-wrap">
                          {b.text || <span className="text-gray-300">正在输入…</span>}
                        </div>
                      </div>
                    </div>
                  )
                }

                const m = b.data
                const isHighlighted = highlightId === m.id
                const setRef = (el: HTMLDivElement | null) => {
                  if (el) messageRefs.current.set(m.id, el)
                  else messageRefs.current.delete(m.id)
                }
                const memberNames = detail?.members.map((x) => x.name) || []

                // 飞书式引用块：显示原消息片段，点击跳回去
                const quoteBlock = m.meta?.reply_to ? (
                  (() => {
                    const quotedId = m.meta.reply_to as number
                    // 从 bubbles 找：messages 只在进群时加载一次，
                    // 本轮刚发出的消息还没同步进去，会错误显示「查看原消息」
                    const quotedBubble = bubbles.find(
                      (b) => b.kind === 'message' && b.data.id === quotedId
                    )
                    const quoted = quotedBubble?.kind === 'message' ? quotedBubble.data : undefined
                    const who = quoted
                      ? quoted.sender_name || (quoted.sender_type === 'user' ? '你' : '成员')
                      : '原消息'
                    const excerpt = (quoted?.content || '查看原消息').slice(0, 48)
                    return (
                      <button
                        onClick={() => jumpToMessage(quotedId)}
                        className="mb-1.5 block w-full max-w-[280px] rounded-md border-l-2 border-brand-300 bg-white/70 px-2 py-1 text-left text-[10.5px] leading-4 text-gray-500 transition hover:bg-white"
                        title="点击跳转到原消息"
                      >
                        <span className="font-medium text-gray-600">{who}：</span>
                        {excerpt}
                        {(quoted?.content || '').length > 48 ? '…' : ''}
                      </button>
                    )
                  })()
                ) : null

                // 系统消息：路由决策
                if (m.sender_type === 'system') {
                  const assignee = m.meta?.assignee
                  return (
                    <div key={`m-${m.id}`} ref={setRef} className="flex justify-center">
                      <div
                        className={`inline-flex items-start gap-2 max-w-[80%] rounded-lg bg-amber-50 border border-amber-100 px-3 py-2 transition ${
                          isHighlighted ? 'ring-2 ring-amber-300' : ''
                        }`}
                      >
                        <span className="text-[13px] leading-5">🔀</span>
                        <span className="text-[11.5px] text-amber-800 leading-5">
                          {m.content}
                        </span>
                        {assignee && (
                          <span className="text-[10px] text-amber-600 whitespace-nowrap mt-0.5">
                            {typeof m.meta?.confidence === 'number'
                              ? `置信度 ${Math.round(m.meta.confidence * 100)}%`
                              : ''}
                          </span>
                        )}
                      </div>
                    </div>
                  )
                }

                // 智能体消息
                if (m.sender_type === 'agent') {
                  const name = m.sender_name || memberName(m.sender_id)
                  return (
                    <div
                      key={`m-${m.id}`}
                      ref={setRef}
                      className={`group flex gap-2.5 rounded-lg px-1 py-0.5 transition ${
                        isHighlighted ? 'bg-amber-50' : ''
                      }`}
                    >
                      <div className="w-8 h-8 shrink-0 rounded-full bg-gradient-to-br from-brand-500 to-blue-500 text-white text-xs flex items-center justify-center">
                        {name.slice(0, 1)}
                      </div>
                      <div className="max-w-[75%]">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-xs font-medium text-gray-700">{name}</span>
                          <span className="text-[10px] text-gray-400">{formatMessageTime(m.created_at)}</span>
                          {m.meta?.reply_to && (
                            <span className="text-[10px] text-gray-400">引用回复</span>
                          )}
                        </div>
                        {quoteBlock}
                        <div className="rounded-xl rounded-tl-sm bg-gray-50 border border-gray-100 px-3.5 py-2.5 text-sm text-gray-800">
                          {m.is_revoked ? (
                            <span className="text-gray-400 italic">消息已撤回</span>
                          ) : (
                            <Markdown content={markMentions(m.content, memberNames)} />
                          )}
                        </div>
                        {Array.isArray(m.meta?.files) && m.meta.files.length > 0 && (
                          <div className="mt-2 space-y-1.5">
                            <p className="text-[10.5px] text-gray-400">
                              生成了 {m.meta.files.length} 个文件
                            </p>
                            <div className="flex flex-wrap gap-1.5">
                              {m.meta.files.map((f: PiArtifact, i: number) => (
                                <ArtifactCard key={i} file={f} agentId={m.sender_id || undefined} />
                              ))}
                            </div>
                            {m.meta.files.some((f: PiArtifact) => IMAGE_EXT.test(f.name)) && (
                              <div className="flex flex-wrap gap-2 pt-0.5">
                                {m.meta.files
                                  .filter((f: PiArtifact) => IMAGE_EXT.test(f.name))
                                  .map((f: PiArtifact, i: number) => (
                                    <ArtifactPreview
                                      key={`p-${i}`}
                                      file={f}
                                      agentId={m.sender_id || undefined}
                                    />
                                  ))}
                              </div>
                            )}
                          </div>
                        )}
                        <button
                          onClick={() => setReplyTo(m)}
                          className="mt-1 text-[10.5px] text-gray-400 opacity-0 transition group-hover:opacity-100 hover:text-brand-600"
                        >
                          ↩ 回复这条
                        </button>
                        <ReactionBar m={m} groupId={detail.id} onReact={async (emoji) => {
                          const res = await groupsApi.react(detail.id, m.id, emoji)
                          setBubbles((prev) => prev.map((b) =>
                            b.kind === 'message' && b.data.id === m.id
                              ? { ...b, data: { ...b.data, reactions: res.reactions } }
                              : b
                          ))
                        }} />
                        {m.meta?.route_reason && (
                          <p className="text-[10px] text-gray-400 mt-0.5">
                            指派理由：{m.meta.route_reason}
                          </p>
                        )}
                      </div>
                    </div>
                  )
                }

                // 用户消息
                return (
                  <div
                    key={`m-${m.id}`}
                    ref={setRef}
                    className={`group flex justify-end rounded-lg px-1 py-0.5 transition ${
                      isHighlighted ? 'bg-amber-50' : ''
                    }`}
                  >
                    <div className="max-w-[75%]">
                      {quoteBlock}
                      <div className="rounded-xl rounded-tr-sm bg-brand-600 px-3.5 py-2.5 text-sm text-white [&_*]:!text-white [&_code]:!bg-white/20">
                        {m.is_revoked ? (
                          <span className="opacity-70 italic">消息已撤回</span>
                        ) : (
                          <Markdown content={markMentions(m.content, memberNames)} />
                        )}
                      </div>
                      {Array.isArray(m.meta?.files) && m.meta.files.length > 0 && (
                        <div className="mt-1.5 flex flex-wrap justify-end gap-1.5">
                          {(m.meta.files as GroupFileInfo[]).map((f, i) =>
                            f.stored_name ? (
                              <GroupFileCard key={i} file={f} groupId={detail.id} />
                            ) : null
                          )}
                        </div>
                      )}
                      {/* @全体标记 */}
                      {m.meta?.mention_all && (
                        <p className="mt-1 text-right text-[10.5px] font-medium text-brand-600">
                          @全体成员
                        </p>
                      )}
                      {/* 表情回应 */}
                      <ReactionBar m={m} groupId={detail.id} onReact={async (emoji) => {
                        const res = await groupsApi.react(detail.id, m.id, emoji)
                        setBubbles((prev) => prev.map((b) =>
                          b.kind === 'message' && b.data.id === m.id
                            ? { ...b, data: { ...b.data, reactions: res.reactions } }
                            : b
                        ))
                      }} />
                      {/* 编辑态 */}
                      {editingId === m.id ? (
                        <div className="mt-1.5 flex justify-end gap-1.5">
                          <input
                            autoFocus
                            value={editText}
                            onChange={(e) => setEditText(e.target.value)}
                            onKeyDown={async (e) => {
                              if (e.key === 'Enter' && editText.trim() && detail) {
                                const updated = await saveEdit(detail.id, m.id, editText.trim())
                                setBubbles((prev) => prev.map((b) =>
                                  b.kind === 'message' && b.data.id === m.id
                                    ? { ...b, data: updated }
                                    : b
                                ))
                                setEditingId(null)
                              }
                              if (e.key === 'Escape') setEditingId(null)
                            }}
                            className="flex-1 rounded-md border border-brand-300 px-2 py-1 text-xs outline-none"
                          />
                          <button onClick={() => setEditingId(null)} className="text-[10.5px] text-gray-400">取消</button>
                        </div>
                      ) : null}
                      {/* 消息操作 */}
                      <div className="mt-0.5 flex justify-end items-center gap-2">
                        {m.meta?.edited && <span className="text-[10px] text-gray-400">已编辑</span>}
                        <button
                          onClick={() => { setMenuId(menuId === m.id ? null : m.id) }}
                          className="text-[10.5px] text-gray-400 opacity-0 transition group-hover:opacity-100 hover:text-brand-600"
                        >
                          ⋯
                        </button>
                        <button
                          onClick={() => setReplyTo(m)}
                          className="text-[10.5px] text-gray-400 hover:text-brand-600"
                        >
                          ↩ 回复这条
                        </button>
                      </div>
                      {menuId === m.id && detail && (
                        <div className="mt-1 flex justify-end gap-2 rounded-md border border-gray-200 bg-white px-2 py-1 text-[10.5px]">
                          <button
                            onClick={() => { setEditingId(m.id); setEditText(m.content); setMenuId(null) }}
                            className="text-gray-600 hover:text-brand-600"
                          >
                            编辑
                          </button>
                          <button
                            onClick={async () => {
                              if (!window.confirm('撤回这条消息？')) return
                              await groupsApi.revokeMessage(detail.id, m.id)
                              setBubbles((prev) => prev.map((b) =>
                                b.kind === 'message' && b.data.id === m.id
                                  ? { ...b, data: { ...b.data, is_revoked: true, content: '' } }
                                  : b
                              ))
                              setMenuId(null)
                            }}
                            className="text-gray-600 hover:text-red-600"
                          >
                            撤回
                          </button>
                        </div>
                      )}
                      {m.read_by && m.read_by.length > 0 && (
                        <p className="mt-0.5 text-right text-[10px] text-gray-400">
                          {m.read_by.length} 人已读
                        </p>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>

            {/* 输入区 */}
            {/* @全体成员与搜索入口 */}
          <div className="flex items-center gap-2 px-2 pt-2 md:px-4">
            <button
              onClick={() => setMentionAll((v) => !v)}
              className={`rounded-md border px-2 py-0.5 text-[10.5px] transition ${
                mentionAll
                  ? 'border-brand-400 bg-brand-50 text-brand-700'
                  : 'border-gray-200 text-gray-500 hover:border-brand-300'
              }`}
              title="标记这条消息为 @全体成员"
            >
              @全体成员{mentionAll ? ' ✓' : ''}
            </button>
            <button
              onClick={() => setSearchOpen((v) => !v)}
              className="rounded-md border border-gray-200 px-2 py-0.5 text-[10.5px] text-gray-500 hover:border-brand-300 hover:text-brand-600"
              title="搜索聊天记录"
            >
              搜索记录
            </button>
          </div>
          <div className="relative border-t border-gray-100 px-2 py-2.5 md:px-4 md:py-3">
              {routingHint && (
                <p className="text-[11px] text-amber-600 mb-2">{routingHint}</p>
              )}

              {/* 执行方式：快速回答（一次模型调用） vs 工作模式（PiAgent，可产出文件） */}
              <div className="mb-2 flex items-center gap-2">
                <span className="text-[10.5px] text-gray-400">执行方式</span>
                <button
                  onClick={() => setExecutionMode('llm')}
                  className={`text-[10.5px] px-2 py-0.5 rounded-full border transition ${
                    executionMode === 'llm'
                      ? 'border-brand-500 bg-brand-50 text-brand-700 font-medium'
                      : 'border-gray-200 text-gray-500 hover:border-gray-300'
                  }`}
                  title="快速回答：一次模型调用，秒级返回，适合问答、文案、分析与建议"
                >
                  {EXEC_MODE_LABEL.llm}
                </button>
                <button
                  onClick={() => setExecutionMode('pi')}
                  className={`text-[10.5px] px-2 py-0.5 rounded-full border transition ${
                    executionMode === 'pi'
                      ? 'border-brand-500 bg-brand-50 text-brand-700 font-medium'
                      : 'border-gray-200 text-gray-500 hover:border-gray-300'
                  }`}
                  title="工作模式：可读写工作区、调用工具、生成并交付真实文件，耗时较长"
                >
                  {EXEC_MODE_LABEL.pi}
                </button>
                <span className="text-[10px] text-gray-400">
                  {executionMode === 'pi' ? '生成文件，耗时较长' : '秒级返回，纯对话'}
                </span>
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="ml-auto text-[10.5px] px-2 py-0.5 rounded-full border border-gray-200 text-gray-500 transition hover:border-brand-300 hover:text-brand-600"
                  title={`添加附件（最多 ${MAX_FILES} 个，单个 ≤ 10MB）`}
                >
                  📎 附件
                </button>
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  className="hidden"
                  onChange={(e) => {
                    handlePickFiles(e.target.files)
                    // 清空，否则同一个文件第二次选不到 change 事件
                    e.target.value = ''
                  }}
                />
              </div>

              {/* 待发送附件：上传进度 / 成功 / 失败重试 */}
              {uploads.length > 0 && (
                <div className="mb-2 flex flex-wrap gap-1.5">
                  {uploads.map((u) => (
                    <UploadChip
                      key={u.id}
                      item={u}
                      onRetry={() => void uploadOne(u.id, u.file)}
                      onRemove={() => setUploads((prev) => prev.filter((x) => x.id !== u.id))}
                    />
                  ))}
                </div>
              )}

              {/* 引用头：发消息前能取消 */}
              {replyTo && (
                <div className="mb-2 flex items-center gap-2 rounded-md border-l-2 border-brand-400 bg-brand-50/60 px-2.5 py-1.5 text-[11px] text-gray-600">
                  <span className="font-medium text-brand-700">
                    回复 {replyTo.sender_name || (replyTo.sender_type === 'user' ? '你' : '成员')}
                  </span>
                  <span className="min-w-0 flex-1 truncate">
                    {replyTo.content.slice(0, 60)}
                  </span>
                  <button
                    onClick={() => setReplyTo(null)}
                    className="text-gray-400 hover:text-gray-700"
                    title="取消引用"
                  >
                    ✕
                  </button>
                </div>
              )}

              {/* @ 成员选择器：输入 @ 后浮在输入框上方 */}
              {mentionQuery !== null && mentionOptions.length > 0 && (
                <div className="absolute bottom-full left-4 mb-2 w-56 overflow-hidden rounded-lg border border-gray-200 bg-white shadow-lg">
                  <div className="border-b border-gray-100 px-3 py-1.5 text-[10px] text-gray-400">
                    选择要 @ 的成员（↑↓ 切换，Enter 选中）
                  </div>
                  {mentionOptions.map((m, i) => (
                    <button
                      key={m.id}
                      onClick={() => pickMention(m)}
                      onMouseEnter={() => setMentionIndex(i)}
                      className={`flex w-full items-center gap-2 px-3 py-2 text-left text-xs transition ${
                        i === mentionIndex ? 'bg-brand-50' : 'hover:bg-gray-50'
                      }`}
                    >
                      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-brand-500 to-blue-500 text-[10px] text-white">
                        {m.name.slice(0, 1)}
                      </span>
                      <span className="min-w-0">
                        <span className="block truncate font-medium text-gray-800">{m.name}</span>
                        {m.description && (
                          <span className="block truncate text-[10px] text-gray-400">
                            {m.description}
                          </span>
                        )}
                      </span>
                    </button>
                  ))}
                </div>
              )}

              <div className="flex items-end gap-2">
                <textarea
                  value={input}
                  onChange={(e) => updateInput(e.target.value)}
                  onKeyDown={(e) => {
                    // @ 选择器打开时，方向键与 Enter 用于选择成员
                    if (mentionQuery !== null && mentionOptions.length > 0) {
                      if (e.key === 'ArrowDown') {
                        e.preventDefault()
                        setMentionIndex((i) => (i + 1) % mentionOptions.length)
                        return
                      }
                      if (e.key === 'ArrowUp') {
                        e.preventDefault()
                        setMentionIndex((i) => (i - 1 + mentionOptions.length) % mentionOptions.length)
                        return
                      }
                      if (e.key === 'Enter' || e.key === 'Tab') {
                        e.preventDefault()
                        pickMention(mentionOptions[mentionIndex] || mentionOptions[0])
                        return
                      }
                      if (e.key === 'Escape') {
                        e.preventDefault()
                        setMentionQuery(null)
                        return
                      }
                    }
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault()
                      void handleSend()
                    }
                  }}
                  rows={2}
                  placeholder="发一个任务，输入 @ 可指定成员；Enter 发送，Shift+Enter 换行"
                  className="flex-1 resize-none text-sm px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-brand-500"
                />
                <button
                  onClick={() => void handleSend()}
                  disabled={sending || !input.trim()}
                  className="h-10 px-4 rounded-lg bg-brand-600 text-white text-sm font-medium disabled:opacity-40 hover:bg-brand-700"
                >
                  {sending ? '处理中' : '发送'}
                </button>
              </div>
              {detail.route_mode === 'manual' && mentionQuery === null && (
                <p className="text-[11px] text-gray-400 mt-2">
                  当前是手动模式，输入 <span className="font-mono">@</span> 选择谁来接
                </p>
              )}
            </div>
          </>
        )}
      </section>

      {/* 群设置：成员管理 + 协作参数集中在这里 */}
      {showSettings && detail && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/30"
          onClick={() => setShowSettings(false)}
        >
          <div
            className="w-[520px] max-h-[80vh] overflow-y-auto rounded-xl bg-white shadow-xl border border-gray-200"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
              <div>
                <h3 className="text-sm font-semibold text-gray-900">群设置</h3>
                <p className="text-[11px] text-gray-400 mt-0.5">{detail.name}</p>
              </div>
              <button
                onClick={() => setShowSettings(false)}
                className="text-gray-400 hover:text-gray-600 text-lg leading-none"
              >
                ×
              </button>
            </div>

            <div className="px-5 py-4 space-y-5">
              {/* 成员 */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <p className="text-xs font-semibold text-gray-700">
                    群成员 · {detail.members.length}
                  </p>
                  <span className="text-[10px] text-gray-400">
                    自动招募的可移出并彻底删除
                  </span>
                </div>
                <div className="space-y-1">
                  {detail.members.map((m) => {
                    const auto = !!(m as any).auto_created
                    return (
                      <div
                        key={m.id}
                        className="flex items-center gap-2 rounded-md border border-gray-100 px-2.5 py-1.5"
                      >
                        <div className="w-6 h-6 rounded-md bg-brand-50 text-brand-700 flex items-center justify-center text-[11px] font-semibold">
                          {m.name.slice(0, 1)}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-xs text-gray-800 truncate">
                            {m.name}
                            {auto && (
                              <span className="ml-1.5 text-[9.5px] text-amber-600">
                                自动招募
                              </span>
                            )}
                          </p>
                          <p className="text-[10px] text-gray-400 truncate">
                            {(m.description || '未填写能力描述').slice(0, 46)}
                          </p>
                        </div>
                        <button
                          onClick={() => void handleRemoveMember(m)}
                          disabled={detail.members.length <= 1}
                          className="text-[10.5px] text-gray-400 hover:text-red-600 disabled:opacity-30"
                        >
                          移出
                        </button>
                      </div>
                    )
                  })}
                </div>
                {/* 拉已有 Agent 进群 */}
                {allAgents.filter(
                  (a) => !detail.members.some((m) => m.id === a.id)
                ).length > 0 && (
                  <div className="mt-2">
                    <p className="text-[10.5px] text-gray-400 mb-1">拉入已有 Agent</p>
                    <div className="flex flex-wrap gap-1">
                      {allAgents
                        .filter((a) => !detail.members.some((m) => m.id === a.id))
                        .map((a) => (
                          <button
                            key={a.id}
                            onClick={() => void handleAddMember(a.id)}
                            className="text-[10.5px] px-2 py-1 rounded-md border border-gray-200 text-gray-600 hover:border-brand-300 hover:text-brand-600"
                          >
                            + {a.name}
                          </button>
                        ))}
                    </div>
                  </div>
                )}
              </div>

              {/* 协作 */}
              <div className="border-t border-gray-100 pt-4 space-y-3">
                <p className="text-xs font-semibold text-gray-700">协作方式</p>
                <label className="flex items-center justify-between">
                  <span>
                    <span className="text-xs text-gray-700">协作接力</span>
                    <span className="block text-[10px] text-gray-400 mt-0.5">
                      关 = 一人接活；开 = 成员之间依次补充对方的结论
                    </span>
                  </span>
                  <button
                    onClick={() => void toggleCollaboration()}
                    className={`relative w-9 h-5 rounded-full transition ${
                      collaborationMode === 'chain' ? 'bg-brand-600' : 'bg-gray-300'
                    }`}
                  >
                    <span
                      className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all ${
                        collaborationMode === 'chain' ? 'left-4.5' : 'left-0.5'
                      }`}
                    />
                  </button>
                </label>
                {collaborationMode === 'chain' && (
                  <label className="flex items-center justify-between">
                    <span className="text-xs text-gray-600">最多几位成员接力</span>
                    <select
                      value={maxSpeakers}
                      onChange={(e) => void changeMaxSpeakers(Number(e.target.value))}
                      className="text-xs border border-gray-200 rounded-md px-2 py-1"
                    >
                      {[2, 3, 4, 5, 6, 7, 8].map((n) => (
                        <option key={n} value={n}>
                          {n} 人
                        </option>
                      ))}
                    </select>
                  </label>
                )}
                <label className="flex items-center justify-between">
                  <span>
                    <span className="text-xs text-gray-600">自动补人上限</span>
                    <span className="block text-[10px] text-gray-400 mt-0.5">
                      没人能做时最多现场创建几个成员
                    </span>
                  </span>
                  <select
                    value={recruitLimit}
                    onChange={(e) => void changeRecruitLimit(Number(e.target.value))}
                    className="text-xs border border-gray-200 rounded-md px-2 py-1"
                  >
                    {[1, 2, 3, 4, 5, 6, 8].map((n) => (
                      <option key={n} value={n}>
                        {n} 个
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              {/* 危险操作 */}
              <div className="border-t border-gray-100 pt-4">
                <button
                  onClick={() => {
                    setShowSettings(false)
                    void handleDeleteGroup(detail)
                  }}
                  className="text-[11px] text-red-500 hover:text-red-700"
                >
                  删除这个群聊（含全部聊天记录）
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
