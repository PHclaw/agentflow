import React, { useState, useEffect } from 'react'
import {
  User,
  Key,
  Bell,
  Palette,
  Globe,
  Shield,
  CreditCard,
  Code,
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
import { api } from '../services/api'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Card } from '../components/ui/Card'
import { Modal } from '../components/ui/Modal'
import { useThemeStore } from '../hooks/useTheme'

type Tab = 'profile' | 'api-keys' | 'models' | 'appearance' | 'notifications' | 'billing'

interface APIKey {
  id: string
  name: string
  key: string
  created_at: string
  last_used: string | null
}

interface ModelConfig {
  id: string
  name: string
  provider: 'openai' | 'anthropic' | 'deepseek'
  api_key: string
  enabled: boolean
}

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<Tab>('profile')
  const [apiKeys, setApiKeys] = useState<APIKey[]>([])
  const [models, setModels] = useState<ModelConfig[]>([])
  const [showCreateKeyModal, setShowCreateKeyModal] = useState(false)
  const [newKeyName, setNewKeyName] = useState('')
  const [showNewKey, setShowNewKey] = useState(false)
  const [createdKey, setCreatedKey] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const { theme, setTheme, resolvedTheme } = useThemeStore()

  useEffect(() => {
    loadSettings()
  }, [])

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

    setModels([
      {
        id: '1',
        name: 'OpenAI',
        provider: 'openai',
        api_key: '',
        enabled: true,
      },
      {
        id: '2',
        name: 'Anthropic Claude',
        provider: 'anthropic',
        api_key: '',
        enabled: true,
      },
      {
        id: '3',
        name: 'DeepSeek',
        provider: 'deepseek',
        api_key: '',
        enabled: false,
      },
    ])
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

  const handleSaveModel = async (model: ModelConfig) => {
    setSaving(true)
    await new Promise((resolve) => setTimeout(resolve, 500))
    setModels(models.map((m) => (m.id === model.id ? model : m)))
    setSaving(false)
  }

  const tabs = [
    { id: 'profile' as Tab, label: '个人资料', icon: User },
    { id: 'api-keys' as Tab, label: 'API 密钥', icon: Key },
    { id: 'models' as Tab, label: '模型配置', icon: Code },
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
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm font-medium whitespace-nowrap transition-colors ${
                  activeTab === tab.id
                    ? 'bg-indigo-50 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-400'
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
              <div className="space-y-6">
                <div className="flex items-center gap-6">
                  <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white text-2xl font-bold">
                    A
                  </div>
                  <div>
                    <Button variant="outline" size="sm">更换头像</Button>
                    <p className="text-sm text-slate-500 mt-2">支持 JPG、PNG，最大 2MB</p>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <Input label="姓名" defaultValue="Admin User" />
                  <Input label="邮箱" type="email" defaultValue="admin@example.com" />
                  <Input label="手机号" type="tel" defaultValue="+86 138****8888" />
                  <Input label="公司" defaultValue="AgentFlow Inc." />
                </div>

                <div className="flex justify-end">
                  <Button leftIcon={<Save className="w-4 h-4" />}>
                    保存更改
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
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-6">
                模型配置
              </h2>
              <div className="space-y-6">
                {models.map((model) => (
                  <div
                    key={model.id}
                    className="p-4 rounded-xl border border-slate-200 dark:border-slate-700"
                  >
                    <div className="flex items-center justify-between mb-4">
                      <div className="flex items-center gap-3">
                        <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                          model.provider === 'openai'
                            ? 'bg-emerald-100 text-emerald-600'
                            : model.provider === 'anthropic'
                            ? 'bg-orange-100 text-orange-600'
                            : 'bg-blue-100 text-blue-600'
                        }`}>
                          <Code className="w-5 h-5" />
                        </div>
                        <div>
                          <p className="font-medium text-slate-900 dark:text-white">
                            {model.name}
                          </p>
                          <p className="text-sm text-slate-500 capitalize">
                            {model.provider}
                          </p>
                        </div>
                      </div>
                      <label className="relative inline-flex items-center cursor-pointer">
                        <input
                          type="checkbox"
                          checked={model.enabled}
                          onChange={(e) =>
                            setModels(
                              models.map((m) =>
                                m.id === model.id ? { ...m, enabled: e.target.checked } : m
                              )
                            )
                          }
                          className="sr-only peer"
                        />
                        <div className="w-11 h-6 bg-slate-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-indigo-300 dark:peer-focus:ring-indigo-800 rounded-full peer dark:bg-slate-700 peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-slate-600 peer-checked:bg-indigo-600"></div>
                      </label>
                    </div>

                    <div className="space-y-4">
                      <Input
                        label="API Key"
                        type="password"
                        placeholder="输入 API Key"
                        value={model.api_key}
                        onChange={(e) =>
                          setModels(
                            models.map((m) =>
                              m.id === model.id ? { ...m, api_key: e.target.value } : m
                            )
                          )
                        }
                      />
                      <div className="flex justify-end">
                        <Button
                          size="sm"
                          onClick={() => handleSaveModel(model)}
                          disabled={saving}
                        >
                          保存
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {activeTab === 'appearance' && (
            <Card className="p-6">
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-6">
                外观设置
              </h2>
              
              <div className="mb-8">
                <p className="font-medium text-slate-900 dark:text-white mb-4">主题</p>
                <div className="grid grid-cols-3 gap-4">
                  <button
                    onClick={() => setTheme('light')}
                    className={`p-4 rounded-xl border-2 transition-colors ${
                      theme === 'light' || (theme === 'system' && resolvedTheme === 'light')
                        ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-900/30'
                        : 'border-slate-200 dark:border-slate-700 hover:border-slate-300'
                    }`}
                  >
                    <Sun className="w-8 h-8 mx-auto mb-2 text-amber-500" />
                    <p className="text-sm font-medium text-slate-900 dark:text-white">浅色</p>
                  </button>
                  <button
                    onClick={() => setTheme('dark')}
                    className={`p-4 rounded-xl border-2 transition-colors ${
                      theme === 'dark' || (theme === 'system' && resolvedTheme === 'dark')
                        ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-900/30'
                        : 'border-slate-200 dark:border-slate-700 hover:border-slate-300'
                    }`}
                  >
                    <Moon className="w-8 h-8 mx-auto mb-2 text-indigo-500" />
                    <p className="text-sm font-medium text-slate-900 dark:text-white">深色</p>
                  </button>
                  <button
                    onClick={() => setTheme('system')}
                    className={`p-4 rounded-xl border-2 transition-colors ${
                      theme === 'system'
                        ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-900/30'
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
                      <div className="w-11 h-6 bg-slate-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-indigo-300 dark:peer-focus:ring-indigo-800 rounded-full peer dark:bg-slate-700 peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-slate-600 peer-checked:bg-indigo-600"></div>
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
              
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
                {[
                  { name: '免费', price: '¥0', features: ['3 个 Agent', '1000 条消息/月', '基础支持'], current: false },
                  { name: '专业版', price: '¥199', features: ['无限 Agent', '100,000 条消息/月', '优先支持', '自定义模型'], current: true },
                  { name: '企业版', price: '¥599', features: ['无限所有', '无限制', '专属客服', '私有部署', 'SSO'], current: false },
                ].map((plan, i) => (
                  <div
                    key={i}
                    className={`p-6 rounded-2xl border-2 ${
                      plan.current
                        ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-900/30'
                        : 'border-slate-200 dark:border-slate-700'
                    }`}
                  >
                    {plan.current && (
                      <span className="inline-block px-3 py-1 rounded-full bg-indigo-500 text-white text-xs font-medium mb-4">
                        当前计划
                      </span>
                    )}
                    <p className="font-semibold text-slate-900 dark:text-white">{plan.name}</p>
                    <p className="text-3xl font-bold text-slate-900 dark:text-white mt-2">
                      {plan.price}<span className="text-base font-normal text-slate-500">/月</span>
                    </p>
                    <ul className="mt-4 space-y-2">
                      {plan.features.map((feature, j) => (
                        <li key={j} className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400">
                          <Check className="w-4 h-4 text-emerald-500" />
                          {feature}
                        </li>
                      ))}
                    </ul>
                    <Button
                      variant={plan.current ? 'outline' : 'primary'}
                      className="w-full mt-6"
                      disabled={plan.current}
                    >
                      {plan.current ? '当前计划' : '升级'}
                    </Button>
                  </div>
                ))}
              </div>

              <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50">
                <p className="text-sm text-slate-600 dark:text-slate-400">
                  <strong>用量统计：</strong> 本月已使用 45,230 条消息，还剩 54,770 条
                </p>
              </div>
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
