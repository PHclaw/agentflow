import React, { useEffect, useState } from 'react'
import {
  Plus,
  Pencil,
  Trash2,
  PlugZap,
  Loader2,
  CheckCircle2,
  XCircle,
  Database,
  FlaskConical,
} from 'lucide-react'
import {
  connectors,
  type ErpConnector,
  type ErpConnectorPayload,
} from '../services/api'
import { Button } from './ui/Button'
import { Input } from './ui/Input'
import { Modal, ConfirmModal } from './ui/Modal'
import { useToastStore } from '../stores'

interface FormState {
  alias: string
  db_type: string
  host: string
  port: string
  database: string
  schema: string
  user: string
  password: string
  dsn_override: string
  allowed_tables: string
  field_map: string
  row_limit: number
  connect_timeout: number
  is_active: boolean
}

const EMPTY_FORM: FormState = {
  alias: '',
  db_type: 'postgresql',
  host: '',
  port: '5432',
  database: '',
  schema: '',
  user: '',
  password: '',
  dsn_override: '',
  allowed_tables: '',
  field_map: '',
  row_limit: 200,
  connect_timeout: 10,
  is_active: true,
}

const DB_TYPES = [
  { value: 'postgresql', label: 'PostgreSQL' },
  { value: 'sqlite', label: 'SQLite（文件库）' },
]

