import React, { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { templates } from '../services/api'

interface Template {
  id: string
  name: string
  description: string
  category: string
  icon: string
  features: string[]
  color: string
}

/**
 * 模板表里存的是内部英文分类值，界面要显示中文。
 *
 * 关键：筛选也必须按显示用的中文值比对。此前筛选用写死的中文列表
 * 去比库里的英文值（'客服' vs 'customer_service'），点任何分类都是空网格。
 */
const CATEGORY_LABELS: Record<string, string> = {
  customer_service: '客服',
  sales: '销售',
  hr: 'HR',
  finance: '财务',
  general: '通用',
}

const categoryLabel = (raw: string) => CATEGORY_LABELS[raw] ?? raw

export default function TemplateMarket() {
  const [templateList, setTemplateList] = useState<Template[]>([])
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  // 筛选项从数据推导：写死一份清单既会与库里的分类值对不上，
  // 也会出现「财务」这种一个模板都没有的空分类
  const categories = useMemo(() => {
    const labels = templateList.map((t) => categoryLabel(t.category))
    return ['全部', ...Array.from(new Set(labels))]
  }, [templateList])

  useEffect(() => {
    async function loadTemplates() {
      try {
        const data = await templates.list()
        setTemplateList(data)
      } catch (err) {
        console.error('Failed to load templates:', err)
      } finally {
        setLoading(false)
      }
    }
    loadTemplates()
  }, [])

  const filteredTemplates = selectedCategory && selectedCategory !== '全部'
    ? templateList.filter((t) => categoryLabel(t.category) === selectedCategory)
    : templateList

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-gray-500">加载中...</div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-gradient-to-r from-blue-600 to-brand-600 text-white py-16">
        <div className="max-w-6xl mx-auto px-4 text-center">
          <h1 className="text-4xl font-bold mb-4">模板市场</h1>
          <p className="text-xl text-blue-100">
            选择适合你的模板，5 分钟上线你的第一个 AI Agent
          </p>
        </div>
      </div>

      {/* Category Filter */}
      <div className="max-w-6xl mx-auto px-4 -mt-8">
        <div className="bg-white rounded-xl shadow-lg p-4 flex items-center gap-4 overflow-x-auto">
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              className={`px-4 py-2 rounded-lg whitespace-nowrap transition ${
                (selectedCategory === cat || (cat === '全部' && !selectedCategory))
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>
      </div>

      {/* Templates Grid */}
      <div className="max-w-6xl mx-auto px-4 py-12">
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredTemplates.map((template) => (
            <div
              key={template.id}
              className="bg-white rounded-xl shadow-sm border hover:shadow-lg transition overflow-hidden"
            >
              {/* Header */}
              <div className={`bg-gradient-to-r ${template.color || 'from-blue-500 to-brand-600'} p-6 text-white`}>
                <div className="text-4xl mb-2">{template.icon || '🤖'}</div>
                <h3 className="text-xl font-semibold">{template.name}</h3>
                <span className="text-sm opacity-80">{categoryLabel(template.category)}</span>
              </div>

              {/* Content */}
              <div className="p-6">
                <p className="text-gray-600 mb-4">{template.description}</p>

                {template.features && template.features.length > 0 && (
                  <div className="space-y-2 mb-6">
                    {template.features.map((feature, i) => (
                      <div key={i} className="flex items-center gap-2 text-sm text-gray-500">
                        <span className="text-green-500">✓</span>
                        <span>{feature}</span>
                      </div>
                    ))}
                  </div>
                )}

                <div className="flex gap-2">
                  <button
                    onClick={() => navigate(`/agents/new?template=${template.id}`)}
                    className="flex-1 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
                  >
                    使用模板
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Custom Section */}
      <div className="max-w-6xl mx-auto px-4 pb-12">
        <div className="bg-gradient-to-r from-gray-800 to-gray-900 rounded-xl p-8 text-white text-center">
          <h3 className="text-2xl font-bold mb-2">没有找到合适的模板？</h3>
          <p className="text-gray-300 mb-6">
            从零开始构建你的专属 AI Agent
          </p>
          <button
            onClick={() => navigate('/agents/new')}
            className="px-8 py-3 bg-white text-gray-900 rounded-xl font-medium hover:bg-gray-100 transition"
          >
            自定义创建
          </button>
        </div>
      </div>
    </div>
  )
}
