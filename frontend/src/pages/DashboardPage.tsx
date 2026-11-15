import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import {
  MessageSquare,
  Users,
  BookOpen,
  Zap,
  Clock,
  ArrowUpRight,
  ArrowDownRight,
  ChevronRight,
  Activity,
  Bot,
  Plus,
} from 'lucide-react'
import { api } from '../services/api'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { GrowthPanel } from '../components/dashboard/GrowthPanel'

interface DashboardStats {
  totalAgents: number
  activeConversations: number
  totalKnowledgeBases: number
  apiCallsThisMonth: number
  growthRate: number
  /**
   * 平均响应时间。**没有埋点时后端会返回 null**，前端渲染为「—」，
   * 宁缺毋滥——历史上这里曾写死 850ms，与任何真实观测无关。
   */
  avgResponseTime: number | null
  /** 月度增量：本月新增数 - 上月新增数；卡片 trend 用它，别再硬编码 +3/+12%/+2 */
  agentsDelta: number
  sessionsDelta: number
  knowledgeDelta: number
}

interface RecentActivity {
  id: string
  type: 'agent_created' | 'conversation' | 'knowledge_added' | 'workflow_run'
  title: string
  description: string
  timestamp: string
}

/**
 * 把月度增量（本月新增 - 上月新增）射成卡片右上角的 trend 徽章。
 * 为 0 时显「±0」而非「+0」，避免零变化看上去像在长。
 */
