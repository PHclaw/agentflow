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

  private async request(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<any> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string>),
    }

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`
    }

    const response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers,
    })

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
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`
    }

    const response = await fetch(`${API_BASE}${endpoint}`, {
      method: 'POST',
      headers,
      body: formData,
    })

    if (!response.ok) {
      throw new Error('上传失败')
    }

    return response.json()
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
    return api.get('/auth/me')
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
