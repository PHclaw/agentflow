/**
 * 多智能体群聊
 *
 * 交互重点：
 * 1. 用户发任务 → 系统判断谁接 → 界面明确显示「谁接了 + 为什么」
 * 2. 被选中的智能体回复时 @ 回发起人，并带引用关系
 * 3. 其他人保持沉默，不让群里变成一堆人在说话
 */
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'

import {
  agents as agentsApi,
  groups as groupsApi,
  type GroupDetail,
  type GroupMessageItem,
  type GroupSummary,
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

/** 把正文里的 @成员名 渲染成可辨识的高亮片段。
 *  长名字优先匹配，避免把 @文案编辑 里的 @文案 先切走。
 */
function renderMentions(text: string, names: string[]): ReactNode[] {
  const sorted = [...names].sort((a, b) => b.length - a.length)
  if (!sorted.length) return [text]
  const escaped = sorted.map((n) => n.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
  const re = new RegExp(`@(${escaped.join('|')})`, 'g')
  const out: ReactNode[] = []
  let last = 0
  let m: RegExpExecArray | null
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push(text.slice(last, m.index))
    out.push(
      <span
        key={`at-${m.index}`}
        className="rounded bg-blue-50 px-0.5 font-medium text-brand-700"
      >
        {m[0]}
      </span>
    )
    last = m.index + m[0].length
  }
  if (last < text.length) out.push(text.slice(last))
  return out
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
  const [highlightId, setHighlightId] = useState<number | null>(null)
  const messageRefs = useRef<Map<number, HTMLDivElement>>(new Map())

  // 新建群
  const [showCreate, setShowCreate] = useState(false)
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
          groupsApi.messages(activeId),
        ])
        if (cancelled) return
        setDetail(g)
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
  }, [activeId, scrollToBottom])

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
    (name: string) => {
      const at = input.lastIndexOf('@')
      if (at < 0 || mentionQuery === null) return
      const head = input.slice(0, at)
      const tail = input.slice(at + mentionQuery.length + 1)
      setInput(`${head}@${name} ${tail}`)
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

  const handleSend = async () => {
    const text = input.trim()
    if (!text || !activeId || sending) return

    setInput('')
    setMentionQuery(null)
    setMentionIndex(0)
    setSending(true)
    setRoutingHint(null)

    // 先把用户消息推到界面；临时 id 为负，等落库后用正式的 id
    const now = new Date().toISOString()
    const quoted = replyTo
    setReplyTo(null)
    setBubbles((prev) => [
      ...prev,
      {
        kind: 'message',
        data: {
          id: -Date.now(),
          sender_type: 'user',
          content: text,
          meta: quoted ? { reply_to: quoted.id } : {},
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
        undefined,
        ctrl.signal,
        quoted?.id && quoted.id > 0 ? quoted.id : undefined
      )) {
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

        if (evt.type === 'agent_start') {
          pendingAgent = { name: evt.agent || '智能体', text: '' }
          setBubbles((prev) => [
            ...prev,
            { kind: 'pending', agentName: pendingAgent!.name, text: '', replyToName: '你' },
          ])
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
          const finalText = pendingAgent?.text || ''
          const finalName = pendingAgent?.name || '智能体'
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
                  meta: { reply_to: evt.reply_to, mentions: ['你'] },
                  created_at: new Date().toISOString(),
                },
              },
            ]
          })
          pendingAgent = null
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
      setBubbles((prev) => prev.filter((b) => b.kind !== 'routing'))
      abortRef.current = null
      void loadList()
    }
  }

  const activeGroup = useMemo(
    () => list.find((g) => g.id === activeId) || null,
    [list, activeId]
  )

  return (
    <div className="flex h-[calc(100vh-4rem)] gap-4">
      {/* 左：群列表 */}
      <aside className="w-64 shrink-0 flex flex-col rounded-xl border border-gray-200 bg-white">
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
            <button
              key={g.id}
              onClick={() => setActiveId(g.id)}
              className={`w-full text-left px-4 py-3 border-b border-gray-50 transition ${
                g.id === activeId ? 'bg-brand-50' : 'hover:bg-gray-50'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-gray-900 truncate">{g.name}</span>
                <span className="text-[10px] text-gray-400">{g.member_count} 人</span>
              </div>
              <p className="text-[11px] text-gray-400 truncate mt-0.5">
                {g.last_message || '还没有消息'}
              </p>
            </button>
          ))}
        </div>
      </aside>

      {/* 右：聊天区 */}
      <section className="flex-1 flex flex-col rounded-xl border border-gray-200 bg-white overflow-hidden">
        {!detail ? (
          <div className="flex-1 flex items-center justify-center">
            <p className="text-sm text-gray-400">
              {list.length ? '选择左侧的群聊' : '先创建一个群聊'}
            </p>
          </div>
        ) : (
          <>
            {/* 头部 */}
            <header className="px-5 py-3 border-b border-gray-100 flex items-center justify-between">
              <div>
                <h2 className="text-sm font-semibold text-gray-900">{detail.name}</h2>
                <p className="text-[11px] text-gray-400 mt-0.5">
                  {ROUTE_MODE_LABEL[detail.route_mode] || detail.route_mode} ·{' '}
                  {detail.members.length} 位成员
                </p>
              </div>
              <div className="flex -space-x-1.5">
                {detail.members.slice(0, 5).map((m) => (
                  <div
                    key={m.id}
                    title={m.name}
                    className="w-7 h-7 rounded-full bg-gradient-to-br from-brand-500 to-blue-500 text-white text-[11px] flex items-center justify-center ring-2 ring-white"
                  >
                    {m.name.slice(0, 1)}
                  </div>
                ))}
              </div>
            </header>

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
                          {m.meta?.reply_to && (
                            <span className="text-[10px] text-gray-400">引用回复</span>
                          )}
                        </div>
                        {quoteBlock}
                        <div className="rounded-xl rounded-tl-sm bg-gray-50 border border-gray-100 px-3.5 py-2.5 text-sm text-gray-800 whitespace-pre-wrap">
                          {renderMentions(m.content, memberNames)}
                        </div>
                        <button
                          onClick={() => setReplyTo(m)}
                          className="mt-1 text-[10.5px] text-gray-400 opacity-0 transition group-hover:opacity-100 hover:text-brand-600"
                        >
                          ↩ 回复这条
                        </button>
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
                      <div className="rounded-xl rounded-tr-sm bg-brand-600 px-3.5 py-2.5 text-sm text-white whitespace-pre-wrap">
                        {renderMentions(m.content, memberNames)}
                      </div>
                      <button
                        onClick={() => setReplyTo(m)}
                        className="mt-1 block ml-auto text-[10.5px] text-gray-400 opacity-0 transition group-hover:opacity-100 hover:text-brand-600"
                      >
                        ↩ 回复这条
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>

            {/* 输入区 */}
            <div className="relative border-t border-gray-100 px-4 py-3">
              {routingHint && (
                <p className="text-[11px] text-amber-600 mb-2">{routingHint}</p>
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
                      onClick={() => pickMention(m.name)}
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
                        pickMention(mentionOptions[mentionIndex]?.name || mentionOptions[0].name)
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
    </div>
  )
}
