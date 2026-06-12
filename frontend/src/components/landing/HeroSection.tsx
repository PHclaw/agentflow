import { Link } from 'react-router-dom'
import { Button } from '../ui/Button'
import { ArrowRight, Play, Cpu, Globe, Lock, Zap, MessageSquare } from 'lucide-react'

const stats = [
  { label: '企业用户', value: '10,000+' },
  { label: 'AI Agent', value: '50,000+' },
  { label: '对话处理', value: '100M+' },
]

const features = [
  { icon: Cpu, text: '拖拽式构建' },
  { icon: Globe, text: '多渠道接入' },
  { icon: Lock, text: '企业级安全' },
  { icon: Zap, text: '5分钟上线' },
]

export function HeroSection() {
  return (
    <section className="relative min-h-screen flex items-center pt-20 overflow-hidden">
      {/* Animated background */}
      <div className="absolute inset-0 -z-10">
        {/* Base gradient */}
        <div className="absolute inset-0 bg-gradient-to-br from-slate-50 via-indigo-50/30 to-purple-50/30" />
        
        {/* Animated orbs */}
        <div className="absolute top-1/4 -left-32 w-96 h-96 bg-indigo-400/20 rounded-full blur-3xl animate-pulse" />
        <div className="absolute bottom-1/4 -right-32 w-96 h-96 bg-purple-400/20 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '1s' }} />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-gradient-to-r from-indigo-500/10 via-purple-500/10 to-pink-500/10 rounded-full blur-3xl" />
        
        {/* Grid pattern */}
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#80808012_1px,transparent_1px),linear-gradient(to_bottom,#80808012_1px,transparent_1px)] bg-[size:24px_24px]" />
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 lg:py-20">
        <div className="grid lg:grid-cols-2 gap-12 lg:gap-16 items-center">
          {/* Left - Content */}
          <div className="text-center lg:text-left">
            {/* Badge */}
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-gradient-to-r from-indigo-500/10 to-purple-500/10 border border-indigo-200/50 backdrop-blur-sm mb-8">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-indigo-500" />
              </span>
              <span className="text-sm font-medium bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">
                v2.0 全新发布
              </span>
            </div>

            {/* Heading */}
            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-black text-slate-900 mb-6 leading-tight tracking-tight">
              <span className="block">构建你的</span>
              <span className="block bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-600 bg-clip-text text-transparent pb-2">
                AI Agent
              </span>
              <span className="block text-3xl sm:text-4xl lg:text-5xl text-slate-500 font-bold mt-2">
                无需一行代码
              </span>
            </h1>

            {/* Subheading */}
            <p className="text-lg sm:text-xl text-slate-600 mb-8 max-w-xl mx-auto lg:mx-0 leading-relaxed">
              拖拽式构建企业专属 AI 智能体。开箱即用的客服、销售、HR 等行业模板，
              <span className="text-indigo-600 font-semibold"> 5 分钟</span>快速上线。
            </p>

            {/* CTA Buttons */}
            <div className="flex flex-col sm:flex-row items-center justify-center lg:justify-start gap-4 mb-10">
              <Link to="/register">
                <Button size="lg" className="w-full sm:w-auto shadow-xl shadow-indigo-500/30 hover:shadow-indigo-500/50 group">
                  <span>免费开始</span>
                  <ArrowRight className="ml-2 w-5 h-5 group-hover:translate-x-1 transition-transform" />
                </Button>
              </Link>
              <Link to="/templates">
                <Button variant="outline" size="lg" className="w-full sm:w-auto group">
                  <Play className="mr-2 w-5 h-5" />
                  查看演示
                </Button>
              </Link>
            </div>

            {/* Feature pills */}
            <div className="flex flex-wrap items-center justify-center lg:justify-start gap-3">
              {features.map((feature, i) => (
                <div
                  key={i}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/80 backdrop-blur-sm border border-slate-200/50 shadow-sm"
                >
                  <feature.icon className="w-4 h-4 text-indigo-500" />
                  <span className="text-sm font-medium text-slate-700">{feature.text}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Right - Visual */}
          <div className="relative hidden lg:block">
            {/* Main card */}
            <div className="relative">
              {/* Glow effect */}
              <div className="absolute -inset-4 bg-gradient-to-r from-indigo-500/20 via-purple-500/20 to-pink-500/20 rounded-3xl blur-2xl" />
              
              {/* Card */}
              <div className="relative bg-white/90 backdrop-blur-xl rounded-3xl border border-slate-200/50 shadow-2xl overflow-hidden">
                {/* Header */}
                <div className="px-6 py-4 border-b border-slate-100 bg-gradient-to-r from-slate-50 to-white">
                  <div className="flex items-center gap-3">
                    <div className="flex gap-1.5">
                      <div className="w-3 h-3 rounded-full bg-red-400" />
                      <div className="w-3 h-3 rounded-full bg-yellow-400" />
                      <div className="w-3 h-3 rounded-full bg-green-400" />
                    </div>
                    <span className="text-sm font-medium text-slate-500">工作流编辑器</span>
                  </div>
                </div>
                
                {/* Content - Workflow preview */}
                <div className="p-8 min-h-[400px] bg-gradient-to-br from-slate-50 to-indigo-50/30">
                  {/* Nodes */}
                  <div className="space-y-6">
                    {/* Trigger node */}
                    <div className="flex items-center gap-4">
                      <div className="relative">
                        <div className="w-48 p-4 bg-gradient-to-r from-indigo-500 to-indigo-600 rounded-xl text-white shadow-lg shadow-indigo-500/30">
                          <div className="flex items-center gap-3">
                            <MessageSquare className="w-5 h-5" />
                            <div>
                              <div className="font-semibold text-sm">用户消息</div>
                              <div className="text-xs opacity-75">触发节点</div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                    
                    {/* Arrow */}
                    <div className="flex justify-center">
                      <svg className="w-6 h-10 text-indigo-400" fill="none" viewBox="0 0 24 40">
                        <path d="M12 0v32m0 0l8 8m-8 8l8-8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                      </svg>
                    </div>
                    
                    {/* LLM node */}
                    <div className="flex items-center gap-4">
                      <div className="w-48 p-4 bg-gradient-to-r from-purple-500 to-purple-600 rounded-xl text-white shadow-lg shadow-purple-500/30">
                        <div className="flex items-center gap-3">
                          <Cpu className="w-5 h-5" />
                          <div>
                            <div className="font-semibold text-sm">GPT-4 分析</div>
                            <div className="text-xs opacity-75">LLM 节点</div>
                          </div>
                        </div>
                      </div>
                    </div>
                    
                    {/* Arrow */}
                    <div className="flex justify-center">
                      <svg className="w-6 h-10 text-purple-400" fill="none" viewBox="0 0 24 40">
                        <path d="M12 0v32m0 0l8 8m-8 8l8-8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                      </svg>
                    </div>
                    
                    {/* Response node */}
                    <div className="flex items-center gap-4">
                      <div className="w-48 p-4 bg-gradient-to-r from-green-500 to-emerald-500 rounded-xl text-white shadow-lg shadow-green-500/30">
                        <div className="flex items-center gap-3">
                          <Zap className="w-5 h-5" />
                          <div>
                            <div className="font-semibold text-sm">回复用户</div>
                            <div className="text-xs opacity-75">响应节点</div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
              
              {/* Floating elements */}
              <div className="absolute -top-4 -right-4 p-3 bg-white rounded-2xl shadow-xl border border-slate-100 animate-bounce">
                <div className="flex items-center gap-2 text-green-600">
                  <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                  <span className="text-xs font-medium">运行中</span>
                </div>
              </div>
              
              <div className="absolute -bottom-4 -left-4 p-4 bg-white rounded-2xl shadow-xl border border-slate-100">
                <div className="text-2xl font-bold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">98.5%</div>
                <div className="text-xs text-slate-500">准确率</div>
              </div>
            </div>
          </div>
        </div>

        {/* Stats */}
        <div className="mt-16 lg:mt-24">
          <div className="grid grid-cols-3 gap-4 sm:gap-8 max-w-2xl mx-auto">
            {stats.map((stat, i) => (
              <div key={i} className="text-center">
                <div className="text-2xl sm:text-3xl lg:text-4xl font-black bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">
                  {stat.value}
                </div>
                <div className="text-xs sm:text-sm text-slate-500 mt-1">{stat.label}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
