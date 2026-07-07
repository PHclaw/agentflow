import { useRef } from 'react'
import { Card } from '../ui/Card'
import {
  MousePointer2,
  Package,
  Link2,
  Brain,
  Zap,
  BarChart3,
  Shield,
  Users,
  Code2,
  Layers,
  GitBranch,
  Timer,
} from 'lucide-react'

const features = [
  {
    icon: MousePointer2,
    title: '拖拽式构建',
    description: '可视化界面，拖拽节点即可构建复杂的工作流，无需编程经验',
    gradient: 'from-blue-500 to-cyan-500',
  },
  {
    icon: Package,
    title: '预置行业模板',
    description: '客服、销售、HR、财务等开箱即用的行业模板，快速上线',
    gradient: 'from-violet-500 to-purple-500',
  },
  {
    icon: Link2,
    title: '多渠道集成',
    description: '一键接入微信、钉钉、企业微信、网站、API 等多渠道',
    gradient: 'from-emerald-500 to-green-500',
  },
  {
    icon: Brain,
    title: '知识库 RAG',
    description: '上传文档，AI 自动学习企业知识，精准回答专业问题',
    gradient: 'from-orange-500 to-amber-500',
  },
  {
    icon: Zap,
    title: '工具调用',
    description: '支持搜索、计算、API 调用等工具，让 Agent 真正帮你做事',
    gradient: 'from-yellow-500 to-orange-500',
  },
  {
    icon: BarChart3,
    title: '数据分析',
    description: '完整的数据面板，了解用户意图，优化 Agent 效果',
    gradient: 'from-pink-500 to-rose-500',
  },
  {
    icon: Shield,
    title: '安全合规',
    description: '企业级安全防护，数据加密传输，符合 GDPR 合规',
    gradient: 'from-slate-600 to-slate-700',
  },
  {
    icon: Users,
    title: '团队协作',
    description: '支持多人协作，版本控制，权限管理',
    gradient: 'from-indigo-500 to-violet-500',
  },
]

export function FeaturesSection() {
  const sectionRef = useRef<HTMLDivElement>(null)

  return (
    <section id="features" ref={sectionRef} className="py-24 lg:py-32 relative overflow-hidden">
      {/* Background */}
      <div className="absolute inset-0 bg-gradient-to-b from-slate-50 via-white to-slate-50" />
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[400px] bg-gradient-to-b from-indigo-100/50 to-transparent rounded-full blur-3xl" />

      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <div className="text-center max-w-2xl mx-auto mb-16">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-indigo-50 border border-indigo-100 text-indigo-600 text-sm font-medium mb-6">
            <Code2 className="w-4 h-4" />
            核心功能
          </div>
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-black text-slate-900 mb-4">
            强大的功能集
          </h2>
          <p className="text-lg text-slate-600">
            助力企业快速构建和部署 AI Agent，覆盖全场景业务需求
          </p>
        </div>

        {/* Features Grid */}
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 lg:gap-6">
          {features.map((feature, index) => (
            <Card
              key={feature.title}
              hover
              className="group relative overflow-hidden"
            >
              {/* Background gradient on hover */}
              <div className={`absolute inset-0 bg-gradient-to-br ${feature.gradient} opacity-0 group-hover:opacity-5 transition-opacity duration-500`} />
              
              <div className="relative">
                {/* Icon */}
                <div className={`inline-flex p-3 rounded-2xl bg-gradient-to-br ${feature.gradient} shadow-lg mb-5 group-hover:scale-110 transition-transform duration-300`}>
                  <feature.icon className="w-6 h-6 text-white" />
                </div>

                {/* Content */}
                <h3 className="text-lg font-bold text-slate-900 mb-2 group-hover:text-indigo-600 transition-colors">
                  {feature.title}
                </h3>
                <p className="text-sm text-slate-600 leading-relaxed">
                  {feature.description}
                </p>
              </div>

              {/* Bottom accent */}
              <div className={`absolute bottom-0 left-0 right-0 h-1 bg-gradient-to-r ${feature.gradient} opacity-0 group-hover:opacity-100 transition-opacity duration-300`} />
            </Card>
          ))}
        </div>

        {/* Highlight feature */}
        <div className="mt-16">
          <Card className="relative overflow-hidden bg-gradient-to-r from-indigo-600 via-purple-600 to-indigo-600 border-0">
            {/* Animated background */}
            <div className="absolute inset-0 opacity-20">
              <div className="absolute top-0 left-1/4 w-64 h-64 bg-white rounded-full blur-3xl animate-pulse" />
              <div className="absolute bottom-0 right-1/4 w-48 h-48 bg-purple-300 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '1s' }} />
            </div>

            <div className="relative flex flex-col lg:flex-row items-center justify-between gap-8 p-8 lg:p-12">
              {/* Left content */}
              <div className="text-center lg:text-left">
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/20 text-white text-sm font-medium mb-4">
                  <Layers className="w-4 h-4" />
                  新功能
                </div>
                <h3 className="text-2xl lg:text-3xl font-bold text-white mb-3">
                  多 Agent 协作模式
                </h3>
                <p className="text-indigo-100 max-w-lg">
                  支持多个 AI Agent 协同工作，通过 GitBranch 节点实现复杂业务流程，
                  处理企业级复杂场景游刃有余。
                </p>
              </div>

              {/* Right - Visual */}
              <div className="flex items-center gap-4">
                <div className="flex -space-x-3">
                  {['🤖', '🤖', '🤖'].map((emoji, i) => (
                    <div
                      key={i}
                      className="w-14 h-14 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center text-2xl border-2 border-white/50"
                    >
                      {emoji}
                    </div>
                  ))}
                </div>
                <div className="text-white">
                  <div className="text-2xl font-bold">+10</div>
                  <div className="text-sm text-indigo-200">协作 Agent</div>
                </div>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </section>
  )
}
