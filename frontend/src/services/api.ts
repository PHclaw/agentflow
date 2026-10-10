const API_BASE = '/api/v1'

class ApiClient {
  private token: string | null = null

  constructor() {
    this.token = localStorage.getItem('token')
  }

  setToken(token: string) {
    this.token = token
    localStorage.setItem('token', token)
  }

  clearToken() {
    this.token = null
    localStorage.removeItem('token')
  }

  /**
   * 每次请求时实时解析 token。
   *
   * 不能只依赖构造函数里缓存的那一份：登录成功后 token 是写进 localStorage /
   * zustand store 的，而这个实例在模块加载时就已经创建，内存中的 this.token
   * 仍是 null，会导致登录后首个请求 401 并被踢回登录页。
   */
  private resolveToken(): string | null {
    // 以 localStorage 为准；不可用时（SSR / 测试环境）退回内存中的值
    try {
      const stored = globalThis.localStorage?.getItem('token')
      return stored ?? this.token
    } catch {
      return this.token
    }
  }

  private async request(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<any> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string>),
    }

    const token = this.resolveToken()
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }

    const response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers,
    })

    if (response.status === 401) {
      this.clearToken()
      if (
        typeof window !== 'undefined' &&
        !window.location.pathname.startsWith('/login') &&
        !window.location.pathname.startsWith('/register')
      ) {
        window.location.href = '/login'
      }
      throw new Error('未登录或登录已过期，请重新登录')
    }

    if (!response.ok) {
      let errorMsg = '请求失败'
      try {
        const errorBody: any = await response.json()
        if (Array.isArray(errorBody)) {
          errorMsg = errorBody.map((e: any) => e.detail || e.msg || JSON.stringify(e)).join(', ')
        } else if (errorBody.detail) {
          errorMsg = Array.isArray(errorBody.detail)
            ? errorBody.detail.map((e: any) => e.detail || String(e)).join(', ')
            : String(errorBody.detail)
        } else if (errorBody.message) {
          errorMsg = String(errorBody.message)
        } else {
          errorMsg = JSON.stringify(errorBody) || `错误 (${response.status})`
        }
      } catch (e) {
        errorMsg = `错误 (${response.status})`
      }
      throw new Error(errorMsg)
    }

    return response.json()
  }

  get(endpoint: string) {
    return this.request(endpoint)
  }

  post(endpoint: string, data?: any) {
    return this.request(endpoint, {
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    })
  }

  put(endpoint: string, data?: any) {
    return this.request(endpoint, {
      method: 'PUT',
      body: data ? JSON.stringify(data) : undefined,
    })
  }

  delete(endpoint: string) {
    return this.request(endpoint, { method: 'DELETE' })
  }

  async uploadFile(endpoint: string, file: File) {
    const formData = new FormData()
    formData.append('file', file)

    const headers: Record<string, string> = {}
    const token = this.resolveToken()
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }

    const response = await fetch(`${API_BASE}${endpoint}`, {
      method: 'POST',
      headers,
      body: formData,
    })

    if (response.status === 401) {
      this.clearToken()
      if (
        typeof window !== 'undefined' &&
        !window.location.pathname.startsWith('/login')
      ) {
        window.location.href = '/login'
      }
      throw new Error('未登录或登录已过期，请重新登录')
    }

    if (!response.ok) {
      throw new Error('上传失败')
    }

    return response.json()
  }

  /**
   * 下载二进制内容（如知识库文档的原始文件）。
   * 失败时抛出后端返回的 detail 信息，便于界面提示具体原因。
   */
  async getBlob(endpoint: string): Promise<Blob> {
    const headers: Record<string, string> = {}
    const token = this.resolveToken()
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }

    const response = await fetch(`${API_BASE}${endpoint}`, { headers })

    if (response.status === 401) {
      this.clearToken()
      throw new Error('未登录或登录已过期，请重新登录')
    }

    if (!response.ok) {
      let errorMsg = `下载失败 (${response.status})`
      try {
        const body: any = await response.json()
        if (body?.detail) errorMsg = String(body.detail)
      } catch {
        // 响应体不是 JSON，保留默认提示
      }
      throw new Error(errorMsg)
    }

    return response.blob()
  }
}

export const api = new ApiClient()

export const auth = {
  login: (email: string, password: string) => {
    return api.post('/auth/login', { email, password })
  },
  register: (email: string, password: string, nickname?: string) => {
    return api.post('/auth/register', { email, password, nickname })
  },
  logout: () => {
    api.clearToken()
  },
  getCurrentUser: () => {
    return api.get('/users/me')
  },
}

