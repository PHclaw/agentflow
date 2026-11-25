import { useState, useEffect } from 'react'
import { Card } from '../ui/Card'
import { Reveal } from './Reveal'
import { Button } from '../ui/Button'
import { ArrowRight, Check, MessageSquare, Star, Users } from 'lucide-react'
import { Link } from 'react-router-dom'
import { templates } from '../../services/api'

export function TemplatesSection() {
  const [templateList, setTemplateList] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function loadTemplates() {
      try {
        const data = await templates.list()
        setTemplateList((data || []).slice(0, 6))
      } catch (err) {
        console.error('Failed to load templates:', err)
      } finally {
        setLoading(false)
      }
    }
    loadTemplates()
  }, [])

  if (loading) {
    /*
      骨架屏，而不是「加载中...」一行字。
      这里要等一次接口，而卡片网格是有确定形状的 —— 先把形状占住，
      数据到位时页面就不会整段往下跳。格数和列数跟真卡片对齐（6 张、
      sm 两列 / lg 三列），切换的瞬间位置不挪。写法与定价区块的骨架保持一致。
    */
    return (
      <section id="templates" className="py-24 lg:py-32 relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-b from-slate-50 to-white" />

        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-2xl mx-auto mb-16">
            <div className="mx-auto h-8 w-28 animate-pulse rounded-full bg-slate-100" />
            <div className="mx-auto mt-6 h-11 w-64 animate-pulse rounded-lg bg-slate-100" />
            <div className="mx-auto mt-4 h-5 w-80 max-w-full animate-pulse rounded bg-slate-100" />
          </div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {[0, 1, 2, 3, 4, 5].map((i) => (
              <Card key={i}>
                <div className="animate-pulse p-6">
                  <div className="mb-4 flex items-start justify-between">
                    <div className="h-12 w-12 rounded-2xl bg-slate-200" />
                    <div className="h-5 w-12 rounded bg-slate-100" />
                  </div>
                  <div className="mb-2 h-6 w-32 rounded bg-slate-200" />
                  <div className="mb-4 h-4 w-full rounded bg-slate-100" />
                  <div className="space-y-1.5">
                    <div className="h-3.5 w-5/6 rounded bg-slate-100" />
                    <div className="h-3.5 w-4/6 rounded bg-slate-100" />
                    <div className="h-3.5 w-3/6 rounded bg-slate-100" />
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </div>
      </section>
    )
  }

  return (
    <section id="templates" className="py-24 lg:py-32 relative overflow-hidden">
      {/* Background */}
      <div className="absolute inset-0 bg-gradient-to-b from-slate-50 to-white" />
      <div className="absolute top-1/2 left-0 w-[600px] h-[600px] bg-brand-100/30 rounded-full blur-3xl -translate-y-1/2 animate-breathe motion-reduce:animate-none" />
      {/* 错开半个周期：两团同步呼吸会看出是同一个节拍，错开之后才像各自浮动 */}
      <div
        className="absolute top-1/2 right-0 w-[600px] h-[600px] bg-brand-100/30 rounded-full blur-3xl -translate-y-1/2 animate-breathe motion-reduce:animate-none"
        style={{ animationDelay: '-12s' }}
      />

      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <div className="text-center max-w-2xl mx-auto mb-16">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-brand-50 border border-brand-100 text-brand-600 text-sm font-medium mb-6">
            <MessageSquare className="w-4 h-4" />
            行业模板
          </div>
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-black text-slate-900 mb-4">
            从模板开始
          </h2>
          <p className="text-lg text-slate-600">
            覆盖常见业务场景，可以在模板基础上调整
          </p>
        </div>

        {/* Templates Grid。Reveal 直接当网格容器（className 透传） */}
        <Reveal stagger className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {templateList.map((t, i) => (
            <Card
              key={t.id || t.name}
              hover
              className="group relative overflow-hidden cursor-pointer"
            >
              <div className="p-6">
                {/* Header：模板图标用首字母标，不用表情符号 */}
                <div className="flex items-start justify-between mb-4">
                  <div
                    className={`inline-flex w-12 h-12 items-center justify-center rounded-2xl text-white text-lg font-semibold bg-gradient-to-br ${
                      t.color || 'from-brand-600 to-brand-500'
                    }`}
                  >
                    {(t.name || 'A').trim().charAt(0)}
                  </div>
                  <div className="flex items-center gap-1 text-amber-500">
                    <Star className="w-4 h-4 fill-current" />
                    <span className="text-sm font-medium text-slate-700">{t.rating || 4.5}</span>
                  </div>
                </div>

                {/* Content */}
                <h3 className="text-xl font-bold text-slate-900 mb-2 group-hover:text-brand-600 transition-colors">
                  {t.name}
                </h3>
                <p className="text-slate-600 text-sm leading-relaxed mb-4">
                  {t.description}
                </p>

                {/* Features */}
                {t.features && t.features.length > 0 && (
                  <div className="mb-4 space-y-1">
                    {t.features.slice(0, 3).map((f: string, j: number) => (
                      <div key={j} className="flex items-center gap-2 text-xs text-slate-500">
                        <Check className="w-3.5 h-3.5 text-brand-500 flex-shrink-0" />
                        <span>{f}</span>
                      </div>
                    ))}
                  </div>
                )}

                {/* Stats placeholder */}
                <div className="flex items-center gap-4 text-sm text-slate-400">
                  <span className="flex items-center gap-1">
                    <Users className="w-4 h-4" />
                    {t.usage_count ? `${t.usage_count.toLocaleString()}+` : '1,000+'}
                  </span>
                  <span>使用中</span>
                </div>

                {/* Hover effect */}
                <div className={`absolute bottom-0 left-0 right-0 h-1 bg-gradient-to-r ${t.color || 'from-blue-500 to-cyan-500'} opacity-0 group-hover:opacity-100 transition-opacity`} />
              </div>

              {/* Arrow indicator */}
              <div className="absolute top-6 right-6 opacity-0 group-hover:opacity-100 transition-opacity">
                <div className="p-2 rounded-full bg-brand-50 text-brand-600">
                  <ArrowRight className="w-4 h-4" />
                </div>
              </div>
            </Card>
          ))}
        </Reveal>

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
