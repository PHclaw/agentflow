import { Card } from '../ui/Card'
import { Button } from '../ui/Button'
import { ArrowRight, MessageSquare, ShoppingCart, Users, Building2, Headphones, FileText, Heart, Star } from 'lucide-react'
import { Link } from 'react-router-dom'

const templates = [
  {
    icon: Headphones,
    title: '智能客服',
    description: '7x24 小时在线，自动解答常见问题，大幅降低人工成本',
    color: 'from-blue-500 to-cyan-500',
    gradient: 'bg-blue-50',
    stats: { agents: '12,000+', rating: 4.9 },
  },
  {
    icon: ShoppingCart,
    title: '电商助手',
    description: '智能推荐商品，解答购物疑问，提升转化率和客单价',
    color: 'from-orange-500 to-amber-500',
    gradient: 'bg-orange-50',
    stats: { agents: '8,500+', rating: 4.8 },
  },
  {
    icon: Users,
    title: 'HR 工作台',
    description: '简历筛选、面试安排、员工问答，打造智能化 HR 工作流',
    color: 'from-emerald-500 to-green-500',
    gradient: 'bg-emerald-50',
    stats: { agents: '5,200+', rating: 4.9 },
  },
  {
    icon: Building2,
    title: '企业知识库',
    description: '内部文档问答培训资料查询，提升员工获取知识的效率',
    color: 'from-violet-500 to-purple-500',
    gradient: 'bg-violet-50',
    stats: { agents: '9,800+', rating: 4.8 },
  },
  {
    icon: FileText,
    title: '文档助手',
    description: '长文本摘要关键信息提取，帮你快速理解海量文档',
    color: 'from-pink-500 to-rose-500',
    gradient: 'bg-pink-50',
    stats: { agents: '6,400+', rating: 4.7 },
  },
  {
    icon: Heart,
    title: '健康顾问',
    description: '健康咨询、医疗建议预约提醒，提供个性化健康建议',
    color: 'from-red-500 to-pink-500',
    gradient: 'bg-red-50',
    stats: { agents: '3,100+', rating: 4.9 },
  },
]

export function TemplatesSection() {
  return (
    <section id="templates" className="py-24 lg:py-32 relative overflow-hidden">
      {/* Background */}
      <div className="absolute inset-0 bg-gradient-to-b from-slate-50 to-white" />
      <div className="absolute top-1/2 left-0 w-[600px] h-[600px] bg-purple-100/30 rounded-full blur-3xl -translate-y-1/2" />
      <div className="absolute top-1/2 right-0 w-[600px] h-[600px] bg-indigo-100/30 rounded-full blur-3xl -translate-y-1/2" />

      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <div className="text-center max-w-2xl mx-auto mb-16">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-purple-50 border border-purple-100 text-purple-600 text-sm font-medium mb-6">
            <MessageSquare className="w-4 h-4" />
            行业模板
          </div>
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-black text-slate-900 mb-4">
            开箱即用
          </h2>
          <p className="text-lg text-slate-600">
            精选行业最佳实践，快速启动你的 AI Agent
          </p>
        </div>

        {/* Templates Grid */}
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {templates.map((template, index) => (
            <Card
              key={template.title}
              hover
              className="group relative overflow-hidden cursor-pointer"
            >
              <div className="p-6">
                {/* Header */}
                <div className="flex items-start justify-between mb-4">
                  <div className={`inline-flex p-3 rounded-2xl ${template.gradient}`}>
                    <template.icon className={`w-6 h-6 bg-gradient-to-br ${template.color} bg-clip-text`} />
                  </div>
                  <div className="flex items-center gap-1 text-amber-500">
                    <Star className="w-4 h-4 fill-current" />
                    <span className="text-sm font-medium text-slate-700">{template.stats.rating}</span>
                  </div>
                </div>

                {/* Content */}
                <h3 className="text-xl font-bold text-slate-900 mb-2 group-hover:text-indigo-600 transition-colors">
                  {template.title}
                </h3>
                <p className="text-slate-600 text-sm leading-relaxed mb-4">
                  {template.description}
                </p>

                {/* Stats */}
                <div className="flex items-center gap-4 text-sm text-slate-500">
                  <span className="flex items-center gap-1">
                    <Users className="w-4 h-4" />
                    {template.stats.agents}
                  </span>
                  <span>使用中</span>
                </div>

                {/* Hover effect */}
                <div className={`absolute bottom-0 left-0 right-0 h-1 bg-gradient-to-r ${template.color} opacity-0 group-hover:opacity-100 transition-opacity`} />
              </div>

              {/* Arrow indicator */}
              <div className="absolute top-6 right-6 opacity-0 group-hover:opacity-100 transition-opacity">
                <div className="p-2 rounded-full bg-indigo-50 text-indigo-600">
                  <ArrowRight className="w-4 h-4" />
                </div>
              </div>
            </Card>
          ))}
        </div>

        {/* CTA */}
        <div className="text-center mt-12">
          <Link to="/templates">
            <Button variant="outline" size="lg" rightIcon={<ArrowRight className="w-4 h-4" />}>
              查看全部模板
            </Button>
          </Link>
        </div>
      </div>
    </section>
  )
}
