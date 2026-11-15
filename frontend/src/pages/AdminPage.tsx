import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Activity,
  Bot,
  ChevronLeft,
  ChevronRight,
  Database,
  FileText,
  MessagesSquare,
  Puzzle,
  RefreshCw,
  Search,
  Shield,
  TrendingUp,
  Users,
} from 'lucide-react'
import { admin as adminApi, billing } from '../services/api'
import type { AdminSessionRow, AdminUserRow } from '../services/api'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Input } from '../components/ui/Input'
import { Modal } from '../components/ui/Modal'
import { useToastStore } from '../stores'
import { formatDate, formatDateTime, formatRelative } from '../utils/datetime'

const PAGE_SIZE = 20
const SESSION_PAGE_SIZE = 15
const TREND_DAYS = 14

interface PlanInfo {
  id: string
  name: string
  price: number
  agents?: number
  messages?: number
  features?: string[]
}

const PLAN_LABELS: Record<string, string> = {
  free: '免费版',
  pro: '进阶版',
  team: '团队版',
}

const planLabel = (code: string) => PLAN_LABELS[code] || code

//: 排序选项。value 是「字段:方向」，与后端参数一一对应。
const SORT_OPTIONS = [
  { value: 'created_at:desc', label: '注册时间（新→旧）' },
  { value: 'created_at:asc', label: '注册时间（旧→新）' },
  { value: 'last_login_at:desc', label: '最后登录（近→远）' },
  { value: 'last_login_at:asc', label: '最后登录（远→近）' },
  { value: 'message_count:desc', label: '消息数（多→少）' },
  { value: 'agent_count:desc', label: 'Agent 数（多→少）' },
  { value: 'session_count:desc', label: '会话数（多→少）' },
  { value: 'email:asc', label: '邮箱（A→Z）' },
]

const ACTIVITY_OPTIONS = [
  { value: '', label: '全部活跃度' },
  { value: 'active_7d', label: '7 天内有登录' },
  { value: 'active_30d', label: '30 天内有登录' },
  { value: 'dormant', label: '沉睡（30 天未登录）' },
  { value: 'never', label: '从未登录' },
]

function formatBytes(bytes: number): string {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let value = bytes
  let i = 0
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024
    i += 1
  }
  return `${value.toFixed(value >= 10 || i === 0 ? 0 : 1)} ${units[i]}`
}

const selectClass =
  'px-3 py-2.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm text-slate-700 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-brand-500'

function StatCard({
  icon,
  label,
  value,
  sub,
}: {
  icon: React.ReactNode
  label: string
  value: number | string
  sub?: string
}) {
  return (
    <Card className="p-5">
      <div className="flex items-start justify-between">
        <div className="min-w-0">
          <p className="text-xs font-medium text-slate-500 dark:text-slate-400">{label}</p>
          <p className="text-2xl font-bold text-slate-900 dark:text-white mt-1.5">{value}</p>
          {sub && (
            <p className="text-xs text-slate-400 dark:text-slate-500 mt-1 truncate">{sub}</p>
          )}
        </div>
        <div className="w-9 h-9 rounded-xl bg-brand-50 dark:bg-brand-900/30 flex items-center justify-center text-brand-600 dark:text-brand-400 flex-shrink-0">
          {icon}
        </div>
      </div>
    </Card>
  )
}

/**
 * 每日趋势柱状图。
 *
 * 手写 div 而不是引图表库：只有三组数据、形态固定，
 * 为它加一个几十 KB 的依赖不划算。
 */
