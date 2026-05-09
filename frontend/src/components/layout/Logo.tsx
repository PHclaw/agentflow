import React from 'react'
import { cn } from '../../lib/utils'

interface LogoProps {
  size?: 'sm' | 'md' | 'lg'
  showText?: boolean
  className?: string
}

const sizes = {
  sm: {
    icon: 'w-8 h-8',
    text: 'text-lg',
  },
  md: {
    icon: 'w-10 h-10',
    text: 'text-xl',
  },
  lg: {
    icon: 'w-12 h-12',
    text: 'text-2xl',
  },
}

export function Logo({ size = 'md', showText = true, className }: LogoProps) {
  const sizeConfig = sizes[size]

  return (
    <div className={cn('flex items-center gap-3', className)}>
      {/* Geometric Icon */}
      <div
        className={cn(
          'relative flex items-center justify-center rounded-xl',
          'bg-gradient-to-br from-indigo-500 to-indigo-600',
          'shadow-lg shadow-indigo-500/25',
          sizeConfig.icon
        )}
      >
        {/* Geometric Shape */}
        <svg
          viewBox="0 0 24 24"
          fill="none"
          className="w-5 h-5 text-white"
          style={{ width: '50%', height: '50%' }}
        >
          {/* Hexagon shape representing AI/agent */}
          <path
            d="M12 2L20 7V17L12 22L4 17V7L12 2Z"
            fill="white"
            fillOpacity="0.9"
          />
          <path
            d="M12 6L16 8.5V13.5L12 16L8 13.5V8.5L12 6Z"
            fill="currentColor"
            className="text-indigo-600"
          />
          {/* Central node */}
          <circle cx="12" cy="11" r="2" fill="white" />
        </svg>
      </div>

      {/* Text */}
      {showText && (
        <span className={cn('font-bold text-slate-900', sizeConfig.text)}>
          AgentFlow
        </span>
      )}
    </div>
  )
}

export function LogoSmall({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        'relative w-10 h-10 flex items-center justify-center rounded-xl',
        'bg-gradient-to-br from-indigo-500 to-indigo-600',
        'shadow-lg shadow-indigo-500/25',
        className
      )}
    >
      <svg viewBox="0 0 24 24" fill="none" className="w-5 h-5 text-white">
        <path d="M12 2L20 7V17L12 22L4 17V7L12 2Z" fill="white" fillOpacity="0.9" />
        <circle cx="12" cy="11" r="2" fill="white" />
      </svg>
    </div>
  )
}
