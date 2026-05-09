import React, { forwardRef } from 'react'
import clsx from 'clsx'
import { Loader2 } from 'lucide-react'

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger' | 'success'
  size?: 'xs' | 'sm' | 'md' | 'lg'
  loading?: boolean
  leftIcon?: React.ReactNode
  rightIcon?: React.ReactNode
  as?: 'button' | 'a'
  href?: string
  fullWidth?: boolean
}

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
      as: Component = 'button',
      fullWidth = false,
      ...props
    },
    ref
  ) => {
    const baseStyles = `
      inline-flex items-center justify-center gap-2
      font-medium rounded-xl transition-all duration-200
      focus:outline-none focus:ring-2 focus:ring-offset-2
      disabled:opacity-50 disabled:cursor-not-allowed
      active:scale-[0.98]
    `

    const variants = {
      primary: `
        bg-gradient-to-r from-indigo-500 to-purple-600
        text-white shadow-lg shadow-indigo-500/25
        hover:from-indigo-600 hover:to-purple-700
        hover:shadow-xl hover:shadow-indigo-500/30
        focus:ring-indigo-500
      `,
      secondary: `
        bg-gradient-to-r from-slate-600 to-slate-700
        text-white shadow-lg shadow-slate-500/25
        hover:from-slate-700 hover:to-slate-800
        focus:ring-slate-500
      `,
      outline: `
        border-2 border-slate-200 dark:border-slate-700
        text-slate-700 dark:text-slate-200
        hover:bg-slate-50 dark:hover:bg-slate-800
        focus:ring-slate-500
      `,
      ghost: `
        text-slate-600 dark:text-slate-300
        hover:bg-slate-100 dark:hover:bg-slate-800
        focus:ring-slate-500
      `,
      danger: `
        bg-gradient-to-r from-red-500 to-red-600
        text-white shadow-lg shadow-red-500/25
        hover:from-red-600 hover:to-red-700
        focus:ring-red-500
      `,
      success: `
        bg-gradient-to-r from-emerald-500 to-green-600
        text-white shadow-lg shadow-emerald-500/25
        hover:from-emerald-600 hover:to-green-700
        focus:ring-emerald-500
      `,
    }

    const sizes = {
      xs: 'px-2.5 py-1.5 text-xs',
      sm: 'px-3 py-2 text-sm',
      md: 'px-4 py-2.5 text-sm',
      lg: 'px-6 py-3 text-base',
    }

    const isDisabled = disabled || loading

    return (
      <Component
        ref={ref}
        disabled={isDisabled}
        className={clsx(
          baseStyles,
          variants[variant],
          sizes[size],
          fullWidth && 'w-full',
          className
        )}
        {...props}
      >
        {loading ? (
          <Loader2 className="w-4 h-4 animate-spin" />
        ) : leftIcon ? (
          <span className={clsx(size === 'xs' && 'w-3 h-3')}>{leftIcon}</span>
        ) : null}
        {children}
        {!loading && rightIcon && (
          <span className={clsx(size === 'xs' && 'w-3 h-3')}>{rightIcon}</span>
        )}
      </Component>
    )
  }
)

Button.displayName = 'Button'
