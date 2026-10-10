import React, { useEffect, useMemo, useState } from 'react'
import {
  Plus,
  Pencil,
  Trash2,
  Star,
  PlugZap,
  Loader2,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Power,
} from 'lucide-react'
import {
  llmConfigs,
  type EffectiveConfig,
  type LlmConfig,
  type LlmConfigPayload,
  type LlmProviderPreset,
} from '../services/api'
import { Button } from './ui/Button'
import { Input } from './ui/Input'
import { Modal, ConfirmModal } from './ui/Modal'
import { useToastStore } from '../stores'

interface FormState {
  alias: string
  provider: string
  base_url: string
  model: string
  api_key: string
  description: string
  temperature: number
  max_tokens: number
  is_default: boolean
}

const EMPTY_FORM: FormState = {
  alias: '',
  provider: 'openai',
  base_url: '',
  model: 'gpt-4o-mini',
  api_key: '',
  description: '',
  temperature: 0.7,
  max_tokens: 2048,
  is_default: false,
}

export default function LlmConfigPanel() {
  const { addToast } = useToastStore()

  const [configs, setConfigs] = useState<LlmConfig[]>([])
  const [providers, setProviders] = useState<LlmProviderPreset[]>([])
  const [protocolNote, setProtocolNote] = useState('')
  const [effective, setEffective] = useState<EffectiveConfig | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [busyId, setBusyId] = useState<string | null>(null)

  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState<LlmConfig | null>(null)
  const [form, setForm] = useState<FormState>(EMPTY_FORM)
  const [formError, setFormError] = useState('')
  const [saving, setSaving] = useState(false)
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null)
  const [testing, setTesting] = useState(false)

  const [pendingDelete, setPendingDelete] = useState<LlmConfig | null>(null)

  const providerMap = useMemo(() => {
    const map: Record<string, LlmProviderPreset> = {}
    providers.forEach((p) => {
      map[p.value] = p
    })
    return map
  }, [providers])

  useEffect(() => {
    void loadAll()
  }, [])

  const loadAll = async () => {
    setLoading(true)
    setLoadError('')
    try {
      const [list, presets, active] = await Promise.all([
        llmConfigs.list(),
        llmConfigs.providers(),
        llmConfigs.active(),
      ])
      setConfigs(list.configs)
      setProviders(presets.providers)
      setProtocolNote(presets.protocol_note)
      setEffective(active)
    } catch (error: any) {
      setLoadError(error?.message || '加载配置失败')
    } finally {
      setLoading(false)
    }
  }

  // ------------------------------------------------------------ 表单

  const openCreate = () => {
    setEditing(null)
    const preset = providerMap['openai']
    setForm({ ...EMPTY_FORM, base_url: preset?.base_url || '' })
    setFormError('')
    setTestResult(null)
    setShowForm(true)
  }

  const openEdit = (config: LlmConfig) => {
    setEditing(config)
    setForm({
      alias: config.alias,
      provider: config.provider,
      base_url: config.base_url,
      model: config.model,
      api_key: '', // 留空表示保留原密钥
      description: config.description,
      temperature: config.temperature,
      max_tokens: config.max_tokens,
      is_default: config.is_default,
    })
    setFormError('')
    setTestResult(null)
    setShowForm(true)
  }

  const handleProviderChange = (value: string) => {
    const preset = providerMap[value]
    setForm((prev) => {
      // 仅当当前端点为空或正好是另一个预设的默认值时才自动填充，避免覆盖用户输入
      const isPresetDefault = Object.values(providerMap).some((p) => p.base_url && p.base_url === prev.base_url)
      const nextBase = !prev.base_url || isPresetDefault ? preset?.base_url || '' : prev.base_url
      const modelInPreset = preset?.models.some((m) => m.name === prev.model)
      return {
        ...prev,
        provider: value,
        base_url: nextBase,
        model: modelInPreset ? prev.model : preset?.models[0]?.name || prev.model,
      }
    })
  }

  const buildPayload = (): LlmConfigPayload => {
    const payload: LlmConfigPayload = {
      alias: form.alias.trim(),
      provider: form.provider,
      base_url: form.base_url.trim(),
      model: form.model.trim(),
      description: form.description.trim(),
      temperature: form.temperature,
      max_tokens: form.max_tokens,
    }
    // 编辑时留空 => 不提交 api_key，后端保持原值
    if (form.api_key.trim() || !editing) {
      payload.api_key = form.api_key.trim()
    }
    if (!editing) {
      payload.is_default = form.is_default
    }
    return payload
  }

  const handleTestDraft = async () => {
    setTesting(true)
    setTestResult(null)
    setFormError('')
    try {
      if (editing && !form.api_key.trim()) {
        // 没输入新密钥时，直接测试已保存的配置
        const result = await llmConfigs.test(editing.id)
        setTestResult(result)
      } else {
        const result = await llmConfigs.testDraft({
          provider: form.provider,
          base_url: form.base_url.trim(),
          model: form.model.trim(),
          api_key: form.api_key.trim(),
        })
        setTestResult(result)
      }
    } catch (error: any) {
      setTestResult({ ok: false, message: error?.message || '测试失败' })
    } finally {
      setTesting(false)
    }
  }

  const handleSave = async () => {
    setSaving(true)
    setFormError('')
    try {
      const payload = buildPayload()
      if (editing) {
        await llmConfigs.update(editing.id, payload)
      } else {
        await llmConfigs.create(payload)
      }
      setShowForm(false)
      await loadAll()
      addToast({
        type: 'success',
        message: editing ? '配置已更新，运行时已切换（无需重启）' : '配置已创建并生效',
      })
    } catch (error: any) {
      setFormError(error?.message || '保存失败')
    } finally {
      setSaving(false)
    }
  }

  // ------------------------------------------------------------ 行内操作

  const runAction = async (id: string, action: () => Promise<unknown>, successTitle: string) => {
    setBusyId(id)
    try {
      await action()
      await loadAll()
      addToast({ type: 'success', message: successTitle })
    } catch (error: any) {
      addToast({ type: 'error', message: error?.message || '操作失败' })
    } finally {
      setBusyId(null)
    }
  }

  const handleTestSaved = async (config: LlmConfig) => {
    setBusyId(config.id)
    try {
      const result = await llmConfigs.test(config.id)
      await loadAll()
      addToast({
        type: result.ok ? 'success' : 'error',
        message: result.ok ? `连接正常：${result.message}` : `连接失败：${result.message}`,
      })
    } catch (error: any) {
      addToast({ type: 'error', message: error?.message || '测试失败' })
    } finally {
      setBusyId(null)
    }
  }

  const handleConfirmDelete = async () => {
    if (!pendingDelete) return
    const target = pendingDelete
    setBusyId(target.id)
    try {
      await llmConfigs.remove(target.id)
      setPendingDelete(null)
      await loadAll()
      addToast({ type: 'success', message: '配置已删除' })
    } catch (error: any) {
      addToast({ type: 'error', message: error?.message || '删除失败' })
    } finally {
      setBusyId(null)
    }
  }

  // ------------------------------------------------------------ 渲染

  const providerLabel = (value: string) => providerMap[value]?.label || value
  const preset = providerMap[form.provider]

  return (
    <div className="space-y-5">
      {/* 当前生效 */}
      <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50 p-4">
        <div className="flex items-center justify-between gap-4">
          <div className="min-w-0">
            <p className="text-xs text-slate-500 dark:text-slate-400 mb-1">当前生效配置</p>
            {effective && effective.source !== 'none' ? (
              <p className="text-sm text-slate-900 dark:text-white truncate">
                <span className="font-medium">{effective.alias}</span>
                <span className="text-slate-400 mx-2">·</span>
                <span className="text-slate-500 dark:text-slate-400">{effective.model}</span>
                <span className="text-slate-400 mx-2">·</span>
                <span className="text-slate-500 dark:text-slate-400 font-mono text-xs">
                  {effective.base_url || '（服务商默认端点）'}
                </span>
              </p>
            ) : (
              <p className="text-sm text-slate-500 dark:text-slate-400">
                {effective?.message || '尚未配置'}
              </p>
            )}
            {effective?.source === 'env' && (
              <p className="text-xs text-amber-600 dark:text-amber-400 mt-1">
                当前来自 .env 回退，新增配置后会自动接管
              </p>
            )}
          </div>
          <Button leftIcon={<Plus className="w-4 h-4" />} onClick={openCreate}>
            新增配置
          </Button>
        </div>
      </div>

      {protocolNote && (
        <p className="text-xs text-slate-400 flex items-start gap-1.5">
          <AlertCircle className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
          {protocolNote}
        </p>
      )}

      {loadError && (
        <div className="rounded-xl border border-red-200 bg-red-50 dark:bg-red-900/20 px-4 py-3 text-sm text-red-600 dark:text-red-400">
          {loadError}
        </div>
      )}

      {loading ? (
        <div className="flex items-center gap-2 text-slate-400 py-8 justify-center">
          <Loader2 className="w-4 h-4 animate-spin" />
          加载中…
        </div>
      ) : configs.length === 0 ? (
        <div className="text-center py-10 border border-dashed border-slate-200 dark:border-slate-700 rounded-xl">
          <p className="text-slate-500 dark:text-slate-400 mb-4">
            还没有任何配置，添加一个即可开始使用
          </p>
          <Button variant="outline" leftIcon={<Plus className="w-4 h-4" />} onClick={openCreate}>
            新增配置
          </Button>
        </div>
      ) : (
        <div className="space-y-3">
          {configs.map((config) => (
            <div
              key={config.id}
              className={`rounded-xl border p-4 transition-colors ${
                config.is_effective
                  ? 'border-indigo-300 dark:border-indigo-600 bg-indigo-50/40 dark:bg-indigo-900/10'
                  : 'border-slate-200 dark:border-slate-700'
              }`}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap mb-1.5">
                    <span className="font-medium text-slate-900 dark:text-white">{config.alias}</span>
                    {config.is_effective && <Badge tone="indigo">当前生效</Badge>}
                    {config.is_default && <Badge tone="amber">默认</Badge>}
                    {!config.is_active && <Badge tone="slate">已停用</Badge>}
                  </div>

                  <div className="text-xs text-slate-500 dark:text-slate-400 space-y-0.5">
                    <p>
                      {providerLabel(config.provider)}
                      <span className="mx-1.5">·</span>
                      <span className="font-mono">{config.model}</span>
                    </p>
                    <p className="font-mono truncate">{config.base_url || '（服务商默认端点）'}</p>
                    <p>
                      API Key：{config.has_api_key ? config.api_key_masked : <span className="text-amber-600">未设置</span>}
                    </p>
                    {config.description && <p className="truncate">{config.description}</p>}
                    {config.last_tested_at && (
                      <p className="flex items-center gap-1">
                        {config.last_test_ok ? (
                          <CheckCircle2 className="w-3 h-3 text-emerald-500" />
                        ) : (
                          <XCircle className="w-3 h-3 text-red-500" />
                        )}
                        {config.last_test_ok ? '连接测试通过' : config.last_test_error || '连接测试失败'}
                      </p>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-1 flex-shrink-0">
                  {!config.is_default && (
                    <IconAction
                      title="设为默认（立即切换，无需重启）"
                      disabled={busyId === config.id}
                      onClick={() =>
                        runAction(config.id, () => llmConfigs.setDefault(config.id), '已切换默认配置')
                      }
                    >
                      <Star className="w-4 h-4" />
                    </IconAction>
                  )}
                  <IconAction
                    title="测试连接"
                    disabled={busyId === config.id || testing}
                    onClick={() => handleTestSaved(config)}
                  >
                    {busyId === config.id ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <PlugZap className="w-4 h-4" />
                    )}
                  </IconAction>
                  <IconAction
                    title={config.is_default ? '默认配置不能停用' : config.is_active ? '停用' : '启用'}
                    disabled={busyId === config.id || config.is_default}
                    onClick={() =>
                      runAction(
                        config.id,
                        () => llmConfigs.setActive(config.id, !config.is_active),
                        config.is_active ? '已停用' : '已启用'
                      )
                    }
                  >
                    <Power className="w-4 h-4" />
                  </IconAction>
                  <IconAction title="编辑" disabled={busyId === config.id} onClick={() => openEdit(config)}>
                    <Pencil className="w-4 h-4" />
                  </IconAction>
                  <IconAction
                    title="删除"
                    danger
                    disabled={busyId === config.id}
                    onClick={() => setPendingDelete(config)}
                  >
                    <Trash2 className="w-4 h-4" />
                  </IconAction>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 新增 / 编辑 */}
      <Modal
        isOpen={showForm}
        onClose={() => setShowForm(false)}
        title={editing ? `编辑配置：${editing.alias}` : '新增模型配置'}
        description="保存后立即生效，正在进行的请求不受影响"
        size="lg"
      >
        <div className="space-y-4">
          {formError && (
            <div className="rounded-lg border border-red-200 bg-red-50 dark:bg-red-900/20 px-3 py-2 text-sm text-red-600 dark:text-red-400">
              {formError}
            </div>
          )}

          <Input
            label="别名"
            placeholder="例如：生产环境-OpenAI"
            value={form.alias}
            onChange={(e) => setForm({ ...form, alias: e.target.value })}
            required
          />

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1.5">
                服务商
              </label>
              <select
                value={form.provider}
                onChange={(e) => handleProviderChange(e.target.value)}
                className="w-full px-3 py-2.5 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 text-sm text-slate-900 dark:text-white"
              >
                {providers.map((p) => (
                  <option key={p.value} value={p.value}>
                    {p.label}
                  </option>
                ))}
              </select>
              {preset?.hint && <p className="text-xs text-slate-400 mt-1">{preset.hint}</p>}
            </div>

            <Input
              label="模型"
              placeholder="gpt-4o-mini"
              value={form.model}
              onChange={(e) => setForm({ ...form, model: e.target.value })}
              list="llm-model-options"
              required
            />
            <datalist id="llm-model-options">
              {preset?.models.map((m) => (
                <option key={m.name} value={m.name}>
                  {m.display_name}
                </option>
              ))}
            </datalist>
          </div>

          <Input
            label="Base URL"
            placeholder="https://api.openai.com/v1"
            value={form.base_url}
            onChange={(e) => setForm({ ...form, base_url: e.target.value })}
            hint="需为 OpenAI 兼容端点，通常以 /v1 结尾"
            required
          />

          <Input
            label="API Key"
            type="password"
            placeholder={
              editing && editing.has_api_key
                ? `留空则保持原密钥（${editing.api_key_masked}）`
                : 'sk-...'
            }
            value={form.api_key}
            onChange={(e) => setForm({ ...form, api_key: e.target.value })}
            hint={preset?.requires_key ? '该服务商需要填写密钥' : '该服务商通常无需密钥'}
          />

          <Input
            label="备注"
            placeholder="可选"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
          />

          <div className="grid grid-cols-2 gap-4">
            <Input
              label={`温度：${form.temperature}`}
              type="number"
              step="0.1"
              min="0"
              max="2"
              value={String(form.temperature)}
              onChange={(e) => setForm({ ...form, temperature: Number(e.target.value) })}
            />
            <Input
              label="最大输出 tokens"
              type="number"
              min="1"
              value={String(form.max_tokens)}
              onChange={(e) => setForm({ ...form, max_tokens: Number(e.target.value) })}
            />
          </div>

          {!editing && (
            <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300 cursor-pointer">
              <input
                type="checkbox"
                checked={form.is_default}
                onChange={(e) => setForm({ ...form, is_default: e.target.checked })}
                className="w-4 h-4 rounded border-slate-300 text-indigo-500 focus:ring-indigo-500"
              />
              设为默认配置（保存后立即生效）
            </label>
          )}

          {testResult && (
            <div
              className={`rounded-lg px-3 py-2 text-sm flex items-start gap-2 ${
                testResult.ok
                  ? 'bg-emerald-50 dark:bg-emerald-900/20 text-emerald-700 dark:text-emerald-400'
                  : 'bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400'
              }`}
            >
              {testResult.ok ? (
                <CheckCircle2 className="w-4 h-4 mt-0.5 flex-shrink-0" />
              ) : (
                <XCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
              )}
              {testResult.message}
            </div>
          )}

          <div className="flex items-center justify-between pt-2">
            <Button
              variant="outline"
              onClick={handleTestDraft}
              loading={testing}
              leftIcon={<PlugZap className="w-4 h-4" />}
            >
              测试连接
            </Button>
            <div className="flex gap-2">
              <Button variant="ghost" onClick={() => setShowForm(false)}>
                取消
              </Button>
              <Button onClick={handleSave} loading={saving}>
                保存
              </Button>
            </div>
          </div>
        </div>
      </Modal>

      <ConfirmModal
        isOpen={Boolean(pendingDelete)}
        onClose={() => setPendingDelete(null)}
        onConfirm={handleConfirmDelete}
        title="删除配置"
        message={`确定要删除「${pendingDelete?.alias}」吗？如果它是默认配置，系统会自动选用其它可用配置。`}
        confirmText="删除"
        loading={busyId === pendingDelete?.id}
      />
    </div>
  )
}

// ---------------------------------------------------------------- 小组件

function Badge({ children, tone }: { children: React.ReactNode; tone: 'indigo' | 'amber' | 'slate' }) {
  const tones = {
    indigo: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300',
    amber: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300',
    slate: 'bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300',
  }
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${tones[tone]}`}>{children}</span>
  )
}

function IconAction({
  children,
  title,
  onClick,
  disabled,
  danger,
}: {
  children: React.ReactNode
  title: string
  onClick: () => void
  disabled?: boolean
  danger?: boolean
}) {
  return (
    <button
      type="button"
      title={title}
      onClick={onClick}
      disabled={disabled}
      className={`p-2 rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${
        danger
          ? 'text-slate-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20'
          : 'text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-700'
      }`}
    >
      {children}
    </button>
  )
}
