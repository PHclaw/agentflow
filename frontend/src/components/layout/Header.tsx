import { Link } from 'react-router-dom'
import { Button } from '../ui/Button'
import { ArrowRight, Play, Sparkles, Shield, Zap, Users } from 'lucide-react'
import { Logo } from '../layout/Logo'

export function Header() {
  return (
    <header className="fixed top-0 left-0 right-0 z-50">
      {/* Backdrop blur */}
      <div className="absolute inset-0 bg-white/80 backdrop-blur-xl border-b border-slate-200/50" />
      
      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16 lg:h-18">
          {/* Logo */}
          <Link to="/" className="flex items-center gap-3 group">
            <div className="relative">
              <div className="absolute -inset-1 bg-gradient-to-r from-indigo-500 to-purple-500 rounded-xl blur opacity-30 group-hover:opacity-50 transition-opacity" />
              <div className="relative bg-gradient-to-br from-indigo-500 to-purple-600 p-2 rounded-xl">
                <Sparkles className="w-5 h-5 text-white" />
              </div>
            </div>
            <span className="text-xl font-bold bg-gradient-to-r from-slate-900 to-slate-700 group-hover:from-indigo-600 group-hover:to-purple-600 transition-all">
              AgentFlow
            </span>
          </Link>

          {/* Navigation - Desktop */}
          <nav className="hidden md:flex items-center gap-8">
            <a href="#features" className="text-sm font-medium text-slate-600 hover:text-slate-900 transition-colors">
              功能
            </a>
            <a href="#templates" className="text-sm font-medium text-slate-600 hover:text-slate-900 transition-colors">
              模板
            </a>
            <a href="#pricing" className="text-sm font-medium text-slate-600 hover:text-slate-900 transition-colors">
              定价
            </a>
            <a href="#" className="text-sm font-medium text-slate-600 hover:text-slate-900 transition-colors">
              文档
            </a>
          </nav>

          {/* Actions */}
          <div className="flex items-center gap-3">
            {/* Theme Toggle */}
            <button
              className="p-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-600 transition-all hover:scale-105"
              onClick={() => document.documentElement.classList.toggle('dark')}
              aria-label="切换主题"
            >
              <svg className="w-5 h-5 hidden dark:block" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4 8a4 4 0 11-8 0 4 4 0 018 0zm-.464 4.95l.707.707a1 1 0 001.414-1.414l-.707-.707a1 1 0 00-1.414 1.414zm2.12-10.607a1 1 0 010 1.414l-.706.707a1 1 0 11-1.414-1.414l.707-.707a1 1 0 011.414 0zM17 11a1 1 0 100-2h-1a1 1 0 100 2h1zm-7 4a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zM5.05 6.464A1 1 0 106.465 5.05l-.708-.707a1 1 0 00-1.414 1.414l.707.707zm1.414 8.486l-.707.707a1 1 0 01-1.414-1.414l.707-.707a1 1 0 011.414 1.414zM4 11a1 1 0 100-2H3a1 1 0 000 2h1z" clipRule="evenodd" />
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
              <Button size="sm" className="shadow-lg shadow-indigo-500/25">
                免费开始
              </Button>
            </Link>
          </div>
        </div>
      </div>
    </header>
  )
}
