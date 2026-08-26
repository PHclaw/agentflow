import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Toast } from './components/ui/Toast'
import { AppLayout, AuthLayout } from './components/layout'
import { ProtectedRoute } from './components/auth/ProtectedRoute'

// Pages
import HomePage from './pages/HomePage'
import DashboardPage from './pages/DashboardPage'
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
import SkillPlazaPage from './pages/SkillPlazaPage'
import SkillChatPage from './pages/SkillChatPage'

// Pages wrapper components
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
        <Route path="/templates" element={<TemplateMarket />} />
        <Route path="/pricing" element={<LandingPage />} />

        {/* Auth Routes */}
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />

        {/* Protected Routes with Sidebar */}
        <Route path="/dashboard" element={<ProtectedDashboard><DashboardPage /></ProtectedDashboard>} />
        <Route path="/agents" element={<ProtectedDashboard><AgentListPage /></ProtectedDashboard>} />
        <Route path="/agents/new" element={<ProtectedDashboard><AgentCreatePage /></ProtectedDashboard>} />
        <Route path="/agents/:id/edit" element={<ProtectedDashboard><AgentCreatePage /></ProtectedDashboard>} />
        <Route path="/conversations" element={<ProtectedDashboard><AgentListPage /></ProtectedDashboard>} />
        <Route path="/knowledge" element={<ProtectedDashboard><KnowledgePage /></ProtectedDashboard>} />
        <Route path="/skills" element={<ProtectedDashboard><SkillPlazaPage /></ProtectedDashboard>} />
        <Route path="/settings" element={<ProtectedDashboard><SettingsPage /></ProtectedDashboard>} />
        <Route path="/help" element={<ProtectedDashboard><HelpPage /></ProtectedDashboard>} />

        {/* Skill Chat - Full Screen */}
        <Route path="/skills/:id" element={<ProtectedRoute><SkillChatPage /></ProtectedRoute>} />

        {/* Chat Page - Full Screen */}
        <Route path="/agents/:id/chat" element={<ProtectedRoute><ChatPage /></ProtectedRoute>} />

        {/* Workflow Editor Page - Full Screen */}
        <Route path="/workflow/:id" element={<ProtectedRoute><WorkflowPage /></ProtectedRoute>} />

        {/* Fallback */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>

      {/* Toast Notifications */}
      <Toast />
    </BrowserRouter>
  )
}