export default function ErpConnectorPanel() {
  const { addToast } = useToastStore()

  const [items, setItems] = useState<ErpConnector[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [busyId, setBusyId] = useState<string | null>(null)

  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState<ErpConnector | null>(null)
  const [form, setForm] = useState<FormState>(EMPTY_FORM)
  const [formError, setFormError] = useState('')
  const [saving, setSaving] = useState(false)

  const [pendingDelete, setPendingDelete] = useState<ErpConnector | null>(null)
  const [deleting, setDeleting] = useState(false)

  // 试查预览
  const [queryTarget, setQueryTarget] = useState<ErpConnector | null>(null)
  const [queryResource, setQueryResource] = useState('')
  const [queryResult, setQueryResult] = useState<{ count: number; rows: any[] } | null>(null)
  const [querying, setQuerying] = useState(false)

  useEffect(() => {
    void loadAll()
  }, [])

  const loadAll = async () => {
    setLoading(true)
    setLoadError('')
    try {
      setItems(await connectors.list())
    } catch (e: any) {
      setLoadError(e?.message || '加载连接器失败')
    } finally {
      setLoading(false)
    }
  }

  const openCreate = () => {
    setEditing(null)
    setForm(EMPTY_FORM)
    setFormError('')
    setShowForm(true)
  }

  const openEdit = (c: ErpConnector) => {
    setEditing(c)
    setForm({
      alias: c.alias,
      db_type: c.db_type,
      host: c.host || '',
      port: c.port != null ? String(c.port) : '',
      database: c.database || '',
      schema: c.schema || '',
      user: c.user || '',
      password: '', // 留空 = 保留原密码
      dsn_override: '',
      allowed_tables: (c.allowed_tables || []).join('\n'),
      field_map: Object.keys(c.field_map || {}).length ? JSON.stringify(c.field_map, null, 2) : '',
      row_limit: c.row_limit ?? 200,
      connect_timeout: c.connect_timeout ?? 10,
      is_active: c.is_active,
    })
    setFormError('')
    setShowForm(true)
  }

  const buildPayload = (): ErpConnectorPayload => {
    const allowed = form.allowed_tables
      .split(/[,\n]/)
      .map((t) => t.trim())
      .filter(Boolean)

    let fieldMap: ErpConnectorPayload['field_map'] = {}
    if (form.field_map.trim()) {
      fieldMap = JSON.parse(form.field_map) // 调用方已 try/catch
    }

    const payload: ErpConnectorPayload = {
      alias: form.alias.trim(),
      db_type: form.db_type,
      database: form.database.trim(),
      allowed_tables: allowed,
      field_map: fieldMap,
      row_limit: Number(form.row_limit) || 200,
      connect_timeout: Number(form.connect_timeout) || 10,
      is_active: form.is_active,
    }
    if (form.db_type === 'postgresql') {
      payload.host = form.host.trim() || null
      payload.port = form.port ? Number(form.port) : null
      payload.user = form.user.trim() || null
      payload.schema = form.schema.trim() || null
    } else if (form.db_type === 'sqlite') {
      // sqlite 用 database 存文件路径
    }
    if (form.dsn_override.trim()) payload.dsn_override = form.dsn_override.trim()
    // 编辑留空 = 不提交 password，后端保留原值
    if (form.password.trim() || !editing) payload.password = form.password
    return payload
  }

  const handleSave = async () => {
    if (!form.alias.trim()) {
      setFormError('请填写别名')
      return
    }
    setSaving(true)
    setFormError('')
    let payload: ErpConnectorPayload
    try {
      payload = buildPayload()
    } catch {
      setFormError('字段映射（field_map）不是合法 JSON')
      setSaving(false)
      return
    }
    try {
      if (editing) await connectors.update(editing.id, payload)
      else await connectors.create(payload)
      addToast({ type: 'success', message: editing ? '连接器已更新' : '连接器已创建' })
      setShowForm(false)
      await loadAll()
    } catch (e: any) {
      setFormError(e?.message || '保存失败')
    } finally {
      setSaving(false)
    }
  }

  const handleTest = async (c: ErpConnector) => {
    setBusyId(c.id)
    try {
      const r = await connectors.test(c.id)
      addToast({
        type: r.ok ? 'success' : 'error',
        message: r.ok ? `${c.alias}：连接成功` : `${c.alias}：${r.error || '连接失败'}`,
      })
    } catch (e: any) {
      addToast({ type: 'error', message: e?.message || '测试失败' })
    } finally {
      setBusyId(null)
    }
  }

  const openQuery = (c: ErpConnector) => {
    setQueryTarget(c)
    setQueryResource(c.allowed_tables?.[0] || '')
    setQueryResult(null)
  }

  const handleQuery = async () => {
    if (!queryTarget || !queryResource.trim()) return
    setQuerying(true)
    try {
      const r = await connectors.query(queryTarget.id, { resource: queryResource.trim() })
      setQueryResult({ count: r.count, rows: r.rows })
    } catch (e: any) {
      addToast({ type: 'error', message: e?.message || '查询失败' })
    } finally {
      setQuerying(false)
    }
  }

  const handleDelete = async () => {
    if (!pendingDelete) return
    setDeleting(true)
    try {
      await connectors.remove(pendingDelete.id)
      addToast({ type: 'success', message: '连接器已删除' })
      setPendingDelete(null)
      await loadAll()
    } catch (e: any) {
      addToast({ type: 'error', message: e?.message || '删除失败' })
    } finally {
      setDeleting(false)
    }
  }

  const set = (patch: Partial<FormState>) => setForm((f) => ({ ...f, ...patch }))

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm text-slate-500 dark:text-slate-400">
          第三方 ERP 的**只读**数据源。工作流的「ERP 数据读取」工具节点从这里选择连接器。
        </p>
        <Button leftIcon={<Plus className="w-4 h-4" />} onClick={openCreate}>
          新增连接器
        </Button>
      </div>

      {loadError && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-xl text-red-600 text-sm">
          {loadError}
        </div>
      )}

      {loading ? (
        <div className="flex items-center gap-2 text-slate-400 py-8 justify-center">
          <Loader2 className="w-4 h-4 animate-spin" /> 加载中…
        </div>
      ) : items.length === 0 ? (
        <div className="text-center py-10 text-slate-400">
          <Database className="w-8 h-8 mx-auto mb-2 opacity-50" />
          <p className="text-sm mb-3">还没有连接器，创建一个以接入 ERP 只读数据</p>
          <Button variant="outline" leftIcon={<Plus className="w-4 h-4" />} onClick={openCreate}>
            新增连接器
          </Button>
        </div>
      ) : (
        <div className="divide-y divide-slate-100 dark:divide-slate-700">
          {items.map((c) => (
            <div key={c.id} className="py-3 flex items-center justify-between gap-3">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-slate-900 dark:text-white truncate">{c.alias}</span>
                  <span className="text-xs px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-700 text-slate-500">
                    {c.db_type}
                  </span>
                  {!c.is_active && (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-700">已停用</span>
                  )}
                </div>
                <div className="text-xs text-slate-500 truncate mt-0.5">
                  {c.database}
                  {c.host ? ` · ${c.host}${c.port ? ':' + c.port : ''}` : ''}
                  {' · '}表 {c.allowed_tables?.length || 0} 个
                </div>
              </div>
              <div className="flex items-center gap-1 flex-shrink-0">
                <button
                  className="p-2 rounded-lg text-slate-400 hover:text-brand-600 hover:bg-slate-50"
                  title="连接测试"
                  disabled={busyId === c.id}
                  onClick={() => handleTest(c)}
                >
                  {busyId === c.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <PlugZap className="w-4 h-4" />}
                </button>
                <button
                  className="p-2 rounded-lg text-slate-400 hover:text-emerald-600 hover:bg-slate-50"
                  title="试查（预览脱敏结果）"
                  onClick={() => openQuery(c)}
                >
                  <FlaskConical className="w-4 h-4" />
                </button>
                <button
                  className="p-2 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-50"
                  title="编辑"
                  onClick={() => openEdit(c)}
                >
                  <Pencil className="w-4 h-4" />
                </button>
                <button
                  className="p-2 rounded-lg text-slate-400 hover:text-red-600 hover:bg-red-50"
                  title="删除"
                  onClick={() => setPendingDelete(c)}
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 新增 / 编辑 */}
      <Modal
        isOpen={showForm}
        onClose={() => setShowForm(false)}
        title={editing ? `编辑连接器：${editing.alias}` : '新增外部数据连接器'}
        description="仅支持只读访问；建议为对方配置只读账号，表名需登记到白名单"
        size="lg"
      >
        <div className="space-y-4">
          <Input label="别名" value={form.alias} onChange={(e) => set({ alias: e.target.value })} placeholder="如：生产ERP-只读" />

          <label className="block">
            <span className="block text-sm font-medium text-slate-700 mb-1.5">数据库类型</span>
            <select
              className="w-full px-4 py-2.5 bg-white border border-slate-200 rounded-lg text-slate-900"
              value={form.db_type}
              onChange={(e) => set({ db_type: e.target.value })}
            >
              {DB_TYPES.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </label>

          {form.db_type === 'postgresql' && (
            <div className="grid grid-cols-2 gap-3">
              <Input label="主机 host" value={form.host} onChange={(e) => set({ host: e.target.value })} placeholder="数据库地址" />
              <Input label="端口 port" value={form.port} onChange={(e) => set({ port: e.target.value })} placeholder="5432" />
              <Input label="用户名 user" value={form.user} onChange={(e) => set({ user: e.target.value })} placeholder="只读账号" />
              <Input label="schema（可选）" value={form.schema} onChange={(e) => set({ schema: e.target.value })} placeholder="public" />
            </div>
          )}

          <Input
            label={form.db_type === 'sqlite' ? '数据库文件路径' : '数据库名 database'}
            value={form.database}
            onChange={(e) => set({ database: e.target.value })}
            placeholder={form.db_type === 'sqlite' ? '/path/to/erp.db' : 'erp'}
          />

          <Input
            label="密码 password"
            type="password"
            value={form.password}
            onChange={(e) => set({ password: e.target.value })}
            placeholder={editing ? '留空表示保留原密码' : '只读账号密码'}
          />
          {editing?.has_password && (
            <p className="text-xs text-slate-400 -mt-2">当前密码：{editing.password_masked}</p>
          )}

          <Input
            label="表白名单 allowed_tables（逗号或换行分隔）"
            value={form.allowed_tables}
            onChange={(e) => set({ allowed_tables: e.target.value })}
            placeholder={'customers\norders\nproducts'}
          />

          <label className="block">
            <span className="block text-sm font-medium text-slate-700 mb-1.5">
              字段映射 / 脱敏 field_map（JSON，可选）
            </span>
            <textarea
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-brand-500"
              rows={5}
              value={form.field_map}
              onChange={(e) => set({ field_map: e.target.value })}
              placeholder={'{\n  "phone": { "mask": "pii" },\n  "salary": { "mask": "drop" }\n}'}
            />
          </label>

          <div className="grid grid-cols-2 gap-3">
            <Input label="默认行数上限" type="number" value={String(form.row_limit)} onChange={(e) => set({ row_limit: Number(e.target.value) })} />
            <Input label="连接超时（秒）" type="number" value={String(form.connect_timeout)} onChange={(e) => set({ connect_timeout: Number(e.target.value) })} />
          </div>

          <Input
            label="高级：完整连接串覆盖 dsn_override（可选）"
            value={form.dsn_override}
            onChange={(e) => set({ dsn_override: e.target.value })}
            placeholder="留空则用上面的字段拼装"
          />

          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input type="checkbox" checked={form.is_active} onChange={(e) => set({ is_active: e.target.checked })} />
            启用
          </label>

          {formError && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-red-600 text-sm">{formError}</div>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="ghost" onClick={() => setShowForm(false)}>取消</Button>
            <Button onClick={handleSave} loading={saving}>保存</Button>
          </div>
        </div>
      </Modal>

      {/* 试查预览 */}
      <Modal
        isOpen={Boolean(queryTarget)}
        onClose={() => setQueryTarget(null)}
        title={`试查：${queryTarget?.alias || ''}`}
        description="只读等值查询，结果已按 field_map 脱敏"
        size="lg"
      >
        <div className="space-y-4">
          <div className="flex gap-2 items-end">
            <div className="flex-1">
              <Input
                label="表名 resource"
                value={queryResource}
                onChange={(e) => setQueryResource(e.target.value)}
                placeholder={queryTarget?.allowed_tables?.join(', ') || '表名'}
              />
            </div>
            <Button onClick={handleQuery} loading={querying}>查询</Button>
          </div>

          {queryResult && (
            <div>
              <p className="text-sm text-slate-500 mb-2">返回 {queryResult.count} 行</p>
              {queryResult.rows.length > 0 && (
                <div className="overflow-auto max-h-80 border border-slate-200 rounded-lg">
                  <table className="w-full text-sm">
                    <thead className="bg-slate-50 sticky top-0">
                      <tr>
                        {Object.keys(queryResult.rows[0]).map((k) => (
                          <th key={k} className="px-3 py-2 text-left text-slate-600 font-medium whitespace-nowrap">{k}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {queryResult.rows.map((row, i) => (
                        <tr key={i} className="border-t border-slate-100">
                          {Object.keys(row).map((k) => (
                            <td key={k} className="px-3 py-2 text-slate-700 whitespace-nowrap">{String(row[k])}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      </Modal>

      <ConfirmModal
        isOpen={Boolean(pendingDelete)}
        onClose={() => setPendingDelete(null)}
        onConfirm={handleDelete}
        title="删除连接器"
        message={`确定删除连接器「${pendingDelete?.alias || ''}」？引用它的工作流节点会失效。`}
        confirmText="删除"
        loading={deleting}
      />
    </div>
  )
}
