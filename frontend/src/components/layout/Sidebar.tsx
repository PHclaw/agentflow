import { useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { 
  LayoutDashboard, 
  Users, 
  BarChart3, 
  Settings, 
  MessageSquare,
  BookOpen,
  ChevronLeft,
  ChevronRight,
  Plus,
  Workflow,
  Bell,
  HelpCircle,
  Sparkles,
  FileText,
} from 'lucide-react'
import { Logo } from './Logo'
import { Button } from '../ui/Button'

const navItems = [
  { icon: LayoutDashboard, label: '控制台', href: '/dashboard' },
  { icon: MessageSquare, label: 'Agent', href: '/agents' },
  { icon: Workflow, label: '工作流', href: '/workflow/new' },
  { icon: FileText, label: '知识库', href: '/knowledge' },
]

const bottomNavItems = [
  { icon: Settings, label: '设置', href: '/settings' },
  { icon: HelpCircle, label: '帮助', href: '/help' },
]

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false)
  const location = useLocation()

  return (
    <aside
      className={`fixed left-0 top-0 h-screen bg-white border-r border-slate-200 transition-all duration-300 z-40 flex flex-col ${
        collapsed ? 'w-20' : 'w-64'
      }`}
    >
      {/* Logo */}
      <div className="h-16 flex items-center justify-between px-4 border-b border-slate-100">
        {!collapsed && (
          <NavLink to="/" className="flex items-center gap-3 group">
            <div className="relative">
              <div className="absolute -inset-1 bg-gradient-to-r from-indigo-500 to-purple-500 rounded-xl blur opacity-30 group-hover:opacity-50 transition-opacity" />
              <div className="relative bg-gradient-to-br from-indigo-500 to-purple-600 p-2 rounded-xl">
                <Sparkles className="w-5 h-5 text-white" />
              </div>
            </div>
            <span className="text-xl font-bold bg-gradient-to-r from-slate-900 to-slate-700">
              AgentFlow
            </span>
          </NavLink>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="p-2 rounded-xl hover:bg-slate-100 text-slate-400 hover:text-slate-600 transition-all"
        >
          {collapsed ? (
            <ChevronRight className="w-5 h-5" />
          ) : (
            <ChevronLeft className="w-5 h-5" />
          )}
        </button>
      </div>

      {/* Quick create */}
      <div className="p-4">
        {!collapsed ? (
          <NavLink to="/agents/new">
            <Button className="w-full shadow-lg shadow-indigo-500/20" leftIcon={<Plus className="w-4 h-4" />}>
              创建 Agent
            </Button>
          </NavLink>
        ) : (
          <NavLink to="/agents/new">
            <Button className="w-full" size="sm">
              <Plus className="w-4 h-4" />
            </Button>
          </NavLink>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 overflow-y-auto">
        <div className="space-y-1">
          {navItems.map((item) => (
            <NavLink
              key={item.href}
              to={item.href}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all group ${
                  isActive || location.pathname.startsWith(item.href)
                    ? 'bg-gradient-to-r from-indigo-500 to-purple-600 text-white shadow-lg shadow-indigo-500/20'
                    : 'text-slate-600 hover:bg-slate-100'
                }`
              }
            >
              <item.icon className="w-5 h-5 flex-shrink-0" />
              {!collapsed && <span>{item.label}</span>}
            </NavLink>
          ))}
        </div>

        {!collapsed && (
          <div className="mt-8">
            <h3 className="px-3 text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
              最近
            </h3>
            <div className="space-y-1">
              {[
                { name: '智能客服助手', avatar: '🤖' },
                { name: 'HR 工作台', avatar: '👥' },
                { name: '产品推荐', avatar: '🛍️' },
              ].map((agent) => (
                <button
                  key={agent.name}
                  className="w-full flex items-center gap-3 px-3 py-2 rounded-xl text-sm text-slate-600 hover:bg-slate-50 transition-all"
                >
                  <span className="text-lg">{agent.avatar}</span>
                  <span className="truncate">{agent.name}</span>
                </button>
              ))}
            </div>
          </div>
        )}
      </nav>

      {/* Bottom navigation */}
      <div className="p-3 border-t border-slate-100">
        <div className="space-y-1">
          {bottomNavItems.map((item) => (
            <NavLink
              key={item.href}
              to={item.href}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all ${
                  isActive
                    ? 'bg-indigo-50 text-indigo-600'
                    : 'text-slate-600 hover:bg-slate-100'
                }`
              }
            >
              <item.icon className="w-5 h-5 flex-shrink-0" />
              {!collapsed && <span>{item.label}</span>}
            </NavLink>
          ))}
        </div>
      </div>
    </aside>
  )
}
