const API_BASE = '/api/v1'

/**
 * 带结构化信息的请求错误。
 *
 * 后端的配额超限响应形如
 * ``{ error: 'QUOTA_EXCEEDED', resource, used, limit, message }``。
 * 只用 ``Error(message)`` 会把 error code 丢掉，调用方就没法区分
 * 「该升级套餐了」和「服务出错了」，只能弹一样的提示。
 */
export class ApiError extends Error {
  /** 机器可读的错误码，如 QUOTA_EXCEEDED */
  code?: string
  status: number
  /** 完整响应体，调用方可按需取 used / limit / resource 等字段 */
  data?: any

  constructor(message: string, status: number, code?: string, data?: any) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.data = data
  }
}

/**
 * 把一条错误明细渲染成人话。
 *
 * FastAPI 的 422 校验错误形如 ``{type, loc, msg, input}`` —— **没有 detail
 * 字段**。早先取 ``e.detail || String(e)``，于是界面上显示的是
 * ``[object Object]``：既不知道错在哪，也看不出其实是前端发错了请求。
 */
function describeErrorEntry(entry: any): string {
  if (entry == null) return '未知错误'
  if (typeof entry === 'string') return entry
  if (entry.msg) {
    const loc = Array.isArray(entry.loc)
      ? entry.loc.filter((p: any) => p !== 'body').join('.')
      : ''
    return loc ? `${loc}: ${entry.msg}` : String(entry.msg)
  }
  if (entry.detail) return String(entry.detail)
  try {
    return JSON.stringify(entry)
  } catch {
    return String(entry)
  }
}

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

  /**
   * 拼接请求地址。
   *
   * 后端有时会回传完整路径（例如产物条目里的
   * `url = /api/v1/pi/{agent}/files/xxx.md`），这类地址必须原样使用：
   * 再拼一次 API_BASE 会得到 `/api/v1/api/v1/...`，直接 404。
   *
   * 只接受站内相对路径：站外地址一律拒绝，避免把 Authorization 头
   * 带到外部域名。
   */
  private resolveUrl(endpoint: string): string {
    if (endpoint === API_BASE || endpoint.startsWith(`${API_BASE}/`)) {
      return endpoint
    }
    if (/^[a-z][a-z0-9+.-]*:/i.test(endpoint) || endpoint.startsWith('//')) {
      throw new Error(`不允许请求站外地址：${endpoint}`)
    }
    return `${API_BASE}${endpoint}`
  }

  private async request(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<any> {
    const isForm = typeof FormData !== 'undefined' && options.body instanceof FormData
    const headers: Record<string, string> = {
      // FormData 必须让浏览器自己写 Content-Type —— 它要带上 boundary。
      // 强行套 application/json 的话后端 multipart 解析直接失败，
      // 报的错还是「请求失败」，看不出真正原因。
      ...(isForm ? {} : { 'Content-Type': 'application/json' }),
      ...(options.headers as Record<string, string>),
    }

    const token = this.resolveToken()
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }

    const response = await fetch(this.resolveUrl(endpoint), {
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
      let code: string | undefined
      let body: any = null
      try {
        body = await response.json()
        if (Array.isArray(body)) {
          errorMsg = body.map(describeErrorEntry).join('；')
        } else if (body.detail) {
          errorMsg = Array.isArray(body.detail)
            ? body.detail.map(describeErrorEntry).join('；')
            : String(body.detail)
        } else if (body.error) {
          // 配额超限等结构化错误：message 是可读文案，error 是给程序用的码。
          // 必须放在 body.message 之前判断——两者同时存在，先取 code 才不会丢。
          code = String(body.error)
          errorMsg = String(body.message || body.error)
        } else if (body.message) {
          errorMsg = String(body.message)
        } else {
          errorMsg = JSON.stringify(body) || `错误 (${response.status})`
        }
      } catch (e) {
        errorMsg = `错误 (${response.status})`
      }
      throw new ApiError(errorMsg, response.status, code, body)
    }

    return response.json()
  }

  get(endpoint: string) {
    return this.request(endpoint)
  }

  /**
   * 编码请求体。
   *
   * **FormData 必须原样透传。** 之前三个方法一律 ``JSON.stringify(data)``，
   * 而 ``JSON.stringify(new FormData())`` 得到的是 ``"{}"`` —— 文件根本没
   * 发出去，后端收到一个空 JSON 体，报的是 422（缺 file 字段）。上传接口
   * 于是全部不可用，且错误信息看不出原因。
   *
   * 顺带修掉 ``data ? ... : undefined`` 那个写法：``0`` / ``false`` / ``''``
   * 都是合法请求体，三元会被当成「没传」。
   */
  private encodeBody(data: any): BodyInit | undefined {
    if (data === undefined || data === null) return undefined
    if (typeof FormData !== 'undefined' && data instanceof FormData) return data
    return JSON.stringify(data)
  }

  post(endpoint: string, data?: any) {
    return this.request(endpoint, {
      method: 'POST',
      body: this.encodeBody(data),
    })
  }

  put(endpoint: string, data?: any) {
    return this.request(endpoint, {
      method: 'PUT',
      body: this.encodeBody(data),
    })
  }

  patch(endpoint: string, data?: any) {
    return this.request(endpoint, {
      method: 'PATCH',
      body: this.encodeBody(data),
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

    const response = await fetch(this.resolveUrl(endpoint), {
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
      // 必须把后端返回的 detail 带出来：它才是用户能行动的原因
      // （例如「请在设置 → 模型配置中填写 API Key」），
      // 笼统的「上传失败」会让界面无法给出有用提示
      let detail = ''
      try {
        const body: any = await response.json()
        if (Array.isArray(body)) {
          detail = body.map((e: any) => e?.msg || JSON.stringify(e)).join('; ')
        } else if (typeof body?.detail === 'string') {
          detail = body.detail
        } else if (body?.detail) {
          detail = JSON.stringify(body.detail)
        }
      } catch {
        // 响应体不是 JSON，沿用兜底文案
      }
      throw new Error(detail || `上传失败（HTTP ${response.status}）`)
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

    const response = await fetch(this.resolveUrl(endpoint), { headers })

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

/** /auth/send-code 的返回 */
export interface SendCodeResult {
  success: boolean
  message: string
  /** 验证码有效期（秒） */
  expires_in: number
  /** 多久之后可以重发（秒） */
  resend_after: number
  /**
   * 后端是否真的发出去了邮件。
   * false 表示没配 SMTP，验证码只打印在后端日志里（本地开发用）。
   */
  mail_enabled: boolean
}

export const auth = {
  login: (email: string, password: string) => {
    return api.post('/auth/login', { email, password })
  },
  /** 发送注册邮箱验证码 */
  sendCode: (email: string) => {
    return api.post('/auth/send-code', { email }) as Promise<SendCodeResult>
  },
  register: (email: string, password: string, nickname?: string, code?: string) => {
    return api.post('/auth/register', { email, password, nickname, code })
  },
  /**
   * 修改密码。
   *
   * 成功后**所有 token 立即失效**，包括当前这个 —— 后端靠
   * `password_changed_at` 比对实现。所以调用方必须接着登出并跳登录页，
   * 不能只弹个 toast：那样用户还停在原页面，下一个请求就 401，
   * 看起来像功能坏了。
   */
  changePassword: (data: { old_password: string; new_password: string }) => {
    return api.post('/auth/change-password', data)
  },
  logout: () => {
    api.clearToken()
  },
  getCurrentUser: () => {
    return api.get('/users/me')
  },

  /**
   * 改昵称 / 手机号。
   *
   * 邮箱**不能在这里改**：它同时是登录标识、ADMIN_EMAILS 的匹配键和
   * 验证码投递目标，自助修改得配套「发验证码到新地址」的完整流程。
   * 后端没有开这个口子，前端也就不摆这个输入框。
   */
  updateProfile: (data: { nickname?: string; phone?: string }) =>
    api.patch('/users/me', data),

  /** 上传头像，返回 { avatar: '/static/avatars/xxx.png' } */
  uploadAvatar: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return api.post('/users/me/avatar', form)
  },

  /** 删回默认头像 */
  deleteAvatar: () => api.delete('/users/me/avatar'),
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

/** 一段历史对话的摘要（列表里用，不含正文） */
export interface ChatSessionItem {
  id: string
  agent_id: string
  agent_name: string
  /** 首条用户消息截断后的标题；空会话为空串 */
  title: string
  message_count: number
  created_at: string | null
  updated_at: string | null
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
  /** 跨 Agent 的对话记录列表；不传 agentId 就是该用户的全部会话 */
  allSessions: (params?: { agentId?: string; limit?: number; offset?: number }) => {
    const q = new URLSearchParams()
    if (params?.agentId) q.set('agent_id', params.agentId)
    if (params?.limit) q.set('limit', String(params.limit))
    if (params?.offset) q.set('offset', String(params.offset))
    const qs = q.toString()
    return api.get(`/chat/sessions${qs ? `?${qs}` : ''}`) as Promise<{
      sessions: ChatSessionItem[]
      total: number
    }>
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
  stream: (
    agentId: string,
    message: string,
    sessionId?: string | null,
    signal?: AbortSignal,
    newSession?: boolean
  ) =>
    streamSse<{
      type: string
      content?: string
      session_id?: string
      error?: string
      files?: PiArtifact[]
    }>(
      `/api/v1/chat/${agentId}`,
      { message, session_id: sessionId, stream: true, new_session: newSession || false },
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

/**
 * 外部只读数据源（ERP）连接器。对应后端 /api/v1/connectors。
 *
 * 密码只回掩码；列表供工作流「工具节点 erp_read」下拉选择。
 */
export interface ConnectorFieldSpec {
  as?: string
  mask?: 'none' | 'pii' | 'drop'
}

export interface ErpConnector {
  id: string
  alias: string
  db_type: string
  host: string | null
  port: number | null
  database: string
  schema: string | null
  user: string | null
  has_password: boolean
  password_masked: string
  has_dsn_override: boolean
  allowed_tables: string[]
  field_map: Record<string, ConnectorFieldSpec>
  row_limit: number
  connect_timeout: number
  is_active: boolean
}

export interface ErpConnectorPayload {
  alias: string
  db_type?: string
  host?: string | null
  port?: number | null
  database?: string
  schema?: string | null
  user?: string | null
  password?: string
  dsn_override?: string | null
  allowed_tables?: string[]
  field_map?: Record<string, ConnectorFieldSpec>
  row_limit?: number
  connect_timeout?: number
  is_active?: boolean
}

export const connectors = {
  list: () => api.get('/connectors') as Promise<ErpConnector[]>,
  create: (data: ErpConnectorPayload) =>
    api.post('/connectors', data) as Promise<ErpConnector>,
  update: (id: string, data: Partial<ErpConnectorPayload>) =>
    api.patch(`/connectors/${id}`, data) as Promise<ErpConnector>,
  remove: (id: string) => api.delete(`/connectors/${id}`),
  test: (id: string) =>
    api.post(`/connectors/${id}/test`) as Promise<{ ok: boolean; error: string | null }>,
  query: (id: string, data: { resource: string; filters?: Record<string, any>; columns?: string[]; limit?: number }) =>
    api.post(`/connectors/${id}/query`, data) as Promise<{ resource: string; count: number; rows: any[] }>,
}

/**
 * `GET /llm-configs/models` 的响应。
 *
 * ``SelectableModel`` 的定义在文件下方（随 ``llmConfigs`` 一起）。**别在这里
 * 再声明一个同名的** —— TypeScript 会静默地把两个 interface 合并，于是类型上
 * 同时存在 ``name`` 和 ``label``，``tsc`` 一声不吭，而运行时的那个字段
 * 只有一个，取另一个就得到 ``undefined``。这个坑真踩过。
 */
export interface SelectableModels {
  /** 当前生效的配置；source 为 'none' 表示连 .env 都没有可用配置 */
  effective: { alias: string; provider: string; model: string; source: string } | null
  models: SelectableModel[]
}

/**
 * 用户实际可用的模型。
 *
 * 用它而不是 `/templates/models/list` —— 后者是**静态内置目录**，全是
 * OpenAI / Anthropic 的型号名，跟用户自己的端点毫无关系；把里面的名字
 * 发到本地 Ollama 上只会换来「model not found」。
 */
export const llmModels = {
  list: () => api.get('/llm-configs/models') as Promise<SelectableModels>,
}

export interface AdminUserRow {
  id: string
  email: string | null
  nickname: string | null
  role: string
  is_active: boolean
  created_at: string | null
  last_login_at: string | null
  last_active_at: string | null
  plan: string
  plan_status: string
  agents_used: number
  messages_used: number
  agent_count: number
  session_count: number
  message_count: number
}

export interface AdminUserQuery {
  search?: string
  plan?: string
  role?: string
  status?: string
  activity?: string
  sort?: string
  order?: string
  limit?: number
  offset?: number
}

/** 管理后台的技能列表项。技能是文件不是数据库行。 */
export interface AdminSkill {
  slug: string
  id: string
  name: string
  description: string
  specialty: string
  version: string
  tags: any[]
  status: string
  visibility: string
  author_name: string
  total_calls: number
  avg_rating: number
  has_scripts: boolean
  /** 命中平台保留名单，广场不展示 */
  hidden: boolean
  /** SKILL.md 解析失败的原因；非空表示这个技能在广场里凭空消失 */
  broken: string | null
  updated_at: string | null
}

/** 单个技能的完整内容，编辑表单的数据源。 */
export interface AdminSkillDetail extends AdminSkill {
  frontmatter: Record<string, any>
  body: string
}

/** 新建 / 更新技能的请求体。 */
export interface SkillWritePayload {
  slug: string
  frontmatter: Record<string, any>
  body: string
}

export interface AdminSessionRow {
  id: string
  agent_id: string
  agent_name: string
  title: string
  message_count: number
  created_at: string | null
  updated_at: string | null
}

/** 把非空参数拼成 query string。空串 / undefined 一律跳过 —— 空串在后端
 *  是「用包里的值」，不是「设置成空」。 */
function queryString(params: Record<string, string | undefined>): string {
  const q = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value != null && value !== '') q.set(key, value)
  })
  const s = q.toString()
  return s ? `?${s}` : ''
}

export const admin = {
  overview: () => api.get('/admin/overview'),

  /** 近 N 天的每日趋势（新增用户 / 新建会话 / 活跃用户） */
  trends: (days = 14) => api.get(`/admin/trends?days=${days}`),

  /** 最活跃的 Agent 排行 */
  topAgents: (limit = 8) => api.get(`/admin/agents/top?limit=${limit}`),

  users: (params: AdminUserQuery = {}) => {
    const q = new URLSearchParams()
    for (const key of ['search', 'plan', 'role', 'status', 'activity', 'sort', 'order'] as const) {
      const value = params[key]
      if (value) q.set(key, value)
    }
    q.set('limit', String(params.limit ?? 20))
    q.set('offset', String(params.offset ?? 0))
    return api.get(`/admin/users?${q.toString()}`)
  },

  userDetail: (id: string) => api.get(`/admin/users/${id}`),

  /** 某用户的会话列表（分页） */
  userSessions: (id: string, limit = 20, offset = 0) =>
    api.get(`/admin/users/${id}/sessions?limit=${limit}&offset=${offset}`),

  /** 单个会话的完整消息内容 */
  sessionDetail: (sessionId: string) => api.get(`/admin/sessions/${sessionId}`),

  /** 设定用户的订阅版本。reset_usage 会同时把用量计数器归零。 */
  setSubscription: (id: string, data: { plan: string; reset_usage?: boolean }) =>
    api.patch(`/admin/users/${id}/subscription`, data),

  /** 启用 / 停用账号。停用后旧 token 立即失效 */
  setUserStatus: (id: string, isActive: boolean) =>
    api.patch(`/admin/users/${id}/status`, { is_active: isActive }),

  /** 技能列表（含广场不可见的保留目录）。broken 非空表示 SKILL.md 解析失败 */
  skills: () => api.get('/admin/skills'),

  /** 单个技能的完整内容：frontmatter 与正文分开返回 */
  skillDetail: (slug: string) => api.get(`/admin/skills/${slug}`),

  /** 新建技能。slug 已存在会 400，不会覆盖 */
  createSkill: (data: SkillWritePayload) => api.post('/admin/skills', data),

  /** 更新技能。slug 不能改，改名请删了重建 */
  updateSkill: (slug: string, data: SkillWritePayload) =>
    api.patch(`/admin/skills/${slug}`, data),

  /** 删除技能目录（含 scripts/）。平台保留目录会被拒绝 */
  deleteSkill: (slug: string) => api.delete(`/admin/skills/${slug}`),

  /**
   * 预览技能包（zip），不写任何文件。
   *
   * 单独一步预览而不是选完文件直接导：解析规则必须和真正导入时一致，
   * 否则用户确认完看到的结果和预览不是一回事。
   *
   * `skillPath` 用于包内含多个技能时指定导哪个；留空则自动取唯一最浅的
   * 那个，同深度有多个会报错并列出候选。
   */
  previewSkillPackage: (file: File, opts: { skillPath?: string } = {}) => {
    const form = new FormData()
    form.append('file', file)
    return api.post(
      `/admin/skills/import/preview${queryString({ skill_path: opts.skillPath })}`,
      form,
    )
  },

  /**
   * 导入技能包。
   *
   * slug 已存在会返回 **409** —— 静默覆盖线上技能是最难排查的事故，
   * 所以默认必须让人显式传 overwrite。
   *
   * 其余是**覆盖值**：GitHub 上的技能包（尤其 Claude Code 生态那种）字段
   * 不符合 AgentFlow 的约定，名字、广场描述、系统提示词都得由管理员自己定。
   * 留空则沿用包里的值。
   */
  importSkillPackage: (
    file: File,
    opts: {
      slug?: string
      overwrite?: boolean
      skillPath?: string
      name?: string
      description?: string
      systemPrompt?: string
    } = {},
  ) => {
    const form = new FormData()
    form.append('file', file)
    const suffix = queryString({
      slug: opts.slug,
      overwrite: opts.overwrite ? 'true' : undefined,
      skill_path: opts.skillPath,
      name: opts.name,
      description: opts.description,
      system_prompt: opts.systemPrompt,
    })
    return api.post(`/admin/skills/import${suffix}`, form)
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

/** 用户上传到 Agent 工作目录的文件 */
export interface UploadedFile {
  name: string
  size: number
  path: string
  url: string
}

export interface PiChatBody {
  message: string
  session_id?: string | null
  /** 「新建对话」：强制另起一段会话，不再复用最近一次 */
  new_session?: boolean
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

export interface SelectableModel {
  id: string
  label: string
  provider: string
  alias: string | null
  config_id: string | null
  /** config = 来自「设置 → 模型配置」；catalog = 内置目录 */
  source: 'config' | 'catalog'
  /** 是否来自当前生效的那份配置 */
  is_effective: boolean
}

export const llmConfigs = {
  list: () =>
    api.get('/llm-configs') as Promise<{
      configs: LlmConfig[]
      effective_id: string | null
      effective_source: string
    }>,

  /**
   * 实际可选的模型，生效项排最前。
   *
   * 与 /templates/models/list 的区别：那个是静态内置目录，不反映用户配了什么；
   * 这个来自用户自己的「模型配置」，选了一定能发到对应的端点上。
   */
  models: () =>
    api.get('/llm-configs/models') as Promise<{
      models: SelectableModel[]
      effective: {
        model: string | null
        alias: string | null
        provider: string | null
        source: string
      }
      note: string
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
  /** 把文件上传到该 Agent 的工作目录（模型可直接读取） */
  uploadToWorkspace: (agentId: string, file: File) =>
    api.uploadFile(`/agents/${agentId}/files`, file),
  /** 工作目录里已上传的文件 */
  listWorkspaceFiles: (agentId: string) =>
    api.get(`/agents/${agentId}/files`) as Promise<{ files: UploadedFile[] }>,
  downloadWorkspaceFile: (agentId: string, name: string) =>
    api.getBlob(`/agents/${agentId}/files/${encodeURIComponent(name)}`),
}
