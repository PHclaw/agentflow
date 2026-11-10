import React, { useCallback, useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  User,
  Key,
  Bell,
  Palette,
  Globe,
  Shield,
  CreditCard,
  Code,
  Database,
  Check,
  Copy,
  Eye,
  EyeOff,
  Plus,
  Trash2,
  Edit2,
  Save,
  RefreshCw,
  Moon,
  Sun,
  Monitor,
} from 'lucide-react'
import { api, auth, billing } from '../services/api'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Card } from '../components/ui/Card'
import { Modal } from '../components/ui/Modal'
import { useThemeStore } from '../hooks/useTheme'
import { useAuthStore, useToastStore } from '../stores'
import { formatDate } from '../utils/datetime'
import LlmConfigPanel from '../components/LlmConfigPanel'
import ErpConnectorPanel from '../components/ErpConnectorPanel'

type Tab = 'profile' | 'api-keys' | 'models' | 'connectors' | 'appearance' | 'notifications' | 'billing'

/** 合法的标签 id。用于校验 ``?tab=`` 参数，见 SettingsPage 里的初始化。 */
const TAB_IDS: Tab[] = [
  'profile',
  'api-keys',
  'models',
  'connectors',
  'appearance',
  'notifications',
  'billing',
]

interface APIKey {
  id: string
  name: string
  key: string
  created_at: string
  last_used: string | null
}

/** 后端 /billing/plans 返回的套餐。 */
interface BillingPlan {
  id: string
  name: string
  price: number
  agents: number
  messages: number
  features: string[]
}

/** 后端 /billing/subscription 返回的订阅状态。 */
interface SubscriptionInfo {
  plan: string
  status: string
  agents_used: number
  messages_used: number
  agents_limit: number
  messages_limit: number
  current_period_end: string | null
}

//: 套餐 id 到中文名的映射。后端存的是 free/pro/team。
const PLAN_LABELS: Record<string, string> = {
  free: '免费版',
  pro: '进阶版',
  team: '团队版',
}

/**
 * 用量进度条。
 *
 * 接近上限时变色：用户该在撞墙之前看到预警，
 * 而不是等一次 402 弹到脸上才知道额度用完了。
 */