export const agents = {
  list: (params?: { limit?: number; offset?: number }) => {
    const query = params
      ? '?' + new URLSearchParams(
          Object.entries(params).map(([k, v]) => [k, String(v)])
        ).toString()
      : ''
    return api.get(`/agents${query}`)
  },
  get: (id: string) => {
    return api.get(`/agents/${id}`)
  },
  create: (data: any) => {
    return api.post('/agents', data)
  },
  update: (id: string, data: any) => {
    return api.put(`/agents/${id}`, data)
  },
  delete: (id: string) => {
    return api.delete(`/agents/${id}`)
  },
  chat: (id: string, message: string, sessionId?: string) => {
    return api.post(`/chat/${id}`, { message, session_id: sessionId })
  },
  stats: (id: string) => {
    return api.get(`/agents/${id}/stats`)
  },
  duplicate: (id: string, name: string, description?: string) => {
    return api.post(`/agents/${id}/duplicate`, { name, description })
  },
}

export const chat = {
  send: (agentId: string, message: string, sessionId?: string, stream?: boolean) => {
    return api.post(`/chat/${agentId}`, { message, session_id: sessionId, stream })
  },
  history: (agentId: string, sessionId?: string) => {
    const query = sessionId ? `?session_id=${sessionId}` : ''
    return api.get(`/chat/${agentId}/history${query}`)
  },
  sessions: (agentId: string) => {
    return api.get(`/chat/${agentId}/sessions`)
  },
  feedback: (agentId: string, messageId: string, rating: string, comment?: string) => {
    return api.post(`/chat/${agentId}/feedback`, { message_id: messageId, rating, comment })
  },
  withTools: (agentId: string, message: string, sessionId?: string) => {
    return api.post(`/chat/${agentId}/with-tools`, { message, session_id: sessionId })
  },
  /** 内置链路的流式对话（SSE：session / chunk / done / error）
   *  done 事件可能带 files：工作流里的智能体节点生成了工作区产物
   */
  stream: (agentId: string, message: string, sessionId?: string | null, signal?: AbortSignal) =>
    streamSse<{
      type: string
      content?: string
      session_id?: string
      error?: string
      files?: PiArtifact[]
    }>(
      `/api/v1/chat/${agentId}`,
      { message, session_id: sessionId, stream: true },
      signal
    ),
}

export const knowledge = {
  list: () => {
    return api.get('/knowledge')
  },
  create: (data: any) => {
    return api.post('/knowledge', data)
  },
  get: (kbId: string) => {
    return api.get(`/knowledge/${kbId}`)
  },
  delete: (kbId: string) => {
    return api.delete(`/knowledge/${kbId}`)
  },
  upload: async (kbId: string, file: File) => {
    return api.uploadFile(`/knowledge/${kbId}/documents`, file)
  },
  getDocuments: (kbId: string) => {
    return api.get(`/knowledge/${kbId}/documents`)
  },
  deleteDocument: (kbId: string, docId: number) => {
    return api.delete(`/knowledge/${kbId}/documents/${docId}`)
  },
  downloadDocument: (kbId: string, docId: number) => {
    return api.getBlob(`/knowledge/${kbId}/documents/${docId}/download`)
  },
  search: (query: string, kbIds?: string[], topK?: number) => {
    return api.post('/knowledge/search', { query, kb_ids: kbIds, top_k: topK || 5 })
  },
  getContext: (query: string, kbIds?: string[]) => {
    return api.post('/knowledge/context', { query, kb_ids: kbIds })
  },
  ragQuery: (query: string, kbIds?: string[], systemPrompt?: string) => {
    return api.post('/knowledge/rag', { query, kb_ids: kbIds, system_prompt: systemPrompt })
  },
  ragChat: (query: string, chatHistory: any[], kbIds?: string[]) => {
    return api.post('/knowledge/rag/chat', { query, chat_history: chatHistory, kb_ids: kbIds })
  },
  getStats: (kbId: string) => {
    return api.get(`/knowledge/${kbId}/stats`)
  },
}

export const workflow = {
  execute: (workflowDefinition: any, inputData: any) => {
    return api.post('/workflow/execute', { workflow_definition: workflowDefinition, input_data: inputData })
  },
  executeNode: (workflowDefinition: any, nodeId: string, inputData: any) => {
    return api.post('/workflow/execute/node', { workflow_definition: workflowDefinition, node_id: nodeId, input_data: inputData })
  },
  test: (nodes: any[], edges: any[], inputData: any) => {
    return api.post('/workflow/test', { nodes, edges, input_data: inputData })
  },
  getExecutionOrder: (nodes: any[], edges: any[]) => {
    return api.get(`/workflow/execution-order?${new URLSearchParams({
      nodes: JSON.stringify(nodes),
      edges: JSON.stringify(edges),
    })}`)
  },
}