function TrendChart({
  series,
}: {
  series: { date: string; new_users: number; new_sessions: number; active_users: number }[]
}) {
  const max = Math.max(
    1,
    ...series.flatMap((p) => [p.new_users, p.new_sessions, p.active_users])
  )

  return (
    <div>
      <div className="flex items-end gap-1.5 h-36">
        {series.map((p) => (
          <div key={p.date} className="flex-1 flex items-end gap-0.5 group relative">
            {[
              { v: p.new_users, cls: 'bg-brand-500', name: '新增用户' },
              { v: p.new_sessions, cls: 'bg-amber-400', name: '新建会话' },
              { v: p.active_users, cls: 'bg-slate-300 dark:bg-slate-600', name: '活跃用户' },
            ].map((bar) => (
              <div
                key={bar.name}
                className={`flex-1 rounded-t ${bar.cls} transition-all hover:opacity-80`}
                style={{ height: `${(bar.v / max) * 100}%`, minHeight: bar.v > 0 ? 2 : 0 }}
              />
            ))}
            {/* 悬停明细。用原生 title 而不是自绘 tooltip，省一套定位逻辑 */}
            <div className="absolute -top-1 left-1/2 -translate-x-1/2 -translate-y-full hidden group-hover:block z-10 pointer-events-none">
              <div className="whitespace-nowrap rounded-lg bg-slate-900 px-2.5 py-1.5 text-[11px] text-white shadow-lg">
                {p.date}
                <br />
                新增用户 {p.new_users} · 新建会话 {p.new_sessions} · 活跃 {p.active_users}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* 横轴：太密就只标首尾和中点 */}
      <div className="flex gap-1.5 mt-2">
        {series.map((p, i) => (
          <div
            key={p.date}
            className="flex-1 text-center text-[10px] text-slate-400 truncate"
          >
            {i % 3 === 0 || i === series.length - 1 ? p.date.slice(5) : ''}
          </div>
        ))}
      </div>
    </div>
  )
}

export default function AdminPage() {
  const { addToast } = useToastStore()
  const navigate = useNavigate()

  // ---- 概览 ----
  const [overview, setOverview] = useState<any>(null)
  const [trends, setTrends] = useState<any>(null)
  const [topAgents, setTopAgents] = useState<any[]>([])
  const [plans, setPlans] = useState<PlanInfo[]>([])

  // ---- 列表 ----
  const [rows, setRows] = useState<AdminUserRow[]>([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [searchInput, setSearchInput] = useState('')
  const [search, setSearch] = useState('')
  const [planFilter, setPlanFilter] = useState('')
  const [roleFilter, setRoleFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [activityFilter, setActivityFilter] = useState('')
  const [sortValue, setSortValue] = useState('created_at:desc')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  // ---- 详情 ----
  const [detail, setDetail] = useState<any>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailTab, setDetailTab] = useState<'overview' | 'agents' | 'kb' | 'sessions'>('overview')
  const [sessions, setSessions] = useState<AdminSessionRow[]>([])
  const [sessionsTotal, setSessionsTotal] = useState(0)
  const [sessionsOffset, setSessionsOffset] = useState(0)
  const [sessionsLoading, setSessionsLoading] = useState(false)

  // ---- 会话内容 ----
  const [sessionDetail, setSessionDetail] = useState<any>(null)

  // ---- 改套餐 / 启停 ----
  const [draftPlan, setDraftPlan] = useState('')
  const [resetUsage, setResetUsage] = useState(false)
  const [saving, setSaving] = useState(false)
  const [togglingStatus, setTogglingStatus] = useState(false)

  const planLimits = useMemo(() => {
    const map: Record<string, PlanInfo> = {}
    for (const p of plans) map[p.id] = p
    return map
  }, [plans])

  const [sort, order] = sortValue.split(':')

  // 输入停顿 350ms 再发请求，否则每敲一个字符都会打一次后端
  useEffect(() => {
    const timer = setTimeout(() => {
      setSearch(searchInput)
      setOffset(0)
    }, 350)
    return () => clearTimeout(timer)
  }, [searchInput])

  const loadOverview = useCallback(async () => {
    try {
      const [ov, planRes, trendRes, agentRes] = await Promise.all([
        adminApi.overview(),
        billing.listPlans(),
        adminApi.trends(TREND_DAYS),
        adminApi.topAgents(8),
      ])
      setOverview(ov)
      setPlans(planRes?.plans || [])
      setTrends(trendRes)
      setTopAgents(agentRes?.items || [])
    } catch (e: any) {
      setError(e?.message || '加载概览失败')
    }
  }, [])

  const loadUsers = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const res = await adminApi.users({
        search,
        plan: planFilter,
        role: roleFilter,
        status: statusFilter,
        activity: activityFilter,
        sort,
        order,
        limit: PAGE_SIZE,
        offset,
      })
      setRows(res?.items || [])
      setTotal(res?.total || 0)
    } catch (e: any) {
      setError(e?.message || '加载用户列表失败')
    } finally {
      setLoading(false)
    }
  }, [search, planFilter, roleFilter, statusFilter, activityFilter, sort, order, offset])

  useEffect(() => {
    loadOverview()
  }, [loadOverview])

  useEffect(() => {
    loadUsers()
  }, [loadUsers])

  const loadSessions = useCallback(async (userId: string, nextOffset: number) => {
    setSessionsLoading(true)
    try {
      const res = await adminApi.userSessions(userId, SESSION_PAGE_SIZE, nextOffset)
      setSessions(res?.items || [])
      setSessionsTotal(res?.total || 0)
      setSessionsOffset(nextOffset)
    } catch (e: any) {
      addToast({ type: 'error', message: e?.message || '加载会话失败' })
    } finally {
      setSessionsLoading(false)
    }
  }, [addToast])

  const openDetail = useCallback(async (userId: string) => {
    setDetailLoading(true)
    setDetail(null)
    setSessions([])
    setSessionsTotal(0)
    setSessionsOffset(0)
    setDetailTab('overview')
    try {
      const d = await adminApi.userDetail(userId)
      setDetail(d)
      setDraftPlan(d?.subscription?.plan || 'free')
      setResetUsage(false)
    } catch (e: any) {
      addToast({ type: 'error', message: e?.message || '加载用户详情失败' })
    } finally {
      setDetailLoading(false)
    }
  }, [addToast])

  const openSession = async (sessionId: string) => {
    setSessionDetail({ loading: true })
    try {
      const d = await adminApi.sessionDetail(sessionId)
      setSessionDetail(d)
    } catch (e: any) {
      setSessionDetail(null)
      addToast({ type: 'error', message: e?.message || '加载会话内容失败' })
    }
  }

  const savePlan = async () => {
    if (!detail?.user?.id) return
    setSaving(true)
    try {
      const res = await adminApi.setSubscription(detail.user.id, {
        plan: draftPlan,
        reset_usage: resetUsage,
      })
      addToast({
        type: 'success',
        message: `${detail.user.email} 的套餐已改为 ${planLabel(res.plan)}`,
      })
      await Promise.all([loadUsers(), loadOverview()])
      await openDetail(detail.user.id)
    } catch (e: any) {
      addToast({ type: 'error', message: e?.message || '保存失败' })
    } finally {
      setSaving(false)
    }
  }

  const toggleStatus = async () => {
    if (!detail?.user?.id) return
    const next = !detail.user.is_active
    setTogglingStatus(true)
    try {
      await adminApi.setUserStatus(detail.user.id, next)
      addToast({
        type: 'success',
        message: next ? '账号已启用' : '账号已停用，其旧登录凭据会立即失效',
      })
      await Promise.all([loadUsers(), loadOverview()])
      await openDetail(detail.user.id)
    } catch (e: any) {
      addToast({ type: 'error', message: e?.message || '操作失败' })
    } finally {
      setTogglingStatus(false)
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1
  const sessionPages = Math.max(1, Math.ceil(sessionsTotal / SESSION_PAGE_SIZE))
  const sessionPage = Math.floor(sessionsOffset / SESSION_PAGE_SIZE) + 1

  const resetFilters = () => {
    setSearchInput('')
    setPlanFilter('')
    setRoleFilter('')
    setStatusFilter('')
    setActivityFilter('')
    setSortValue('created_at:desc')
    setOffset(0)
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">管理后台</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            查看用户行为，调整订阅版本与账号状态
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            leftIcon={<Puzzle className="w-4 h-4" />}
            onClick={() => navigate('/admin/skills')}
          >
            技能管理
          </Button>
          <Button
            variant="outline"
            size="sm"
            leftIcon={<RefreshCw className="w-4 h-4" />}
            onClick={() => {
              loadOverview()
              loadUsers()
            }}
          >
            刷新
          </Button>
        </div>
      </div>

      {/* ==================== 概览 ==================== */}
      {overview && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
            <StatCard
              icon={<Users className="w-4 h-4" />}
              label="用户总数"
              value={overview.users.total}
              sub={`今日 +${overview.users.new_1d} · 7日 +${overview.users.new_7d} · 30日 +${overview.users.new_30d}`}
            />
            <StatCard
              icon={<Activity className="w-4 h-4" />}
              label="活跃用户"
              value={overview.users.active_7d}
              sub={`7日活跃 · 30日 ${overview.users.active_30d} · 从未登录 ${overview.users.never_logged_in}`}
            />
            <StatCard
              icon={<TrendingUp className="w-4 h-4" />}
              label="付费转化"
              value={`${overview.users.conversion}%`}
              sub={`付费 ${overview.users.paid} / 总 ${overview.users.total}`}
            />
            <StatCard
              icon={<MessagesSquare className="w-4 h-4" />}
              label="Agent / 会话"
              value={`${overview.content.agents} / ${overview.content.sessions}`}
              sub={`累计消息 ${overview.content.messages}`}
            />
          </div>

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            <StatCard
              icon={<Database className="w-4 h-4" />}
              label="知识库"
              value={overview.content.knowledge_bases}
              sub={`文档 ${overview.content.documents} 份`}
            />
            <StatCard
              icon={<FileText className="w-4 h-4" />}
              label="文档占用"
              value={formatBytes(overview.content.document_bytes)}
              sub="上传到知识库的原始文件总量"
            />
            <StatCard
              icon={<Shield className="w-4 h-4" />}
              label="管理员"
              value={overview.users.admins}
              sub={`停用账号 ${overview.users.disabled}`}
            />
            <StatCard
              icon={<Bot className="w-4 h-4" />}
              label="套餐分布"
              value={overview.plans.map((p: any) => p.count).join(' / ')}
              sub={overview.plans.map((p: any) => planLabel(p.plan)).join(' · ')}
            />
          </div>

          <div className="grid lg:grid-cols-3 gap-4 mb-6">
            {/* 趋势图 */}
            <Card className="p-5 lg:col-span-2">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-sm font-semibold text-slate-900 dark:text-white">
                  近 {TREND_DAYS} 天趋势
                </h2>
                <div className="flex items-center gap-3 text-[11px] text-slate-500 dark:text-slate-400">
                  <span className="flex items-center gap-1">
                    <span className="w-2.5 h-2.5 rounded-sm bg-brand-500 inline-block" />
                    新增用户 {trends?.totals?.new_users ?? 0}
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-2.5 h-2.5 rounded-sm bg-amber-400 inline-block" />
                    新建会话 {trends?.totals?.new_sessions ?? 0}
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-2.5 h-2.5 rounded-sm bg-slate-300 inline-block" />
                    活跃用户合计 {trends?.totals?.active_users ?? 0}
                  </span>
                </div>
              </div>
              {trends?.series?.length ? (
                <TrendChart series={trends.series} />
              ) : (
                <p className="text-sm text-slate-400 py-10 text-center">暂无数据</p>
              )}
              <p className="mt-3 text-[11px] text-slate-400 dark:text-slate-500">
                按 UTC 日期切分。消息量无法按天统计 —— 库里只存了累计值，没有消息流水。
              </p>
            </Card>

            {/* Agent 排行 */}
            <Card className="p-5">
              <h2 className="text-sm font-semibold text-slate-900 dark:text-white mb-4">
                最活跃 Agent
              </h2>
              <div className="space-y-3">
                {topAgents.length === 0 && (
                  <p className="text-sm text-slate-400">还没有 Agent</p>
                )}
                {topAgents.map((a, i) => (
                  <div key={a.id} className="flex items-start gap-3">
                    <span className="w-5 text-xs font-semibold text-slate-400 flex-shrink-0 pt-0.5">
                      {i + 1}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm text-slate-800 dark:text-slate-200 truncate">
                        {a.name}
                        {a.has_workflow && (
                          <span className="ml-1.5 px-1.5 py-0.5 rounded text-[10px] bg-brand-50 dark:bg-brand-900/30 text-brand-600 dark:text-brand-400">
                            工作流
                          </span>
                        )}
                      </p>
                      <p className="text-[11px] text-slate-400 truncate">
                        {a.owner_email || '（未知用户）'}
                      </p>
                    </div>
                    <div className="text-right flex-shrink-0">
                      <p className="text-xs font-medium text-slate-700 dark:text-slate-300">
                        {a.message_count} 条
                      </p>
                      <p className="text-[11px] text-slate-400">{a.session_count} 会话</p>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          </div>
        </>
      )}

      {/* ==================== 筛选 ==================== */}
      <Card className="p-4 mb-4">
        <div className="flex flex-wrap items-center gap-3">
          <div className="w-64">
            <Input
              placeholder="搜索邮箱或昵称"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              leftIcon={<Search className="w-4 h-4" />}
            />
          </div>

          <select
            value={planFilter}
            onChange={(e) => { setPlanFilter(e.target.value); setOffset(0) }}
            className={selectClass}
          >
            <option value="">全部套餐</option>
            {Object.keys(PLAN_LABELS).map((code) => (
              <option key={code} value={code}>{planLabel(code)}</option>
            ))}
          </select>

          <select
            value={roleFilter}
            onChange={(e) => { setRoleFilter(e.target.value); setOffset(0) }}
            className={selectClass}
          >
            <option value="">全部角色</option>
            <option value="user">普通用户</option>
            <option value="admin">管理员</option>
          </select>

          <select
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setOffset(0) }}
            className={selectClass}
          >
            <option value="">全部状态</option>
            <option value="active">启用中</option>
            <option value="disabled">已停用</option>
          </select>

          <select
            value={activityFilter}
            onChange={(e) => { setActivityFilter(e.target.value); setOffset(0) }}
            className={selectClass}
          >
            {ACTIVITY_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>

          <select
            value={sortValue}
            onChange={(e) => { setSortValue(e.target.value); setOffset(0) }}
            className={selectClass}
          >
            {SORT_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>

          <Button variant="ghost" size="sm" onClick={resetFilters}>
            重置
          </Button>

          <span className="text-sm text-slate-400 dark:text-slate-500 ml-auto">
            共 {total} 个用户
          </span>
        </div>
      </Card>

      {error && <p className="text-sm text-red-600 dark:text-red-400 mb-4">{error}</p>}

      {/* ==================== 用户列表 ==================== */}
      <Card padding="none" className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50">
                {['用户', '角色', '套餐', 'Agent', '会话', '消息', '注册', '最后活跃', ''].map((h) => (
                  <th
                    key={h}
                    className="px-4 py-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400 whitespace-nowrap"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((u) => {
                const limit = planLimits[u.plan]?.agents
                // 存量超额：Agent 数超过当前套餐上限。只提示、不阻止，
                // 因为限制的是新建而不是已有
                const overQuota = typeof limit === 'number' && u.agent_count > limit
                return (
                  <tr
                    key={u.id}
                    className="border-b border-slate-100 dark:border-slate-800 last:border-0 hover:bg-slate-50 dark:hover:bg-slate-800/40 cursor-pointer"
                    onClick={() => openDetail(u.id)}
                  >
                    <td className="px-4 py-3">
                      <span className="font-medium text-slate-900 dark:text-white">
                        {u.email || '（无邮箱）'}
                      </span>
                      {u.nickname && (
                        <p className="text-xs text-slate-400 dark:text-slate-500 mt-0.5">
                          {u.nickname}
                        </p>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {u.role === 'admin' ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-brand-100 dark:bg-brand-900/40 text-brand-700 dark:text-brand-300 text-[11px] font-medium">
                          <Shield className="w-3 h-3" />
                          管理员
                        </span>
                      ) : (
                        <span className="text-xs text-slate-400">普通</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-medium ${
                          u.plan === 'free'
                            ? 'bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300'
                            : 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300'
                        }`}
                      >
                        {planLabel(u.plan)}
                      </span>
                      {u.plan_status !== 'active' && (
                        <span className="ml-1.5 text-[11px] text-red-500">{u.plan_status}</span>
                      )}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <span
                        className={
                          overQuota
                            ? 'text-amber-600 dark:text-amber-400 font-medium'
                            : 'text-slate-600 dark:text-slate-300'
                        }
                      >
                        {u.agent_count}
                        {typeof limit === 'number' && (
                          <span className="text-slate-400 dark:text-slate-500"> / {limit}</span>
                        )}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-600 dark:text-slate-300">
                      {u.session_count}
                    </td>
                    <td className="px-4 py-3 text-slate-600 dark:text-slate-300">
                      {u.message_count}
                    </td>
                    <td className="px-4 py-3 text-slate-500 dark:text-slate-400 whitespace-nowrap">
                      {formatDate(u.created_at)}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <span className={u.is_active ? 'text-slate-500 dark:text-slate-400' : 'text-red-500'}>
                        {u.is_active ? formatRelative(u.last_active_at) : '已停用'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span className="text-xs text-brand-600 dark:text-brand-400 font-medium">
                        查看 / 管理
                      </span>
                    </td>
                  </tr>
                )
              })}
              {!loading && rows.length === 0 && (
                <tr>
                  <td colSpan={9} className="px-4 py-12 text-center text-slate-400">
                    没有匹配的用户
                  </td>
                </tr>
              )}
              {loading && rows.length === 0 && (
                <tr>
                  <td colSpan={9} className="px-4 py-12 text-center text-slate-400">
                    正在加载…
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {total > PAGE_SIZE && (
        <div className="flex items-center justify-between mt-4">
          <span className="text-sm text-slate-500 dark:text-slate-400">
            第 {currentPage} / {totalPages} 页
          </span>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={offset === 0}
              leftIcon={<ChevronLeft className="w-4 h-4" />}
              onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
            >
              上一页
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={offset + PAGE_SIZE >= total}
              rightIcon={<ChevronRight className="w-4 h-4" />}
              onClick={() => setOffset(offset + PAGE_SIZE)}
            >
              下一页
            </Button>
          </div>
        </div>
      )}

      {/* ==================== 用户详情 ==================== */}
      <Modal
        isOpen={!!detail || detailLoading}
        onClose={() => setDetail(null)}
        title={detail?.user?.email || '用户详情'}
        description={detail?.user?.nickname || undefined}
        size="full"
      >
        {detailLoading && !detail && <p className="text-sm text-slate-500">正在加载…</p>}

        {detail && (
          <div className="space-y-5">
            {/* 顶部：状态 + 快捷操作 */}
            <div className="flex flex-wrap items-center gap-2">
              {detail.user.role === 'admin' && (
                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-brand-100 dark:bg-brand-900/40 text-brand-700 dark:text-brand-300 text-xs font-medium">
                  <Shield className="w-3.5 h-3.5" />
                  管理员
                </span>
              )}
              <span
                className={`px-2.5 py-1 rounded-full text-xs font-medium ${
                  detail.user.is_active
                    ? 'bg-emerald-50 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300'
                    : 'bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-300'
                }`}
              >
                {detail.user.is_active ? '启用中' : '已停用'}
              </span>
              {detail.user.is_verified && (
                <span className="px-2.5 py-1 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 text-xs">
                  邮箱已验证
                </span>
              )}
              <Button
                variant={detail.user.is_active ? 'danger' : 'success'}
                size="xs"
                className="ml-auto"
                loading={togglingStatus}
                onClick={toggleStatus}
              >
                {detail.user.is_active ? '停用账号' : '启用账号'}
              </Button>
            </div>

            {/* 数字概览 */}
            <div className="grid grid-cols-3 md:grid-cols-6 gap-3">
              {[
                { label: 'Agent', value: detail.stats.agents },
                { label: '会话', value: detail.stats.sessions },
                { label: '消息', value: detail.stats.messages },
                { label: '知识库', value: detail.stats.knowledge_bases },
                { label: '文档', value: detail.stats.documents },
                { label: '文档占用', value: formatBytes(detail.stats.document_bytes) },
              ].map((s) => (
                <div key={s.label} className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50">
                  <p className="text-[11px] text-slate-500 dark:text-slate-400">{s.label}</p>
                  <p className="text-lg font-semibold text-slate-900 dark:text-white mt-0.5">
                    {s.value}
                  </p>
                </div>
              ))}
            </div>

            {/* 时间与订阅 */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <p className="text-xs text-slate-500 dark:text-slate-400">注册时间</p>
                <p className="text-slate-700 dark:text-slate-200 mt-1">
                  {formatDateTime(detail.user.created_at)}
                </p>
              </div>
              <div>
                <p className="text-xs text-slate-500 dark:text-slate-400">最后登录</p>
                <p className="text-slate-700 dark:text-slate-200 mt-1">
                  {formatRelative(detail.user.last_login_at)}
                </p>
              </div>
              <div>
                <p className="text-xs text-slate-500 dark:text-slate-400">最后活跃</p>
                <p className="text-slate-700 dark:text-slate-200 mt-1">
                  {formatDateTime(detail.user.last_active_at)}
                </p>
              </div>
              <div>
                <p className="text-xs text-slate-500 dark:text-slate-400">用量</p>
                <p className="text-slate-700 dark:text-slate-200 mt-1">
                  Agent {detail.subscription.agents_used}
                  {planLimits[detail.subscription.plan]?.agents != null &&
                    ` / ${planLimits[detail.subscription.plan].agents}`}
                  {' · '}消息 {detail.subscription.messages_used}
                  {planLimits[detail.subscription.plan]?.messages != null &&
                    ` / ${planLimits[detail.subscription.plan].messages}`}
                </p>
              </div>
            </div>

            {/* 改套餐 */}
            <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-700">
              <h3 className="text-sm font-semibold text-slate-900 dark:text-white mb-3">
                设定订阅版本
              </h3>
              <div className="flex flex-wrap items-end gap-3">
                <div>
                  <label className="block text-xs text-slate-500 dark:text-slate-400 mb-1.5">
                    套餐
                  </label>
                  <select
                    value={draftPlan}
                    onChange={(e) => setDraftPlan(e.target.value)}
                    className={selectClass}
                  >
                    {plans.map((p) => (
                      <option key={p.id} value={p.id}>
                        {planLabel(p.id)}
                        {p.agents != null ? `（${p.agents} Agent / ${p.messages} 消息）` : ''}
                      </option>
                    ))}
                  </select>
                </div>
                <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300 pb-2.5 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={resetUsage}
                    onChange={(e) => setResetUsage(e.target.checked)}
                    className="rounded border-slate-300 text-brand-600 focus:ring-brand-500"
                  />
                  同时重置本月消息用量
                </label>
                <Button
                  className="ml-auto"
                  loading={saving}
                  disabled={draftPlan === detail.subscription.plan && !resetUsage}
                  onClick={savePlan}
                >
                  保存
                </Button>
              </div>
              <p className="mt-3 text-xs text-slate-400 dark:text-slate-500">
                当前套餐：{planLabel(detail.subscription.plan)}
                {detail.subscription.current_period_end
                  ? ` · 本周期至 ${formatDate(detail.subscription.current_period_end)}`
                  : ''}
                。改套餐只调整额度，不会清除已用量；需要归零请勾选上面的选项。
              </p>
            </div>

            {/* 分区：Agent / 知识库 / 会话 */}
            <div>
              <div className="flex gap-1 border-b border-slate-200 dark:border-slate-700 mb-3">
                {([
                  ['agents', `Agent（${detail.agents.length}）`],
                  ['kb', `知识库（${detail.knowledge_bases.length}）`],
                  ['sessions', `会话（${detail.stats.sessions}）`],
                ] as const).map(([key, label]) => (
                  <button
                    key={key}
                    onClick={() => {
                      setDetailTab(key)
                      if (key === 'sessions' && sessions.length === 0 && detail.stats.sessions > 0) {
                        loadSessions(detail.user.id, 0)
                      }
                    }}
                    className={`px-4 py-2 text-sm font-medium -mb-px border-b-2 transition-colors ${
                      detailTab === key
                        ? 'border-brand-500 text-brand-600 dark:text-brand-400'
                        : 'border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>

              {detailTab === 'agents' && (
                <div className="max-h-64 overflow-y-auto rounded-xl border border-slate-200 dark:border-slate-700">
                  {detail.agents.length === 0 ? (
                    <p className="p-4 text-sm text-slate-400">还没有创建 Agent</p>
                  ) : (
                    detail.agents.map((a: any) => (
                      <div
                        key={a.id}
                        className="flex items-center justify-between gap-3 px-4 py-2.5 border-b border-slate-100 dark:border-slate-800 last:border-0 text-sm"
                      >
                        <div className="min-w-0">
                          <span className="text-slate-700 dark:text-slate-200">{a.name}</span>
                          {a.has_workflow && (
                            <span className="ml-2 px-1.5 py-0.5 rounded text-[10px] bg-brand-50 dark:bg-brand-900/30 text-brand-600 dark:text-brand-400">
                              工作流
                            </span>
                          )}
                          {!a.is_active && (
                            <span className="ml-2 text-[10px] text-slate-400">已停用</span>
                          )}
                          {a.model && (
                            <p className="text-[11px] text-slate-400 mt-0.5">{a.model}</p>
                          )}
                        </div>
                        <span className="text-xs text-slate-400 whitespace-nowrap">
                          {a.message_count} 条 · {formatDate(a.created_at)}
                        </span>
                      </div>
                    ))
                  )}
                </div>
              )}

              {detailTab === 'kb' && (
                <div className="max-h-64 overflow-y-auto rounded-xl border border-slate-200 dark:border-slate-700">
                  {detail.knowledge_bases.length === 0 ? (
                    <p className="p-4 text-sm text-slate-400">还没有知识库</p>
                  ) : (
                    detail.knowledge_bases.map((k: any) => (
                      <div
                        key={k.id}
                        className="flex items-center justify-between gap-3 px-4 py-2.5 border-b border-slate-100 dark:border-slate-800 last:border-0 text-sm"
                      >
                        <span className="text-slate-700 dark:text-slate-200">{k.name}</span>
                        <span className="text-xs text-slate-400 whitespace-nowrap">
                          {k.document_count} 份文档 · {formatBytes(k.bytes)}
                        </span>
                      </div>
                    ))
                  )}
                </div>
              )}

              {detailTab === 'sessions' && (
                <div>
                  <div className="max-h-64 overflow-y-auto rounded-xl border border-slate-200 dark:border-slate-700">
                    {sessionsLoading && sessions.length === 0 ? (
                      <p className="p-4 text-sm text-slate-400">正在加载…</p>
                    ) : sessions.length === 0 ? (
                      <p className="p-4 text-sm text-slate-400">还没有对话记录</p>
                    ) : (
                      sessions.map((s) => (
                        <button
                          key={s.id}
                          onClick={() => openSession(s.id)}
                          className="w-full text-left px-4 py-2.5 border-b border-slate-100 dark:border-slate-800 last:border-0 hover:bg-slate-50 dark:hover:bg-slate-800/40"
                        >
                          <div className="flex items-center justify-between gap-3">
                            <span className="text-sm text-slate-700 dark:text-slate-200 truncate">
                              {s.title}
                            </span>
                            <span className="text-xs text-slate-400 whitespace-nowrap">
                              {s.message_count} 条 · {formatRelative(s.updated_at)}
                            </span>
                          </div>
                          <p className="text-[11px] text-slate-400 dark:text-slate-500 mt-0.5">
                            {s.agent_name}
                          </p>
                        </button>
                      ))
                    )}
                  </div>

                  {sessionsTotal > SESSION_PAGE_SIZE && (
                    <div className="flex items-center justify-between mt-2">
                      <span className="text-xs text-slate-500 dark:text-slate-400">
                        第 {sessionPage} / {sessionPages} 页 · 共 {sessionsTotal} 段
                      </span>
                      <div className="flex gap-2">
                        <Button
                          variant="outline"
                          size="xs"
                          disabled={sessionsOffset === 0}
                          onClick={() => loadSessions(detail.user.id, Math.max(0, sessionsOffset - SESSION_PAGE_SIZE))}
                        >
                          上一页
                        </Button>
                        <Button
                          variant="outline"
                          size="xs"
                          disabled={sessionsOffset + SESSION_PAGE_SIZE >= sessionsTotal}
                          onClick={() => loadSessions(detail.user.id, sessionsOffset + SESSION_PAGE_SIZE)}
                        >
                          下一页
                        </Button>
                      </div>
                    </div>
                  )}
                  <p className="mt-2 text-[11px] text-slate-400 dark:text-slate-500">
                    点任意一条查看完整对话内容。管理权限等同于可读全部用户对话，请谨慎授予。
                  </p>
                </div>
              )}
            </div>
          </div>
        )}
      </Modal>

      {/* ==================== 会话内容 ==================== */}
      <Modal
        isOpen={!!sessionDetail}
        onClose={() => setSessionDetail(null)}
        title={sessionDetail?.title || '会话内容'}
        description={
          sessionDetail && !sessionDetail.loading
            ? `${sessionDetail.agent_name} · ${sessionDetail.user_email || ''} · ${sessionDetail.message_count} 条消息`
            : undefined
        }
        size="full"
      >
        {sessionDetail?.loading && <p className="text-sm text-slate-500">正在加载…</p>}

        {sessionDetail && !sessionDetail.loading && (
          <div className="space-y-3 max-h-[60vh] overflow-y-auto pr-1">
            {(sessionDetail.messages || []).map((m: any, i: number) => (
              <div
                key={i}
                className={`p-3 rounded-xl text-sm ${
                  m.role === 'user'
                    ? 'bg-slate-50 dark:bg-slate-800/60'
                    : 'bg-brand-50/60 dark:bg-brand-900/20'
                }`}
              >
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400">
                    {m.role === 'user' ? '用户' : '助手'}
                  </span>
                  {m.created_at && (
                    <span className="text-[11px] text-slate-400">
                      {formatDateTime(m.created_at)}
                    </span>
                  )}
                </div>
                <pre className="whitespace-pre-wrap break-words font-sans text-slate-700 dark:text-slate-200">
                  {m.content || '（空）'}
                </pre>
                {m.files?.length > 0 && (
                  <p className="mt-2 text-[11px] text-slate-400">
                    产物 {m.files.length} 个：{m.files.map((f: any) => f.name).filter(Boolean).join('、')}
                  </p>
                )}
              </div>
            ))}
            {(sessionDetail.messages || []).length === 0 && (
              <p className="text-sm text-slate-400">这段会话还没有消息</p>
            )}
          </div>
        )}
      </Modal>
    </div>
  )
}
