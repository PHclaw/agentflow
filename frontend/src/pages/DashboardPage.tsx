import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import {
  MessageSquare,
  Users,
  BookOpen,
  Zap,
  TrendingUp,
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

interface DashboardStats {
  totalAgents: number
  activeConversations: number
  totalKnowledgeBases: number
  apiCallsThisMonth: number
  growthRate: number
  avgResponseTime: number
}

interface RecentActivity {
  id: string
  type: 'agent_created' | 'conversation' | 'knowledge_added' | 'workflow_run'
  title: string
  description: string
  timestamp: string
}

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats>({
    totalAgents: 0,
    activeConversations: 0,
    totalKnowledgeBases: 0,
    apiCallsThisMonth: 0,
    growthRate: 0,
    avgResponseTime: 0,
  })
  const [activities, setActivities] = useState<RecentActivity[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadDashboardData()
  }, [])

  const loadDashboardData = async () => {
    try {
      // 模拟数据（实际应从 API 获取）
      setStats({
        totalAgents: 12,
        activeConversations: 156,
        totalKnowledgeBases: 8,
        apiCallsThisMonth: 45230,
        growthRate: 23.5,
        avgResponseTime: 850,
      })

      setActivities([
        {
          id: '1',
          type: 'conversation',
          title: '新对话 - 客服助手',
          description: '用户 "张先生" 发起咨询',
          timestamp: '2 分钟前',
        },
        {
          id: '2',
          type: 'knowledge_added',
          title: '知识库更新',
          description: '产品文档新增 25 条记录',
          timestamp: '15 分钟前',
        },
        {
          id: '3',
          type: 'workflow_run',
          title: '工作流执行',
          description: '销售机器人成功执行 145 次',
          timestamp: '1 小时前',
        },
        {
          id: '4',
          type: 'agent_created',
          title: '新 Agent 上线',
          description: 'HR 助手已创建并配置完成',
          timestamp: '3 小时前',
        },
      ])
    } catch (error) {
      console.error('Failed to load dashboard data:', error)
    } finally {
      setLoading(false)
    }
  }

  const statCards = [
    {
      title: '总 Agent 数',
      value: stats.totalAgents,
      icon: Bot,
      trend: '+3',
      trendUp: true,
      color: 'from-indigo-500 to-purple-600',
    },
    {
      title: '活跃对话',
      value: stats.activeConversations,
      icon: MessageSquare,
      trend: '+12%',
      trendUp: true,
      color: 'from-emerald-500 to-green-600',
    },
    {
      title: '知识库',
      value: stats.totalKnowledgeBases,
      icon: BookOpen,
      trend: '+2',
      trendUp: true,
      color: 'from-amber-500 to-orange-600',
    },
    {
      title: '本月 API 调用',
      value: stats.apiCallsThisMonth.toLocaleString(),
      icon: Zap,
      trend: `${stats.growthRate}%`,
      trendUp: true,
      color: 'from-blue-500 to-cyan-600',
    },
  ]

  return (
    <div className="p-6 lg:p-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8">
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

      {/* Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 lg:gap-6 mb-8">
        {statCards.map((stat) => (
          <Card key={stat.title} className="p-6 hover:shadow-lg transition-shadow">
            <div className="flex items-start justify-between">
              <div
                className={`p-3 rounded-xl bg-gradient-to-br ${stat.color} shadow-lg`}
              >
                <stat.icon className="w-6 h-6 text-white" />
              </div>
              <div
                className={`flex items-center gap-1 text-sm font-medium ${
                  stat.trendUp ? 'text-emerald-600' : 'text-red-600'
                }`}
              >
                {stat.trendUp ? (
                  <ArrowUpRight className="w-4 h-4" />
                ) : (
                  <ArrowDownRight className="w-4 h-4" />
                )}
                {stat.trend}
              </div>
            </div>
            <div className="mt-4">
              <p className="text-3xl font-bold text-slate-900 dark:text-white">
                {loading ? '-' : stat.value}
              </p>
              <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                {stat.title}
              </p>
            </div>
          </Card>
        ))}
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Activity */}
        <div className="lg:col-span-2">
          <Card className="p-6">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white flex items-center gap-2">
                <Activity className="w-5 h-5 text-indigo-500" />
                最近活动
              </h2>
              <button className="text-sm text-indigo-600 dark:text-indigo-400 hover:text-indigo-700">
                查看全部
              </button>
            </div>

            <div className="space-y-4">
              {activities.map((activity) => (
                <div
                  key={activity.id}
                  className="flex items-start gap-4 p-4 rounded-xl hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors cursor-pointer"
                >
                  <div
                    className={`p-2 rounded-lg ${
                      activity.type === 'agent_created'
                        ? 'bg-indigo-100 dark:bg-indigo-900/30 text-indigo-600'
                        : activity.type === 'conversation'
                        ? 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-600'
                        : activity.type === 'knowledge_added'
                        ? 'bg-amber-100 dark:bg-amber-900/30 text-amber-600'
                        : 'bg-blue-100 dark:bg-blue-900/30 text-blue-600'
                    }`}
                  >
                    {activity.type === 'agent_created' && <Bot className="w-4 h-4" />}
                    {activity.type === 'conversation' && <MessageSquare className="w-4 h-4" />}
                    {activity.type === 'knowledge_added' && <BookOpen className="w-4 h-4" />}
                    {activity.type === 'workflow_run' && <Zap className="w-4 h-4" />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-slate-900 dark:text-white">
                      {activity.title}
                    </p>
                    <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">
                      {activity.description}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 text-sm text-slate-400">
                    <Clock className="w-4 h-4" />
                    {activity.timestamp}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>

        {/* Quick Actions */}
        <div className="space-y-6">
          {/* Performance Card */}
          <Card className="p-6">
            <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">
              性能指标
            </h2>
            <div className="space-y-4">
              <div>
                <div className="flex items-center justify-between text-sm mb-2">
                  <span className="text-slate-500 dark:text-slate-400">平均响应时间</span>
                  <span className="font-medium text-slate-900 dark:text-white">
                    {stats.avgResponseTime}ms
                  </span>
                </div>
                <div className="h-2 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-emerald-500 to-green-500 rounded-full"
                    style={{ width: '75%' }}
                  />
                </div>
              </div>
              <div>
                <div className="flex items-center justify-between text-sm mb-2">
                  <span className="text-slate-500 dark:text-slate-400">成功率</span>
                  <span className="font-medium text-slate-900 dark:text-white">99.2%</span>
                </div>
                <div className="h-2 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-indigo-500 to-purple-500 rounded-full"
                    style={{ width: '92%' }}
                  />
                </div>
              </div>
              <div>
                <div className="flex items-center justify-between text-sm mb-2">
                  <span className="text-slate-500 dark:text-slate-400">Token 效率</span>
                  <span className="font-medium text-slate-900 dark:text-white">85%</span>
                </div>
                <div className="h-2 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-amber-500 to-orange-500 rounded-full"
                    style={{ width: '85%' }}
                  />
                </div>
              </div>
            </div>
          </Card>

          {/* Quick Actions */}
          <Card className="p-6">
            <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">
              快捷操作
            </h2>
            <div className="space-y-2">
              <Link
                to="/workflow/new"
                className="flex items-center justify-between p-3 rounded-xl hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors group"
              >
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-purple-100 dark:bg-purple-900/30">
                    <Zap className="w-4 h-4 text-purple-600" />
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

          {/* Usage This Month */}
          <Card className="p-6 bg-gradient-to-br from-indigo-500 to-purple-600 border-0">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-white font-semibold">本月使用</h2>
              <TrendingUp className="w-5 h-5 text-white/70" />
            </div>
            <p className="text-4xl font-bold text-white">
              {stats.apiCallsThisMonth.toLocaleString()}
            </p>
            <p className="text-indigo-100 mt-1">API 调用次数</p>
            <div className="mt-4 flex items-center gap-2 text-sm text-indigo-100">
              <ArrowUpRight className="w-4 h-4" />
              相比上月增长 {stats.growthRate}%
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
