import React from 'react'
import { cn } from '../../lib/utils'
import { useToastStore } from '../../stores'
import { X, CheckCircle, AlertCircle, Info, AlertTriangle } from 'lucide-react'

const icons = {
  success: CheckCircle,
  error: AlertCircle,
  info: Info,
  warning: AlertTriangle,
}

const styles = {
  success: 'bg-green-50 border-green-200 text-green-800',
  error: 'bg-red-50 border-red-200 text-red-800',
  info: 'bg-blue-50 border-blue-200 text-blue-800',
  warning: 'bg-yellow-50 border-yellow-200 text-yellow-800',
}

const iconStyles = {
  success: 'text-green-500',
  error: 'text-red-500',
  info: 'text-blue-500',
  warning: 'text-yellow-500',
}

export function Toast() {
  const { toasts, removeToast } = useToastStore()

  if (toasts.length === 0) return null

  return (
    <div
      className="fixed right-4 z-[110] flex flex-col gap-2
        bottom-[calc(3.5rem+env(safe-area-inset-bottom)+0.75rem)] lg:bottom-4
        max-w-[calc(100vw-2rem)]"
    >
      {/*
        位置与层级各有原因：

        - `z-[110]`：比浮窗（z-[100]）高。弹窗里操作成功后的提示不能被弹窗
          自己盖住 —— 那是用户最需要看到反馈的时刻。
        - 手机端 bottom 抬高到底部导航之上：全局导航（z-70）贴着屏幕底部，
          Toast 若还是 bottom-4 就会被压在它下面（甚至被完全挡住）。
        - `max-w-[calc(100vw-2rem)]`：长错误信息换行而不是把提示条撑出屏幕。
      */}
      {toasts.map((toast) => {
        const Icon = icons[toast.type]
        return (
          <div
            key={toast.id}
            className={cn(
              'flex items-center gap-3 px-4 py-3 rounded-xl border shadow-lg',
              'animate-slide-up backdrop-blur-sm',
              styles[toast.type]
            )}
          >
            <Icon className={cn('w-5 h-5 flex-shrink-0', iconStyles[toast.type])} />
            <p className="text-sm font-medium">{toast.message}</p>
            <button
              onClick={() => removeToast(toast.id)}
              className="p-1 rounded hover:bg-black/5 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        )
      })}
    </div>
  )
}
