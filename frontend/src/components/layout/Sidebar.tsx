import { useEffect, useState } from 'react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
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
  LayoutTemplate,
  LogOut,
  History,
  Shield,
  X,
  Github,
} from 'lucide-react'
import { Logo, LogoSmall } from './Logo'
import { GITHUB_REPO_URL } from '../../lib/links'
import { Button } from '../ui/Button'
import { agents as agentsApi, auth } from '../../services/api'
import { useAuthStore, useIsAdmin } from '../../stores'

interface RecentAgent {
  id: string
  name: string
  description?: string
}

const navItems = [
  { icon: LayoutDashboard, label: '控制台', href: '/dashboard' },
  { icon: MessageSquare, label: 'Agent', href: '/agents' },
  // 历史对话原先没有任何入口，/conversations 只是重复渲染 Agent 列表
  { icon: History, label: '对话记录', href: '/conversations' },
  { icon: Sparkles, label: 'Skill 广场', href: '/skills' },
  { icon: Workflow, label: '工作流', href: '/workflow/new' },
  // 模板市场原先只从落地页能进，登录后在应用里没有任何入口
  { icon: LayoutTemplate, label: '模板市场', href: '/templates' },
  { icon: FileText, label: '知识库', href: '/knowledge' },
]

const bottomNavItems = [
  { icon: Settings, label: '设置', href: '/settings' },
  { icon: HelpCircle, label: '帮助', href: '/help' },
]

/**
 * 管理后台入口，只对管理员显示。
 *
 * 这只是体验层：让普通用户看不到后台入口，避免误点后拿到一屏 403。
 * 真正的权限在后端 require_admin —— 前端隐藏不等于禁止。
 */
const adminNavItem = { icon: Shield, label: '管理后台', href: '/admin' }

interface SidebarProps {
  /** 折叠状态由 AppLayout 持有：内容区的左边距必须跟着一起变，否则会留出空隙 */
  collapsed?: boolean
  onToggleCollapsed?: (collapsed: boolean) => void
  /**
   * 移动端抽屉是否拉开。
   *
   * 手机（<lg）上侧边栏是**离屏抽屉**：默认整个推到屏幕外，只留顶栏的汉堡
   * 按钮把它拉出来。改造前它是 `fixed w-60` 且没有任何收起手段 —— 在 375px
   * 宽的手机上，240px 的侧边栏直接盖住六成内容，而且用户没有办法把它关掉。
   */
  mobileOpen?: boolean
  /** 关闭移动端抽屉。点了导航项、点了遮罩、按了 Esc 都会调它 */
  onCloseMobile?: () => void
}

