import { useEffect, useState } from 'react'
import { Card } from '../ui/Card'
import { Button } from '../ui/Button'
import { Reveal } from './Reveal'
import { Check, Sparkles, Building2, Zap } from 'lucide-react'
import { billing } from '../../services/api'

/**
 * 各档的展示外观。
 *
 * 只放「长什么样」，**不放额度和价格** —— 那些必须来自后端 /billing/plans。
 * 这里的文案以前是写死的（免费版「3 个 Agent / 1,000 次对话」、
 * 专业版「无限 Agent / 100,000 次对话」），和后端实际额度（1 / 5 / 20 个 Agent，
 * 5 / 150 / 666 条消息）差了几个数量级，属于对外承诺和产品实际不符。
 */
const APPEARANCE: Record<string, {
  description: string
  icon: typeof Sparkles
  gradient: string
  cta: string
  popular: boolean
}> = {
  free: {
    description: '适合个人试用',
    icon: Sparkles,
    gradient: 'from-slate-500 to-slate-600',
    cta: '免费开始',
    popular: false,
  },
  pro: {
    description: '适合中小团队',
    icon: Zap,
    gradient: 'from-brand-500 to-brand-500',
    cta: '立即升级',
    popular: true,
  },
  team: {
    description: '适合团队协作与规模化使用',
    icon: Building2,
    gradient: 'from-amber-500 to-orange-500',
    cta: '联系销售',
    popular: false,
  },
}

//: 套餐 id 到中文名。后端存的是 free / pro / team。
const PLAN_LABELS: Record<string, string> = {
  free: '免费版',
  pro: '进阶版',
  team: '团队版',
}

//: 年付折扣。后端目前只有单个月价，没有 price_yearly 字段，
//: 这里沿用在用界面上原本就标注的 -20%。
const YEARLY_DISCOUNT = 0.8

interface PlanRow {
  id: string
  name: string
  price: number
  features?: string[]
}

