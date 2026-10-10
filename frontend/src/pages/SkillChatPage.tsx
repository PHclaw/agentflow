import { useEffect, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { ArrowLeft, ArrowRight, Sparkles, Wrench } from 'lucide-react'
import { agents as agentsApi, skills as skillsApi } from '../services/api'
import { ChatSession } from './ChatPage'

interface SkillInfo {
  id: string
  name: string
  description: string
  specialty?: string
}

interface AgentItem {
  id: string
  name: string
  description?: string
}

/**
 * 技能广场的对话入口。
 *
 * 技能本身不能独立运行 —— 它需要挂在某个 Agent 上（由 AI Agent 引擎按
 * agentId + skills 调用）。所以这里先给出 Agent 选择，选定后复用
 * ChatSession 渲染与 Agent 对话页完全一致的界面。
 *
 * 选中的 Agent 存在 URL（?agent=xxx）上，刷新和浏览器前进/后退都能保持。
 */
export default function SkillChatPage() {
  const { id: skillId } = useParams<{ id: string }>()
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()

  const [skill, setSkill] = useState<SkillInfo | null>(null)
  const [agents, setAgents] = useState<AgentItem[]>([])
  const [loadingAgents, setLoadingAgents] = useState(true)
  const [loadError, setLoadError] = useState('')

  const selectedAgentId = searchParams.get('agent')

  useEffect(() => {
    if (!skillId) return
    setLoadError('')
    skillsApi
      .get(skillId)
      .then((data: any) =>
        setSkill({
          id: data.id,
          name: data.name,
          description: data.description || '',
          specialty: data.specialty,
        })
      )
      .catch((e: { message?: string }) => setLoadError(e?.message || '加载技能失败'))
  }, [skillId])

  useEffect(() => {
    agentsApi
      .list()
      .then((data: any) => {
        const list = Array.isArray(data) ? data : data?.items ?? data?.agents ?? []
        setAgents(list)
      })
      .catch(() => setAgents([]))
      .finally(() => setLoadingAgents(false))
  }, [])

  const chooseAgent = (agentId: string) => {
    const next = new URLSearchParams(searchParams)
    next.set('agent', agentId)
    setSearchParams(next, { replace: true })
  }

  const switchAgent = () => {
    const next = new URLSearchParams(searchParams)
    next.delete('agent')
    setSearchParams(next, { replace: true })
  }

  // 已选定 Agent：直接进入对话界面，技能自动挂载
  if (selectedAgentId && skillId) {
    return (
      <ChatSession id={selectedAgentId} skillId={skillId} onSwitchAgent={switchAgent} />
    )
  }

  return (
    <div className="h-screen flex flex-col bg-white dark:bg-slate-950">
      <header className="flex-shrink-0 px-4 py-3">
        <div className="flex items-center gap-2 max-w-2xl mx-auto">
          <button
            onClick={() => navigate('/skills')}
            title="返回技能广场"
            className="p-2 rounded-full text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-900 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <span className="text-[15px] font-medium text-slate-900 dark:text-white truncate">
            {skill?.name || '技能'}
          </span>
        </div>
      </header>

      <main className="flex-1 overflow-y-auto px-6 pb-16">
        <div className="max-w-2xl mx-auto pt-8">
          {/* 技能介绍：与对话页空状态同一套排版 */}
          <div className="text-center mb-10">
            <div className="w-12 h-12 mx-auto mb-5 rounded-2xl bg-slate-900 dark:bg-white flex items-center justify-center">
              <Sparkles className="w-6 h-6 text-white dark:text-slate-900" />
            </div>
            <h1 className="text-4xl font-bold tracking-tight text-slate-900 dark:text-white mb-3">
              {skill?.name || '技能'}
            </h1>
            <p className="text-slate-500 dark:text-slate-400">
              {skill?.specialty || skill?.description || '选择一个 Agent 来使用这个技能'}
            </p>
            {loadError && (
              <p className="mt-3 text-sm text-red-500">{loadError}</p>
            )}
          </div>

          {skill?.description && skill?.specialty && (
            <div className="mb-8 px-4 py-3 rounded-2xl bg-slate-100/70 dark:bg-slate-900 text-sm text-slate-600 dark:text-slate-300 whitespace-pre-line">
              {skill.description}
            </div>
          )}

          {/* Agent 选择 */}
          <div className="flex items-center gap-2 mb-3">
            <Wrench className="w-4 h-4 text-slate-400" />
            <h2 className="text-sm font-semibold text-slate-900 dark:text-white">
              选择一个 Agent 开始对话
            </h2>
            <span className="text-xs text-slate-400">
              技能会挂载到该 Agent 上执行
            </span>
          </div>

          {loadingAgents ? (
            <p className="text-sm text-slate-400 py-6 text-center">正在加载 Agent…</p>
          ) : agents.length === 0 ? (
            <div className="py-8 text-center border border-dashed border-slate-200 dark:border-slate-800 rounded-2xl">
              <p className="text-sm text-slate-500 mb-4">
                你还没有创建 Agent，技能需要挂载在 Agent 上才能使用
              </p>
              <button
                onClick={() => navigate('/agents/new')}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-slate-900 dark:bg-white text-white dark:text-slate-900 text-sm hover:opacity-90 transition-opacity"
              >
                <Sparkles className="w-4 h-4" />
                创建 Agent
              </button>
            </div>
          ) : (
            <div className="space-y-2">
              {agents.map((agent) => (
                <button
                  key={agent.id}
                  onClick={() => chooseAgent(agent.id)}
                  className="w-full flex items-center gap-3 p-4 rounded-2xl border border-slate-200 dark:border-slate-800 hover:border-slate-400 dark:hover:border-slate-600 text-left transition-colors"
                >
                  <span className="w-9 h-9 flex-shrink-0 rounded-xl bg-slate-900 dark:bg-white text-white dark:text-slate-900 text-sm font-medium flex items-center justify-center">
                    {agent.name.slice(0, 1)}
                  </span>
                  <span className="flex-1 min-w-0">
                    <span className="block text-sm font-medium text-slate-900 dark:text-white truncate">
                      {agent.name}
                    </span>
                    {agent.description && (
                      <span className="block text-xs text-slate-500 truncate">
                        {agent.description}
                      </span>
                    )}
                  </span>
                  <ArrowRight className="w-4 h-4 text-slate-400 flex-shrink-0" />
                </button>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