function formatDelta(n: number): string {
  if (n > 0) return `+${n}`
  if (n < 0) return `${n}`
  return '±0'
}

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats>({
    totalAgents: 0,
    activeConversations: 0,
    totalKnowledgeBases: 0,
    apiCallsThisMonth: 0,
    growthRate: 0,
    avgResponseTime: null,
    agentsDelta: 0,
    sessionsDelta: 0,
    knowledgeDelta: 0,
  })
  const [activities, setActivities] = useState<RecentActivity[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadDashboardData()
  }, [])

  const loadDashboardData = async () => {
    try {
      setLoading(true)
      const data = await api.get('/agents/stats/summary')
      setStats({
        totalAgents: data.totalAgents ?? 0,
        activeConversations: data.activeConversations ?? 0,
        totalKnowledgeBases: data.totalKnowledgeBases ?? 0,
        apiCallsThisMonth: data.apiCallsThisMonth ?? 0,
        growthRate: data.growthRate ?? 0,
        // null 保持 null，渲染成「—」；旧行为会把 null 变成 0，看着像「零延迟」
        avgResponseTime: data.avgResponseTime ?? null,
        agentsDelta: data.agentsDelta ?? 0,
        sessionsDelta: data.sessionsDelta ?? 0,
        knowledgeDelta: data.knowledgeDelta ?? 0,
      })
      setActivities([])
    } catch (error) {
      console.error('Failed to load dashboard data:', error)
    } finally {
      setLoading(false)
    }
  }

  const statCards = [
    {
      // trend 一律走后端返回的 delta，不再写死 +3/+12%/+2
      title: '总 Agent 数',
      value: stats.totalAgents,
      icon: Bot,
      trend: formatDelta(stats.agentsDelta),
      trendUp: stats.agentsDelta >= 0,
      color: 'from-brand-500 to-brand-600',
    },
    {
      title: '活跃对话',
      value: stats.activeConversations,
      icon: MessageSquare,
      trend: formatDelta(stats.sessionsDelta),
      trendUp: stats.sessionsDelta >= 0,
      color: 'from-emerald-500 to-green-600',
    },
    {
      title: '知识库',
      value: stats.totalKnowledgeBases,
      icon: BookOpen,
      trend: formatDelta(stats.knowledgeDelta),
      trendUp: stats.knowledgeDelta >= 0,
      color: 'from-amber-500 to-orange-600',
    },
    {
      // 后端在没有消息行级表的前提下把「本月 API 调用」重定义为「本月新增对话」，
      // 数字来自 chat_sessions.created_at 落在本月的行；卡片文案同步跟上。
      title: '本月新增对话',
      value: stats.apiCallsThisMonth.toLocaleString(),
      icon: Zap,
      trend: `${stats.growthRate >= 0 ? '+' : ''}${stats.growthRate}%`,
      trendUp: stats.growthRate >= 0,
      color: 'from-blue-500 to-cyan-600',
    },
  ]

  return (
    <div className="mx-auto max-w-7xl p-4 sm:p-6 lg:p-8">
      {/* Header */}
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between lg:mb-8">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
            控制台
          </h1>
          <p className="mt-1 text-slate-500 dark:text-slate-400">
            欢迎回来！以下是您的 AgentFlow 概览
          </p>
        </div>
        <div className="flex gap-3">
          <Link to="/agents/new">
            <Button leftIcon={<Plus className="w-4 h-4" />}>
              创建 Agent
            </Button>
          </Link>
        </div>
      </div>

      {/*
        统计卡：手机上直接两列，不再用 sm: 断点。

        原来写的是 grid-cols-1 sm:grid-cols-2 —— 390px 的手机够不到 sm（640px），
        于是四张卡竖着排，一屏只装得下一张半，光这一块就要往下滚一屏多。
        这类「四个数字」的卡片本来就是拿来一眼扫过的，两列才符合用途。
      */}
      <div className="mb-6 grid grid-cols-2 gap-3 lg:mb-8 lg:grid-cols-4 lg:gap-6">
        {statCards.map((stat) => (
          <Card key={stat.title} className="p-4 transition-shadow hover:shadow-lg lg:p-6">
            <div className="flex items-start justify-between gap-2">
              <div
                className={`rounded-xl bg-gradient-to-br p-2.5 shadow-lg lg:p-3 ${stat.color}`}
              >
                <stat.icon className="h-5 w-5 text-white lg:h-6 lg:w-6" />
              </div>
              <div
                className={`flex shrink-0 items-center gap-0.5 text-xs font-medium lg:gap-1 lg:text-sm ${
                  stat.trendUp ? 'text-emerald-600' : 'text-red-600'
                }`}
              >
                {stat.trendUp ? (
                  <ArrowUpRight className="h-3.5 w-3.5 lg:h-4 lg:w-4" />
                ) : (
                  <ArrowDownRight className="h-3.5 w-3.5 lg:h-4 lg:w-4" />
                )}
                {stat.trend}
              </div>
            </div>
            <div className="mt-3 lg:mt-4">
              {/* 两列时卡片只有 160px 上下，3xl 的数字会和标题抢行 */}
              <p className="text-2xl font-bold text-slate-900 dark:text-white lg:text-3xl">
                {loading ? '-' : stat.value}
              </p>
              <p className="mt-1 text-xs text-slate-500 dark:text-slate-400 lg:text-sm">
                {stat.title}
              </p>
            </div>
          </Card>
        ))}
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 成长面板：占原来「最近活动」的位置 */}
        <div className="lg:col-span-2">
          {/*
            成长面板上移，填在原来「最近活动」的位置。

            数据全部来自真实落库记录（会话按天去重、新增 Agent/知识库按天计数），
            见后端 GET /agents/stats/activity。
          */}
          <GrowthPanel />
        </div>

        {/* Quick Actions */}
        <div className="space-y-6">
          {/*
            性能指标卡——历史上三行内容全部是硬编码（850ms / 99.2% / 85%），
            既无埋点也无数据源。后端现在返回 null 的 avgResponseTime，三行
            无数据支撑的旧字段则直接砍掉。埋点接入后重新开卡。
          */}
          <Card className="p-4 sm:p-6">
            <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">
              性能指标
            </h2>
            <div className="space-y-4">
              <div>
                <div className="flex items-center justify-between text-sm mb-2">
                  <span className="text-slate-500 dark:text-slate-400">平均响应时间</span>
                  <span className="font-medium text-slate-900 dark:text-white">
                    {stats.avgResponseTime === null ? '—' : `${stats.avgResponseTime}ms`}
                  </span>
                </div>
                <p className="text-xs text-slate-400 dark:text-slate-500">
                  {stats.avgResponseTime === null
                    ? '尚未接入埋点，数据就位后自动展示'
                    : '来自最近一次采样'}
                </p>
              </div>
            </div>
          </Card>

          {/* Quick Actions */}
          <Card className="p-4 sm:p-6">
            <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">
              快捷操作
            </h2>
            <div className="space-y-2">
              <Link
                to="/workflow/new"
                className="flex items-center justify-between p-3 rounded-xl hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors group"
              >
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-brand-100 dark:bg-brand-900/30">
                    <Zap className="w-4 h-4 text-brand-600" />
                  </div>
                  <span className="text-slate-700 dark:text-slate-300">创建工作流</span>
                </div>
                <ChevronRight className="w-4 h-4 text-slate-400 group-hover:translate-x-1 transition-transform" />
              </Link>
              <Link
                to="/knowledge"
                className="flex items-center justify-between p-3 rounded-xl hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors group"
              >
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-emerald-100 dark:bg-emerald-900/30">
                    <BookOpen className="w-4 h-4 text-emerald-600" />
                  </div>
                  <span className="text-slate-700 dark:text-slate-300">上传知识库</span>
                </div>
                <ChevronRight className="w-4 h-4 text-slate-400 group-hover:translate-x-1 transition-transform" />
              </Link>
              <Link
                to="/agents"
                className="flex items-center justify-between p-3 rounded-xl hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors group"
              >
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-blue-100 dark:bg-blue-900/30">
                    <Users className="w-4 h-4 text-blue-600" />
                  </div>
                  <span className="text-slate-700 dark:text-slate-300">管理 Agent</span>
                </div>
                <ChevronRight className="w-4 h-4 text-slate-400 group-hover:translate-x-1 transition-transform" />
              </Link>
            </div>
          </Card>
        </div>
      </div>

      {/*
        「最近活动」整行铺开，放在页尾。

        为什么不留在左栏里：手机上左栏排在右栏**之前**，留在左栏它就出现在
        性能指标 / 快捷操作之上，那就不是「最下面」了。整行铺在
        网格之后，桌面和手机都落在页尾。

        活动列表本身也是横向的：一条记录是「图标 + 标题/描述 + 时间」，
        宽一点一行就能读完，挤在窄栏里反而要折行。
      */}
      <div className="mt-6">
        <Card className="p-4 sm:p-6">
          <div className="mb-6 flex items-center justify-between">
            <h2 className="flex items-center gap-2 text-lg font-semibold text-slate-900 dark:text-white">
              <Activity className="h-5 w-5 text-brand-500" />
              最近活动
            </h2>
            <button className="text-sm text-brand-600 hover:text-brand-700 dark:text-brand-400">
              查看全部
            </button>
          </div>

          {/*
            空状态。后端目前不返回活动列表，这里一直是空的 —— 只留一张带标题的
            白卡片会被读成「坏了」，手机上它还要白占掉一屏的七分之一。
          */}
          {activities.length === 0 && (
            <div className="flex flex-col items-center justify-center gap-1.5 rounded-xl border border-dashed border-slate-200 px-4 py-6 text-center dark:border-slate-800">
              <Activity className="h-5 w-5 text-slate-300 dark:text-slate-600" />
              <p className="text-sm text-slate-500 dark:text-slate-400">还没有活动记录</p>
              <p className="text-xs text-slate-400 dark:text-slate-500">
                创建 Agent 或发起一次对话后，这里会显示最近动态
              </p>
            </div>
          )}

          <div className="space-y-4">
            {activities.map((activity) => (
              <div
                key={activity.id}
                className="flex cursor-pointer items-start gap-4 rounded-xl p-4 transition-colors hover:bg-slate-50 dark:hover:bg-slate-800/50"
              >
                <div
                  className={`rounded-lg p-2 ${
                    activity.type === 'agent_created'
                      ? 'bg-brand-100 text-brand-600 dark:bg-brand-900/30'
                      : activity.type === 'conversation'
                      ? 'bg-emerald-100 text-emerald-600 dark:bg-emerald-900/30'
                      : activity.type === 'knowledge_added'
                      ? 'bg-amber-100 text-amber-600 dark:bg-amber-900/30'
                      : 'bg-blue-100 text-blue-600 dark:bg-blue-900/30'
                  }`}
                >
                  {activity.type === 'agent_created' && <Bot className="h-4 w-4" />}
                  {activity.type === 'conversation' && <MessageSquare className="h-4 w-4" />}
                  {activity.type === 'knowledge_added' && <BookOpen className="h-4 w-4" />}
                  {activity.type === 'workflow_run' && <Zap className="h-4 w-4" />}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="font-medium text-slate-900 dark:text-white">
                    {activity.title}
                  </p>
                  <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-400">
                    {activity.description}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-2 text-sm text-slate-400">
                  <Clock className="h-4 w-4" />
                  {activity.timestamp}
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  )
}
