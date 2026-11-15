import { useEffect, useRef } from 'react'

import { cn } from '../../lib/utils'
import {
  PIXEL_BEAT_MS,
  clamp01,
  easeInOut,
  fillCell,
  observeTheme,
  observeVisibility,
  pixelPalette,
  prepareCanvas,
  prefersReducedMotion,
  type PixelKind,
  type PixelPalette,
} from '../pixel/pixelKit'

/**
 * 像素点阵变形动画：一串「形状」之间来回变形，用来讲智能体在做什么。
 *
 * 形状用 ASCII 点阵写，不画路径、也不做画布采样
 * ---------------------------------------------------------------
 * 每个形状就是几行字符，`#` 是主色、`B` 是品牌色、`G` 是完成色、
 * `W` 是进行中、`F` 是失败、`.` 是空。这么写有三个好处：
 *
 * - **改形状不用懂代码**。想给「步骤清单」加一行，就加一行字符。
 * - **在卡片这种小尺寸下认得出来**。这几种图形（气泡、清单、表格、柱状图、
 *   幻灯片）本质就是格子，按格子画出来的才是它们该有的样子；用贝塞尔曲线
 *   画一个表格图标，缩到 100px 就糊成一团。
 * - **无需离屏采样**。采样是为了把不可控的矢量形状变成点阵，而这里点阵
 *   本来就是源头。
 *
 * 画面上其实有四层，从下往上
 * ------------------------
 * 0. **底格**：整张 22×13 的网格上，每个格子的左上角点一个极淡的小方块。
 *    它让形状"坐"在一块画布上，而不是浮在空白里。因为它每次重建后才变一次，
 *    所以预渲染到一张离屏画布上，每帧只花一次 drawImage。
 * 1. **拖尾**：飞行中的方块在自己身后 0.22 个行程处留一个更小更淡的影子。
 *    没有拖尾的话，快速移动的方块看起来是"跳"过去的；有了它才有速度感。
 * 2. **光晕 + 本体**：品牌色/完成色的方块落位后，身后垫一块 1.5 倍大的同色
 *    低透明方块。相邻方块的光晕会连成一片，形状边缘就有了柔和的发光轮廓。
 * 3. **扫光**：停留期的最后 45%，一道斜向的亮带从头扫到尾，扫过的方块被提亮
 *    并微微鼓起。这是"确认"的手势 —— 前面几秒在变形，这一下告诉你它完工了。
 *
 * 为什么不用 GIF / Lottie
 * ----------------------
 * 三张卡同时循环播 GIF，等于三份解码器常驻；Lottie 要引一整个运行时。
 * 这里只有几十个方块，每帧就是几百次 fillRect，且**离屏自动停**（见下），
 * 对首屏没有可测量的负担。
 *
 * 节奏：离散的出发，连续的飞行
 * --------------------------
 * 像素感来自**离散推进**，但整张图"一跳一跳"地挪动会显得卡。所以把两者拆开：
 *
 * - **出发时刻量化到拍**。每次变形拆成 7 个出发批次，每批 90ms，按方块在
 *   目标形状里的斜向位置排队 —— 于是看起来是一道斜向的波次扫过，而不是
 *   所有方块同时起跑（那像一张纸被整体推走，是位移不是变形）。
 * - **单个方块的飞行是连续的**，占 3 拍，用三次缓动。
 *
 * 结果：整体听上去是一个 90ms 的鼓点（和编辑器里的操作反馈同一个拍子，
 * 见 pixelKit.ts），每一帧看上去又是平滑的。
 *
 * 粒子配对：按相对中心的方位角排序后再一一对应
 * ------------------------------------------------
 * 不排序（按点阵扫描顺序配）会让左下角的方块飞向右上角，整片互相穿插，
 * 看起来像一团乱麻；按方位角配对之后整体是绕圈收拢／张开的，变形有方向感。
 *
 * 多出来的方块不是凭空出现／消失，而是**往中心收缩 + 淡出**
 * ------------------------------------------------------------
 * 各形状的方块数不一样（清单 58 个、表格 125 个）。多出来的那些被补成
 * 位于形状重心、透明度为 0 的「幽灵」，于是它们的去向是"飘回中心消失"，
 * 而不是在半空中瞬间闪现或跳到别处 —— 后者一眼就露馅。
 *
 * 性能与降级
 * ----------
 * - 方块数上限 150 左右（最多的一张是表格，125 个），每帧几百次 fillRect
 * - 用 IntersectionObserver 在离屏时停掉 rAF（滚动到别处就零开销）
 * - `prefers-reduced-motion` 下直接画最后一帧（"做完了"的状态），不启动循环
 */

/** 点阵尺寸。所有形状必须按同一个宽高写，否则会错位。 */
const GRID_W = 22
const GRID_H = 13

