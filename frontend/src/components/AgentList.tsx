import React, { useState, useEffect } from 'react'

interface Agent {
  id: string
  name: string
  description: string
  is_active: boolean
  message_count: number
  created_at: string
}

export default function AgentList() {
  const [agents, setAgents] = useState<Agent[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)

  useEffect(() => {
    fetchAgents()
  }, [])

  const fetchAgents = async () => {
    try {
      const response = await fetch('/api/v1/agents')
      const data = await response.json()
      setAgents(data)
    } catch (error) {
      console.error('Failed to fetch agents:', error)
    } finally {
      setLoading(false)
    }
  }

  const deleteAgent = async (id: string) => {
    if (!confirm('确定要删除这个 Agent 吗？')) return

    try {
      await fetch(`/api/v1/agents/${id}`, { method: 'DELETE' })
      setAgents((prev) => prev.filter((a) => a.id !== id))
    } catch (error) {
      alert('删除失败')
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-400">加载中...</div>
      </div>
    )
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-gray-900">我的 Agents</h2>
        <button
          onClick={() => setShowCreate(true)}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition flex items-center gap-2"
        >
          <span>+</span>
          <span>创建 Agent</span>
        </button>
      </div>

      {agents.length === 0 ? (
        <div className="text-center py-16 bg-gray-50 rounded-xl">
          <div className="text-6xl mb-4">🤖</div>
          <h3 className="text-xl font-semibold text-gray-700 mb-2">还没有 Agent</h3>
          <p className="text-gray-500 mb-4">创建你的第一个 AI Agent 开始吧</p>
          <button
            onClick={() => setShowCreate(true)}
            className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            创建 Agent
          </button>
        </div>
      ) : (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
          {agents.map((agent) => (
            <div
              key={agent.id}
              className="bg-white rounded-xl shadow-sm border hover:shadow-md transition p-6"
            >
              <div className="flex items-start justify-between mb-4">
                <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-lg flex items-center justify-center">
                  <span className="text-white text-xl">🤖</span>
                </div>
                <span className={`px-2 py-1 text-xs rounded-full ${
                  agent.is_active ? 'bg-green-100 text-green-600' : 'bg-gray-100 text-gray-600'
                }`}>
                  {agent.is_active ? '运行中' : '已停止'}
                </span>
              </div>

              <h3 className="text-lg font-semibold text-gray-900 mb-1">{agent.name}</h3>
              <p className="text-gray-500 text-sm mb-4 line-clamp-2">
                {agent.description || '暂无描述'}
              </p>

              <div className="flex items-center justify-between text-sm text-gray-400 mb-4">
                <span>💬 {agent.message_count || 0} 次对话</span>
                <span>{new Date(agent.created_at).toLocaleDateString('zh-CN')}</span>
              </div>

              <div className="flex gap-2">
                <button className="flex-1 py-2 bg-blue-50 text-blue-600 rounded-lg hover:bg-blue-100 transition text-sm">
                  编辑
                </button>
                <button className="flex-1 py-2 bg-green-50 text-green-600 rounded-lg hover:bg-green-100 transition text-sm">
                  对话
                </button>
                <button
                  onClick={() => deleteAgent(agent.id)}
                  className="py-2 px-3 bg-red-50 text-red-600 rounded-lg hover:bg-red-100 transition text-sm"
                >
                  删除
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 创建弹窗 */}
      {showCreate && (
        <CreateAgentModal onClose={() => setShowCreate(false)} onSuccess={fetchAgents} />
      )}
    </div>
  )
}

function CreateAgentModal({
  onClose,
  onSuccess,
}: {
  onClose: () => void
  onSuccess: () => void
}) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [loading, setLoading] = useState(false)

  const create = async () => {
    if (!name.trim()) return

    setLoading(true)
    try {
      await fetch('/api/v1/agents', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name,
          description,
          workflow_definition: { nodes: [], edges: [], entry: 'start' },
        }),
      })
      onSuccess()
      onClose()
    } catch (error) {
      alert('创建失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl p-6 w-full max-w-md">
        <h3 className="text-xl font-semibold mb-4">创建 Agent</h3>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">名称</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="我的 AI 助手"
              className="w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">描述</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="描述这个 Agent 的功能..."
              rows={3}
              className="w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>

        <div className="flex gap-2 mt-6">
          <button
            onClick={onClose}
            className="flex-1 py-2 border rounded-lg hover:bg-gray-50"
          >
            取消
          </button>
          <button
            onClick={create}
            disabled={loading || !name.trim()}
            className="flex-1 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300"
          >
            {loading ? '创建中...' : '创建'}
          </button>
        </div>
      </div>
    </div>
  )
}