export function PricingSection() {
  const [isYearly, setIsYearly] = useState(false)
  const [plans, setPlans] = useState<PlanRow[]>([])
  const [loading, setLoading] = useState(true)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let cancelled = false
    billing
      .listPlans()
      .then((res) => {
        if (!cancelled) setPlans(res?.plans || [])
      })
      .catch(() => {
        if (!cancelled) setFailed(true)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  // 把后端的额度/价格和本地的展示外观拼起来
  const display = plans.map((plan) => {
    const look = APPEARANCE[plan.id] || APPEARANCE.free
    const monthly = plan.price ?? 0
    return {
      id: plan.id,
      features: plan.features,
      label: PLAN_LABELS[plan.id] || plan.name,
      monthly,
      yearly: monthly > 0 ? Math.round(monthly * YEARLY_DISCOUNT) : 0,
      ...look,
    }
  })

  return (
    <section id="pricing" className="py-24 lg:py-32 relative overflow-hidden">
      {/* Background */}
      <div className="absolute inset-0 bg-gradient-to-b from-white via-slate-50 to-white" />
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[1000px] h-[500px] bg-gradient-to-b from-brand-100/50 to-transparent rounded-full blur-3xl animate-breathe motion-reduce:animate-none" />

      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <div className="text-center max-w-2xl mx-auto mb-12">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-amber-50 border border-amber-100 text-amber-600 text-sm font-medium mb-6">
            <Sparkles className="w-4 h-4" />
            定价方案
          </div>
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-black text-slate-900 mb-4">
            按需选择方案
          </h2>
          <p className="text-lg text-slate-600">
            从个人使用到团队部署，按实际用量选择
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
        {loading && (
          <div className="grid lg:grid-cols-3 gap-6 lg:gap-8 items-start">
            {[0, 1, 2].map((i) => (
              <Card key={i} className="p-6 lg:p-8">
                <div className="animate-pulse space-y-4">
                  <div className="h-12 w-12 rounded-2xl bg-slate-200" />
                  <div className="h-4 w-24 rounded bg-slate-200" />
                  <div className="h-9 w-32 rounded bg-slate-200" />
                  <div className="h-3 w-full rounded bg-slate-100" />
                  <div className="h-3 w-5/6 rounded bg-slate-100" />
                  <div className="h-3 w-4/6 rounded bg-slate-100" />
                </div>
              </Card>
            ))}
          </div>
        )}

        {/* 取不到套餐就明说，不退回写死的数字 ——
            写死的额度和真实额度不一致，正是这次要修掉的问题 */}
        {!loading && failed && (
          <p className="text-center text-slate-500">
            定价信息暂时无法加载，请稍后重试或登录后在「设置 → 订阅」中查看。
          </p>
        )}

        {!loading && !failed && (
          <Reveal stagger className="grid lg:grid-cols-3 gap-6 lg:gap-8 items-start">
            {display.map((plan) => (
              <div
                key={plan.id}
                className={`relative ${plan.popular ? 'lg:-mt-4 lg:mb-4' : ''}`}
              >
                {/* Popular badge */}
                {plan.popular && (
                  <div className="absolute -top-4 left-1/2 -translate-x-1/2 z-10">
                    <div className="px-4 py-1 bg-gradient-to-r from-brand-500 to-brand-500 text-white text-sm font-medium rounded-full shadow-lg shadow-brand-500/30">
                      推荐
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
                  <div
                    className={`absolute inset-0 bg-gradient-to-br ${plan.gradient} ${
                      plan.popular ? 'opacity-10' : 'opacity-5'
                    }`}
                  />

                  <div className="relative p-6 lg:p-8">
                    {/* Header */}
                    <div className="flex items-center gap-4 mb-6">
                      <div className={`p-3 rounded-2xl bg-gradient-to-br ${plan.gradient}`}>
                        <plan.icon className="w-6 h-6 text-white" />
                      </div>
                      <div>
                        <h3 className={`text-xl font-bold ${plan.popular ? 'text-white' : 'text-slate-900'}`}>
                          {plan.label}
                        </h3>
                        <p className={`text-sm ${plan.popular ? 'text-slate-400' : 'text-slate-500'}`}>
                          {plan.description}
                        </p>
                      </div>
                    </div>

                    {/* Price */}
                    <div className="mb-6">
                      <div className="flex items-baseline gap-1">
                        {/*
                          切换月付/年付时让数字重播一次短进场：key 变了 React 会
                          重建这个节点，动画跟着重播 —— 这是「价格确实变了」最省事
                          也最清楚的反馈。用 0.15s 的 scale-in，不用首屏那套 0.65s：
                          这是按下之后的即时响应，慢一点就显得迟钝。
                        */}
                        <span
                          key={isYearly ? 'yearly' : 'monthly'}
                          className={`animate-scale-in text-4xl font-black motion-reduce:animate-none ${
                            plan.popular ? 'text-white' : 'text-slate-900'
                          }`}
                        >
                          {plan.monthly === 0
                            ? '免费'
                            : `¥${isYearly ? plan.yearly : plan.monthly}`}
                        </span>
                        {plan.monthly > 0 && (
                          <span className={plan.popular ? 'text-slate-400' : 'text-slate-500'}>
                            /月
                          </span>
                        )}
                      </div>
                      {isYearly && plan.monthly > 0 && (
                        <p key="saving" className="animate-fade-in mt-1 text-sm text-green-500">
                          节省 ¥{(plan.monthly - plan.yearly) * 12}/年
                        </p>
                      )}
                    </div>

                    {/* Features：额度直接来自后端，不再手写 */}
                    <ul className="space-y-3 mb-8">
                      {(plan.features || []).map((feature, i) => (
                        <li key={i} className="flex items-start gap-3">
                          <div className={`p-0.5 rounded-full bg-gradient-to-br ${plan.gradient}`}>
                            <Check className="w-4 h-4 text-white" />
                          </div>
                          <span className={plan.popular ? 'text-slate-300' : 'text-slate-600'}>
                            {feature}
                          </span>
                        </li>
                      ))}
                    </ul>

                    {/* CTA */}
                    <Button
                      variant={plan.popular ? 'primary' : 'outline'}
                      className={`w-full ${
                        plan.popular
                          ? 'bg-gradient-to-r from-brand-500 to-brand-500 hover:from-brand-600 hover:to-brand-600 shadow-lg shadow-brand-500/30'
                          : ''
                      }`}
                    >
                      {plan.cta}
                    </Button>
                  </div>
                </Card>
              </div>
            ))}
          </Reveal>
        )}

        {/* Footer note */}
        <p className="text-center text-sm text-slate-500 mt-12">
          所有方案均提供 14 天试用，试用期内可全额退款
        </p>
      </div>
    </section>
  )
}