/*
  时间轴，全部写成拍的整数倍 —— 想整体调快调慢，改 pixelKit 里的
  PIXEL_BEAT_MS 一处即可。
*/
/** 停留：18 拍 */
const HOLD_MS = PIXEL_BEAT_MS * 18
/** 变形：9 拍 = 6 个出发批次 + 3 拍飞行，刚好整除 */
const MORPH_MS = PIXEL_BEAT_MS * 9
/** 单个方块的飞行时长：3 拍 */
const TRAVEL_MS = PIXEL_BEAT_MS * 3
/** 出发批次数量 */
const SLOTS = 7
/** 停留期的前 55% 用来"看清"，后 45% 扫光 */
const SWEEP_START = 0.55

/** 扫光用的提亮色。白色在浅色和深色底上都能提亮，不用分主题。 */
const SWEEP_COLOR = '#ffffff'

interface Cell {
  /** 点阵坐标（格子下标，不是像素） */
  x: number
  y: number
  kind: PixelKind
  /** 幽灵方块：画在同一位置但不可见，只用来承接"多出来的粒子" */
  ghost: boolean
}

/** 一张像素图：若干行等宽字符串。 */
export type PixelFrame = string[]

/** 一帧解析 + 排队后的结果。 */
interface FrameNode {
  cells: Cell[]
  /**
   * 每个方块的出发顺序，0~1。
   *
   * 按"斜向位置"（x + 0.6y）在整帧里的排名来定，而不是按数组下标 ——
   * 下标是按方位角排的，用它出发会变成绕圈；用斜向位置才是一道扫过去的波。
   */
  order: number[]
}

const KIND_BY_CHAR: Record<string, PixelKind> = {
  '#': 'ink',
  B: 'brand',
  G: 'done',
  W: 'warn',
  F: 'fail',
}

function parseFrame(rows: PixelFrame): Cell[] {
  const out: Cell[] = []
  for (let y = 0; y < rows.length && y < GRID_H; y += 1) {
    const row = rows[y]
    for (let x = 0; x < row.length && x < GRID_W; x += 1) {
      const kind = KIND_BY_CHAR[row[x]]
      if (kind) out.push({ x, y, kind, ghost: false })
    }
  }
  return out
}

/** 形状重心。幽灵方块挂在这里，粒子看起来是"收回中心"。 */
function centroid(cells: Cell[]) {
  if (!cells.length) return { x: (GRID_W - 1) / 2, y: (GRID_H - 1) / 2 }
  let sx = 0
  let sy = 0
  for (const c of cells) {
    sx += c.x
    sy += c.y
  }
  return { x: sx / cells.length, y: sy / cells.length }
}

/**
 * 按「相对重心的方位角」排序，两批点按序号一一配对。
 * 排序后整体是绕圈收拢／张开，而不是互相穿插。
 */
function sortByAngle<T extends { x: number; y: number }>(
  cells: T[],
  c: { x: number; y: number }
) {
  return [...cells].sort(
    (a, b) => Math.atan2(a.y - c.y, a.x - c.x) - Math.atan2(b.y - c.y, b.x - c.x)
  )
}

/** 斜向排名：左上的方块先出发，右下最后。 */
function diagonalOrder(cells: Cell[]) {
  const keys = cells.map((c) => c.x + c.y * 0.6)
  const min = Math.min(...keys)
  const max = Math.max(...keys)
  const span = max - min
  return span > 0 ? keys.map((k) => (k - min) / span) : keys.map(() => 0)
}