export function Sidebar({
  collapsed: collapsedProp,
  onToggleCollapsed,
  mobileOpen = false,
  onCloseMobile,
}: SidebarProps = {}) {
  const [collapsedState, setCollapsedState] = useState(false)
  const collapsed = collapsedProp ?? collapsedState
  const location = useLocation()
  const navigate = useNavigate()
  const logout = useAuthStore((s) => s.logout)
  const isAdmin = useIsAdmin()
  const [recentAgents, setRecentAgents] = useState<RecentAgent[]>([])

  const items = isAdmin ? [...navItems, adminNavItem] : navItems

  const toggleCollapsed = () => {
    const next = !collapsed
    setCollapsedState(next)
    onToggleCollapsed?.(next)
  }

  /** 点了任何一个导航项都该把抽屉收起来 —— 否则它盖着刚跳转过去的页面。 */
  const closeMobile = () => onCloseMobile?.()

  // Esc 关抽屉。移动端没有「点外面」的习惯，键盘（外接键盘/无障碍）至少要有
  // 一条不依赖鼠标的退出路径。
  useEffect(() => {
    if (!mobileOpen) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeMobile()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [mobileOpen])

  // 「最近」此前是写死的假数据（智能客服助手 / HR 工作台 / 产品推荐），
  // 点了没有任何反应。改为拉取该账号真实的 Agent。
  useEffect(() => {
    let cancelled = false
    agentsApi
      .list({ limit: 3 })
      .then((data: any) => {
        if (cancelled) return
        const list = Array.isArray(data) ? data : data?.items ?? data?.agents ?? []
        setRecentAgents(list.slice(0, 3))
      })
      .catch(() => {
        if (!cancelled) setRecentAgents([])
      })
    return () => {
      cancelled = true
    }
  }, [location.pathname])

  const handleLogout = () => {
    auth.logout()
    logout()
    navigate('/login')
  }

  /**
   * 侧边栏是「框架」，不是内容区 —— 所以这里一个强调色都不用。
   *
   * 旧版选中项是 `bg-gradient-to-r from-brand-500 to-brand-600` 外加
   * `shadow-lg shadow-brand-500/20` 的彩色光晕，整条侧边栏从头亮到尾，
   * 和内容区抢注意力；而且这层强调色和 logo 的青蓝、按钮的靛蓝三处并置，
   * 反而谁都不突出。
   *
   * 选中态改用「底色加深 + 文字变深」表达，够清楚且不吵。侧边栏里唯一的
   * 颜色是左上角的 logo —— 那是品牌该出现的位置。
   */
  /**
   * 导航项样式。参考 Kimi 侧边栏：
   *
   * - **不用色块标选中**。原来选中项是一整块 bg-slate-200，一列下来像贴了
   *   几张膏药；现在只靠「文字变深 + 加粗」区分，底色最多给到极淡的一层。
   * - **hover 也压到很淡**，避免鼠标划过时整列闪。
   * - 图标与文字之间留白稍大，靠间距而不是分割线分组。
   */
  /**
   * 导航项样式。参考 Kimi 侧边栏：
   *
   * - **不用色块标选中**。原来选中项是一整块 bg-slate-200，一列下来像贴了
   *   几张膏药；现在只靠「文字变深 + 加粗」区分，底色最多给到极淡的一层。
   * - **hover 也压到很淡**，避免鼠标划过时整列闪。
   * - 图标与文字之间留白稍大，靠间距而不是分割线分组。
   *
   * 手机上用 `py-2.5` 把点击区撑到 40px 左右：桌面上 36px 用鼠标刚好，
   * 但手指按 36px 的目标容易点偏，而抽屉里点偏的代价是跳去错的页面。
   */
  const itemBase =
    'flex items-center gap-3 rounded-lg text-[13px] transition-colors duration-150 px-2 py-2.5 lg:py-2'
  const itemIdle =
    'text-slate-600 hover:bg-slate-100/70 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800/60 dark:hover:text-slate-100'
  const itemActive =
    'text-slate-900 font-semibold bg-slate-200/50 dark:text-white dark:bg-slate-800/50'

  /** 分组标题：Kimi 里就是一行灰色小字，不大写、不加字距、不加粗。 */
  const sectionLabel = 'px-2 mb-1 text-xs text-slate-400 dark:text-slate-500'

  const isItemActive = (href: string) =>
    location.pathname === href || location.pathname.startsWith(href + '/')

  return (
    <aside
      className={`fixed left-0 top-0 z-50 flex flex-col
        h-[100dvh]
        transition-[width,transform] duration-200
        bg-white dark:bg-slate-950 border-r border-slate-200 dark:border-slate-800
        w-72 ${collapsed ? 'lg:w-[60px]' : 'lg:w-60'}
        ${mobileOpen ? 'translate-x-0' : '-translate-x-full'} lg:translate-x-0`}
    >
      {/*
        Logo：统一走 Logo 组件，避免这里另写一份而出现样式不一致。

        移动端这一行比桌面多一个「关闭」按钮：抽屉拉开后总得有个明显的收起
        入口，只靠遮罩不够 —— 遮罩在很矮的屏幕上可能被抽屉自己占满。
      */}
      <div
        className={`h-14 flex items-center shrink-0 ${
          collapsed ? 'justify-center px-2' : 'justify-between px-3'
        }`}
      >
        {!collapsed ? (
          <NavLink
            to="/"
            onClick={closeMobile}
            className="min-w-0 rounded-lg -ml-1 px-1 py-1 hover:bg-slate-200 dark:hover:bg-slate-800 transition-colors"
          >
            <Logo size="sm" />
          </NavLink>
        ) : (
          <NavLink to="/" onClick={closeMobile} title="AgentFlow" className="rounded-lg hover:bg-slate-200 dark:hover:bg-slate-800 transition-colors">
            <LogoSmall />
          </NavLink>
        )}
        <div className="flex items-center gap-1">
          {/* 折叠按钮只给桌面：手机上抽屉要么全开要么全关，没有中间态 */}
          <button
            onClick={toggleCollapsed}
            aria-label={collapsed ? '展开侧边栏' : '收起侧边栏'}
            className="hidden lg:block p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-200 dark:hover:text-slate-200 dark:hover:bg-slate-800 transition-colors"
          >
            {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
          </button>
          <button
            onClick={closeMobile}
            aria-label="关闭菜单"
            className="lg:hidden p-2 -mr-1 rounded-lg text-slate-500 hover:text-slate-700 hover:bg-slate-200 dark:text-slate-400 dark:hover:text-slate-200 dark:hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/*
        Quick create —— 仿 Kimi 侧边栏的「新建会话」：

        - **通栏描边按钮**而不是实色填充。实色按钮在侧边栏里视觉重量太大，
          会把导航和内容区都压下去；描边 + 白底只占「一个可点的入口」的分量。
        - 不放快捷键提示。用户不想要那个角标，快捷键监听也随之移除 ——
          提示和功能必须同时存在，缺了任何一个都是残留。
      */}
      <div className="px-3 pt-1 pb-2">
        {!collapsed ? (
          <NavLink to="/agents/new">
            <Button
              className="w-full justify-center"
              variant="outline"
              size="md"
              leftIcon={<Plus className="w-4 h-4" />}
            >
              创建 Agent
            </Button>
          </NavLink>
        ) : (
          <NavLink to="/agents/new" title="创建 Agent">
            <Button className="w-full" size="sm" variant="outline">
              <Plus className="w-4 h-4" />
            </Button>
          </NavLink>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 overflow-y-auto">
        <div className="space-y-1">
          {items.map((item) => (
            <NavLink
              key={item.href}
              to={item.href}
              onClick={closeMobile}
              title={collapsed ? item.label : undefined}
              className={`${itemBase} ${isItemActive(item.href) ? itemActive : itemIdle}`}
            >
              <item.icon className="w-4 h-4 flex-shrink-0" strokeWidth={1.75} />
              {!collapsed && <span className="truncate">{item.label}</span>}
            </NavLink>
          ))}
        </div>

        {!collapsed && (
          <div className="mt-7">
            <h3 className={sectionLabel}>最近</h3>
            <div className="space-y-1">
              {recentAgents.length === 0 ? (
                <p className="px-2 py-1.5 text-xs text-slate-400 dark:text-slate-500">暂无 Agent</p>
              ) : (
                recentAgents.map((agent) => (
                  <button
                    key={agent.id}
                    onClick={() => {
                      navigate(`/agents/${agent.id}/chat`)
                      closeMobile()
                    }}
                    title={agent.description || agent.name}
                    className={`w-full flex items-center gap-3 px-2 py-2 rounded-lg text-[13px] transition-colors ${
                      location.pathname === `/agents/${agent.id}/chat`
                        ? itemActive
                        : itemIdle
                    }`}
                  >
                    {/* 首字母块：Kimi 里「对话」列表就是纯文字，这里保留一个小色块
                        是为了和上面的导航图标区分开 —— 纯文字会看不出是哪一级。 */}
                    <span className="w-5 h-5 flex-shrink-0 rounded-md bg-slate-200/80 dark:bg-slate-800 text-slate-500 dark:text-slate-400 text-2xs font-semibold flex items-center justify-center">
                      {agent.name.slice(0, 1)}
                    </span>
                    <span className="truncate">{agent.name}</span>
                  </button>
                ))
              )}
            </div>
          </div>
        )}
      </nav>

      {/* Bottom navigation —— 分割线也去掉，改用上边距分组（Kimi 无此区，
          但「设置/帮助/退出」总得有个收尾的位置，用留白区分最轻）。

          pb 带上安全区：iPhone 底部那条小黑条会盖住最后一项，没有这层内边距
          的话「退出登录」在最下面一排就是点不中的状态。 */}
      <div className="px-3 pt-2 pb-3 pb-[calc(0.75rem+env(safe-area-inset-bottom))]">
        <div className="space-y-1">
          {bottomNavItems.map((item) => (
            <NavLink
              key={item.href}
              to={item.href}
              onClick={closeMobile}
              title={collapsed ? item.label : undefined}
              className={`${itemBase} ${isItemActive(item.href) ? itemActive : itemIdle}`}
            >
              <item.icon className="w-4 h-4 flex-shrink-0" strokeWidth={1.75} />
              {!collapsed && <span className="truncate">{item.label}</span>}
            </NavLink>
          ))}
          <a
            href={GITHUB_REPO_URL}
            target="_blank"
            rel="noopener noreferrer"
            title={collapsed ? 'GitHub 仓库' : undefined}
            className={`${itemBase} ${itemIdle}`}
          >
            <Github className="w-4 h-4 flex-shrink-0" strokeWidth={1.75} />
            {!collapsed && <span className="truncate">GitHub 仓库</span>}
          </a>
          <button
            type="button"
            onClick={() => {
              handleLogout()
              closeMobile()
            }}
            title={collapsed ? '退出登录' : undefined}
            className={`w-full ${itemBase} text-slate-600 dark:text-slate-400 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950/40 dark:hover:text-red-400`}
          >
            <LogOut className="w-4 h-4 flex-shrink-0" strokeWidth={1.75} />
            {!collapsed && <span>退出登录</span>}
          </button>
        </div>
      </div>
    </aside>
  )
}
