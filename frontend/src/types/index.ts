// Agent 类型
export interface Agent {
  id: string
  name: string
  description: string
  model: string
  prompt: string
  is_active: boolean
  message_count: number
  created_at: string
  updated_at: string
  workflow_definition?: WorkflowDefinition
}

// 工作流定义
export interface WorkflowDefinition {
  nodes: WorkflowNode[]
  edges: WorkflowEdge[]
  entry: string
}

export interface WorkflowNode {
  id: string
  type: NodeType
  position: { x: number; y: number }
  data: NodeData
}

export interface WorkflowEdge {
  id: string
  source: string
  target: string
  label?: string
  animated?: boolean
}

export type NodeType = 'trigger' | 'llm' | 'knowledge' | 'tool' | 'condition' | 'response'

export interface NodeData {
  label: string
  description?: string
  model?: string
  temperature?: number
  prompt?: string
  knowledgeBaseId?: string
  toolName?: string
  toolParams?: Record<string, any>
  condition?: string
  branches?: { label: string; condition: string }[]
  responseTemplate?: string
}

// 消息类型
export interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: Date
  references?: MessageReference[]
}

export interface MessageReference {
  id: string
  content: string
  source: string
}

// 用户类型
export interface User {
  id: string
  email: string
  nickname?: string
  avatar?: string
  plan: 'free' | 'pro' | 'enterprise'
}

// 知识库类型
export interface KnowledgeBase {
  id: string
  name: string
  description: string
  document_count: number
  created_at: string
}

// 统计类型
export interface Stats {
  agents_count: number
  messages_count: number
  knowledge_bases: number
  today_messages: number
}

// 表单验证类型
export interface ValidationError {
  field: string
  message: string
}

// Toast 类型
export type ToastType = 'success' | 'error' | 'info' | 'warning'

export interface Toast {
  id: string
  type: ToastType
  message: string
  duration?: number
}

// 模板类型
export interface Template {
  id: string
  name: string
  description: string
  icon: string
  category: string
  workflow: WorkflowDefinition
}
