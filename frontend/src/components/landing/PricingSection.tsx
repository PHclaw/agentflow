import { useState } from 'react'
import { Card } from '../ui/Card'
import { Button } from '../ui/Button'
import { Check, Sparkles, Building2, Zap } from 'lucide-react'

const plans = [
  {
    name: '免费版',
    description: '适合个人开发者和爱好者',
    price: { monthly: 0, yearly: 0 },
    icon: Sparkles,
    gradient: 'from-slate-500 to-slate-600',
    features: [
      '3 个 AI Agent',
      '1,000 次对话/月',
      '基础模板库',
      '社区支持',
      '7x24 在线',
    ],
    notIncluded: [
      '高级模板',
      'API 接入',
      '数据分析',
      '团队协作',
    ],
    cta: '免费开始',
    popular: false,
  },
  {
    name: '专业版',
    description: '适合中小企业团队',
    price: { monthly: 99, yearly: 79 },
    icon: Zap,
    gradient: 'from-indigo-500 to-purple-500',
    features: [
      '无限 AI Agent',
      '100,000 次对话/月',
      '全部模板库',
      'API 接入',
      '数据分析面板',
      '优先邮件支持',
      '7x24 在线',
    ],
    notIncluded: [],
    cta: '立即升级',
    popular: true,
  },
  {
    name: '企业版',
    description: '适合大型企业',
    price: { monthly: 399, yearly: 319 },
    icon: Building2,
    gradient: 'from-amber-500 to-orange-500',
    features: [
      '无限 AI Agent',
      '无限对话',
      '全部模板库',
      'API 接入',
      '高级数据分析',
      '团队协作',
      '专属客户成功经理',
      'SLA 保障',
      '私有化部署',
    ],
    notIncluded: [],
    cta: '联系销售',
    popular: false,
  },
]

export function PricingSection() {
  const [isYearly, setIsYearly] = useState(false)

  return (
    <section id="pricing" className="py-24 lg:py-32 relative overflow-hidden">
      {/* Background */}
      <div className="absolute inset-0 bg-gradient-to-b from-white via-slate-50 to-white" />
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[1000px] h-[500px] bg-gradient-to-b from-indigo-100/50 to-transparent rounded-full blur-3xl" />

      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <div className="text-center max-w-2xl mx-auto mb-12">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-amber-50 border border-amber-100 text-amber-600 text-sm font-medium mb-6">
            <Sparkles className="w-4 h-4" />
            定价方案
          </div>
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-black text-slate-900 mb-4">
            简单透明，按需选择
          </h2>
          <p className="text-lg text-slate-600">
            无论你是个人开发者还是企业团队，都能找到适合的方案
          </p>

          {/* Toggle */}
          <div className="mt-8 inline-flex items-center gap-3 p-1.5 bg-slate-100 rounded-full">
            <button
              onClick={() => setIsYearly(false)}
              className={`px-4 py-2 rounded-full text-sm font-medium transition-all ${
                !isYearly
                  ? 'bg-white text-slate-900 shadow-sm'
                  : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              月付
            </button>
            <button
              onClick={() => setIsYearly(true)}
              className={`px-4 py-2 rounded-full text-sm font-medium transition-all flex items-center gap-2 ${
                isYearly
                  ? 'bg-white text-slate-900 shadow-sm'
                  : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              年付
              <span className="px-2 py-0.5 bg-green-100 text-green-600 text-xs rounded-full">
                -20%
              </span>
            </button>
          </div>
        </div>

        {/* Pricing Cards */}
        <div className="grid lg:grid-cols-3 gap-6 lg:gap-8 items-start">
          {plans.map((plan, index) => (
            <div
              key={plan.name}
              className={`relative ${plan.popular ? 'lg:-mt-4 lg:mb-4' : ''}`}
            >
              {/* Popular badge */}
              {plan.popular && (
                <div className="absolute -top-4 left-1/2 -translate-x-1/2 z-10">
                  <div className="px-4 py-1 bg-gradient-to-r from-indigo-500 to-purple-500 text-white text-sm font-medium rounded-full shadow-lg shadow-indigo-500/30">
                    最受欢迎
                  </div>
                </div>
              )}

              <Card
                className={`relative overflow-hidden ${
                  plan.popular
                    ? 'bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 border-slate-700'
                    : 'bg-white border-slate-200'
                }`}
              >
                {/* Background decoration */}
                <div className={`absolute inset-0 bg-gradient-to-br ${plan.gradient} opacity-${plan.popular ? '10' : '5'}`} />
                
                <div className="relative p-6 lg:p-8">
                  {/* Header */}
                  <div className="flex items-center gap-4 mb-6">
                    <div className={`p-3 rounded-2xl bg-gradient-to-br ${plan.gradient}`}>
                      <plan.icon className="w-6 h-6 text-white" />
                    </div>
                    <div>
                      <h3 className={`text-xl font-bold ${plan.popular ? 'text-white' : 'text-slate-900'}`}>
                        {plan.name}
                      </h3>
                      <p className={`text-sm ${plan.popular ? 'text-slate-400' : 'text-slate-500'}`}>
                        {plan.description}
                      </p>
                    </div>
                  </div>

                  {/* Price */}
                  <div className="mb-6">
                    <div className="flex items-baseline gap-1">
                      <span className={`text-4xl font-black ${plan.popular ? 'text-white' : 'text-slate-900'}`}>
                        ¥{isYearly ? plan.price.yearly : plan.price.monthly}
                      </span>
                      <span className={`${plan.popular ? 'text-slate-400' : 'text-slate-500'}`}>
                        /月
                      </span>
                    </div>
                    {isYearly && plan.price.monthly > 0 && (
                      <p className="text-sm text-green-500 mt-1">
                        节省 ¥{(plan.price.monthly - plan.price.yearly) * 12}/年
                      </p>
                    )}
                  </div>

                  {/* Features */}
                  <ul className="space-y-3 mb-8">
                    {plan.features.map((feature, i) => (
                      <li key={i} className="flex items-start gap-3">
                        <div className={`p-0.5 rounded-full bg-gradient-to-br ${plan.gradient}`}>
                          <Check className="w-4 h-4 text-white" />
                        </div>
                        <span className={plan.popular ? 'text-slate-300' : 'text-slate-600'}>
                          {feature}
                        </span>
                      </li>
                    ))}
                    {plan.notIncluded.map((feature, i) => (
                      <li key={i} className="flex items-start gap-3 opacity-50">
                        <div className="p-0.5 rounded-full bg-slate-300">
                          <Check className="w-4 h-4 text-slate-500" />
                        </div>
                        <span className={plan.popular ? 'text-slate-500' : 'text-slate-400'}>
                          {feature}
                        </span>
                      </li>
                    ))}
                  </ul>

                  {/* CTA */}
                  <Button
                    variant={plan.popular ? 'default' : 'outline'}
                    className={`w-full ${
                      plan.popular
                        ? 'bg-gradient-to-r from-indigo-500 to-purple-500 hover:from-indigo-600 hover:to-purple-600 shadow-lg shadow-indigo-500/30'
                        : ''
                    }`}
                  >
                    {plan.cta}
                  </Button>
                </div>
              </Card>
            </div>
          ))}
        </div>

        {/* Footer note */}
        <p className="text-center text-sm text-slate-500 mt-12">
          所有方案都包含 14 天免费试用，不满意全额退款
        </p>
      </div>
    </section>
  )
}
