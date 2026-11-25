import React, { useEffect, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'
import clsx from 'clsx'

interface ModalProps {
  isOpen: boolean
  onClose: () => void
  title?: string
  description?: string
  children: React.ReactNode
  size?: 'sm' | 'md' | 'lg' | 'xl' | 'full'
  showClose?: boolean
  closeOnOverlay?: boolean
  closeOnEscape?: boolean
  className?: string
}

/**
 * 浮窗。
 *
 * 定位规则（按视口宽度分两档，刻意只分两档 —— 再多档位没人记得住）
 * ------------------------------------------------------------------
 *
 * | 视口         | 形态           | 定位                                  |
 * |--------------|----------------|---------------------------------------|
 * | < 640px      | 底部抽屉       | 贴底、全宽、只有上方圆角、带拖拽把手  |
 * | >= 640px     | 居中对话框     | 垂直水平居中、四角圆角、按 size 限宽  |
 *
 * 为什么手机端要用底部抽屉而不是继续居中：
 *
 * 1. **拇指够得到**。手机上单手操作时拇指的活动范围在屏幕下半部，居中的
 *    对话框把「取消 / 创建」两个按钮放在屏幕正中间，是最别扭的位置。
 * 2. **键盘不挡**。点输入框会弹出虚拟键盘，可视高度可能只剩一半；贴底的
 *    抽屉会跟着上移，而居中的对话框容易被顶到屏幕外。
 * 3. **矮视口不会挤扁**。横屏手机只有 320~430px 高，居中对话框在这个高度
 *    里又小又局促；抽屉天然占满宽度、按内容收缩。
 *
 * 视觉高度与溢出
 * --------------
 * 面板限高 `92dvh`（手机）/ `85dvh`（桌面以上），标题区固定、正文区滚动：
 *
 * - 内容超高时**内部滚动**，不会撑破视口，也不会被窗口边缘裁掉；
 * - 用 `dvh` 而不是 `vh`：移动端浏览器地址栏收放时 `vh` 不变，`dvh` 跟随
 *   可视高度，否则会出现「底部按钮被地址栏盖住」；
 * - 底部留 `env(safe-area-inset-bottom)`，iPhone 的横条不会压住按钮。
 *
 * 层级
 * ----
 * `z-[100]`：高于侧边栏与全局底部导航（z-50 / z-[70]）。改动前这里是 z-50，
 * 和侧边栏、落地页顶栏、Toast 同级 —— 同级只靠 DOM 顺序决胜，加一层元素
 * 就可能让浮窗被压在下面。层级的完整约定见 `layout/BottomNav`。
 *
 * 宽度
 * ----
 * `w-full` + `sm:max-w-*`：手机上永远是「屏幕宽 - 两侧留白」，所以 320px 的
 * 小屏也不会被固定宽度撑出横向滚动。
 */
export function Modal({
  isOpen,
  onClose,
  title,
  description,
  children,
  size = 'md',
  showClose = true,
  closeOnOverlay = true,
  closeOnEscape = true,
  className,
}: ModalProps) {
  // ESC 键关闭
  const handleEscape = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape' && closeOnEscape) {
        onClose()
      }
    },
    [onClose, closeOnEscape]
  )

  useEffect(() => {
    if (isOpen) {
      document.addEventListener('keydown', handleEscape)
      document.body.style.overflow = 'hidden'
    }

    return () => {
      document.removeEventListener('keydown', handleEscape)
      document.body.style.overflow = ''
    }
  }, [isOpen, handleEscape])

  if (!isOpen) return null

  // 限宽只在 >= 640px 生效；手机上由 w-full + 外层留白决定宽度
  const sizes = {
    sm: 'sm:max-w-sm',
    md: 'sm:max-w-md',
    lg: 'sm:max-w-lg',
    xl: 'sm:max-w-xl',
    full: 'sm:max-w-4xl',
  }

  const hasHeader = Boolean(title || description || showClose)

  const modalContent = (
    // `overscroll-contain`：内容不超高时（弹窗自带滚动容器），滚轮/滑动不会
    // 链式传给背后的 main —— 否则浮窗开着、背景页面还在滚，看着像界面失控。
    <div className="fixed inset-0 z-[100] overflow-y-auto overscroll-contain">
      {/* Overlay */}
      <div
        className="fixed inset-0 bg-black/50 backdrop-blur-sm animate-fade-in"
        onClick={closeOnOverlay ? onClose : undefined}
      />

      {/*
        定位容器。

        `min-h-full` 让它能随内容长高，超高时由最外层滚动 —— 内容永远够得着。
        手机上 items-end（贴底）+ 无内边距；>=640px 才改成居中 + p-4。
      */}
      <div className="relative flex min-h-full items-end justify-center sm:items-center sm:p-4">
        <div
          className={clsx(
            'relative flex w-full flex-col bg-white dark:bg-slate-900',
            'shadow-2xl',
            // 手机：贴底 → 只圆上方两角 + 向上滑入；桌面：四角圆角 + 缩放淡入
            'rounded-t-2xl animate-slide-up sm:rounded-2xl sm:animate-scale-in',
            // 限高 + 内部滚动的前提：面板本身是 flex 容器，正文区才能 flex-1
            'max-h-[92dvh] sm:max-h-[85dvh]',
            // 手机底部避开 iPhone 的横条
            'pb-[env(safe-area-inset-bottom)] sm:pb-0',
            sizes[size],
            className
          )}
          onClick={(e) => e.stopPropagation()}
        >
          {/*
            拖拽把手。只给手机 —— 它是「这块可以往下收」的唯一视觉暗示，
            桌面端的对话框没有这个习惯。纯装饰，不可交互（真做手势要处理
            触摸事件与滚动冲突，收益不成正比）。
          */}
          <div className="sm:hidden pt-3 pb-1 flex justify-center shrink-0">
            <span className="w-9 h-1 rounded-full bg-slate-300 dark:bg-slate-700" />
          </div>

          {/*
            Header。`shrink-0` —— 正文超高时它必须留在原地，否则滚动到一半
            用户就看不到「自己在填什么」了。
          */}
          {hasHeader && (
            <div className="flex items-start justify-between gap-4 px-4 pt-2 pb-0 sm:p-6 sm:pb-0 shrink-0">
              <div className="min-w-0">
                {title && (
                  <h2 className="text-lg sm:text-xl font-semibold text-slate-900 dark:text-white break-words">
                    {title}
                  </h2>
                )}
                {description && (
                  <p className="mt-1 text-sm text-slate-500 dark:text-slate-400 break-words">
                    {description}
                  </p>
                )}
              </div>
              {showClose && (
                <button
                  onClick={onClose}
                  aria-label="关闭"
                  className="-mr-1 -mt-0.5 p-2 shrink-0 rounded-xl text-slate-400 hover:text-slate-600
                    dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              )}
            </div>
          )}

          {/*
            Content。
            `flex-1 min-h-0 overflow-y-auto` 三件套缺一不可：
            flex-1 占满剩余高度、min-h-0 允许它收缩到比内容矮（否则 flex 子项
            默认 min-height:auto，会被内容撑开、把面板顶破限高）、
            overflow-y-auto 才真的滚起来。
          */}
          <div className="flex-1 min-h-0 overflow-y-auto px-4 py-5 sm:p-6">{children}</div>
        </div>
      </div>
    </div>
  )

  // 使用 portal 渲染到 body
  if (typeof document !== 'undefined') {
    return createPortal(modalContent, document.body)
  }

  return null
}

