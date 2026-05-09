import React, { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  Plus,
  Search,
  Bot,
  MessageSquare,
  BookOpen,
  Zap,
  MoreVertical,
  Edit2,
  Trash2,
  Copy,
  ExternalLink,
  Clock,
  MessageCircle,
  BarChart2,
  Grid,
  List,
  Filter,
} from 'lucide-react'
import { api } from '../services/api'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Card } from '../components/ui/Card'
import { Modal, ConfirmModal } from '../components/ui/Modal'

interface Agent {
  id: string
  name: string
  description: string
  model: string
  conversation_count: number
  created_at: string
  updated_at: string
  status: 'active' | 'inactive' | 'draft'
}

export default function AgentListPage() {
  const navigate = useNavigate()
  const [agents, setAgents] = useState<Agent[]>([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid')
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null)
  const [showDeleteModal, setShowDeleteModal] = useState(false)
  const [agentToDelete, setAgentToDelete] = useState<Agent | null>(null)
  const [filter, setFilter] = useState<'all' | 'active' | 'inactive'>('all')

  useEffect(() => {
    loadAgents()
  }, [])

  const loadAgents = async () => {
    try {
      setLoading(true)
      const response = await api.get('/agents')
      setAgents(response.data || [])
    } catch (error) {
      console.error('Failed to load agents:', error)
      // 使用模拟数据
      setAgents([
        {
          id: '1',
          name: '智能客服助手',
          description: '基于知识库的 24/7 客户支持 Agent',
          model: 'gpt-4o-mini',
          conversation_count: 1250,
          created_at: '2024-01-15T10:30:00Z',
          updated_at: '2024-01-20T15:45:00Z',
          status: 'active',
        },
        {
          id: '2',
          name: '销售线索机器人',
          description: '自动识别和跟进销售线索',
          model: 'gpt-4o',
          conversation_count: 856,
          created_at: '2024-01-10T09:00:00Z',
          updated_at: '2024-01-19T11:20:00Z',
          status: 'active',
        },
        {
          id: '3',
          name: 'HR 入职助手',
          description: '帮助新员工完成入职流程',
          model: 'claude-3-sonnet',
          conversation_count: 423,
          created_at: '2024-01-05T14:00:00Z',
          updated_at: '2024-01-18T09:30:00Z',
          status: 'draft',
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  const handleDeleteAgent = async () => {
    if (!agentToDelete) return
    try {
      await api.delete(`/agents/${agentToDelete.id}`)
      setAgents(agents.filter((a) => a.id !== agentToDelete.id))
      setShowDeleteModal(false)
      setAgentToDelete(null)
    } catch (error) {
      console.error('Failed to delete agent:', error)
    }
  }

  const handleDuplicateAgent = async (agent: Agent) => {
    try {
      const response = await api.post(`/agents/${agent.id}/duplicate`, {
        name: `${agent.name} (副本)`,
      })
      loadAgents()
    } catch (error) {
      console.error('Failed to duplicate agent:', error)
    }
  }

  const filteredAgents = agents.filter((agent) => {
    const matchesSearch =
      agent.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      agent.description.toLowerCase().includes(searchQuery.toLowerCase())
    const matchesFilter = filter === 'all' || agent.status === filter
    return matchesSearch && matchesFilter
  })

  const statusColors = {
    active: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
    inactive: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400',
    draft: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
  }

  return (
    <div className="p-6 lg:p-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
            Agent 管理
          </h1>
          <p className="mt-1 text-slate-500 dark:text-slate-400">
            创建和管理您的 AI Agent
          </p>
        </div>
        <Link to="/agents/new">
          <Button leftIcon={<Plus className="w-4 h-4" />}>
            创建 Agent
          </Button>
        </Link>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-4 mb-6">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
          <input
            type="text"
            placeholder="搜索 Agent..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>
        <div className="flex gap-2">
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value as any)}
            className="px-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="all">全部状态</option>
            <option value="active">活跃</option>
            <option value="inactive">未激活</option>
            <option value="draft">草稿</option>
          </select>
          <div className="flex border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden">
            <button
              onClick={() => setViewMode('grid')}
              className={`p-2.5 ${
                viewMode === 'grid'
                  ? 'bg-indigo-50 dark:bg-indigo-900/30 text-indigo-600'
                  : 'bg-white dark:bg-slate-800 text-slate-400 hover:text-slate-600'
              }`}
            >
              <Grid className="w-5 h-5" />
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={`p-2.5 ${
                viewMode === 'list'
                  ? 'bg-indigo-50 dark:bg-indigo-900/30 text-indigo-600'
                  : 'bg-white dark:bg-slate-800 text-slate-400 hover:text-slate-600'
              }`}
            >
              <List className="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>

      {/* Agent List */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2, 3].map((i) => (
            <Card key={i} className="p-6 animate-pulse">
              <div className="h-4 bg-slate-200 dark:bg-slate-700 rounded w-1/2 mb-4" />
              <div className="h-3 bg-slate-200 dark:bg-slate-700 rounded w-3/4 mb-2" />
              <div className="h-3 bg-slate-200 dark:bg-slate-700 rounded w-1/4" />
            </Card>
          ))}
        </div>
      ) : filteredAgents.length === 0 ? (
        <Card className="p-12 text-center">
          <Bot className="w-16 h-16 text-slate-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-slate-900 dark:text-white mb-2">
            {searchQuery ? '没有找到匹配的 Agent' : '还没有创建 Agent'}
          </h3>
          <p className="text-slate-500 dark:text-slate-400 mb-6">
            {searchQuery
              ? '尝试使用不同的搜索词'
              : '开始创建您的第一个 AI Agent'}
          </p>
          {!searchQuery && (
            <Link to="/agents/new">
              <Button leftIcon={<Plus className="w-4 h-4" />}>创建 Agent</Button>
            </Link>
          )}
        </Card>
      ) : viewMode === 'grid' ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredAgents.map((agent) => (
            <Card key={agent.id} className="p-6 hover:shadow-lg transition-shadow group">
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="p-3 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 shadow-lg">
                    <Bot className="w-6 h-6 text-white" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-slate-900 dark:text-white group-hover:text-indigo-600 transition-colors">
                      {agent.name}
                    </h3>
                    <span
                      className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${
                        statusColors[agent.status]
                      }`}
                    >
                      {agent.status === 'active'
                        ? '活跃'
                        : agent.status === 'inactive'
                        ? '未激活'
                        : '草稿'}
                    </span>
                  </div>
                </div>
                <div className="relative">
                  <button
                    onClick={() => setSelectedAgent(agent)}
                    className="p-2 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 dark:hover:bg-slate-800"
                  >
                    <MoreVertical className="w-5 h-5" />
                  </button>
                </div>
              </div>

              <p className="text-sm text-slate-500 dark:text-slate-400 mb-4 line-clamp-2">
                {agent.description}
              </p>

              <div className="flex items-center gap-4 text-sm text-slate-400 mb-4">
                <div className="flex items-center gap-1">
                  <MessageSquare className="w-4 h-4" />
                  {agent.conversation_count}
                </div>
                <div className="flex items-center gap-1">
                  <Clock className="w-4 h-4" />
                  {new Date(agent.updated_at).toLocaleDateString('zh-CN')}
                </div>
              </div>

              <div className="flex gap-2">
                <Link to={`/agents/${agent.id}/chat`} className="flex-1">
                  <Button variant="outline" size="sm" className="w-full" leftIcon={<MessageCircle className="w-4 h-4" />}>
                    对话
                  </Button>
                </Link>
                <Link to={`/workflow/${agent.id}`} className="flex-1">
                  <Button variant="ghost" size="sm" className="w-full" leftIcon={<Zap className="w-4 h-4" />}>
                    编辑
                  </Button>
                </Link>
              </div>
            </Card>
          ))}
        </div>
      ) : (
        <Card className="overflow-hidden">
          <table className="w-full">
            <thead className="bg-slate-50 dark:bg-slate-800/50">
              <tr>
                <th className="px-6 py-4 text-left text-sm font-medium text-slate-500 dark:text-slate-400">
                  Agent
                </th>
                <th className="px-6 py-4 text-left text-sm font-medium text-slate-500 dark:text-slate-400">
                  状态
                </th>
                <th className="px-6 py-4 text-left text-sm font-medium text-slate-500 dark:text-slate-400">
                  对话数
                </th>
                <th className="px-6 py-4 text-left text-sm font-medium text-slate-500 dark:text-slate-400">
                  更新时间
                </th>
                <th className="px-6 py-4 text-right text-sm font-medium text-slate-500 dark:text-slate-400">
                  操作
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
              {filteredAgents.map((agent) => (
                <tr key={agent.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <div className="p-2 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600">
                        <Bot className="w-5 h-5 text-white" />
                      </div>
                      <div>
                        <p className="font-medium text-slate-900 dark:text-white">
                          {agent.name}
                        </p>
                        <p className="text-sm text-slate-500 dark:text-slate-400">
                          {agent.description}
                        </p>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <span
                      className={`inline-block px-2 py-1 rounded-full text-xs font-medium ${
                        statusColors[agent.status]
                      }`}
                    >
                      {agent.status === 'active'
                        ? '活跃'
                        : agent.status === 'inactive'
                        ? '未激活'
                        : '草稿'}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-slate-500 dark:text-slate-400">
                    {agent.conversation_count}
                  </td>
                  <td className="px-6 py-4 text-slate-500 dark:text-slate-400">
                    {new Date(agent.updated_at).toLocaleDateString('zh-CN')}
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex justify-end gap-2">
                      <Link to={`/agents/${agent.id}/chat`}>
                        <Button variant="ghost" size="sm">
                          <MessageCircle className="w-4 h-4" />
                        </Button>
                      </Link>
                      <Link to={`/workflow/${agent.id}`}>
                        <Button variant="ghost" size="sm">
                          <Edit2 className="w-4 h-4" />
                        </Button>
                      </Link>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          setAgentToDelete(agent)
                          setShowDeleteModal(true)
                        }}
                      >
                        <Trash2 className="w-4 h-4 text-red-500" />
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {/* Action Dropdown */}
      {selectedAgent && (
        <div
          className="fixed inset-0 z-40"
          onClick={() => setSelectedAgent(null)}
        >
          <div
            className="absolute right-6 top-20 w-48 bg-white dark:bg-slate-800 rounded-xl shadow-xl border border-slate-200 dark:border-slate-700 py-2 z-50"
            onClick={(e) => e.stopPropagation()}
          >
            <Link
              to={`/workflow/${selectedAgent.id}`}
              className="flex items-center gap-2 px-4 py-2 text-sm text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700"
            >
              <Edit2 className="w-4 h-4" />
              编辑
            </Link>
            <Link
              to={`/agents/${selectedAgent.id}/chat`}
              className="flex items-center gap-2 px-4 py-2 text-sm text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700"
            >
              <MessageCircle className="w-4 h-4" />
              对话
            </Link>
            <Link
              to={`/agents/${selectedAgent.id}/stats`}
              className="flex items-center gap-2 px-4 py-2 text-sm text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700"
            >
              <BarChart2 className="w-4 h-4" />
              统计
            </Link>
            <button
              onClick={() => handleDuplicateAgent(selectedAgent)}
              className="flex items-center gap-2 px-4 py-2 text-sm text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 w-full"
            >
              <Copy className="w-4 h-4" />
              复制
            </button>
            <hr className="my-2 border-slate-200 dark:border-slate-700" />
            <button
              onClick={() => {
                setAgentToDelete(selectedAgent)
                setShowDeleteModal(true)
                setSelectedAgent(null)
              }}
              className="flex items-center gap-2 px-4 py-2 text-sm text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 w-full"
            >
              <Trash2 className="w-4 h-4" />
              删除
            </button>
          </div>
        </div>
      )}

      {/* Delete Confirmation */}
      <ConfirmModal
        isOpen={showDeleteModal}
        onClose={() => {
          setShowDeleteModal(false)
          setAgentToDelete(null)
        }}
        onConfirm={handleDeleteAgent}
        title="删除 Agent"
        message={`确定要删除 "${agentToDelete?.name}" 吗？此操作无法撤销。`}
        confirmText="删除"
        variant="danger"
      />
    </div>
  )
}
