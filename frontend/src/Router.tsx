import { useEffect, useState } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Toast } from './components/ui/Toast'
import { AppLayout } from './components/layout'
import { ProtectedRoute } from './components/auth/ProtectedRoute'
import { agents as agentsApi } from './services/api'

// Pages（精简版：仅对话相关界面）
import HomePage from './pages/HomePage'
import AgentListPage from './pages/AgentListPage'
import AgentCreatePage from './pages/AgentCreatePage'
import ChatPage from './pages/ChatPage'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import SettingsPage from './pages/SettingsPage'
import HelpPage from './pages/HelpPage'
import ConversationListPage from './pages/ConversationListPage'
import SkillPlazaPage from './pages/SkillPlazaPage'
import SkillChatPage from './pages/SkillChatPage'

/**
 * 「对话」入口：不写死任何 Agent id，从真实接口取当前账号的第一个 Agent，
 * 再跳到项目原有的 /agents/:id/chat —— PiAgent 链路在 ChatPage.tsx 里。
 */
function ChatEntry() {
  const [target, setTarget] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    agentsApi
      .list({ limit: 1 })
      .then((data: any) => {
        if (cancelled) return
        const list = Array.isArray(data) ? data : data?.items ?? data?.agents ?? []
        setTarget(list[0]?.id ? `/agents/${list[0].id}/chat?new=1` : '/agents')
      })
      .catch(() => {
        if (!cancelled) setTarget('/agents')
      })
    return () => {
      cancelled = true
    }
  }, [])

  if (!target) return <div className="p-8 text-sm text-slate-500">正在进入对话…</div>
  return <Navigate to={target} replace />
}

function LandingPage() {
  return <HomePage />
}

function DashboardLayout({ children }: { children: React.ReactNode }) {
  return <AppLayout hideSidebar={false}>{children}</AppLayout>
}

function ProtectedDashboard({ children }: { children: React.ReactNode }) {
  return (
    <ProtectedRoute>
      <DashboardLayout>{children}</DashboardLayout>
    </ProtectedRoute>
  )
}

export default function Router() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Public Routes with Header/Footer */}
        <Route path="/" element={<LandingPage />} />
        <Route path="/pricing" element={<LandingPage />} />

        {/* 对话：跳到真实 Agent 的聊天页（PiAgent 链路） */}
        <Route path="/chat" element={<ProtectedDashboard><ChatEntry /></ProtectedDashboard>} />

        {/* Auth Routes */}
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />

        {/* Protected Routes with Sidebar */}
        <Route path="/agents" element={<ProtectedDashboard><AgentListPage /></ProtectedDashboard>} />
        <Route path="/agents/new" element={<ProtectedDashboard><AgentCreatePage /></ProtectedDashboard>} />
        <Route path="/agents/:id/edit" element={<ProtectedDashboard><AgentCreatePage /></ProtectedDashboard>} />
        <Route path="/conversations" element={<ProtectedDashboard><ConversationListPage /></ProtectedDashboard>} />
        <Route path="/skills" element={<ProtectedDashboard><SkillPlazaPage /></ProtectedDashboard>} />
        <Route path="/settings" element={<ProtectedDashboard><SettingsPage /></ProtectedDashboard>} />
        <Route path="/help" element={<ProtectedDashboard><HelpPage /></ProtectedDashboard>} />

        {/* 详情类页面：都嵌在侧边栏右侧的内容区里，不再整页接管 */}
        <Route path="/skills/:id" element={<ProtectedDashboard><SkillChatPage /></ProtectedDashboard>} />
        <Route path="/agents/:id/chat" element={<ProtectedDashboard><ChatPage /></ProtectedDashboard>} />

        {/* Fallback */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>

      {/* Toast Notifications */}
      <Toast />
    </BrowserRouter>
  )
}
