import React, { useState, useRef, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import ChatWidget from '../components/ChatWidget'

export default function ChatPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [agentInfo, setAgentInfo] = useState<any>(null)

  useEffect(() => {
    if (id) {
      fetchAgentInfo(id)
    }
  }, [id])

  const fetchAgentInfo = async (agentId: string) => {
    try {
      const response = await fetch(`/api/v1/agents/${agentId}`)
      const data = await response.json()
      setAgentInfo(data)
    } catch (error) {
      console.error('Failed to fetch agent:', error)
    }
  }

  return (
    <div className="h-screen flex flex-col bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b px-4 py-3">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate(-1)}
            className="p-2 hover:bg-gray-100 rounded-lg"
          >
            ←
          </button>
          {agentInfo ? (
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-lg flex items-center justify-center">
                <span className="text-white text-xl">🤖</span>
              </div>
              <div>
                <h1 className="font-semibold text-gray-900">{agentInfo.name}</h1>
                <p className="text-sm text-gray-500">{agentInfo.description}</p>
              </div>
            </div>
          ) : (
            <div className="text-gray-400">加载中...</div>
          )}
        </div>
      </header>

      {/* Chat */}
      <div className="flex-1 p-4">
        <div className="h-full max-w-4xl mx-auto">
          <ChatWidget
            agentId={id || ''}
            title={agentInfo?.name || 'AI 助手'}
          />
        </div>
      </div>
    </div>
  )
}
