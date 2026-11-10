import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowUpRight, Flame } from 'lucide-react'

import { api } from '../../services/api'
import { useAuthStore } from '../../stores'
import { cn } from '../../lib/utils'
import { Card } from '../ui/Card'
import { Button } from '../ui/Button'
import { ActivityHeatmap } from './ActivityHeatmap'
import { LogoMorph } from './LogoMorph'

/**
 * 控制台的「成长面板」：陪伴天数、活跃度热力图，以及一块成长说明 + 动画。
 *
 * 数据全部来自 `GET /agents/stats/activity` 的真实聚合（会话按天去重、
 * 新增的 Agent 与知识库按天计数），没有估算、没有写死的曲线。
 * 控制台上别的卡片里那几个「本月 API 调用 = Agent 数 × 100」之类的假数字
 * 是另一个问题，不在这次改动范围内 —— 但至少这块新面板不再往里加。
 */

interface ActivityStats {
  days: number
  start: string
  end: string
  joinedAt: string | null
  companionDays: number | null
  totalSessions: number
  activeDays: number
  currentStreak: number
  longestStreak: number
  daily: {
    activity: Record<string, number>
    growth: Record<string, number>
  }
}

type Mode = 'activity' | 'growth'

const MODES: { key: Mode; label: string; hint: string; unit: string }[] = [
  {
    key: 'activity',
    label: '活跃度',
    hint: '每一次对话都会在当天记一笔，格子越深说明那天用得越多。',
    unit: '次对话',
  },
  {
    key: 'growth',
    label: '成长度',
    hint: '当天新增的 Agent 与知识库 —— 它们会进入之后的每一次对话。',
    unit: '项新增',
  },
]

export function GrowthPanel() {
  const user = useAuthStore((s) => s.user)
  const [data, setData] = useState<ActivityStats | null>(null)
  const [failed, setFailed] = useState(false)
  const [mode, setMode] = useState<Mode>('activity')

  useEffect(() => {
    let alive = true
    api
      .get('/agents/stats/activity')
      .then((res) => {
        if (alive) setData(res as ActivityStats)
      })
      .catch((err) => {
        // 这块面板是锦上添花。取不到就安静降级成一句说明，绝不把控制台
        // 的其余部分一起拖下水（那些卡片各有各的请求，不该被这里连累）。
        console.warn('成长面板数据加载失败：', err)
        if (alive) setFailed(true)
      })
    return () => {
      // 请求回来时组件可能已经卸载（切路由），别往已经没了的组件上写状态
      alive = false
    }
  }, [])

  const active = MODES.find((m) => m.key === mode) ?? MODES[0]
  const counts = data?.daily[mode] ?? {}

  const displayName = user?.nickname?.trim() || '你'

  const summary = failed
    ? '成长数据暂时取不到，其他功能不受影响'
    : !data
      ? '正在统计…'
      : [
          data.companionDays ? `陪伴 ${data.companionDays} 天` : null,
          `共 ${data.totalSessions} 次对话`,
          `近一年活跃 ${data.activeDays} 天`,
        ]
          .filter(Boolean)
          .join(' · ')

  return (
    /*
      桌面端撑满整列（lg:h-full + flex-col）：这块面板比右栏那三张卡矮，
      不撑满的话它下面会空出一条 —— 看起来像少放了一个模块。
      撑满之后多出来的高度落在说明区上方（下面那个 mt-auto），
      说明区贴着卡片底边，反而像是有意留白。
    */
    <Card className="p-4 sm:p-6 lg:flex lg:h-full lg:flex-col">
      {/* 头部：头像 + 称呼 + 真实统计。
          窄屏上允许换行：不然右边那枚徽标会把「昵称 的 AgentFlow」挤成
          「smoke 的 Age…」，一个被截断的产品名比少一行难看。 */}
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div className="flex min-w-0 items-center gap-3">
          <div className="grid h-11 w-11 shrink-0 place-items-center overflow-hidden rounded-full bg-gradient-to-br from-brand-500 to-brand-600 text-lg font-semibold text-white">
            {user?.avatar ? (
              <img src={user.avatar} alt="" className="h-full w-full object-cover" />
            ) : (
              displayName.slice(0, 1)
            )}
          </div>
          <div className="min-w-0">
            <h2 className="truncate text-lg font-semibold text-slate-900 dark:text-white">
              {displayName} 的 AgentFlow
            </h2>
            <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-400">{summary}</p>
          </div>
        </div>

        {/*
          这里参考图放的是一个「开启自我成长」开关。我们没有那个功能，
          摆一个按不动（或者按了没反应）的开关比不摆更糟 —— 所以换成
          真实的连续天数。位置和分量都和原来那枚按钮相当，但它是真的。
        */}
        {data && data.currentStreak > 0 && (
          <span
            title={`历史最长连续 ${data.longestStreak} 天`}
            className="inline-flex shrink-0 items-center gap-1 rounded-full bg-brand-50 px-2.5 py-1 text-xs font-medium text-brand-700 dark:bg-brand-500/10 dark:text-brand-300"
          >
            <Flame className="h-3.5 w-3.5" />
            连续 {data.currentStreak} 天
          </span>
        )}
      </div>

      {/* 分段控件：两个维度各自对应一条真实的序列，不是换个说法看同一张图 */}
      <div
        role="tablist"
        aria-label="统计维度"
        className="mt-5 inline-flex rounded-lg bg-slate-100 p-0.5 dark:bg-slate-800"
      >
        {MODES.map((m) => (
          <button
            key={m.key}
            type="button"
            role="tab"
            aria-selected={mode === m.key}
            onClick={() => setMode(m.key)}
            className={cn(
              'rounded-md px-3 py-1.5 text-sm transition-colors',
              mode === m.key
                ? 'bg-white font-medium text-slate-900 dark:bg-slate-900 dark:text-white'
                : 'text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200'
            )}
          >
            {m.label}
          </button>
        ))}
      </div>

      <p className="mt-3 text-sm text-slate-500 dark:text-slate-400">{active.hint}</p>

      {/* 热力图。加载中给骨架，别让下面那块内容先跳上来再被顶下去 */}
      <div className="mt-3">
        {data ? (
          <ActivityHeatmap
            start={data.start}
            end={data.end}
            counts={counts}
            unit={active.unit}
          />
        ) : (
          <div className="h-[92px] animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800" />
        )}
      </div>

      {/* 下方：说明 + 动画。动画是纯装饰，不承载任何信息 */}
      <div className="mt-6 grid gap-6 border-t border-slate-100 pt-6 dark:border-slate-800 md:grid-cols-[1.15fr_1fr] md:items-center lg:mt-auto">
        <div>
          <h3 className="text-base font-semibold text-slate-900 dark:text-white">
            AgentFlow 会跟着你一起长
          </h3>
          <p className="mt-2 text-sm leading-relaxed text-slate-500 dark:text-slate-400">
            你上传的资料、沉淀的知识库、调顺的 Agent，都会进入之后的每一次对话。
            用得越多，它越贴合你的场景。
          </p>
          <Link to="/knowledge" className="mt-4 inline-block">
            <Button
              variant="outline"
              size="sm"
              rightIcon={<ArrowUpRight className="h-3.5 w-3.5" />}
            >
              完善知识库
            </Button>
          </Link>
        </div>

        {/* 「agentflow」字标 ⇄ AF 标识 的粒子变形。纯装饰，不承载信息 */}
        <LogoMorph />
      </div>
    </Card>
  )
}