function UsageBar({ label, used, limit }: { label: string; used: number; limit: number }) {
  const safeLimit = limit > 0 ? limit : 0
  const pct = safeLimit > 0 ? Math.min(100, Math.round((used / safeLimit) * 100)) : 0
  const nearLimit = pct >= 80

  return (
    <div>
      <div className="flex items-center justify-between text-sm mb-1.5">
        <span className="text-slate-600 dark:text-slate-400">{label}</span>
        <span
          className={
            nearLimit
              ? 'text-amber-600 dark:text-amber-400 font-medium'
              : 'text-slate-600 dark:text-slate-400'
          }
        >
          {used} / {safeLimit}
        </span>
      </div>
      <div className="h-2 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${
            nearLimit ? 'bg-amber-500' : 'bg-brand-500'
          }`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

export default function SettingsPage() {
  /**
   * 支持 ``/settings?tab=models`` 直达某个标签。
   *
   * 帮助中心里「模型配置」「订阅」这些条目要能一次点到位置上 —— 只把用户
   * 送到设置页、再让他自己找是第几个标签，等于把指引的最后一公里丢给用户。
   */
  const [searchParams, setSearchParams] = useSearchParams()
  const [activeTab, setActiveTab] = useState<Tab>(() => {
    const want = searchParams.get('tab')
    return (TAB_IDS as string[]).includes(want || '') ? (want as Tab) : 'profile'
  })

  /** 切标签时把状态写回地址栏：刷新、后退、分享链接都能回到同一个标签。 */
  const selectTab = useCallback(
    (id: Tab) => {
      setActiveTab(id)
      setSearchParams(id === 'profile' ? {} : { tab: id }, { replace: true })
    },
    [setSearchParams],
  )
  const [apiKeys, setApiKeys] = useState<APIKey[]>([])
  const [showCreateKeyModal, setShowCreateKeyModal] = useState(false)
  const [newKeyName, setNewKeyName] = useState('')
  const [showNewKey, setShowNewKey] = useState(false)
  const [createdKey, setCreatedKey] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  // 个人资料。原来整个页是写死的假数据（Admin User / admin@example.com /
  // AgentFlow Inc.），输入框是非受控的 defaultValue，「保存更改」按钮没有
  // onClick —— 改什么都不会发生，也没有任何提示。后端那时也确实没有
  // PATCH /users/me，现在补齐了，这里改成真实读写。
  const [me, setMe] = useState<any>(null)
  const [meLoading, setMeLoading] = useState(false)
  const [meSaving, setMeSaving] = useState(false)
  const [avatarBusy, setAvatarBusy] = useState(false)
  const [nickname, setNickname] = useState('')
  const [phone, setPhone] = useState('')

  // 修改密码。成功后 token 会失效，所以必须走 auth.logout() 清干净再跳登录页 ——
  // 只弹个 toast 的话用户还停在设置页，下一个请求就 401，看起来像功能坏了。
  const [oldPwd, setOldPwd] = useState('')
  const [newPwd, setNewPwd] = useState('')
  const [newPwd2, setNewPwd2] = useState('')
  const [pwdSaving, setPwdSaving] = useState(false)
  const [pwdError, setPwdError] = useState('')

  // 订阅数据。原先这里是写死的假套餐和假用量（¥199/¥599、45,230 条消息），
  // 和后端 /billing 的实际额度对不上，用户看到的和能用的不是一回事。
  const [plans, setPlans] = useState<BillingPlan[]>([])
  const [subscription, setSubscription] = useState<SubscriptionInfo | null>(null)
  const [subLoading, setSubLoading] = useState(false)
  const [subError, setSubError] = useState('')

  const { theme, setTheme, resolvedTheme } = useThemeStore()
  const { addToast } = useToastStore()
  const logout = useAuthStore((s) => s.logout)
  const navigate = useNavigate()

  const loadMe = useCallback(async () => {
    setMeLoading(true)
    try {
      const data: any = await auth.getCurrentUser()
      setMe(data)
      setNickname(data?.nickname || '')
      setPhone(data?.phone || '')
    } catch (e: any) {
      addToast({ type: 'error', message: e?.message || '加载个人资料失败' })
    } finally {
      setMeLoading(false)
    }
  }, [addToast])

  useEffect(() => {
    loadSettings()
    loadMe()
  }, [loadMe])

  const saveProfile = async () => {
    setMeSaving(true)
    try {
      const updated: any = await auth.updateProfile({
        nickname: nickname.trim(),
        phone: phone.trim(),
      })
      setMe(updated)
      addToast({ type: 'success', message: '个人资料已保存' })
    } catch (e: any) {
      addToast({ type: 'error', message: e?.message || '保存失败' })
    } finally {
      setMeSaving(false)
    }
  }

  const onPickAvatar = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    // 必须清空：同一个文件第二次选不到 change 事件，用户会以为点了没反应
    e.target.value = ''
    if (!file) return
    if (file.size > 2 * 1024 * 1024) {
      addToast({ type: 'error', message: '头像不能超过 2MB' })
      return
    }
    setAvatarBusy(true)
    try {
      const res: any = await auth.uploadAvatar(file)
      setMe((prev: any) => (prev ? { ...prev, avatar: res.avatar } : prev))
      addToast({ type: 'success', message: '头像已更新' })
    } catch (err: any) {
      addToast({ type: 'error', message: err?.message || '头像上传失败' })
    } finally {
      setAvatarBusy(false)
    }
  }

  const onRemoveAvatar = async () => {
    setAvatarBusy(true)
    try {
      await auth.deleteAvatar()
      setMe((prev: any) => (prev ? { ...prev, avatar: null } : prev))
      addToast({ type: 'success', message: '已恢复默认头像' })
    } catch (err: any) {
      addToast({ type: 'error', message: err?.message || '操作失败' })
    } finally {
      setAvatarBusy(false)
    }
  }

  const changePassword = async () => {
    setPwdError('')
    if (newPwd !== newPwd2) {
      setPwdError('两次输入的新密码不一致')
      return
    }
    if (newPwd.length < 8) {
      setPwdError('新密码至少 8 位')
      return
    }
    setPwdSaving(true)
    try {
      await auth.changePassword({ old_password: oldPwd, new_password: newPwd })
      addToast({ type: 'success', message: '密码已修改，请重新登录' })
      // 后端已让所有 token 失效，这里主动登出并跳登录页，
      // 而不是等下一个请求 401 才被踢走
      auth.logout()
      logout()
      navigate('/login')
    } catch (e: any) {
      setPwdError(e?.message || '修改失败')
    } finally {
      setPwdSaving(false)
    }
  }

  // 只在切到订阅页时才拉数据，避免每次进设置页都多发两个请求
  useEffect(() => {
    if (activeTab !== 'billing') return

    let cancelled = false
    const loadBilling = async () => {
      setSubLoading(true)
      setSubError('')
      try {
        const [plansRes, subRes] = await Promise.all([
          billing.listPlans(),
          billing.getSubscription(),
        ])
        if (cancelled) return
        setPlans(plansRes?.plans || [])
        setSubscription(subRes || null)
      } catch (e: any) {
        if (!cancelled) setSubError(e?.message || '加载订阅信息失败')
      } finally {
        if (!cancelled) setSubLoading(false)
      }
    }

    loadBilling()
    return () => {
      cancelled = true
    }
  }, [activeTab])

  const loadSettings = () => {
    // 模拟加载设置
    setApiKeys([
      {
        id: '1',
        name: '生产环境密钥',
        key: 'sk-live-xxxx...xxxx',
        created_at: '2024-01-15T10:30:00Z',
        last_used: '2024-01-20T15:45:00Z',
      },
      {
        id: '2',
        name: '测试环境密钥',
        key: 'sk-test-xxxx...xxxx',
        created_at: '2024-01-10T09:00:00Z',
        last_used: null,
      },
    ])

    // 模型配置改为由 LlmConfigPanel 直接对接后端 /api/v1/llm-configs
  }

  const handleCreateKey = async () => {
    if (!newKeyName.trim()) return

    setSaving(true)
    // 模拟创建
    await new Promise((resolve) => setTimeout(resolve, 1000))
    
    const newKey = `sk-${Math.random().toString(36).substring(2, 15)}${Math.random().toString(36).substring(2, 15)}`
    setCreatedKey(newKey)
    setApiKeys([
      {
        id: Date.now().toString(),
        name: newKeyName,
        key: newKey,
        created_at: new Date().toISOString(),
        last_used: null,
      },
      ...apiKeys,
    ])
    setNewKeyName('')
    setSaving(false)
  }

  const tabs = [
    { id: 'profile' as Tab, label: '个人资料', icon: User },
    { id: 'api-keys' as Tab, label: 'API 密钥', icon: Key },
    { id: 'models' as Tab, label: '模型配置', icon: Code },
    { id: 'connectors' as Tab, label: '数据连接器', icon: Database },
    { id: 'appearance' as Tab, label: '外观', icon: Palette },
    { id: 'notifications' as Tab, label: '通知', icon: Bell },
    { id: 'billing' as Tab, label: '订阅', icon: CreditCard },
  ]

  return (
    <div className="p-6 lg:p-8 max-w-6xl mx-auto">
      <h1 className="text-2xl font-bold text-slate-900 dark:text-white mb-8">
        设置
      </h1>

      <div className="flex flex-col lg:flex-row gap-8">
        {/* Sidebar */}
        <div className="w-full lg:w-64 flex-shrink-0">
          <nav className="flex lg:flex-col gap-1 overflow-x-auto lg:overflow-visible pb-2 lg:pb-0">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => selectTab(tab.id)}
                className={`flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm font-medium whitespace-nowrap transition-colors ${
                  activeTab === tab.id
                    ? 'bg-brand-50 dark:bg-brand-900/30 text-brand-600 dark:text-brand-400'
                    : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
                }`}
              >
                <tab.icon className="w-5 h-5" />
                {tab.label}
              </button>
            ))}
          </nav>
        </div>

        {/* Content */}
        <div className="flex-1">
          {activeTab === 'profile' && (
            <Card className="p-6">
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-6">
                个人资料
              </h2>

              {meLoading && !me && (
                <p className="text-sm text-slate-500 dark:text-slate-400">正在加载…</p>
              )}

              {me && (
                <div className="space-y-6">
                  {/* 头像：真实上传。原来的「更换头像」按钮没有 onClick，
                      点一万次也不会弹出文件选择框。 */}
                  <div className="flex items-center gap-6">
                    {me.avatar ? (
                      <img
                        src={me.avatar}
                        alt="头像"
                        className="w-20 h-20 rounded-2xl object-cover bg-slate-100 dark:bg-slate-800"
                      />
                    ) : (
                      <div className="w-20 h-20 rounded-2xl bg-slate-900 dark:bg-white flex items-center justify-center text-white dark:text-slate-900 text-2xl font-bold">
                        {(me.nickname || me.email || '?').slice(0, 1).toUpperCase()}
                      </div>
                    )}
                    <div>
                      <div className="flex items-center gap-2">
                        <label className="inline-flex">
                          <input
                            type="file"
                            accept=".jpg,.jpeg,.png,.webp"
                            className="hidden"
                            onChange={onPickAvatar}
                            disabled={avatarBusy}
                          />
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={avatarBusy}
                            onClick={() => {
                              // Button 不会替 label 触发文件选择，得手动点
                              const input = document.querySelector<HTMLInputElement>(
                                'input[type="file"][accept^=".jpg"]'
                              )
                              input?.click()
                            }}
                          >
                            {avatarBusy ? '处理中…' : '更换头像'}
                          </Button>
                        </label>
                        {me.avatar && (
                          <Button
                            variant="ghost"
                            size="sm"
                            disabled={avatarBusy}
                            onClick={onRemoveAvatar}
                          >
                            移除
                          </Button>
                        )}
                      </div>
                      <p className="text-sm text-slate-500 mt-2">支持 JPG、PNG、WebP，最大 2MB</p>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <Input
                      label="昵称"
                      value={nickname}
                      onChange={(e) => setNickname(e.target.value)}
                      placeholder="留空则显示邮箱前缀"
                      maxLength={50}
                    />
                    {/* 邮箱只读。它不是"懒得做"，而是改它牵扯登录标识、
                        管理员白名单和验证码投递三处，需要配套流程。 */}
                    <div>
                      <Input label="邮箱" value={me.email || ''} disabled />
                      <p className="text-xs text-slate-400 mt-1">
                        邮箱用于登录，暂不支持自助修改
                      </p>
                    </div>
                    <Input
                      label="手机号"
                      type="tel"
                      value={phone}
                      onChange={(e) => setPhone(e.target.value)}
                      placeholder="选填"
                    />
                  </div>

                  <div className="flex justify-end">
                    <Button
                      leftIcon={<Save className="w-4 h-4" />}
                      onClick={saveProfile}
                      disabled={meSaving}
                    >
                      {meSaving ? '保存中…' : '保存更改'}
                    </Button>
                  </div>
                </div>
              )}

              {/* 修改密码。原来是整块缺失 —— 后端没有接口，前端也没有入口，
                  用户想改密码只能找管理员改库。 */}
              <div className="mt-8 pt-8 border-t border-slate-200 dark:border-slate-800">
                <h3 className="text-[15px] font-semibold text-slate-900 dark:text-white mb-1">
                  修改密码
                </h3>
                <p className="text-[13px] text-slate-500 dark:text-slate-400 mb-5">
                  修改成功后需要重新登录，其它设备上的登录状态也会一并失效。
                </p>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-2xl">
                  <Input
                    label="当前密码"
                    type="password"
                    value={oldPwd}
                    onChange={(e) => setOldPwd(e.target.value)}
                    placeholder="请输入当前密码"
                    autoComplete="current-password"
                  />
                  <div />
                  <Input
                    label="新密码"
                    type="password"
                    value={newPwd}
                    onChange={(e) => setNewPwd(e.target.value)}
                    placeholder="至少 8 位"
                    autoComplete="new-password"
                  />
                  <Input
                    label="确认新密码"
                    type="password"
                    value={newPwd2}
                    onChange={(e) => setNewPwd2(e.target.value)}
                    placeholder="再输一次"
                    autoComplete="new-password"
                  />
                </div>

                {pwdError && (
                  <p className="mt-3 text-[13px] text-red-600 dark:text-red-400">{pwdError}</p>
                )}

                <div className="mt-5">
                  <Button
                    leftIcon={<Key className="w-4 h-4" />}
                    onClick={changePassword}
                    disabled={pwdSaving || !oldPwd || !newPwd || !newPwd2}
                  >
                    {pwdSaving ? '提交中…' : '修改密码'}
                  </Button>
                </div>
              </div>
            </Card>
          )}

          {activeTab === 'api-keys' && (
            <Card className="p-6">
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h2 className="text-lg font-semibold text-slate-900 dark:text-white">
                    API 密钥
                  </h2>
                  <p className="text-sm text-slate-500 mt-1">
                    用于访问 AgentFlow API
                  </p>
                </div>
                <Button
                  leftIcon={<Plus className="w-4 h-4" />}
                  onClick={() => setShowCreateKeyModal(true)}
                >
                  创建密钥
                </Button>
              </div>

              <div className="space-y-3">
                {apiKeys.map((apiKey) => (
                  <div
                    key={apiKey.id}
                    className="flex items-center justify-between p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50"
                  >
                    <div>
                      <p className="font-medium text-slate-900 dark:text-white">
                        {apiKey.name}
                      </p>
                      <p className="text-sm text-slate-500 font-mono mt-1">
                        {apiKey.key}
                      </p>
                      <p className="text-xs text-slate-400 mt-2">
                        创建于 {new Date(apiKey.created_at).toLocaleDateString('zh-CN')}
                        {apiKey.last_used && ` · 最后使用于 ${new Date(apiKey.last_used).toLocaleDateString('zh-CN')}`}
                      </p>
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => navigator.clipboard.writeText(apiKey.key)}
                        className="p-2 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100"
                      >
                        <Copy className="w-4 h-4" />
                      </button>
                      <button className="p-2 rounded-lg text-red-500 hover:bg-red-50">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>

              <div className="mt-6 p-4 rounded-xl bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800">
                <p className="text-sm text-amber-800 dark:text-amber-200">
                  <strong>安全提示：</strong>请妥善保管您的 API 密钥，不要泄露给他人。如果密钥被盗，请立即删除并重新创建。
                </p>
              </div>
            </Card>
          )}

          {activeTab === 'models' && (
            <Card className="p-6">
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-1">
                大模型 API 配置
              </h2>
              <p className="text-sm text-slate-500 dark:text-slate-400 mb-6">
                填写自己的密钥与端点。保存后立即生效，无需重启服务。
              </p>
              <LlmConfigPanel />
            </Card>
          )}

          {activeTab === 'connectors' && (
            <Card className="p-6">
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-1">
                外部数据连接器
              </h2>
              <p className="text-sm text-slate-500 dark:text-slate-400 mb-6">
                接入第三方 ERP 等数据源（仅只读）。凭证加密存储，表名白名单 + 字段脱敏。
              </p>
              <ErpConnectorPanel />
            </Card>
          )}

          {activeTab === 'appearance' && (
            <Card className="p-6">
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-6">
                外观设置
              </h2>
              
              <div className="mb-8">
                <p className="font-medium text-slate-900 dark:text-white mb-4">主题</p>
                <div className="grid grid-cols-3 gap-2 sm:gap-4">
                  <button
                    onClick={() => setTheme('light')}
                    className={`p-3 sm:p-4 rounded-xl border-2 transition-colors ${
                      theme === 'light' || (theme === 'system' && resolvedTheme === 'light')
                        ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/30'
                        : 'border-slate-200 dark:border-slate-700 hover:border-slate-300'
                    }`}
                  >
                    <Sun className="w-8 h-8 mx-auto mb-2 text-amber-500" />
                    <p className="text-sm font-medium text-slate-900 dark:text-white">浅色</p>
                  </button>
                  <button
                    onClick={() => setTheme('dark')}
                    className={`p-3 sm:p-4 rounded-xl border-2 transition-colors ${
                      theme === 'dark' || (theme === 'system' && resolvedTheme === 'dark')
                        ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/30'
                        : 'border-slate-200 dark:border-slate-700 hover:border-slate-300'
                    }`}
                  >
                    <Moon className="w-8 h-8 mx-auto mb-2 text-brand-500" />
                    <p className="text-sm font-medium text-slate-900 dark:text-white">深色</p>
                  </button>
                  <button
                    onClick={() => setTheme('system')}
                    className={`p-3 sm:p-4 rounded-xl border-2 transition-colors ${
                      theme === 'system'
                        ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/30'
                        : 'border-slate-200 dark:border-slate-700 hover:border-slate-300'
                    }`}
                  >
                    <Monitor className="w-8 h-8 mx-auto mb-2 text-slate-500" />
                    <p className="text-sm font-medium text-slate-900 dark:text-white">跟随系统</p>
                  </button>
                </div>
              </div>

              <div>
                <p className="font-medium text-slate-900 dark:text-white mb-4">语言</p>
                <select className="w-full px-4 py-3 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white">
                  <option value="zh-CN">简体中文</option>
                  <option value="en">English</option>
                  <option value="ja">日本語</option>
                </select>
              </div>
            </Card>
          )}

          {activeTab === 'notifications' && (
            <Card className="p-6">
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-6">
                通知设置
              </h2>
              <div className="space-y-4">
                {[
                  { label: '对话消息通知', description: '当收到新消息时通知', defaultChecked: true },
                  { label: '使用量警告', description: '当 API 使用量达到 80% 时通知', defaultChecked: true },
                  { label: '系统公告', description: '接收产品更新和公告', defaultChecked: false },
                  { label: '营销邮件', description: '接收促销和活动信息', defaultChecked: false },
                ].map((item, i) => (
                  <div key={i} className="flex items-center justify-between p-4 rounded-xl hover:bg-slate-50 dark:hover:bg-slate-800/50">
                    <div>
                      <p className="font-medium text-slate-900 dark:text-white">{item.label}</p>
                      <p className="text-sm text-slate-500">{item.description}</p>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input type="checkbox" defaultChecked={item.defaultChecked} className="sr-only peer" />
                      <div className="w-11 h-6 bg-slate-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-brand-300 dark:peer-focus:ring-brand-800 rounded-full peer dark:bg-slate-700 peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-slate-600 peer-checked:bg-brand-600"></div>
                    </label>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {activeTab === 'billing' && (
            <Card className="p-6">
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-6">
                订阅计划
              </h2>

              {subLoading && (
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  正在加载订阅信息…
                </p>
              )}

              {subError && (
                <p className="text-sm text-red-600 dark:text-red-400">{subError}</p>
              )}

              {!subLoading && !subError && subscription && (
                <>
                  {/* 当前套餐与真实用量 */}
                  <div className="p-5 rounded-2xl bg-brand-50 dark:bg-brand-900/20 border border-brand-100 dark:border-brand-800 mb-8">
                    <div className="flex items-center justify-between mb-4">
                      <div>
                        <p className="text-xs text-brand-600 dark:text-brand-400 font-medium tracking-wider">
                          当前套餐
                        </p>
                        <p className="text-lg font-semibold text-slate-900 dark:text-white mt-0.5">
                          {PLAN_LABELS[subscription.plan] || subscription.plan}
                        </p>
                      </div>
                      {subscription.current_period_end && (
                        <p className="text-xs text-slate-500 dark:text-slate-400 text-right">
                          额度将于
                          <br />
                          {formatDate(subscription.current_period_end)}
                          {' '}重置
                        </p>
                      )}
                    </div>

                    <div className="space-y-3">
                      <UsageBar
                        label="Agent 数量"
                        used={subscription.agents_used}
                        limit={subscription.agents_limit}
                      />
                      <UsageBar
                        label="本月消息"
                        used={subscription.messages_used}
                        limit={subscription.messages_limit}
                      />
                    </div>
                  </div>

                  {/* 套餐列表：额度与价格都来自后端，不再前端各写一份 */}
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {plans.map((plan) => {
                      const isCurrent = plan.id === subscription.plan
                      return (
                        <div
                          key={plan.id}
                          className={`p-6 rounded-2xl border-2 ${
                            isCurrent
                              ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/30'
                              : 'border-slate-200 dark:border-slate-700'
                          }`}
                        >
                          {isCurrent && (
                            <span className="inline-block px-3 py-1 rounded-full bg-brand-500 text-white text-xs font-medium mb-4">
                              当前计划
                            </span>
                          )}
                          <p className="font-semibold text-slate-900 dark:text-white">
                            {PLAN_LABELS[plan.id] || plan.name}
                          </p>
                          <p className="text-3xl font-bold text-slate-900 dark:text-white mt-2">
                            {plan.price === 0 ? '免费' : `¥${plan.price}`}
                            <span className="text-base font-normal text-slate-500">/月</span>
                          </p>
                          <ul className="mt-4 space-y-2">
                            {(plan.features || []).map((feature, j) => (
                              <li
                                key={j}
                                className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400"
                              >
                                <Check className="w-4 h-4 text-emerald-500 flex-shrink-0" />
                                {feature}
                              </li>
                            ))}
                          </ul>
                          <Button
                            variant={isCurrent ? 'outline' : 'primary'}
                            className="w-full mt-6"
                            disabled={isCurrent}
                            title={isCurrent ? undefined : '在线支付尚未开通，请联系管理员手动升级'}
                          >
                            {isCurrent ? '当前计划' : '升级'}
                          </Button>
                        </div>
                      )
                    })}
                  </div>

                  <p className="mt-6 text-xs text-slate-400 dark:text-slate-500">
                    如需升级，请联系管理员开通；升级后 Agent 数量与消息额度会立即提升。
                  </p>
                </>
              )}
            </Card>
          )}
        </div>
      </div>

      {/* Create Key Modal */}
      <Modal
        isOpen={showCreateKeyModal}
        onClose={() => {
          setShowCreateKeyModal(false)
          setCreatedKey(null)
          setNewKeyName('')
        }}
        title={createdKey ? 'API 密钥已创建' : '创建 API 密钥'}
      >
        {createdKey ? (
          <div className="space-y-4">
            <div className="p-4 rounded-xl bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800">
              <p className="text-sm text-amber-800 dark:text-amber-200">
                <strong>请立即复制密钥：</strong> 关闭此对话框后，您将无法再次查看此密钥。
              </p>
            </div>
            <div className="flex gap-2">
              <code className="flex-1 p-3 rounded-lg bg-slate-100 dark:bg-slate-800 text-sm font-mono break-all">
                {createdKey}
              </code>
              <Button
                variant="outline"
                onClick={() => navigator.clipboard.writeText(createdKey)}
              >
                <Copy className="w-4 h-4" />
              </Button>
            </div>
            <div className="flex justify-end">
              <Button onClick={() => {
                setShowCreateKeyModal(false)
                setCreatedKey(null)
              }}>
                完成
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <Input
              label="密钥名称"
              placeholder="例如：生产环境密钥"
              value={newKeyName}
              onChange={(e) => setNewKeyName(e.target.value)}
            />
            <div className="flex justify-end gap-3">
              <Button variant="outline" onClick={() => setShowCreateKeyModal(false)}>
                取消
              </Button>
              <Button onClick={handleCreateKey} disabled={!newKeyName.trim() || saving}>
                {saving ? '创建中...' : '创建'}
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
