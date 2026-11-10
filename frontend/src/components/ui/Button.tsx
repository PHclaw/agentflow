import React, { forwardRef } from 'react'
import { Loader2 } from 'lucide-react'
import { cn } from '../../lib/utils'

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger' | 'success'
  size?: 'xs' | 'sm' | 'md' | 'lg'
  loading?: boolean
  leftIcon?: React.ReactNode
  rightIcon?: React.ReactNode
  fullWidth?: boolean
}

/**
 * 按钮：实色填充 + 细描边，不用渐变、不用彩色光晕。
 *
 * 旧版是 `bg-gradient-to-r from-brand-500 to-brand-600` 配
 * `shadow-lg shadow-brand-500/25`，点下去还会 `scale-[0.98]`。三处都要改：
 *
 * - **渐变**：现在 brand 与 accent 都指向同一强调色，渐变自动变平涂，
 *   但留着 `from-x to-y` 只会让人误以为还有第二个颜色。
 * - **彩色阴影**：`shadow-brand-500/25` 会在按钮周围晕一圈品牌色，
 *   一屏按钮同时晕起来就是一片浑浊。层级靠「实色 / 描边 / 纯文字」
 *   三档区分，不该靠阴影和颜色数量。
 * - **按压缩放**：0.98 的缩放配 200ms 过渡，鼠标快速划过时会看到抖动。
 *   这个结论仍然成立，所以缩放**只挂在 `:active`（真的按下去）上，不挂 hover** ——
 *   快速划过不会触发 active，抖动的前提就不存在了。按下去缩、松开弹回，
 *   是"这个按钮收到了"最直接的反馈。过渡只覆盖 transform 等几个属性，
 *   不是 transition-all：后者会把尺寸、位置变化也接过去，布局一变就跟着抖。
 */
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant = 'primary',
      size = 'md',
      loading = false,
      leftIcon,
      rightIcon,
      disabled,
      children,
      fullWidth = false,
      ...props
    },
    ref
  ) => {
    const baseStyles = `
      inline-flex items-center justify-center gap-2
      font-medium rounded-lg whitespace-nowrap
      transition-[color,background-color,border-color,box-shadow,transform] duration-150
      active:scale-[0.98] motion-reduce:active:scale-100
      focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500/40 focus-visible:ring-offset-1
      disabled:opacity-40 disabled:pointer-events-none
      select-none
    `

    const variants = {
      primary: `
        bg-indigo-600 text-white
        hover:bg-indigo-700
        dark:bg-indigo-500 dark:hover:bg-indigo-600
      `,
      secondary: `
        bg-slate-900 text-white
        hover:bg-slate-800
        dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white
      `,
      outline: `
        border border-slate-200 bg-white text-slate-700
        hover:bg-slate-50 hover:text-slate-900
        dark:border-slate-700 dark:bg-transparent dark:text-slate-200
        dark:hover:bg-slate-800
      `,
      ghost: `
        text-slate-600
        hover:bg-slate-100 hover:text-slate-900
        dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-white
      `,
      danger: `
        bg-red-600 text-white
        hover:bg-red-700
      `,
      success: `
        bg-emerald-600 text-white
        hover:bg-emerald-700
      `,
    }

    // 用固定高度而不是 py-*：这样同一行里不同 variant 的按钮高度一致，
    // 也不会因为内容换行而忽高忽低。
    const sizes = {
      xs: 'h-7 px-2.5 text-xs gap-1.5',
      sm: 'h-8 px-3 text-[13px] gap-1.5',
      md: 'h-9 px-3.5 text-sm',
      lg: 'h-11 px-5 text-[15px]',
    }

    const isDisabled = disabled || loading
    const iconSize = size === 'xs' || size === 'sm' ? 'w-3.5 h-3.5' : 'w-4 h-4'

    return (
      <button
        ref={ref}
        disabled={isDisabled}
        className={cn(
          baseStyles,
          variants[variant],
          sizes[size],
          fullWidth && 'w-full',
          className
        )}
        {...props}
      >
        {loading ? (
          <Loader2 className={cn(iconSize, 'animate-spin')} />
        ) : leftIcon ? (
          <span className={cn('shrink-0', iconSize)}>{leftIcon}</span>
        ) : null}
        {children}
        {!loading && rightIcon && (
          <span className={cn('shrink-0', iconSize)}>{rightIcon}</span>
        )}
      </button>
    )
  }
)

Button.displayName = 'Button'
