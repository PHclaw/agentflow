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
      const error = await response.json().catch(() => ({ detail: '请求失败' }))
      throw new Error(error.detail || '请求失败')
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
    const query = params ? `?${new URLSearchParams(params as any)}` : ''
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
  upload: async (kbId: string, file: File, chunkSize?: number) => {
    return api.uploadFile(`/knowledge/${kbId}/upload`, file)
  },
  search: (kbId: string, query: string) => {
    return api.post(`/knowledge/${kbId}/search`, { query })
  },
}