export function PixelMorph({
  frames,
  className,
}: {
  frames: PixelFrame[]
  className?: string
}) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const wrap = wrapRef.current
    const canvas = canvasRef.current
    if (!wrap || !canvas || frames.length < 2) return

    let raf = 0
    let nodes: FrameNode[] = []
    let startedAt = performance.now()
    let visible = true
    let pending = 0
    let palette: PixelPalette = pixelPalette()
    let cell = 0
    let originX = 0
    let originY = 0
    /** 第 0 层：预渲染好的底格 */
    let backdrop: HTMLCanvasElement | null = null

    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)')

    const build = () => {
      const cssW = wrap.clientWidth
      const cssH = wrap.clientHeight
      if (cssW < 40 || cssH < 24) return

      palette = pixelPalette()

      const parsed = frames.map(parseFrame)
      const max = Math.max(...parsed.map((f) => f.length))
      if (!max) return

      nodes = parsed.map((cells) => {
        const c = centroid(cells)
        // 出发顺序要跟着方块一起搬 —— 只重排方块、不搬顺序的话，
        // 配对次序和出发次序就对不上，错峰会错到别的方块身上
        const rankOf = new Map<Cell, number>()
        diagonalOrder(cells).forEach((rank, i) => rankOf.set(cells[i], rank))

        const sorted = sortByAngle(cells, c).map((cell) => ({
          cell,
          rank: rankOf.get(cell) ?? 0,
        }))
        const tailKind: PixelKind = sorted.length
          ? sorted[sorted.length - 1].cell.kind
          : 'ink'
        const items = [...sorted]
        // 幽灵块：位置落在重心、出发顺序取中位，让它们跟着波次一起收进中心
        while (items.length < max) {
          items.push({
            cell: { x: c.x, y: c.y, kind: tailKind, ghost: true },
            rank: 0.5,
          })
        }
        return {
          cells: items.map((it) => it.cell),
          order: items.map((it) => it.rank),
        }
      })

      // 等比铺满卡片：格子尽量大，同时完整放进画布
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      canvas.width = Math.round(cssW * dpr)
      canvas.height = Math.round(cssH * dpr)
      const ctx = canvas.getContext('2d')
      if (!ctx) return
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)

      cell = Math.min(cssW / (GRID_W + 1.2), cssH / (GRID_H + 1.2))
      originX = (cssW - cell * GRID_W) / 2
      originY = (cssH - cell * GRID_H) / 2

      // 底格只在这里画一次。每帧都画的话是 286 次 fillRect，
      // 比整张形状还贵，而它其实从不变化。
      const off = document.createElement('canvas')
      off.width = Math.round(cssW * dpr)
      off.height = Math.round(cssH * dpr)
      const octx = off.getContext('2d')
      if (octx) {
        octx.setTransform(dpr, 0, 0, dpr, 0, 0)
        const dot = Math.max(1, cell * 0.16)
        for (let gy = 0; gy < GRID_H; gy += 1) {
          for (let gx = 0; gx < GRID_W; gx += 1) {
            fillCell(
              octx,
              originX + gx * cell,
              originY + gy * cell,
              dot,
              palette.ink,
              0.16
            )
          }
        }
        backdrop = off
      } else {
        backdrop = null
      }
    }

    const paint = (localMs: number, fromIdx: number) => {
      const ctx = canvas.getContext('2d')
      if (!ctx || nodes.length < 2) return
      const cssW = wrap.clientWidth
      const cssH = wrap.clientHeight
      ctx.clearRect(0, 0, cssW, cssH)

      // 第 0 层：底格
      if (backdrop) ctx.drawImage(backdrop, 0, 0, cssW, cssH)

      const from = nodes[fromIdx]
      const to = nodes[(fromIdx + 1) % nodes.length]
      const base = cell * 0.86
      /** 变形进度，停留期为负 */
      const morphT = localMs - HOLD_MS

      /*
        第 3 层（扫光）只发生在停留期的后半段。它扫的是**已落位**的形状，
        所以要单独算一个进度，不能复用下面的 l。
      */
      let sweepFront = Number.POSITIVE_INFINITY
      const sweepP =
        morphT < 0 ? (localMs / HOLD_MS - SWEEP_START) / (1 - SWEEP_START) : -1
      if (sweepP >= 0 && sweepP <= 1) {
        sweepFront = (-1.5 + sweepP * (GRID_W + GRID_H * 0.6 + 3)) / 1
      }
      const SWEEP_HALF = 2.2

      for (let i = 0; i < from.cells.length; i += 1) {
        const a = from.cells[i]
        const b = to.cells[i]

        /*
          第 1 层：出发时刻按拍量化。
          order 是 0~1 的斜向排名，四舍五入到 0~(SLOTS-1) 个批次 → 每拍放一批。
          slot 相同的一批同时出发，于是能看出"一格一格在推进"。
        */
        const slot = Math.round(to.order[i] * (SLOTS - 1)) * PIXEL_BEAT_MS
        const l = clamp01((morphT - slot) / TRAVEL_MS)

        const eased = easeInOut(l)
        const ax = b.x - a.x
        const ay = b.y - a.y
        const len = Math.hypot(ax, ay) || 1
        // 相邻方块幅度不同，整体不像一块板子在平移
        const bulge = ((i * 37) % 11) - 5
        // 弧线偏移：只在飞行途中出现，起止两端都归零
        const arc = Math.sin(Math.PI * l) * bulge * 0.16

        const posX = a.x + ax * eased + (-ay / len) * arc
        const posY = a.y + ay * eased + (ax / len) * arc

        const alpha =
          (a.ghost ? 0 : 1) + ((b.ghost ? 0 : 1) - (a.ghost ? 0 : 1)) * eased
        if (alpha <= 0.01) continue

        // 颜色在**这个方块自己**走完一半时换，而不是全局进度过半时换 ——
        // 方块是分批落位的，用全局进度会出现"还没动就换了颜色"
        const kind = l < 0.5 ? a.kind : b.kind

        // 落位感：飞行中缩一点（像被抬起来），临落地时鼓一下再收回去
        const dip = Math.sin(Math.PI * l) * 0.3
        const pop = l > 0.78 ? Math.sin((Math.PI * (l - 0.78)) / 0.22) * 0.12 : 0
        // 停留期（l === 0）没有飞行，视为已经稳稳落位
        const landed = morphT < 0 ? 1 : clamp01((l - 0.72) / 0.28)

        // 扫光对当前位置的影响：提亮 + 微微鼓起
        let glow = 0
        if (sweepFront !== Number.POSITIVE_INFINITY && !a.ghost) {
          const d = Math.abs(a.x + a.y * 0.6 - sweepFront)
          if (d < SWEEP_HALF) glow = 1 - d / SWEEP_HALF
        }

        const size = base * (1 - dip + pop + glow * 0.09)
        const px = originX + posX * cell + (cell - size) / 2
        const py = originY + posY * cell + (cell - size) / 2

        // 第 1 层：拖尾。只在真正飞行时出现（l 在 0~1 之间）
        if (l > 0.04 && l < 1) {
          const lt = Math.max(0, l - 0.22)
          const et = easeInOut(lt)
          const tx = a.x + ax * et + (-ay / len) * Math.sin(Math.PI * lt) * bulge * 0.16
          const ty = a.y + ay * et + (ax / len) * Math.sin(Math.PI * lt) * bulge * 0.16
          const tSize = size * 0.62
          fillCell(
            ctx,
            originX + tx * cell + (cell - tSize) / 2,
            originY + ty * cell + (cell - tSize) / 2,
            tSize,
            palette[kind],
            alpha * 0.2 * (1 - l)
          )
        }

        // 第 2 层前段：光晕。落位之后才出现，所以它跟着 landed 淡入
        if (landed > 0.01 && (kind === 'brand' || kind === 'done')) {
          const hs = size * 1.5
          fillCell(
            ctx,
            originX + posX * cell + (cell - hs) / 2,
            originY + posY * cell + (cell - hs) / 2,
            hs,
            palette[kind],
            alpha * landed * 0.14
          )
        }

        // 第 2 层：本体
        fillCell(ctx, px, py, size, palette[kind], alpha)

        // 第 3 层：扫光提亮。画在方块之上，所以是"被照亮"而不是"换了颜色"
        if (glow > 0.01) {
          fillCell(ctx, px, py, size, SWEEP_COLOR, glow * 0.42 * alpha)
        }
      }

      ctx.globalAlpha = 1
    }

    const frame = (now: number) => {
      raf = requestAnimationFrame(frame)
      if (!visible || !nodes.length) return
      const step = HOLD_MS + MORPH_MS
      const cycle = step * nodes.length
      const t = (now - startedAt) % cycle
      const idx = Math.floor(t / step)
      paint(t - idx * step, idx)
    }

    /** 静止时画"做完了"的那一帧，信息量最大。 */
    const paintStill = () => {
      paint(HOLD_MS - 1, Math.max(nodes.length - 2, 0))
    }

    const rebuild = () => {
      window.clearTimeout(pending)
      // 拖窗口时每帧重建太浪费，等停下来再算
      pending = window.setTimeout(() => {
        build()
        startedAt = performance.now()
        if (reduce.matches) paintStill()
      }, 160)
    }

    const onReduceChange = () => {
      if (reduce.matches) {
        cancelAnimationFrame(raf)
        raf = 0
        paintStill()
      } else if (!raf) {
        startedAt = performance.now()
        raf = requestAnimationFrame(frame)
      }
    }

    const resize = new ResizeObserver(rebuild)
    resize.observe(wrap)

    // 滚出视口就停：落地页很长，不能让人滚到下面时这里还在烧 CPU
    const stopVisibility = observeVisibility(wrap, (v) => {
      visible = v
    })

    // 主题切在 <html> 的 class 上，换主题要重取调色板（浅灰在深色底上看不见）
    const stopTheme = observeTheme(rebuild)

    build()
    if (reduce.matches) paintStill()
    else raf = requestAnimationFrame(frame)
    reduce.addEventListener('change', onReduceChange)

    return () => {
      cancelAnimationFrame(raf)
      window.clearTimeout(pending)
      resize.disconnect()
      stopVisibility()
      stopTheme()
      reduce.removeEventListener('change', onReduceChange)
    }
    // frames 是常量点阵，按引用比较即可
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [frames])

  return (
    <div
      ref={wrapRef}
      className={cn('relative w-full select-none pointer-events-none', className)}
      // 纯装饰：旁边文字已经把意思说清楚了，读屏不必再念一遍
      aria-hidden="true"
    >
      <canvas ref={canvasRef} className="h-full w-full" />
    </div>
  )
}
