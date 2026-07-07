import { Sidebar } from './Sidebar'

interface AppLayoutProps {
  children: React.ReactNode
  hideSidebar?: boolean
}

export function AppLayout({ children, hideSidebar = false }: AppLayoutProps) {
  return (
    <div className="min-h-screen bg-slate-50">
      {!hideSidebar && <Sidebar />}
      <main className={`${hideSidebar ? '' : 'lg:ml-64'}`}>
        {children}
      </main>
    </div>
  )
}

export function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-indigo-50/30 to-purple-50/30">
      {children}
    </div>
  )
}
