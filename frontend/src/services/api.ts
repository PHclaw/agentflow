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

  private getToken(): string | null {
    // 每次都从 localStorage 获取最新的 token
    return localStorage.getItem('token') || this.token
  }

  private async request(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<any> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string>),
    }

    const token = this.getToken()
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
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

    const token = this.getToken()
    const headers: Record<string, string> = {}
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
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

// Auth
export const auth = {
  login: (email: string, password: string) => api.post('/auth/login', { email, password }),
  register: (email: string, password: string, nickname?: string) => api.post('/auth/register', { email, password, nickname }),
  me: () => api.get('/auth/me'),
  refreshToken: (token: string) => api.post('/auth/refresh', { token }),
  changePassword: (oldPassword: string, newPassword: string) => api.post('/auth/change-password', { old_password: oldPassword, new_password: newPassword }),
}

// Knowledge Base
export const knowledge = {
  list: () => api.get('/knowledge'),
  create: (name: string, description?: string) => api.post('/knowledge', { name, description }),
  get: (kbId: string) => api.get(`/knowledge/${kbId}`),
  delete: (kbId: string) => api.delete(`/knowledge/${kbId}`),
  uploadDocument: (kbId: string, file: File) => api.uploadFile(`/knowledge/${kbId}/documents`, file),
  listDocuments: (kbId: string) => api.get(`/knowledge/${kbId}/documents`),
  deleteDocument: (kbId: string, docId: number) => api.delete(`/knowledge/${kbId}/documents/${docId}`),
  search: (query: string, kbIds?: string[], topK?: number) => api.post('/knowledge/search', { query, kb_ids: kbIds, top_k: topK || 5 }),
  searchInKb: (kbId: string, query: string, topK?: number) => api.post(`/knowledge/${kbId}/search`, { query, top_k: topK || 5 }),
  upload: (kbId: string, file: File) => api.uploadFile(`/knowledge/${kbId}/documents`, file), // Alias for compatibility
}

// Workflow
export const workflows = {
  list: () => api.get('/workflow/templates'),
  create: (data: any) => api.post('/workflow/templates', data),
  save: (workflowId: string, data: any) => api.put(`/workflow/templates/${workflowId}`, data),
  delete: (workflowId: string) => api.delete(`/workflow/templates/${workflowId}`),
  execute: (workflowDefinition: any, inputData?: any) => api.post('/workflow/execute', { workflow_definition: workflowDefinition, input_data: inputData }),
}

// Agent
export const agents = {
  list: () => api.get('/agents'),
  create: (data: any) => api.post('/agents', data),
  get: (agentId: string) => api.get(`/agents/${agentId}`),
  update: (agentId: string, data: any) => api.put(`/agents/${agentId}`, data),
  delete: (agentId: string) => api.delete(`/agents/${agentId}`),
  chat: (agentId: string, message: string, sessionId?: string) => api.post(`/agents/${agentId}/chat`, { message, session_id: sessionId }),
  getSessions: (agentId: string) => api.get(`/agents/${agentId}/sessions`),
}

// Chat
export const chat = {
  getHistory: (sessionId: string) => api.get(`/chat/${sessionId}/history`),
  send: (sessionId: string, message: string) => api.post(`/chat/${sessionId}`, { message }),
}

// Models
export const models = {
  list: () => api.get('/models'),
}

// Templates (placeholder)
export const templates = {
  list: () => Promise.resolve([]),
  get: (id: string) => Promise.resolve({ id, name: 'Template' }),
}

// Billing (placeholder)
export const billing = {
  getPlans: () => Promise.resolve([]),
  listPlans: () => Promise.resolve([]),
  getSubscription: () => Promise.resolve(null),
  subscribe: (planId: string) => Promise.resolve({ success: true }),
  createCheckout: () => Promise.resolve({ url: '#' }),
}
