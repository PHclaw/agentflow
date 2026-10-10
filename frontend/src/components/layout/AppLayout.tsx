import { useState } from 'react'
import { Sidebar } from './Sidebar'

interface AppLayoutProps {
  children: React.ReactNode
  hideSidebar?: boolean
}

export function AppLayout({ children, hideSidebar = false }: AppLayoutProps) {
  // 折叠状态放在这里：Sidebar 是 fixed 定位，内容区靠 margin 让位，
  // 两边必须用同一个状态，否则折叠后内容区会残留 176px 空隙。
  // lg:ml-64 对应 w-64，lg:ml-20 对应 w-20。
  const [collapsed, setCollapsed] = useState(false)

  return (
    <div className="min-h-screen bg-slate-50">
      {!hideSidebar && (
        <Sidebar collapsed={collapsed} onToggleCollapsed={setCollapsed} />
      )}
      <main
        className={`transition-all duration-300 ${
          hideSidebar ? '' : collapsed ? 'lg:ml-20' : 'lg:ml-64'
        }`}
      >
        {children}
      </main>
    </div>
  )
}

export function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-brand-50/30 to-brand-50/30">
      {children}
    </div>
  )
}
