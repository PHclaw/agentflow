import React from 'react'
import { cn } from '../../lib/utils'

interface TabsProps {
  tabs: { id: string; label: string; icon?: React.ReactNode }[]
  activeTab: string
  onChange: (tabId: string) => void
  className?: string
}

export function Tabs({ tabs, activeTab, onChange, className }: TabsProps) {
  return (
    <div className={cn('flex gap-1 p-1 bg-slate-100 rounded-xl', className)}>
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onChange(tab.id)}
          className={cn(
            'flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-all duration-200',
            activeTab === tab.id
              ? 'bg-white text-slate-900 shadow-sm'
              : 'text-slate-600 hover:text-slate-900'
          )}
        >
          {tab.icon && <span className="w-4 h-4">{tab.icon}</span>}
          {tab.label}
        </button>
      ))}
    </div>
  )
}

interface TabPanelProps {
  children: React.ReactNode
  className?: string
  value?: string
  id?: string
}

export function TabPanel({ children, className }: TabPanelProps) {
  return <div className={className}>{children}</div>
}
