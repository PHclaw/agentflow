import React, { useState, useRef, useEffect } from 'react'
import { cn } from '../../lib/utils'
import { ChevronDown } from 'lucide-react'

interface DropdownItem {
  label: string
  value: string
  icon?: React.ReactNode
  disabled?: boolean
  danger?: boolean
}

interface DropdownProps {
  trigger: React.ReactNode
  items: DropdownItem[]
  onSelect: (value: string) => void
  align?: 'left' | 'right'
  className?: string
}

export function Dropdown({
  trigger,
  items,
  onSelect,
  align = 'left',
  className,
}: DropdownProps) {
  const [isOpen, setIsOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  return (
    <div ref={dropdownRef} className={cn('relative', className)}>
      <div onClick={() => setIsOpen(!isOpen)}>{trigger}</div>

      {isOpen && (
        <div
          className={cn(
            'absolute z-50 mt-2 w-56 bg-white rounded-xl border border-slate-200 shadow-xl',
            'py-1 animate-fade-in',
            align === 'right' ? 'right-0' : 'left-0'
          )}
        >
          {items.map((item, index) => (
            <button
              key={item.value}
              onClick={() => {
                if (!item.disabled) {
                  onSelect(item.value)
                  setIsOpen(false)
                }
              }}
              disabled={item.disabled}
              className={cn(
                'w-full flex items-center gap-3 px-4 py-2.5 text-sm text-left',
                'transition-colors',
                item.disabled
                  ? 'text-slate-400 cursor-not-allowed'
                  : item.danger
                  ? 'text-red-600 hover:bg-red-50'
                  : 'text-slate-700 hover:bg-slate-50'
              )}
            >
              {item.icon && <span className="w-4 h-4">{item.icon}</span>}
              <span>{item.label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

interface SelectDropdownProps {
  value: string
  options: DropdownItem[]
  onChange: (value: string) => void
  placeholder?: string
  className?: string
}

export function SelectDropdown({
  value,
  options,
  onChange,
  placeholder = '选择...',
  className,
}: SelectDropdownProps) {
  const [isOpen, setIsOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  const selectedOption = options.find((opt) => opt.value === value)

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  return (
    <div ref={dropdownRef} className={cn('relative', className)}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          'w-full flex items-center justify-between px-4 py-2.5',
          'bg-white border border-slate-200 rounded-lg',
          'text-left text-sm',
          'transition-all duration-200',
          'focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500'
        )}
      >
        <span className={selectedOption ? 'text-slate-900' : 'text-slate-400'}>
          {selectedOption?.label || placeholder}
        </span>
        <ChevronDown
          className={cn('w-4 h-4 text-slate-400 transition-transform', isOpen && 'rotate-180')}
        />
      </button>

      {isOpen && (
        <div className="absolute z-50 mt-1 w-full bg-white rounded-lg border border-slate-200 shadow-xl py-1 animate-fade-in">
          {options.map((option) => (
            <button
              key={option.value}
              onClick={() => {
                onChange(option.value)
                setIsOpen(false)
              }}
              className={cn(
                'w-full flex items-center gap-3 px-4 py-2.5 text-sm text-left',
                'transition-colors',
                option.value === value
                  ? 'bg-indigo-50 text-indigo-600'
                  : 'text-slate-700 hover:bg-slate-50'
              )}
            >
              {option.icon && <span className="w-4 h-4">{option.icon}</span>}
              <span>{option.label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
