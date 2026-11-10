import { useEffect, useState } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Toast } from './components/ui/Toast'
import { AppLayout, AuthLayout } from './components/layout'
import { ProtectedRoute } from './components/auth/ProtectedRoute'
import { useAuthStore } from './stores'
import { agents as agentsApi } from './services/api'

// Pages
import HomePage from './pages/HomePage'
import AgentListPage from './pages/AgentListPage'
import AgentCreatePage from './pages/AgentCreatePage'
import ChatPage from './pages/ChatPage'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import SettingsPage from './pages/SettingsPage'
import HelpPage from './pages/HelpPage'
import KnowledgePage from './pages/KnowledgePage'
import WorkflowPage from './pages/WorkflowPage'
import TemplateMarket from './pages/TemplateMarket'
import ConversationListPage from './pages/ConversationListPage'
import SkillPlazaPage from './pages/SkillPlazaPage'
import SkillChatPage from './pages/SkillChatPage'
import AdminPage from './pages/AdminPage'
import AdminSkillsPage from './pages/AdminSkillsPage'
import { AdminRoute } from './components/auth/AdminRoute'

// Pages wrapper components
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

/**
 * 模板市场对两种访客都要可用：
 * - 未登录：从落地页链接进入，保持独立的整页展示
 * - 已登录：从侧边栏进入，嵌进布局，否则一点进去侧边栏就消失了
 */
function TemplateMarketRoute() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)

  if (isAuthenticated) {
    return (
      <DashboardLayout>
        <TemplateMarket />
      </DashboardLayout>
    )
  }
  return <TemplateMarket />
}

export default function Router() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Public Routes with Header/Footer */}
        <Route path="/" element={<LandingPage />} />
        <Route path="/templates" element={<TemplateMarketRoute />} />
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
        <Route path="/knowledge" element={<ProtectedDashboard><KnowledgePage /></ProtectedDashboard>} />
        <Route path="/skills" element={<ProtectedDashboard><SkillPlazaPage /></ProtectedDashboard>} />
        <Route path="/settings" element={<ProtectedDashboard><SettingsPage /></ProtectedDashboard>} />
        <Route path="/help" element={<ProtectedDashboard><HelpPage /></ProtectedDashboard>} />

        {/* 管理后台：AdminRoute 在外层，非管理员连页面都不会挂载 */}
        <Route path="/admin" element={<ProtectedDashboard><AdminRoute><AdminPage /></AdminRoute></ProtectedDashboard>} />
        <Route path="/admin/skills" element={<ProtectedDashboard><AdminRoute><AdminSkillsPage /></AdminRoute></ProtectedDashboard>} />

        {/* 详情类页面：都嵌在侧边栏右侧的内容区里，不再整页接管 */}
        <Route path="/skills/:id" element={<ProtectedDashboard><SkillChatPage /></ProtectedDashboard>} />
        <Route path="/agents/:id/chat" element={<ProtectedDashboard><ChatPage /></ProtectedDashboard>} />
        <Route path="/workflow/:id" element={<ProtectedDashboard><WorkflowPage /></ProtectedDashboard>} />

        {/* Fallback */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>

      {/* Toast Notifications */}
      <Toast />
    </BrowserRouter>
  )
}
