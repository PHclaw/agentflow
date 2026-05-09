import React from 'react'
import { Link, useLocation } from 'react-router-dom'
import { cn } from '../../lib/utils'
import { ChevronRight, Home } from 'lucide-react'

interface BreadcrumbItem {
  label: string
  href?: string
}

interface BreadcrumbProps {
  items: BreadcrumbItem[]
  className?: string
}

export function Breadcrumb({ items, className }: BreadcrumbProps) {
  return (
    <nav className={cn('flex items-center gap-1 text-sm', className)}>
      <Link
        to="/"
        className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
      >
        <Home className="w-4 h-4" />
      </Link>

      {items.map((item, index) => (
        <React.Fragment key={index}>
          <ChevronRight className="w-4 h-4 text-slate-300" />
          {item.href ? (
            <Link
              to={item.href}
              className="px-2 py-1 rounded-lg text-slate-500 hover:text-slate-700 hover:bg-slate-100 transition-colors"
            >
              {item.label}
            </Link>
          ) : (
            <span className="px-2 py-1 text-slate-900 font-medium">{item.label}</span>
          )}
        </React.Fragment>
      ))}
    </nav>
  )
}
