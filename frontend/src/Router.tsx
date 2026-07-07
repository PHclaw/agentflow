import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Toast } from './components/ui/Toast'
import { AppLayout, AuthLayout } from './components/layout'

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

// Pages wrapper components
function LandingPage() {
  return <HomePage />
}

function DashboardLayout({ children }: { children: React.ReactNode }) {
  return <AppLayout hideSidebar={false}>{children}</AppLayout>
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
        <Route path="/dashboard" element={<DashboardLayout><DashboardPage /></DashboardLayout>} />
        <Route path="/agents" element={<DashboardLayout><AgentListPage /></DashboardLayout>} />
        <Route path="/agents/new" element={<DashboardLayout><AgentCreatePage /></DashboardLayout>} />
        <Route path="/agents/:id/edit" element={<DashboardLayout><AgentCreatePage /></DashboardLayout>} />
        <Route path="/conversations" element={<DashboardLayout><AgentListPage /></DashboardLayout>} />
        <Route path="/knowledge" element={<DashboardLayout><KnowledgePage /></DashboardLayout>} />
        <Route path="/settings" element={<DashboardLayout><SettingsPage /></DashboardLayout>} />
        <Route path="/help" element={<DashboardLayout><HelpPage /></DashboardLayout>} />

        {/* Chat Page - Full Screen */}
        <Route path="/agents/:id/chat" element={<ChatPage />} />

        {/* Workflow Editor Page - Full Screen */}
        <Route path="/workflow" element={<DashboardLayout><WorkflowPage /></DashboardLayout>} />
        <Route path="/workflow/:id" element={<DashboardLayout><WorkflowPage /></DashboardLayout>} />

        {/* Fallback */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>

      {/* Toast Notifications */}
      <Toast />
    </BrowserRouter>
  )
}
