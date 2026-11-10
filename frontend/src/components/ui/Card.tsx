import React from 'react'
import { cn } from '../../lib/utils'

interface CardProps {
  children: React.ReactNode
  className?: string
  padding?: 'none' | 'sm' | 'md' | 'lg'
  hover?: boolean
  style?: React.CSSProperties
}

const paddingStyles = {
  none: '',
  sm: 'p-4',
  md: 'p-5',
  lg: 'p-6',
}

/**
 * 卡片：细描边 + 无阴影。层级由描边建立，避免「浮起来」的观感。
 *
 * 旧版是 `rounded-2xl ... shadow-sm`，hover 时还升级到 `shadow-md` 并位移。
 * 密集排布的卡片一旦带阴影，相邻卡片的阴影会互相干扰，看起来发脏。
 * 这里只靠 1px 描边区分，hover 时把描边加深就够了。
 *
 * 另外补上了 `dark:` 变体 —— 旧版整个 Card 一个都没有，深色模式全靠
 * index.css 里的兜底规则顶着，那只是安全网，不是设计。
 */
export function Card({
  children,
  className,
  padding = 'md',
  hover = false,
  style,
}: CardProps) {
  return (
    <div
      className={cn(
        'bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800',
        paddingStyles[padding],
        hover && 'card-hover cursor-pointer',
        className
      )}
      style={style}
    >
      {children}
    </div>
  )
}

interface CardHeaderProps {
  children: React.ReactNode
  className?: string
}

export function CardHeader({ children, className }: CardHeaderProps) {
  return (
    <div className={cn('flex items-center justify-between mb-4', className)}>
      {children}
    </div>
  )
}

interface CardTitleProps {
  children: React.ReactNode
  className?: string
}

export function CardTitle({ children, className }: CardTitleProps) {
  return (
    <h3 className={cn('text-[15px] font-semibold text-slate-900 dark:text-slate-100', className)}>
      {children}
    </h3>
  )
}

interface CardContentProps {
  children: React.ReactNode
  className?: string
}

export function CardContent({ children, className }: CardContentProps) {
  return <div className={className}>{children}</div>
}

interface CardDescriptionProps {
  children: React.ReactNode
  className?: string
}

export function CardDescription({ children, className }: CardDescriptionProps) {
  return (
    <p className={cn('text-[13px] text-slate-500 dark:text-slate-400', className)}>
      {children}
    </p>
  )
}
