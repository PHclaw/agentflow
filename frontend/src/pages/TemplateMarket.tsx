import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'

const templates = [
  {
    id: 'customer_service',
    name: '智能客服',
    icon: '💬',
    description: '自动回答常见问题，支持多轮对话和工单创建',
    features: ['FAQ 自动回答', '多轮对话', '工单创建', '满意度调查'],
    color: 'from-green-500 to-emerald-600',
    category: '客服',
  },
  {
    id: 'sales',
    name: '销售助手',
    icon: '💰',
    description: '帮助销售跟进客户、生成报价、安排会议',
    features: ['客户跟进', '报价生成', '会议安排', 'CRM 集成'],
    color: 'from-blue-500 to-indigo-600',
    category: '销售',
  },
  {
    id: 'hr',
    name: 'HR 助手',
    icon: '👥',
    description: '回答员工关于假期、薪资、福利等问题',
    features: ['政策查询', '假期申请', '薪资咨询', '培训推荐'],
    color: 'from-purple-500 to-violet-600',
    category: 'HR',
  },
  {
    id: 'finance',
    name: '财务助手',
    icon: '📊',
    description: '处理报销审批、发票查询、预算咨询',
    features: ['报销审批', '发票查询', '预算咨询', '财务报表'],
    color: 'from-yellow-500 to-orange-600',
    category: '财务',
  },
  {
    id: 'knowledge',
    name: '知识库问答',
    icon: '📚',
    description: '基于企业知识库的智能问答系统',
    features: ['文档导入', '智能检索', '多格式支持', '权限管理'],
    color: 'from-pink-500 to-rose-600',
    category: '通用',
  },
  {
    id: 'appointment',
    name: '预约助手',
    icon: '📅',
    description: '智能预约管理，支持多种业务场景',
    features: ['在线预约', '日程管理', '提醒通知', '数据统计'],
    color: 'from-cyan-500 to-teal-600',
    category: '通用',
  },
]

export default function TemplateMarket() {
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
  const navigate = useNavigate()

  const categories = ['全部', '客服', '销售', 'HR', '财务', '通用']

  const filteredTemplates = selectedCategory && selectedCategory !== '全部'
    ? templates.filter((t) => t.category === selectedCategory)
    : templates

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-gradient-to-r from-blue-600 to-indigo-600 text-white py-16">
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
              <div className={`bg-gradient-to-r ${template.color} p-6 text-white`}>
                <div className="text-4xl mb-2">{template.icon}</div>
                <h3 className="text-xl font-semibold">{template.name}</h3>
                <span className="text-sm opacity-80">{template.category}</span>
              </div>

              {/* Content */}
              <div className="p-6">
                <p className="text-gray-600 mb-4">{template.description}</p>

                <div className="space-y-2 mb-6">
                  {template.features.map((feature, i) => (
                    <div key={i} className="flex items-center gap-2 text-sm text-gray-500">
                      <span className="text-green-500">✓</span>
                      <span>{feature}</span>
                    </div>
                  ))}
                </div>

                <div className="flex gap-2">
                  <button
                    onClick={() => navigate(`/create?template=${template.id}`)}
                    className="flex-1 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
                  >
                    使用模板
                  </button>
                  <button className="py-2 px-4 border rounded-lg hover:bg-gray-50 transition">
                    预览
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
            onClick={() => navigate('/create')}
            className="px-8 py-3 bg-white text-gray-900 rounded-xl font-medium hover:bg-gray-100 transition"
          >
            自定义创建
          </button>
        </div>
      </div>
    </div>
  )
}