export const templates = {
  list: () => {
    return api.get('/templates')
  },
  get: (id: string) => {
    return api.get(`/templates/${id}`)
  },
}

export const models = {
  list: () => {
    return api.get('/templates/models/list')
  },
}

export const billing = {
  listPlans: () => {
    return api.get('/billing/plans')
  },
  getSubscription: () => {
    return api.get('/billing/subscription')
  },
  createCheckout: (data: { price_id: string; success_url: string; cancel_url: string }) => {
    return api.post('/billing/checkout', data)
  },
  createPortal: (data: { return_url: string }) => {
    return api.post('/billing/portal', data)
  },
}

export interface SkillPlazaItem {
  id: string
  name: string
  description: string
  specialty: string
  category?: string
  categoryName?: string
  routerBlurb?: string
  triggers: string[]
  tags?: string[]
  authorName?: string
  version: string
  totalCalls?: number
}

export interface SkillCallResponse {
  output: string
  latencyMs?: number
  agentVersion?: string
  toolTrace?: {
    downloadUrl?: string
    downloadUrls?: string[]
    imageUrl?: string
  }
  sessionId?: string
}

export const skills = {
  plaza: (params?: { specialty?: string; category?: string }) => {
    const query = params
      ? '?' +
        new URLSearchParams(
          Object.entries(params)
            .filter(([, v]) => v)
            .map(([k, v]) => [k, String(v)])
        ).toString()
      : ''
    return api.get(`/skills/plaza${query}`) as Promise<SkillPlazaItem[]>
  },
  get: (id: string) => api.get(`/skills/${id}`),
  call: (id: string, variables: Record<string, string>, sessionId?: string) =>
    api.post(`/skills/${id}/call`, {
      variables,
      sessionId,
    }) as Promise<SkillCallResponse>,
  callWithFiles: async (
    id: string,
    message: string,
    files: File[],
    sessionId?: string
  ): Promise<SkillCallResponse> => {
    const formData = new FormData()
    formData.append('message', message)
    if (sessionId) formData.append('session_id', sessionId)
    files.forEach((f) => formData.append('files', f))

    const headers: Record<string, string> = {}
    const token = localStorage.getItem('token')
    if (token) headers['Authorization'] = `Bearer ${token}`

    const response = await fetch(`/api/v1/skills/${id}/call-with-files`, {
      method: 'POST',
      headers,
      body: formData,
    })
    if (!response.ok) {
      let errorMsg = '请求失败'
      try {
        const body = await response.json()
        errorMsg = body.detail || body.message || errorMsg
      } catch {
        errorMsg = `错误 (${response.status})`
      }
      throw new Error(errorMsg)
    }
    return response.json()
  },
  resolve: (query: string) => api.post('/skills/resolve', { query }),
  categories: () => api.get('/skills/categories'),
}

// ---------------------------------------------------------------------------
// SSE 流式客户端
// ---------------------------------------------------------------------------

/**
 * 逐帧解析 SSE 响应。
 *
 * 不能按“每次 read 到的 chunk”切行：一个事件帧可能被拆到两次读取里，
 * 那样会丢掉前半段。这里用 buffer 累积，只按完整的 `\n\n` 分帧。
 *
 * 事件源需要自定义 Authorization 头，因此不能用 EventSource，改为
 * fetch + ReadableStream。
 */