// 确认对话框
interface ConfirmModalProps {
  isOpen: boolean
  onClose: () => void
  onConfirm: () => void
  title: string
  message: string
  confirmText?: string
  cancelText?: string
  variant?: 'danger' | 'warning' | 'info'
  loading?: boolean
}

export function ConfirmModal({
  isOpen,
  onClose,
  onConfirm,
  title,
  message,
  confirmText = '确认',
  cancelText = '取消',
  variant = 'danger',
  loading = false,
}: ConfirmModalProps) {
  const variantStyles = {
    danger: 'bg-red-500 hover:bg-red-600 focus:ring-red-500',
    warning: 'bg-amber-500 hover:bg-amber-600 focus:ring-amber-500',
    info: 'bg-brand-500 hover:bg-brand-600 focus:ring-brand-500',
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="sm" showClose={false}>
      <div className="text-center">
        <div
          className={clsx(
            'mx-auto w-12 h-12 rounded-full flex items-center justify-center mb-4',
            variant === 'danger' && 'bg-red-100 dark:bg-red-900/30',
            variant === 'warning' && 'bg-amber-100 dark:bg-amber-900/30',
            variant === 'info' && 'bg-brand-100 dark:bg-brand-900/30'
          )}
        >
          {variant === 'danger' && (
            <svg className="w-6 h-6 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          )}
          {variant === 'warning' && (
            <svg className="w-6 h-6 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          )}
          {variant === 'info' && (
            <svg className="w-6 h-6 text-brand-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          )}
        </div>

        <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-2">{title}</h3>
        <p className="text-sm text-slate-500 dark:text-slate-400 mb-6">{message}</p>

        {/* 手机上并排两个按钮各占一半，点击区足够宽；这里的 flex-1 已经保证 */}
        <div className="flex gap-3">
          <button
            onClick={onClose}
            disabled={loading}
            className="flex-1 px-4 py-3 sm:py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 font-medium hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors disabled:opacity-50"
          >
            {cancelText}
          </button>
          <button
            onClick={onConfirm}
            disabled={loading}
            className={clsx(
              'flex-1 px-4 py-3 sm:py-2.5 rounded-xl text-white font-medium transition-colors disabled:opacity-50',
              variantStyles[variant]
            )}
          >
            {loading ? '处理中...' : confirmText}
          </button>
        </div>
      </div>
    </Modal>
  )
}
