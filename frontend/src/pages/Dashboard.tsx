import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../services/api'

interface Stats {
  agents_count: number
  messages_count: number
  knowledge_bases: number
  today_messages: number
}

interface RecentAgent {
  id: string
  name: string
  message_count: number
  is_active: boolean
}

export default function Dashboard() {
  const [stats, setStats] = useState<Stats>({
    agents_count: 0,
    messages_count: 0,
    knowledge_bases: 0,
    today_messages: 0,
  })
  const [recentAgents, setRecentAgents] = useState<RecentAgent[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchDashboard()
  }, [])

  const fetchDashboard = async () => {
    try {
      const [statsRes, agentsRes] = await Promise.all([
        api.get('/stats'),
        api.get('/agents?limit=5'),
      ])
      setStats(statsRes)
      setRecentAgents(agentsRes)
    } catch (error) {
      console.error('Failed to fetch dashboard:', error)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-gray-400">加载中...</div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-lg flex items-center justify-center">
              <span className="text-white font-bold text-xl">A</span>
            </div>
            <h1 className="text-xl font-bold text-gray-900">AgentFlow</h1>
          </div>
          <nav className="flex items-center gap-4">
            <Link to="/dashboard" className="text-blue-600 font-medium">控制台</Link>
            <Link to="/agents" className="text-gray-600 hover:text-blue-600">我的 Agent</Link>
            <Link to="/templates" className="text-gray-600 hover:text-blue-600">模板</Link>
            <div className="w-8 h-8 bg-gray-200 rounded-full"></div>
          </nav>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 py-8">
        {/* Welcome */}
        <div className="mb-8">
          <h2 className="text-2xl font-bold text-gray-900">欢迎回来</h2>
          <p className="text-gray-500">这里是你的 AgentFlow 控制台</p>
        </div>

        {/* Quick Actions */}
        <div className="grid md:grid-cols-3 gap-6 mb-8">
          <Link
            to="/agents/new"
            className="p-6 bg-gradient-to-r from-blue-500 to-indigo-600 rounded-xl text-white hover:shadow-lg transition"
          >
            <div className="text-3xl mb-2">➕</div>
            <h3 className="text-lg font-semibold mb-1">创建新 Agent</h3>
            <p className="text-blue-100 text-sm">从模板或空白开始</p>
          </Link>

          <Link
            to="/templates"
            className="p-6 bg-gradient-to-r from-green-500 to-emerald-600 rounded-xl text-white hover:shadow-lg transition"
          >
            <div className="text-3xl mb-2">📦</div>
            <h3 className="text-lg font-semibold mb-1">浏览模板</h3>
            <p className="text-green-100 text-sm">使用预置行业模板</p>
          </Link>

          <Link
            to="/agents"
            className="p-6 bg-gradient-to-r from-purple-500 to-violet-600 rounded-xl text-white hover:shadow-lg transition"
          >
            <div className="text-3xl mb-2">🤖</div>
            <h3 className="text-lg font-semibold mb-1">管理 Agent</h3>
            <p className="text-purple-100 text-sm">编辑、测试、部署</p>
          </Link>
        </div>

        {/* Stats */}
        <div className="grid md:grid-cols-4 gap-6 mb-8">
          <StatCard
            label="我的 Agent"
            value={stats.agents_count}
            icon="🤖"
            color="bg-blue-50 text-blue-600"
          />
          <StatCard
            label="总对话数"
            value={stats.messages_count}
            icon="💬"
            color="bg-green-50 text-green-600"
          />
          <StatCard
            label="知识库"
            value={stats.knowledge_bases}
            icon="📚"
            color="bg-purple-50 text-purple-600"
          />
          <StatCard
            label="今日对话"
            value={stats.today_messages}
            icon="📊"
            color="bg-orange-50 text-orange-600"
          />
        </div>

        {/* Recent Agents */}
        <div className="bg-white rounded-xl shadow-sm border p-6">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-lg font-semibold text-gray-900">最近的 Agent</h3>
            <Link to="/agents" className="text-blue-600 hover:underline text-sm">
              查看全部
            </Link>
          </div>

          {recentAgents.length === 0 ? (
            <div className="text-center py-12">
              <div className="text-5xl mb-4">🤖</div>
              <h4 className="text-gray-700 font-medium mb-2">还没有 Agent</h4>
              <p className="text-gray-500 text-sm mb-4">创建你的第一个 AI Agent</p>
              <Link
                to="/agents/new"
                className="inline-block px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
              >
                立即创建
              </Link>
            </div>
          ) : (
            <div className="space-y-4">
              {recentAgents.map((agent) => (
                <div
                  key={agent.id}
                  className="flex items-center justify-between p-4 bg-gray-50 rounded-lg hover:bg-gray-100 transition"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-lg flex items-center justify-center">
                      <span className="text-white">🤖</span>
                    </div>
                    <div>
                      <h4 className="font-medium text-gray-900">{agent.name}</h4>
                      <p className="text-sm text-gray-500">{agent.message_count} 次对话</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`px-2 py-1 text-xs rounded-full ${
                      agent.is_active ? 'bg-green-100 text-green-600' : 'bg-gray-200 text-gray-600'
                    }`}>
                      {agent.is_active ? '运行中' : '已停止'}
                    </span>
                    <Link
                      to={`/agents/${agent.id}/chat`}
                      className="px-3 py-1 bg-blue-50 text-blue-600 rounded hover:bg-blue-100 text-sm"
                    >
                      对话
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  )
}

function StatCard({
  label,
  value,
  icon,
  color,
}: {
  label: string
  value: number
  icon: string
  color: string
}) {
  return (
    <div className="bg-white rounded-xl shadow-sm border p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-500 mb-1">{label}</p>
          <p className="text-3xl font-bold text-gray-900">{value}</p>
        </div>
        <div className={`w-12 h-12 ${color} rounded-lg flex items-center justify-center text-2xl`}>
          {icon}
        </div>
      </div>
    </div>
  )
}