export async function* streamSse<T = any>(
  url: string,
  body: unknown,
  signal?: AbortSignal
): AsyncGenerator<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  const token = localStorage.getItem('token')
  if (token) headers['Authorization'] = `Bearer ${token}`

  const response = await fetch(url, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
    signal,
  })

  if (!response.ok) {
    let errorMsg = `请求失败 (${response.status})`
    try {
      const errBody: any = await response.json()
      if (errBody?.detail) errorMsg = String(errBody.detail)
    } catch {
      // 响应体不是 JSON，保留默认提示
    }
    throw new Error(errorMsg)
  }

  const reader = response.body?.getReader()
  if (!reader) return

  const decoder = new TextDecoder()
  let buffer = ''

  const parseFrames = (text: string): T[] => {
    const events: T[] = []
    for (const frame of text.split('\n\n')) {
      for (const line of frame.split('\n')) {
        if (!line.startsWith('data:')) continue
        const payload = line.slice(5).trim()
        if (!payload) continue
        try {
          events.push(JSON.parse(payload) as T)
        } catch {
          // 忽略无法解析的行（例如注释或心跳）
        }
      }
    }
    return events
  }

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })

      // 最后一个片段可能是不完整帧，留到下一轮
      const lastBreak = buffer.lastIndexOf('\n\n')
      if (lastBreak === -1) continue

      const complete = buffer.slice(0, lastBreak + 2)
      buffer = buffer.slice(lastBreak + 2)

      for (const event of parseFrames(complete)) yield event
    }

    // 冲刷没有以 \n\n 收尾的残留
    if (buffer.trim()) {
      for (const event of parseFrames(buffer)) yield event
    }
  } finally {
    reader.releaseLock?.()
  }
}

export interface PiArtifact {
  name: string
  path: string
  size: number
  modified: number
  url: string
}

export interface PiStreamEvent {
  type: 'log' | 'thinking' | 'text' | 'tool_call' | 'done' | 'error'
  content?: string
  files?: PiArtifact[]
  session_id?: string | null
}

export interface PiChatBody {
  message: string
  session_id?: string | null
  skills?: string[]
  timeout?: number
}

export interface PiStatus {
  enabled: boolean
  available: boolean
  exe: string | null
  timeout: number
  workspace_root: string
  skills_root: string
  skills: string[]
}

// ---------------------------------------------------------------------------
// 大模型 API 配置
// ---------------------------------------------------------------------------

export interface LlmConfig {
  id: string
  alias: string
  provider: string
  base_url: string
  model: string
  temperature: number
  max_tokens: number
  description: string
  is_default: boolean
  is_active: boolean
  has_api_key: boolean
  api_key_masked: string
  last_tested_at: string | null
  last_test_ok: boolean | null
  last_test_error: string | null
  created_at: string | null
  updated_at: string | null
  is_effective: boolean
}

export interface LlmProviderPreset {
  value: string
  label: string
  base_url: string
  requires_key: boolean
  hint: string
  models: { name: string; display_name: string }[]
}

export interface LlmConfigPayload {
  alias: string
  provider: string
  base_url: string
  model: string
  api_key?: string
  description?: string
  temperature?: number
  max_tokens?: number
  is_default?: boolean
}

export interface EffectiveConfig {
  source: 'database' | 'env' | 'none'
  id?: string | null
  alias: string | null
  provider: string | null
  base_url: string
  model: string
  api_key_masked: string
  message: string
}

export const llmConfigs = {
  list: () =>
    api.get('/llm-configs') as Promise<{
      configs: LlmConfig[]
      effective_id: string | null
      effective_source: string
    }>,
  active: () => api.get('/llm-configs/active') as Promise<EffectiveConfig>,
  providers: () =>
    api.get('/llm-configs/providers') as Promise<{
      providers: LlmProviderPreset[]
      protocol_note: string
    }>,
  create: (data: LlmConfigPayload) => api.post('/llm-configs', data) as Promise<LlmConfig>,
  update: (id: string, data: Partial<LlmConfigPayload>) =>
    api.put(`/llm-configs/${id}`, data) as Promise<LlmConfig>,
  remove: (id: string) => api.delete(`/llm-configs/${id}`),
  setDefault: (id: string) => api.post(`/llm-configs/${id}/default`) as Promise<LlmConfig>,
  setActive: (id: string, isActive: boolean) =>
    api.post(`/llm-configs/${id}/active`, { is_active: isActive }) as Promise<LlmConfig>,
  test: (id: string) =>
    api.post(`/llm-configs/${id}/test`) as Promise<{ ok: boolean; message: string }>,
  testDraft: (data: { provider: string; base_url: string; model: string; api_key: string }) =>
    api.post('/llm-configs/test', data) as Promise<{ ok: boolean; message: string }>,
}

export const pi = {
  status: () => api.get('/pi/status') as Promise<PiStatus>,
  workspace: (agentId: string) => api.get(`/pi/${agentId}/workspace`),
  run: (agentId: string, data: PiChatBody) => api.post(`/pi/${agentId}/run`, data),
  stream: (agentId: string, data: PiChatBody, signal?: AbortSignal) =>
    streamSse<PiStreamEvent>(`/api/v1/pi/${agentId}/stream`, data, signal),
  downloadArtifact: (agentId: string, path: string) =>
    api.getBlob(`/pi/${agentId}/files/${path}`),
}
