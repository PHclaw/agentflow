import { useEffect, useMemo, useRef, useState } from 'react'

import { cn } from '../../lib/utils'

/**
 * 活跃度热力图（近一年的格子图）。
 *
 * 日期算术**全程走 UTC**，不用本地时区。接口返回的日期串是 UTC 切分的，
 * 用 `new Date('2026-10-14')` 这类本地解析会在东八区把整张图挪错一格
 * （或者在 UTC+ 的地方导致最后一天跑到明天去），表现是「昨天的记录画在
 * 今天」—— 这种错位一天很难被注意到，但会让整张图不可信。
 */

const DAY_MS = 86_400_000

/** 'YYYY-MM-DD' → 当天 0 点的 UTC 毫秒数。 */
function dayMs(iso: string): number {
  const [y, m, d] = iso.split('-').map(Number)
  return Date.UTC(y, m - 1, d)
}

function isoOf(ms: number): string {
  return new Date(ms).toISOString().slice(0, 10)
}

/**
 * 色阶：0 是空，1-4 由浅到深，4 以上都算最深。
 *
 * 用的是绝对档位而不是按分位数分档。分位数在「一年只有十几次活动」的
 * 新账号上会把仅有的两三笔也涂成最深色，看起来像是天天在用 ——
 * 绝对档位虽然颜色浅，但它是真的。
 */
const LEVELS = [
  'bg-slate-100 dark:bg-slate-800',
  'bg-brand-200 dark:bg-brand-900',
  'bg-brand-300 dark:bg-brand-700',
  'bg-brand-400 dark:bg-brand-600',
  'bg-brand-600 dark:bg-brand-500',
]

const levelOf = (n: number) => (n <= 0 ? 0 : Math.min(n, 4))

// 10px + 3px 间隙：53 列合计 686px，正好落在 1440px 屏上的左栏内宽（约 700px）里，
// 不会出现横向滚动条。再大一点（11px）就会超出几十像素，在最常见的桌面宽度上
// 平白多出一条滚动条。
const CELL_W = 'w-[10px]'
const CELL = cn(CELL_W, 'h-[10px] rounded-[3px]')

interface Cell {
  date: string
  count: number
}

interface ActivityHeatmapProps {
  /** 窗口起止（含），'YYYY-MM-DD'。由接口回显，前端不自己推算。 */
  start: string
  end: string
  /** 日期 → 次数 */
  counts: Record<string, number>
  /** 悬停提示里的单位，如「次对话」 */
  unit: string
}

export function ActivityHeatmap({ start, end, counts, unit }: ActivityHeatmapProps) {
  const { weeks, monthLabels } = useMemo(() => {
    const startMs = dayMs(start)
    const endMs = dayMs(end)
    // 回退到起点所在那一周的周日：GitHub 那种格子图每列是一整周，
    // 第一列留白比把整周拆开好看得多
    const gridStart = startMs - new Date(startMs).getUTCDay() * DAY_MS
    const weekCount = Math.floor((endMs - gridStart) / (7 * DAY_MS)) + 1

    const cols: (Cell | null)[][] = []
    for (let w = 0; w < weekCount; w += 1) {
      const col: (Cell | null)[] = []
      for (let d = 0; d < 7; d += 1) {
        const ms = gridStart + (w * 7 + d) * DAY_MS
        // 窗口之外的格子留空（不是 0）—— 让「还没到」和「这天没动」
        // 在视觉上能分开，否则整张图的边界是假的
        col.push(
          ms < startMs || ms > endMs
            ? null
            : { date: isoOf(ms), count: counts[isoOf(ms)] ?? 0 }
        )
      }
      cols.push(col)
    }

    // 月份标签放在列下方（参考图也是放下面的）。只在含「某月 1 号」的那一列
    // 出标签，并且和上一个标签至少隔开 3 列 —— 否则窄屏上两个月份会叠在一起。
    const labels: Record<number, string> = {}
    let lastLabel = -10
    cols.forEach((col, wi) => {
      const first = col.find((c) => c && c.date.endsWith('-01'))
      if (!first || wi - lastLabel < 3) return
      labels[wi] = `${Number(first.date.slice(5, 7))}月`
      lastLabel = wi
    })

    return { weeks: cols, monthLabels: labels }
  }, [start, end, counts])

  /*
    窄屏上这张图放不下：53 列 × 10px 需要约 690px，手机只有 300 出头。
    实际量一次 scrollWidth，只有真的溢出了才提示可以滑 —— 桌面端放得下，
    就不该出现这行字。
  */
  const boxRef = useRef<HTMLDivElement>(null)
  const [scrollable, setScrollable] = useState(false)
  const [atEnd, setAtEnd] = useState(false)

  useEffect(() => {
    const el = boxRef.current
    if (!el) return
    const measure = () => {
      const over = el.scrollWidth - el.clientWidth
      setScrollable(over > 4)
      setAtEnd(el.scrollLeft >= over - 4)
    }
    measure()
    const ro = new ResizeObserver(measure)
    ro.observe(el)
    el.addEventListener('scroll', measure, { passive: true })
    return () => {
      ro.disconnect()
      el.removeEventListener('scroll', measure)
    }
  }, [weeks.length])

  return (
    <div>
      {/*
        窄屏横向滚动。53 列在手机上放不下，压缩格子会让它退化成一片色块，
        滚动是唯一还能读的做法。
      */}
      <div ref={boxRef} className="custom-scrollbar overflow-x-auto pb-1">
        <div className="inline-flex min-w-max flex-col">
          <div className="flex gap-[3px]">
            {weeks.map((col, wi) => (
              <div key={wi} className="flex flex-col gap-[3px]">
                {col.map((cell, di) =>
                  cell ? (
                    <div
                      key={cell.date}
                      title={`${cell.date} · ${cell.count} ${unit}`}
                      className={cn(CELL, LEVELS[levelOf(cell.count)])}
                    />
                  ) : (
                    <div key={`blank-${wi}-${di}`} className={CELL} />
                  )
                )}
              </div>
            ))}
          </div>

          {/* 月份标签行。高度固定，否则会在没有标签的列上塌掉、把图往上挪 */}
          <div className="mt-1.5 flex gap-[3px]">
            {weeks.map((_, wi) => (
              <div key={wi} className={cn('relative h-4 shrink-0', CELL_W)}>
                {monthLabels[wi] && (
                  <span className="absolute left-0 top-0 whitespace-nowrap text-[11px] leading-none text-slate-400 dark:text-slate-500">
                    {monthLabels[wi]}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/*
        图例 + 滑动提示。少了图例，「浅色」到底是「少」还是「没有」只能靠猜。
        提示用 opacity 切换而不是条件渲染：滑到底时它消失，用条件渲染会让
        图例整排向右跳一下。
      */}
      <div className="mt-2 flex items-center justify-between gap-2 text-[11px] text-slate-400 dark:text-slate-500">
        <span
          className={cn(
            'transition-opacity duration-300',
            scrollable && !atEnd ? 'opacity-100' : 'opacity-0'
          )}
          aria-hidden="true"
        >
          可左右滑动看整年 →
        </span>
        <span className="flex shrink-0 items-center gap-1.5">
          <span>少</span>
          {LEVELS.map((cls) => (
            <span key={cls} className={cn(CELL, cls)} />
          ))}
          <span>多</span>
        </span>
      </div>
    </div>
  )
}
