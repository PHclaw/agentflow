import React, { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { templates } from '../services/api'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'

interface Template {
  id: string
  name: string
  description: string
  category: string
  icon: string
  features: string[]
  /**
   * 模板自带的渐变色（seed 里是 `from-pink-500 to-rose-600` 这类）。
   *
   * **现在不再渲染它。** 那一串彩虹渐变让每个模板卡顶部都是一块高饱和色块，
   * 一屏六个模板就是六种颜色互相打架，而且没有任何信息量 —— 分类靠 Badge
   * 已经说清楚了。字段保留是因为后端还在返回它。
   */
  color?: string
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
      <div className="flex items-center justify-center py-24">
        <p className="text-[13px] text-slate-500 dark:text-slate-400">加载中...</p>
      </div>
    )
  }

  return (
    <div className="max-w-6xl mx-auto">
      {/*
        原来这里是一整条全幅的 from-blue-600 to-brand-600 渐变横幅。
        这个页面是挂在 AppLayout 里、左侧有侧边栏的应用内页面，
        不是落地页 —— 满幅色带会和侧边栏抢视觉重量。改成普通页标题。
      */}
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-slate-900 dark:text-white">模板市场</h1>
        <p className="mt-1 text-[13px] text-slate-500 dark:text-slate-400">
          选择适合你的模板，5 分钟上线你的第一个 AI Agent
        </p>
      </div>

      {/* Category Filter */}
      <Card padding="sm" className="mb-6 flex items-center gap-2 overflow-x-auto">
        {categories.map((cat) => (
          <button
            key={cat}
            onClick={() => setSelectedCategory(cat)}
            className={`h-8 px-3 rounded-lg text-[13px] font-medium whitespace-nowrap transition-colors ${
              selectedCategory === cat || (cat === '全部' && !selectedCategory)
                ? 'bg-slate-100 text-slate-900 dark:bg-slate-800 dark:text-white'
                : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
            }`}
          >
            {cat}
          </button>
        ))}
      </Card>

      {/* Templates Grid */}
      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filteredTemplates.map((template) => (
          <Card key={template.id} hover className="flex flex-col">
            <div className="flex items-start gap-3">
              <div className="w-9 h-9 rounded-lg bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-base shrink-0">
                {template.icon || '🤖'}
              </div>
              <div className="min-w-0">
                <h3 className="text-[15px] font-semibold text-slate-900 dark:text-white truncate">
                  {template.name}
                </h3>
                <Badge variant="default" size="sm" className="mt-1">
                  {categoryLabel(template.category)}
                </Badge>
              </div>
            </div>

            <p className="text-[13px] text-slate-600 dark:text-slate-300 mt-4 mb-4">
              {template.description}
            </p>

            {template.features && template.features.length > 0 && (
              <div className="space-y-1.5 mb-5 flex-1">
                {template.features.map((feature, i) => (
                  <div
                    key={i}
                    className="flex items-start gap-2 text-[13px] text-slate-500 dark:text-slate-400"
                  >
                    <span className="text-slate-400 dark:text-slate-500">✓</span>
                    <span>{feature}</span>
                  </div>
                ))}
              </div>
            )}

            <div className="flex gap-2 mt-auto">
              <Button
                fullWidth
                onClick={() => navigate(`/agents/new?template=${template.id}`)}
              >
                使用模板
              </Button>
            </div>
          </Card>
        ))}
      </div>

      {filteredTemplates.length === 0 && (
        <Card className="mt-4 py-10 text-center">
          <p className="text-[13px] text-slate-500 dark:text-slate-400">
            该分类下暂无模板
          </p>
        </Card>
      )}

      {/* Custom Section —— 原为 from-gray-800 to-gray-900 的大色块 */}
      <Card padding="lg" className="mt-6 text-center">
        <h3 className="text-[15px] font-semibold text-slate-900 dark:text-white mb-1.5">
          没有找到合适的模板？
        </h3>
        <p className="text-[13px] text-slate-500 dark:text-slate-400 mb-5">
          从零开始构建你的专属 AI Agent
        </p>
        <Button onClick={() => navigate('/agents/new')}>自定义创建</Button>
      </Card>
    </div>
  )
}
