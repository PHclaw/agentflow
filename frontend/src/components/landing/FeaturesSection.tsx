import { useRef } from 'react'
import { Card } from '../ui/Card'
import { Reveal } from './Reveal'
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
    title: '拖拽式搭建',
    description: '在画布上拖拽节点编排流程，不需要编程经验',
    gradient: 'from-blue-500 to-cyan-500',
  },
  {
    icon: Package,
    title: '预置行业模板',
    description: '客服、销售、HR、财务等场景模板，可在此基础上修改',
    gradient: 'from-brand-500 to-brand-500',
  },
  {
    icon: Link2,
    title: '多渠道接入',
    description: '可接入微信、钉钉、企业微信、网站与 API',
    gradient: 'from-emerald-500 to-green-500',
  },
  {
    icon: Brain,
    title: '知识库检索',
    description: '上传文档后按内容检索，回答时引用相关片段',
    gradient: 'from-orange-500 to-amber-500',
  },
  {
    icon: Zap,
    title: '工具调用',
    description: '可调用搜索、计算与外部 API 完成具体任务',
    gradient: 'from-yellow-500 to-orange-500',
  },
  {
    icon: BarChart3,
    title: '数据分析',
    description: '提供对话量与意图分布，便于调整 Agent 配置',
    gradient: 'from-pink-500 to-rose-500',
  },
  {
    icon: Shield,
    title: '安全合规',
    description: '传输加密，支持按成员划分权限',
    gradient: 'from-slate-600 to-slate-700',
  },
  {
    icon: Users,
    title: '团队协作',
    description: '多人共同编辑，流程变更可回溯',
    gradient: 'from-brand-500 to-brand-500',
  },
]

export function FeaturesSection() {
  const sectionRef = useRef<HTMLDivElement>(null)

  return (
    <section id="features" ref={sectionRef} className="py-24 lg:py-32 relative overflow-hidden">
      {/* Background */}
      <div className="absolute inset-0 bg-gradient-to-b from-slate-50 via-white to-slate-50" />
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[400px] bg-gradient-to-b from-brand-100/50 to-transparent rounded-full blur-3xl animate-breathe motion-reduce:animate-none" />

      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <div className="text-center max-w-2xl mx-auto mb-16">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-brand-50 border border-brand-100 text-brand-600 text-sm font-medium mb-6">
            <Code2 className="w-4 h-4" />
            核心功能
          </div>
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-black text-slate-900 mb-4">
            功能一览
          </h2>
          <p className="text-lg text-slate-600">
            覆盖搭建、接入、检索与运维的主要环节
          </p>
        </div>

        {/* Features Grid。Reveal 直接当网格容器用（className 透传），
            多包一层会把网格的子元素关系打断 */}
        <Reveal stagger className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 lg:gap-6">
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
                <h3 className="text-lg font-bold text-slate-900 mb-2 group-hover:text-brand-600 transition-colors">
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
        </Reveal>

        {/* Highlight feature

            原来是一整块 brand 渐变 + 两团 blur-3xl 光斑 + 白色大字。
            那套做法的问题不是"太花"，而是**它把整页唯一强调色用光了** ——
            一屏里其它地方（按钮、链接、图标）就再没有强调色可用了。

            2.0.2 改成中性卡片：靠小号大写标签 + 字号层级来突出，
            强调色留给真正需要点击的东西。文案和布局结构保持不变。 */}
        <div className="mt-16">
          <Card className="p-6 lg:p-8">
            <div className="flex flex-col lg:flex-row items-center justify-between gap-8">
              {/* Left content */}
              <div className="text-center lg:text-left">
                <div className="inline-flex items-center gap-1.5 text-2xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-3">
                  <Layers className="w-3.5 h-3.5" />
                  新功能
                </div>
                <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-2">
                  多 Agent 协作模式
                </h3>
                <p className="text-[13px] text-slate-500 dark:text-slate-400 max-w-lg leading-relaxed">
                  让多个 Agent 分别处理不同环节，再用条件节点串成完整流程，
                  适合环节较多、需要分工的场景。
                </p>
              </div>

              {/* Right - Visual：用字母标代替表情，避免卡通感 */}
              <div className="flex items-center gap-4 shrink-0">
                <div className="flex -space-x-1.5">
                  {['客', '售', '据'].map((label, i) => (
                    <div
                      key={i}
                      className="w-12 h-12 rounded-full bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 flex items-center justify-center text-sm font-semibold text-slate-600 dark:text-slate-300"
                    >
                      {label}
                    </div>
                  ))}
                </div>
                <div>
                  <div className="text-lg font-semibold text-slate-900 dark:text-white">+10</div>
                  <div className="text-xs text-slate-500 dark:text-slate-400">协作 Agent</div>
                </div>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </section>
  )
}
