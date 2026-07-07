import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Toast, User, Agent, Message } from '../types'

// Auth Store
interface AuthState {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  setUser: (user: User | null) => void
  setToken: (token: string | null) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      token: localStorage.getItem('token'),
      isAuthenticated: !!localStorage.getItem('token'),
      setUser: (user) => set({ user, isAuthenticated: !!user }),
      setToken: (token) => {
        if (token) {
          localStorage.setItem('token', token)
        } else {
          localStorage.removeItem('token')
        }
        set({ token, isAuthenticated: !!token })
      },
      logout: () => {
        localStorage.removeItem('token')
        set({ user: null, token: null, isAuthenticated: false })
      },
    }),
    { name: 'auth-storage' }
  )
)

// Theme Store
interface ThemeState {
  theme: 'light' | 'dark' | 'system'
  resolvedTheme: 'light' | 'dark'
  setTheme: (theme: 'light' | 'dark' | 'system') => void
}

export const useThemeStore = create<ThemeState>((set, get) => ({
  theme: 'light',
  resolvedTheme: 'light',
  setTheme: (theme) => {
    const root = document.documentElement
    let resolved: 'light' | 'dark'

    if (theme === 'system') {
      resolved = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
    } else {
      resolved = theme
    }

    root.classList.remove('light', 'dark')
    root.classList.add(resolved)
    set({ theme, resolvedTheme: resolved })
  },
}))

// Toast Store
interface ToastState {
  toasts: Toast[]
  addToast: (toast: Omit<Toast, 'id'>) => void
  removeToast: (id: string) => void
}

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  addToast: (toast) => {
    const id = Date.now().toString()
    set((state) => ({
      toasts: [...state.toasts, { ...toast, id }],
    }))
    setTimeout(() => {
      set((state) => ({
        toasts: state.toasts.filter((t) => t.id !== id),
      }))
    }, toast.duration || 3000)
  },
  removeToast: (id) => {
    set((state) => ({
      toasts: state.toasts.filter((t) => t.id !== id),
    }))
  },
}))

// Agent Store
interface AgentState {
  agents: Agent[]
  currentAgent: Agent | null
  loading: boolean
  setAgents: (agents: Agent[]) => void
  setCurrentAgent: (agent: Agent | null) => void
  addAgent: (agent: Agent) => void
  updateAgent: (id: string, updates: Partial<Agent>) => void
  removeAgent: (id: string) => void
  setLoading: (loading: boolean) => void
}

export const useAgentStore = create<AgentState>((set) => ({
  agents: [],
  currentAgent: null,
  loading: false,
  setAgents: (agents) => set({ agents }),
  setCurrentAgent: (agent) => set({ currentAgent: agent }),
  addAgent: (agent) => set((state) => ({ agents: [...state.agents, agent] })),
  updateAgent: (id, updates) =>
    set((state) => ({
      agents: state.agents.map((a) => (a.id === id ? { ...a, ...updates } : a)),
      currentAgent:
        state.currentAgent?.id === id ? { ...state.currentAgent, ...updates } : state.currentAgent,
    })),
  removeAgent: (id) =>
    set((state) => ({
      agents: state.agents.filter((a) => a.id !== id),
      currentAgent: state.currentAgent?.id === id ? null : state.currentAgent,
    })),
  setLoading: (loading) => set({ loading }),
}))

// Chat Store
interface ChatState {
  messages: Message[]
  sessionId: string | null
  isLoading: boolean
  addMessage: (message: Message) => void
  setMessages: (messages: Message[]) => void
  setSessionId: (sessionId: string | null) => void
  setLoading: (loading: boolean) => void
  clearMessages: () => void
}

export const useChatStore = create<ChatState>((set) => ({
  messages: [],
  sessionId: null,
  isLoading: false,
  addMessage: (message) => set((state) => ({ messages: [...state.messages, message] })),
  setMessages: (messages) => set({ messages }),
  setSessionId: (sessionId) => set({ sessionId }),
  setLoading: (isLoading) => set({ isLoading }),
  clearMessages: () => set({ messages: [], sessionId: null }),
}))

// Workflow Store
interface WorkflowState {
  nodes: any[]
  edges: any[]
  selectedNode: string | null
  setNodes: (nodes: any[]) => void
  setEdges: (edges: any[]) => void
  setSelectedNode: (nodeId: string | null) => void
  addNode: (node: any) => void
  updateNode: (nodeId: string, data: any) => void
  removeNode: (nodeId: string) => void
}

export const useWorkflowStore = create<WorkflowState>((set) => ({
  nodes: [],
  edges: [],
  selectedNode: null,
  setNodes: (nodes) => set({ nodes }),
  setEdges: (edges) => set({ edges }),
  setSelectedNode: (selectedNode) => set({ selectedNode }),
  addNode: (node) => set((state) => ({ nodes: [...state.nodes, node] })),
  updateNode: (nodeId, data) =>
    set((state) => ({
      nodes: state.nodes.map((n) =>
        n.id === nodeId ? { ...n, data: { ...n.data, ...data } } : n
      ),
    })),
  removeNode: (nodeId) =>
    set((state) => ({
      nodes: state.nodes.filter((n) => n.id !== nodeId),
      edges: state.edges.filter((e) => e.source !== nodeId && e.target !== nodeId),
      selectedNode: state.selectedNode === nodeId ? null : state.selectedNode,
    })),
}))
