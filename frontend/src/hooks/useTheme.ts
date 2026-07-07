import { create } from 'zustand'
import { persist } from 'zustand/middleware'

type Theme = 'light' | 'dark' | 'system'

interface ThemeState {
  theme: Theme
  resolvedTheme: 'light' | 'dark'
  setTheme: (theme: Theme) => void
  toggleTheme: () => void
}

export const useThemeStore = create<ThemeState>()(
  persist(
    (set, get) => ({
      theme: 'system',
      resolvedTheme: 'light',
      
      setTheme: (theme) => {
        const root = document.documentElement
        
        if (theme === 'system') {
          const systemTheme = window.matchMedia('(prefers-color-scheme: dark)').matches
            ? 'dark'
            : 'light'
          root.classList.remove('light', 'dark')
          root.classList.add(systemTheme)
          set({ theme, resolvedTheme: systemTheme })
        } else {
          root.classList.remove('light', 'dark')
          root.classList.add(theme)
          set({ theme, resolvedTheme: theme })
        }
      },
      
      toggleTheme: () => {
        const { resolvedTheme } = get()
        get().setTheme(resolvedTheme === 'light' ? 'dark' : 'light')
      },
    }),
    {
      name: 'agentflow-theme',
      onRehydrateStorage: () => (state) => {
        if (state) {
          state.setTheme(state.theme)
        }
      },
    }
  )
)

// 初始化主题
if (typeof window !== 'undefined') {
  const stored = localStorage.getItem('agentflow-theme')
  if (stored) {
    try {
      const { theme } = JSON.parse(stored)
      useThemeStore.getState().setTheme(theme)
    } catch {
      useThemeStore.getState().setTheme('system')
    }
  }
  
  // 监听系统主题变化
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
    const state = useThemeStore.getState()
    if (state.theme === 'system') {
      state.setTheme('system')
    }
  })
}
