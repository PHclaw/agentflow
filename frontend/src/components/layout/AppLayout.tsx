import { useEffect, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { Menu } from 'lucide-react'
import { Sidebar } from './Sidebar'
import { BottomNav } from './BottomNav'
import { Logo } from './Logo'
import { useAuthStore } from '../../stores'

interface AppLayoutProps {
  children: React.ReactNode
  hideSidebar?: boolean
}

/**
 * 应用外壳。
 *
 * 移动端的两条主线
 * ----------------
 * 1. **侧边栏在 < lg 变成离屏抽屉**。原本它是 `fixed w-60` 且内容区只在
 *    `lg:` 以上让位 —— 375px 的手机上 240px 的侧边栏直接盖住六成内容，
 *    且没有任何收起的办法。现在默认推到屏幕外，由顶栏汉堡按钮拉出。
 * 2. **底部是全局导航栏**（`BottomNav`），五项核心入口常驻。
 *
 * 为什么根容器是纵向 flex，而不是让各页自己 `h-screen`
 * ----------------------------------------------------
 * 有三个页面（对话、技能对话、工作流编辑器）是**满高**的：它们内部靠
 * `overflow-y-auto` 自行滚动，而不是让整篇文档滚。这类页面必须拿到一个
 * **确定的**高度，否则底部会被切掉。
 *
 * 改动前它们写的是 `h-screen` —— 而它们渲染在带 56px 移动顶栏的 `main`
 * 里，`h-screen` 等于「整个视口高」，于是页面比可用空间高出正好一个顶栏，
 * 底部（对话页就是输入框）被切在屏幕外。加上底部导航后会再切掉 56px。
 *
 * 现在的做法：根容器 `min-h-[100dvh] flex flex-col`，`main` 是
 * `flex-1 min-h-0` —— 它拿到的高度天然就是「视口 - 顶栏 - 底栏内边距」，
 * 满高页面只需写 `h-full`。这样无论顶栏/底栏以后怎么改，高度都是自动
 * 对齐的，不用在三处硬编码 `calc(100dvh - Nrem)`。
 *
 * 底部预留放在 `main` 上（而不是让每个页面自己加 spacer），新增页面
 * 不会忘记让位。
 */
export function AppLayout({ children, hideSidebar = false }: AppLayoutProps) {
  // 折叠状态放在这里：Sidebar 是 fixed 定位，内容区靠 margin 让位，
  // 两边必须用同一个状态，否则折叠后内容区会残留空隙。
  //
  // lg:ml-60 对应 Sidebar 的 w-60，lg:ml-[60px] 对应折叠态的 w-[60px]。
  // 这两对数值必须与 Sidebar.tsx 里的宽度**同时改** —— 只改一边的话
  // 内容区会偏移，侧边栏压住或留白。
  const [collapsed, setCollapsed] = useState(false)
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  /** 滚动容器本体。抽屉打开时要连它一起锁（见下面的 effect）。 */
  const mainRef = useRef<HTMLElement>(null)
  const fetchMe = useAuthStore((s) => s.fetchMe)
  const location = useLocation()

  // 进应用时同步一次用户资料。persist 缓存的 user 是「登录那一刻」的，
  // 角色若在那之后才被授予（或被后端按配置补上），前端就一直是旧的，
  // 管理后台入口不会出现。
  useEffect(() => {
    fetchMe()
  }, [fetchMe])

  // 抽屉打开时锁住背后的滚动。不锁的话，手指在抽屉上往上滑，滚的是页面，
  // 抽屉看起来像长在页面上一样 —— 而且滑到底会露出抽屉外的内容。
  //
  // 注意这里**同时锁 body 和 main**：滚动容器已经换成了 main（见下面 main 的
  // 说明），只锁 body 是挡不住的 —— body 本身根本不可滚，锁了等于没锁，
  // 背后的页面照样会滚。
  useEffect(() => {
    if (!mobileNavOpen) return
    const bodyOverflow = document.body.style.overflow
    const mainEl = mainRef.current
    const mainOverflow = mainEl?.style.overflow
    document.body.style.overflow = 'hidden'
    if (mainEl) mainEl.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = bodyOverflow
      if (mainEl) mainEl.style.overflow = mainOverflow ?? ''
    }
  }, [mobileNavOpen])

  // 路由一变就收抽屉。放在这一层而不是 Sidebar 里：路由变化是布局层面的事，
  // 而且这样连「浏览器后退」都能一并收起。
  useEffect(() => {
    setMobileNavOpen(false)
  }, [location.pathname])

  return (
    /*
      `h-[100dvh]` 而不是 `min-h-[100dvh]` —— 这一字之差是桌面端的修复点。

      满高页面（对话、技能对话、工作流编辑器）内部写的是 `h-full`，也就是
      `height: 100%`。**百分比高度需要父级有确定高度**：`min-height` 只是给
      了个下限，不构成"确定高度"，于是 `h-full` 会退回 `auto`。
      后果是那些页面塌成"内容高度" —— 工作流页面尤其明显：画布本身没有
      固有高度，就只剩左右两栏的内容高度，画布被压成一条，
      ReactFlow 的小地图和缩放控件于是漂在画布中间。

      改成 `h-100dvh` 之后，main 通过 `flex-1` 拿到的就是确定高度，
      `h-full` 正常解析，满高页面重新填满视口。
    */
    <div className="h-[100dvh] flex flex-col bg-slate-50 dark:bg-slate-950 overflow-hidden">
      {!hideSidebar && (
        <>
          {/*
            移动端顶栏。`lg:hidden` —— 桌面端侧边栏常驻，这一整行都不该出现。
            sticky 而不是 fixed：让它留在文档流里，下面的内容自然被推开。
          */}
          <header
            className="lg:hidden sticky top-0 z-30 shrink-0 h-14 flex items-center gap-3 px-3
              bg-white/85 dark:bg-slate-950/85 backdrop-blur-xl
              border-b border-slate-200/80 dark:border-slate-800
              pt-[env(safe-area-inset-top)]"
          >
            <button
              type="button"
              onClick={() => setMobileNavOpen(true)}
              aria-label="打开菜单"
              className="p-2 -ml-1 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-100
                dark:text-slate-300 dark:hover:text-white dark:hover:bg-slate-800 transition-colors"
            >
              <Menu className="w-5 h-5" />
            </button>
            <Logo size="sm" />
          </header>

          {/*
            遮罩。z-40 夹在顶栏(z-30)和抽屉(z-50)之间 —— 所以抽屉拉开时它
            也盖住顶栏，点顶部区域同样能关，符合「点外面关掉」的直觉。
          */}
          {mobileNavOpen && (
            <div
              className="lg:hidden fixed inset-0 z-40 bg-black/40 backdrop-blur-[2px]
                animate-fade-in"
              onClick={() => setMobileNavOpen(false)}
              aria-hidden="true"
            />
          )}

          <Sidebar
            collapsed={collapsed}
            onToggleCollapsed={setCollapsed}
            mobileOpen={mobileNavOpen}
            onCloseMobile={() => setMobileNavOpen(false)}
          />
        </>
      )}

      {/*
        内容区。**它自己就是滚动容器**（`overflow-y-auto`），而不是让整篇
        文档滚 —— 这样 main 才能拿到一个确定高度，满高页面里的 `h-full`
        才解析得出来（详见根容器那里的说明）。

        几个类都不能省：
        - `flex-1 min-h-0`：拿到「视口 - 顶栏」的确定高度；
          `min-h-0` 不可省，flex 子项默认 `min-height:auto` 会被内容撑开，
          那样 `overflow-y-auto` 永远不会生效
        - `overscroll-contain`：滚到底不要把滚动传给 body，否则移动端会出现
          「页面滚到头之后整页跟着弹一下」
        - 底部内边距只在移动端留：那是给底部导航让位的。桌面端导航已隐藏
          （侧边栏已覆盖同样的入口），所以 `lg:pb-0`
      */}
      <main
        ref={mainRef}
        className={`flex-1 min-h-0 overflow-y-auto overscroll-contain
          transition-[margin] duration-200
          pb-[calc(3.5rem+env(safe-area-inset-bottom))] lg:pb-0
          ${hideSidebar ? '' : collapsed ? 'lg:ml-[60px]' : 'lg:ml-60'}`}
      >
        {children}
      </main>

      {!hideSidebar && <BottomNav />}
    </div>
  )
}

export function AuthLayout({ children }: { children: React.ReactNode }) {
  // 原先是 from-brand-50/30 叠 brand 渐变；强调色现在只有一个，
  // 登录页不需要靠彩色底来区分 —— 中性渐变即可。
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-950 dark:to-slate-900">
      {children}
    </div>
  )
}
