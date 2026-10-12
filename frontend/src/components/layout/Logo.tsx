import React from 'react'
import { cn } from '../../lib/utils'

interface LogoProps {
  size?: 'sm' | 'md' | 'lg'
  showText?: boolean
  className?: string
  /**
   * 字标渐变跟随哪个主题：
   * - auto：跟随根元素的 dark 类（应用内使用，侧边栏/登录页等有完整深色主题）
   * - light：固定用深色文字渐变（落地页顶栏永远是浅色底，
   *   即使根元素被切到 dark 也不能用浅色渐变，否则浅字压浅底看不见）
   */
  tone?: 'auto' | 'light'
}

const sizes = {
  sm: {
    icon: 'w-8 h-8',
    text: 'text-lg',
    mark: 14,
  },
  md: {
    icon: 'w-10 h-10',
    text: 'text-xl',
    mark: 18,
  },
  lg: {
    icon: 'w-12 h-12',
    text: 'text-2xl',
    mark: 22,
  },
}

/**
 * 标识：两个错位的方块 + 一条连线，示意「流程编排」。
 *
 * 一个方块用白色（反白）、一个用琥珀强调色，避免整块图标同色导致辨识度不足。
 */
function FlowMark({ px }: { px: number }) {
  const gap = Math.max(2, Math.round(px * 0.16))
  const box = Math.round((px - gap) / 2)

  return (
    <svg viewBox={`0 0 ${px} ${px}`} fill="none" width={px} height={px} aria-hidden="true">
      {/* 连线：左上 → 右下，表示流转 */}
      <path
        d={`M${gap + box} ${gap + box} L${px - gap - box} ${px - gap - box}`}
        stroke="white"
        strokeOpacity={0.55}
        strokeWidth={Math.max(1.5, px * 0.08)}
        strokeLinecap="round"
      />
      {/* 左上：主色块（白） */}
      <rect
        x={gap * 0.4}
        y={gap * 0.4}
        width={box}
        height={box}
        rx={Math.max(2, px * 0.13)}
        fill="white"
        fillOpacity={0.95}
      />
      {/* 右下：强调色块（琥珀） */}
      <rect
        x={px - gap * 0.4 - box}
        y={px - gap * 0.4 - box}
        width={box}
        height={box}
        rx={Math.max(2, px * 0.13)}
        className="fill-accent-300"
      />
    </svg>
  )
}

export function Logo({
  size = 'md',
  showText = true,
  className,
  tone = 'auto',
}: LogoProps) {
  const sizeConfig = sizes[size]

  return (
    <div className={cn('flex items-center gap-3', className)}>
      <div
        className={cn(
          'relative flex items-center justify-center rounded-xl',
          'bg-brand-700 shadow-sm shadow-brand-900/20',
          sizeConfig.icon
        )}
      >
        <FlowMark px={sizeConfig.mark} />
      </div>

      {showText && (
        /*
         * 渐变文字必须三件套齐全：bg-gradient-to-r + bg-clip-text + text-transparent。
         * 少任何一个都不会出渐变 —— 之前只写了渐变背景、漏了后两件，
         * 结果深色渐变糊在字后面而文字继承深色前景，成了「黑字黑底」。
         * 侧边栏和落地页顶栏各犯过一次，现已统一走这个组件。
         *
         * 渐变刻意与图标同色系（主色深一档 → 主色），
         * 深浅色各自反向：浅色下字更实，深色下提亮保证可读。
         */
        <span
          className={cn(
            'font-bold bg-clip-text text-transparent bg-gradient-to-r',
            tone === 'light'
              ? 'from-brand-800 to-brand-500'
              : 'from-brand-800 to-brand-500 dark:from-brand-300 dark:to-accent-300',
            sizeConfig.text
          )}
        >
          AgentFlow
        </span>
      )}
    </div>
  )
}

/** 仅图标版本（折叠态侧边栏等） */
export function LogoSmall({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        'w-10 h-10 flex items-center justify-center rounded-xl',
        'bg-brand-700 shadow-sm shadow-brand-900/20',
        className
      )}
    >
      <FlowMark px={18} />
    </div>
  )
}