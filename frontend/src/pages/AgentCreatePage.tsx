import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input, Textarea, Select } from '../components/ui/Input'
import { Tabs, TabPanel } from '../components/ui/Tabs'
import { Breadcrumb } from '../components/ui/Breadcrumb'
import { Modal } from '../components/ui/Modal'
import { Badge } from '../components/ui/Badge'
import { api, models as modelsApi } from '../services/api'
import { useToastStore } from '../stores'
import type { Agent, WorkflowDefinition } from '../types'
import {
  ArrowLeft,
  Save,
  Eye,
  Bot,
  Zap,
  Plus,
  Trash2,
  Play,
} from 'lucide-react'

interface ModelOption {
  value: string
  label: string
  provider?: string
  tier?: string
}

const tabs = [
  { id: 'basic', label: '基础配置' },
  { id: 'workflow', label: '工作流' },
  { id: 'knowledge', label: '知识库' },
]

export default function AgentCreatePage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { addToast } = useToastStore()
  const isEditing = !!id

  const [activeTab, setActiveTab] = useState('basic')
  const [loading, setLoading] = useState(false)
  const [modelOptions, setModelOptions] = useState<ModelOption[]>([])
  const [modelsLoading, setModelsLoading] = useState(true)
  const [modelsError, setModelsError] = useState<string | null>(null)
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    model: 'gpt-4o-mini',
    prompt: '',
  })
  const [previewOpen, setPreviewOpen] = useState(false)

  // 加载模型列表
  useEffect(() => {
    const fetchModels = async () => {
      setModelsLoading(true)
      setModelsError(null)
      try {
        const res = await modelsApi.list()
        const data = res.data || res
        if (Array.isArray(data) && data.length > 0) {
          const options = data.map((m: any) => ({
            value: m.id || m.model_id,
            label: m.name || m.display_name || m.id,
            provider: m.provider,
            tier: m.tier,
          }))
          setModelOptions(options)
        } else {
          setModelsError('未获取到模型列表')
        }
      } catch (error: any) {
        setModelsError(error.message || '加载模型列表失败')
      } finally {
        setModelsLoading(false)
      }
    }
    fetchModels()
  }, [])

  useEffect(() => {
    if (isEditing && id) {
      fetchAgent(id)
    }
  }, [id])

  const fetchAgent = async (agentId: string) => {
    try {
      const agent = await api.get(`/agents/${agentId}`)
      setFormData({
        name: agent.name,
        description: agent.description || '',
        model: agent.model_config?.model || 'gpt-4o-mini',
        prompt: '',
      })
    } catch (error) {
      addToast({ type: 'error', message: '加载 Agent 失败' })
    }
  }

  const handleSubmit = async () => {
    if (!formData.name.trim()) {
      addToast({ type: 'error', message: '请输入 Agent 名称' })
      return
    }

    setLoading(true)
    try {
      const data = {
        name: formData.name,
        description: formData.description,
        workflow_definition: {
          nodes: [],
          edges: [],
          entry: 'start',
        },
        llm_config: {
          provider: 'openai',
          model: formData.model,
          temperature: 0.7,
          max_tokens: 2000,
        },
      }

      if (isEditing && id) {
        await api.put(`/agents/${id}`, data)
        addToast({ type: 'success', message: 'Agent 更新成功' })
      } else {
        const newAgent = await api.post('/agents', data)
        addToast({ type: 'success', message: 'Agent 创建成功' })
        navigate(`/agents/${newAgent.id}/edit`)
        return
      }
      navigate('/agents')
    } catch (error: any) {
      addToast({ type: 'error', message: error.message || '保存失败' })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-6xl mx-auto">
      {/* Breadcrumb */}
      <Breadcrumb
        items={[
          { label: '我的 Agent', href: '/agents' },
          { label: isEditing ? '编辑 Agent' : '创建 Agent' },
        ]}
        className="mb-6"
      />

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate(-1)}
          >
            <ArrowLeft className="w-5 h-5" />
          </Button>
          <div>
            <h1 className="text-2xl font-bold text-slate-900">
              {isEditing ? '编辑 Agent' : '创建新 Agent'}
            </h1>
            <p className="text-slate-500">配置 Agent 的基本信息和工作流程</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            leftIcon={<Eye className="w-4 h-4" />}
            onClick={() => setPreviewOpen(true)}
          >
            预览
          </Button>
          <Button
            leftIcon={<Save className="w-4 h-4" />}
            onClick={handleSubmit}
            loading={loading}
          >
            {isEditing ? '保存更改' : '创建 Agent'}
          </Button>
        </div>
      </div>

      {/* Tabs */}
      <Tabs
        tabs={tabs}
        activeTab={activeTab}
        onChange={setActiveTab}
        className="mb-6"
      />

      {/* Tab Content */}
      <div className="grid lg:grid-cols-3 gap-6">
        {/* Form */}
        <div className="lg:col-span-2">
          <Card padding="lg">
            <TabPanel value={activeTab} id="basic">
              <div className="space-y-6">
                <Input
                  label="Agent 名称"
                  placeholder="例如：智能客服助手"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  required
                />

                <Textarea
                  label="描述"
                  placeholder="描述这个 Agent 的功能和用途..."
                  rows={3}
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                />

                {modelsLoading ? (
                  <div className="space-y-1">
                    <label className="text-sm font-medium text-slate-700">语言模型</label>
                    <div className="text-sm text-slate-500">加载模型中...</div>
                  </div>
                ) : modelsError ? (
                  <div className="space-y-1">
                    <label className="text-sm font-medium text-slate-700">语言模型</label>
                    <div className="text-sm text-red-500">{modelsError}</div>
                  </div>
                ) : (
                  <Select
                    label="语言模型"
                    options={modelOptions}
                    value={formData.model}
                    onChange={(e) => setFormData({ ...formData, model: e.target.value })}
                    hint={modelOptions.length === 0 ? "未获取到模型，请检查后端" : "选择用于处理对话的语言模型"}
                  />
                )}

                <Textarea
                  label="系统提示词"
                  placeholder="定义 Agent 的角色、行为规则和专业知识..."
                  rows={8}
                  value={formData.prompt}
                  onChange={(e) => setFormData({ ...formData, prompt: e.target.value })}
                  hint="详细的提示词可以帮助 Agent 更好地理解任务"
                />
              </div>
            </TabPanel>

            <TabPanel value={activeTab} id="workflow">
              <div className="space-y-6">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="font-semibold text-slate-900">工作流配置</h3>
                    <p className="text-sm text-slate-500">拖拽节点构建工作流程</p>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    leftIcon={<Zap className="w-4 h-4" />}
                    onClick={() => window.open(`/workflow/${id || 'new'}`, '_blank')}
                  >
                    打开工作流编辑器
                  </Button>
                </div>

                {/* Placeholder for workflow editor */}
                <div className="h-96 bg-slate-50 rounded-xl border-2 border-dashed border-slate-200 flex items-center justify-center">
                  <div className="text-center">
                    <Zap className="w-12 h-12 mx-auto text-slate-300 mb-4" />
                    <p className="text-slate-500 mb-2">点击上方按钮打开工作流编辑器</p>
                    <p className="text-sm text-slate-400">在工作流编辑器中拖拽节点来构建工作流程</p>
                  </div>
                </div>
              </div>
            </TabPanel>

            <TabPanel value={activeTab} id="knowledge">
              <div className="space-y-6">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="font-semibold text-slate-900">知识库配置</h3>
                    <p className="text-sm text-slate-500">关联知识库以增强回答能力</p>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    leftIcon={<Plus className="w-4 h-4" />}
                  >
                    添加知识库
                  </Button>
                </div>

                <div className="h-48 bg-slate-50 rounded-xl border-2 border-dashed border-slate-200 flex items-center justify-center">
                  <div className="text-center">
                    <Bot className="w-12 h-12 mx-auto text-slate-300 mb-4" />
                    <p className="text-slate-500">尚未关联知识库</p>
                    <p className="text-sm text-slate-400">添加知识库后，Agent 可以基于知识回答问题</p>
                  </div>
                </div>
              </div>
            </TabPanel>
          </Card>
        </div>

        {/* Preview */}
        <div className="lg:col-span-1">
          <Card padding="lg" className="sticky top-6">
            <CardHeader>
              <CardTitle>实时预览</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex items-center gap-3 p-4 bg-slate-50 rounded-xl">
                  <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-indigo-500 to-indigo-600 flex items-center justify-center">
                    <Bot className="w-6 h-6 text-white" />
                  </div>
                  <div>
                    <h4 className="font-medium text-slate-900">
                      {formData.name || '未命名 Agent'}
                    </h4>
                    <p className="text-sm text-slate-500">
                      {formData.model || 'gpt-4o-mini'}
                    </p>
                  </div>
                </div>

                <div className="p-4 bg-slate-50 rounded-xl">
                  <p className="text-sm font-medium text-slate-700 mb-2">描述</p>
                  <p className="text-sm text-slate-500">
                    {formData.description || '暂无描述'}
                  </p>
                </div>

                <div className="p-4 bg-slate-50 rounded-xl">
                  <p className="text-sm font-medium text-slate-700 mb-2">提示词预览</p>
                  <p className="text-sm text-slate-500 whitespace-pre-wrap line-clamp-6">
                    {formData.prompt || '暂无提示词'}
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <Badge variant="success">草稿</Badge>
                  <Badge variant="default">未部署</Badge>
                </div>

                <Button className="w-full" variant="outline" leftIcon={<Play className="w-4 h-4" />}>
                  测试对话
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Preview Modal */}
      <Modal
        isOpen={previewOpen}
        onClose={() => setPreviewOpen(false)}
        title="Agent 预览"
        size="md"
      >
        <div className="space-y-4">
          <div className="flex items-center gap-3 p-4 bg-slate-50 rounded-xl">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-indigo-500 to-indigo-600 flex items-center justify-center">
              <Bot className="w-6 h-6 text-white" />
            </div>
            <div>
              <h4 className="font-medium text-slate-900">
                {formData.name || '未命名 Agent'}
              </h4>
              <p className="text-sm text-slate-500">
                {formData.description || '暂无描述'}
              </p>
            </div>
          </div>
        </div>
      </Modal>
    </div>
  )
}
