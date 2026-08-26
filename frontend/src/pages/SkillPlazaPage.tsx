import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  Search,
  Sparkles,
  Loader2,
  MessageSquare,
  Tag,
  ArrowRight,
} from 'lucide-react'
import { skills as skillsApi, type SkillPlazaItem } from '../services/api'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Card } from '../components/ui/Card'

export default function SkillPlazaPage() {
  const navigate = useNavigate()
  const [items, setItems] = useState<SkillPlazaItem[]>([])
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    loadPlaza()
  }, [])

  const loadPlaza = async () => {
    try {
      setLoading(true)
      setError('')
      const data = await skillsApi.plaza()
      setItems(Array.isArray(data) ? data : [])
    } catch (e: any) {
      setError(e?.message || '加载失败，请先登录')
      setItems([])
    } finally {
      setLoading(false)
    }
  }

  const filtered = items.filter((s) => {
    const q = query.trim().toLowerCase()
    if (!q) return true
    return (
      s.name.toLowerCase().includes(q) ||
      s.specialty.toLowerCase().includes(q) ||
      (s.description || '').toLowerCase().includes(q) ||
      (s.triggers || []).some((t) => t.toLowerCase().includes(q))
    )
  })

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-indigo-600 mb-2">
            <Sparkles className="w-5 h-5" />
            <span className="text-sm font-semibold">Skill 广场</span>
          </div>
          <h1 className="text-3xl font-bold text-slate-900">预置专业 Skill</h1>
          <p className="text-slate-500 mt-2">
            Excel / PDF / PPT / 会议纪要 / 统计分析等，一键调用。
          </p>
        </div>
        <div className="w-full md:w-80 relative">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="搜索 Skill 名称或场景..."
            className="pl-9"
          />
        </div>
      </div>

      {error && (
        <Card className="p-4 border-red-200 bg-red-50 text-red-700 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <span>{error}</span>
          {(error.includes('登录') || error.includes('401') || error.includes('未登录')) && (
            <Link to="/login">
              <Button size="sm" variant="outline">
                去登录
              </Button>
            </Link>
          )}
        </Card>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-24 text-slate-500">
          <Loader2 className="w-6 h-6 animate-spin mr-2" />
          加载中...
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filtered.map((skill) => (
            <Card
              key={skill.id}
              className="p-5 hover:shadow-lg transition-shadow border-slate-200"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="text-lg font-semibold text-slate-900">{skill.name}</h3>
                  <p className="text-sm text-indigo-600 mt-1">{skill.specialty}</p>
                </div>
                <span className="text-xs text-slate-400">{skill.version}</span>
              </div>
              <p className="text-sm text-slate-600 mt-3 line-clamp-3 whitespace-pre-line">
                {skill.description}
              </p>
              {skill.triggers?.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-3">
                  {skill.triggers.slice(0, 4).map((t) => (
                    <span
                      key={t}
                      className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-600"
                    >
                      <Tag className="w-3 h-3" />
                      {t}
                    </span>
                  ))}
                </div>
              )}
              <div className="mt-5 flex items-center justify-between">
                <span className="text-xs text-slate-400">
                  调用 {skill.totalCalls ?? 0} 次
                </span>
                <Button
                  size="sm"
                  rightIcon={<ArrowRight className="w-4 h-4" />}
                  onClick={() => navigate(`/skills/${skill.id}`)}
                >
                  开始对话
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}

      {!loading && filtered.length === 0 && (
        <div className="text-center py-20 text-slate-500">
          <MessageSquare className="w-10 h-10 mx-auto mb-3 opacity-40" />
          暂无匹配的 Skill
        </div>
      )}
    </div>
  )
}
