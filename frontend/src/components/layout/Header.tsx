import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Button } from '../ui/Button'
// 原来这里 import 了 ArrowRight / Play / Shield / Zap / Users 五个图标，
// 但函数体里一个都没用到 —— 属于死了的 import，顺手清掉。
import { Github, Menu, X } from 'lucide-react'
import { Logo } from '../layout/Logo'
import { GITHUB_REPO_URL } from '../../lib/links'

const NAV_LINKS = [
  { href: '#features', label: '功能' },
  { href: '#templates', label: '模板' },
  { href: '#pricing', label: '定价' },
  { href: '#docs', label: '文档' },
]

export function Header() {
  // 移动端菜单。
  //
  // 改造前导航是 `hidden md:flex`，手机上这些链接**一个都点不到**；而
  // 「登录」按钮又是 `hidden sm:inline-flex`，640px 以下的手机同样没有入口。
  // 也就是说最小的屏幕上，落地页除了「免费开始」之外没有任何可去的地方。
  const [mobileOpen, setMobileOpen] = useState(false)
  const close = () => setMobileOpen(false)

  return (
    <header className="fixed top-0 left-0 right-0 z-50">
      {/* Backdrop blur */}
      <div className="absolute inset-0 bg-white/80 backdrop-blur-xl border-b border-slate-200/50" />

      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16 lg:h-18">
          {/* Logo：复用 Logo 组件。
              这里以前内联了一份，漏写 bg-clip-text/text-transparent 导致黑字黑底。
              tone="light"：本页顶栏永远是浅色底，即使根元素被切到 dark
              也要用深色字标，否则浅字压浅底看不见。 */}
          <Link to="/" className="group" onClick={close}>
            <Logo size="sm" tone="light" />
          </Link>

          {/* Navigation - Desktop */}
          <nav className="hidden md:flex items-center gap-8">
            {NAV_LINKS.map((item) => (
              <a
                key={item.href}
                href={item.href}
                className="text-sm font-medium text-slate-600 hover:text-slate-900 transition-colors"
              >
                {item.label}
              </a>
            ))}
          </nav>

          {/* Actions */}
          <div className="flex items-center gap-3">
            {/* GitHub 仓库 */}
            <a
              href={GITHUB_REPO_URL}
              target="_blank"
              rel="noopener noreferrer"
              aria-label="在 GitHub 上查看 AgentFlow"
              title="GitHub 仓库"
              className="p-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-600 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700 transition-all hover:scale-105"
            >
              <Github className="w-5 h-5" />
            </a>

            {/* Theme Toggle */}
            <button
              className="p-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-600 transition-all hover:scale-105"
              onClick={() => document.documentElement.classList.toggle('dark')}
              aria-label="切换主题"
            >
              <svg className="w-5 h-5 hidden dark:block" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4 8a4 4 0 11-8 0 4 4 0 018 0zm-.464 4.95l.707.707a1 1 0 001.414-1.414l-.707-.707a1 1 0 00-1.414 1.414zm2.12-10.607a1 1 0 010 1.414l-.706.707a1 1 0 11-1.414-1.414l.707-.707a1 1 0 011.414 0zM17 11a1 1 0 100-2h-1a1 1 0 100 2h1zm-7 4a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zM5.05 6.464A1 1 0 106.465 5.05l-.708-.707a1 1 0 00-1.414 1.414l.707.707zm1.414 8.486l-.707.707a1 1 0 01-1.414-1.414l.707-.707a1 1 0 011.414 1.414zM4 11a1 1 0 100-2H3a1 1 0 100 2h1z" clipRule="evenodd" />
              </svg>
              <svg className="w-5 h-5 dark:hidden" fill="currentColor" viewBox="0 0 20 20">
                <path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z" />
              </svg>
            </button>

            {/* Login */}
            <Link to="/login">
              <Button variant="ghost" size="sm" className="hidden sm:inline-flex">
                登录
              </Button>
            </Link>

            {/* Register */}
            <Link to="/register">
              <Button size="sm" className="shadow-lg shadow-brand-500/25">
                免费开始
              </Button>
            </Link>

            {/* 汉堡按钮：只在手机上出现。放在最右边，和「免费开始」并列 */}
            <button
              type="button"
              onClick={() => setMobileOpen((v) => !v)}
              aria-label="菜单"
              aria-expanded={mobileOpen}
              className="md:hidden p-2.5 -mr-1 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-600 transition-colors"
            >
              {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>
        </div>
      </div>

      {/*
        移动端下拉菜单。挂在 header 下沿（h-16 = 64px），不占文档流 ——
        顶栏是 fixed 的，所以面板也得绝对定位，否则会把首屏内容顶下去。

        这里刻意用整块不透明底色而不是半透明：面板叠在正文上，透出来会花。
      */}
      {mobileOpen && (
        <div
          className="md:hidden absolute left-0 right-0 top-16 lg:top-18
            bg-white dark:bg-slate-950 border-b border-slate-200 dark:border-slate-800
            shadow-lg animate-slide-down"
        >
          <nav className="max-w-7xl mx-auto px-4 sm:px-6 py-2">
            {NAV_LINKS.map((item) => (
              <a
                key={item.href}
                href={item.href}
                onClick={close}
                className="block px-2 py-3 rounded-lg text-sm font-medium text-slate-700
                  hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800 transition-colors"
              >
                {item.label}
              </a>
            ))}
            {/* 手机上「登录」按钮被 sm:inline-flex 藏了，菜单里补一个 */}
            <Link
              to="/login"
              onClick={close}
              className="block px-2 py-3 rounded-lg text-sm font-medium text-slate-700
                hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800 transition-colors
                border-t border-slate-100 dark:border-slate-800 mt-1"
            >
              登录
            </Link>
            <a
              href={GITHUB_REPO_URL}
              target="_blank"
              rel="noopener noreferrer"
              onClick={close}
              className="flex items-center gap-2 px-2 py-3 rounded-lg text-sm font-medium text-slate-700
                hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800 transition-colors"
            >
              <Github className="w-4 h-4" />
              GitHub 仓库
            </a>
          </nav>
        </div>
      )}
    </header>
  )
}
