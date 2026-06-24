import { useState, useEffect } from 'react'
import { Card } from '../ui/Card'
import { Button } from '../ui/Button'
import { ArrowRight, MessageSquare, Star, Users } from 'lucide-react'
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
    return (
      <section id="templates" className="py-24 lg:py-32 relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-b from-slate-50 to-white" />
        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <p className="text-slate-400 text-lg">加载中...</p>
        </div>
      </section>
    )
  }

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
          {templateList.map((t, i) => (
            <Card
              key={t.id || t.name}
              hover
              className="group relative overflow-hidden cursor-pointer"
            >
              <div className="p-6">
                {/* Header */}
                <div className="flex items-start justify-between mb-4">
                  <div className={`inline-flex p-3 rounded-2xl bg-gray-50`}>
                    <span className="text-2xl">{t.icon || '🤖'}</span>
                  </div>
                  <div className="flex items-center gap-1 text-amber-500">
                    <Star className="w-4 h-4 fill-current" />
                    <span className="text-sm font-medium text-slate-700">{t.rating || 4.5}</span>
                  </div>
                </div>

                {/* Content */}
                <h3 className="text-xl font-bold text-slate-900 mb-2 group-hover:text-indigo-600 transition-colors">
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
                        <span className="text-green-500">✓</span>
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
