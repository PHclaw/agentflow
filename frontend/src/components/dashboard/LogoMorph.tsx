import { useEffect, useRef } from 'react'

import { cn } from '../../lib/utils'

/**
 * 「agentflow」字标 ⇄ AF 标识 的粒子变形动画。
 *
 * 做法：把字标和标识分别渲染到离屏画布，**按像素采样**成一堆点，然后让
 * 每个点从字标上的位置飞到标识上的位置（再飞回来），循环。
 *
 * 为什么用采样而不是手摆坐标：
 * - 手摆的点拼不出字形，笔画一密就散；采样得到的是真实的墨迹分布
 * - 标识以后改了（换笔画、调焊盘位置），这里不用跟着改 —— 它读的是
 *   绘制指令的输出，不是硬编码的点表
 * - 粒子自带颜色（从像素里读出来的），所以变形过程中藏青/青蓝的分布
 *   和真标识一致，不是半途改成单色
 *
 * 性能上的取舍：
 * - 点数是按「墨迹面积 ÷ 目标点数」反推步长采出来的，固定在一千以内；
 *   再多看不出差别，只是每帧白烧 CPU
 * - 每帧的循环里只有加减乘和一个 fillRect，垂直方向的偏移量在构建时
 *   就算好了 —— 帧内不做开方、不做字符串拼接
 * - 按颜色分两批画，每帧只改两次 fillStyle
 * - 离屏时用 IntersectionObserver 停掉，切到后台时浏览器本来就会暂停 rAF
 * - `prefers-reduced-motion` 下只画一帧静态的标识，不启动循环
 */

const NAVY = '#091B4D'
const CYAN = '#00BFEF'
const NAVY_DARK = '#E7EBF5'
const CYAN_DARK = '#38C9F5'

/** 目标点数。字形在 46px 上下时，约一千个点足够看清笔画。 */
const TARGET_DOTS = 900

/** 时间轴（毫秒）：停 → 变形 → 停 → 变回。 */
const HOLD_TEXT = 1500
const MORPH = 950
const HOLD_LOGO = 1700
const CYCLE = HOLD_TEXT + MORPH + HOLD_LOGO + MORPH

const easeInOut = (p: number) =>
  p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2

interface Ink {
  x: number
  y: number
  /** 是否是青蓝那一路（用来分桶，避免逐点改 fillStyle） */
  cyan: boolean
}

/**
 * 把一段绘制指令渲染到离屏画布，再按像素采点。
 *
 * 全程在 CSS 坐标里画（内部 setTransform 处理缩放），所以返回的点也是
 * CSS 坐标，主画布直接就能用。1 号参数之外的换算都封在这里，调用方
 * 不需要知道 dpr。
 */
function sampleInk(
  cssW: number,
  cssH: number,
  dpr: number,
  draw: (c: CanvasRenderingContext2D) => void,
  target: number,
  navy: string,
  cyan: string
): Ink[] {
  const w = Math.round(cssW * dpr)
  const h = Math.round(cssH * dpr)
  if (w < 8 || h < 8) return []

  const cv = document.createElement('canvas')
  cv.width = w
  cv.height = h
  const c = cv.getContext('2d', { willReadFrequently: true })
  if (!c) return []

  c.setTransform(dpr, 0, 0, dpr, 0, 0)
  draw(c)

  const img = c.getImageData(0, 0, w, h).data

  // 先数「有墨」的像素总数，再按面积反推步长。固定步长在小字形上会采出
  // 一大坨点、在大字形上又太稀，反推出来的步长才两头都合适。
  let ink = 0
  for (let i = 3; i < img.length; i += 4) {
    if (img[i] > 170) ink += 1
  }
  if (!ink) return []

  const step = Math.max(2, Math.sqrt(ink / target))
  const half = step / 2

  const navyRgb = hexToRgb(navy)
  const cyanRgb = hexToRgb(cyan)
  const dots: Ink[] = []

  for (let y = half; y < h; y += step) {
    for (let x = half; x < w; x += step) {
      const i = ((y | 0) * w + (x | 0)) * 4
      if (img[i + 3] <= 170) continue
      // 抗锯齿边上的像素是混色，按到两端的距离归到最近的一路，
      // 不然每个点一个色值，逐点 fillStyle 会把每帧的开销抬上去
      const toNavy =
        Math.abs(img[i] - navyRgb[0]) + Math.abs(img[i + 1] - navyRgb[1]) +
        Math.abs(img[i + 2] - navyRgb[2])
      const toCyan =
        Math.abs(img[i] - cyanRgb[0]) + Math.abs(img[i + 1] - cyanRgb[1]) +
        Math.abs(img[i + 2] - cyanRgb[2])
      dots.push({ x: x / dpr, y: y / dpr, cyan: toCyan < toNavy })
    }
  }
  return dots
}

function hexToRgb(hex: string): [number, number, number] {
  const v = parseInt(hex.slice(1), 16)
  return [(v >> 16) & 255, (v >> 8) & 255, v & 255]
}

function centroidOf(dots: Ink[]) {
  let sx = 0
  let sy = 0
  for (const d of dots) {
    sx += d.x
    sy += d.y
  }
  return { x: sx / dots.length, y: sy / dots.length }
}

/**
 * 两批点按「相对各自中心的方位角」排序后一一配对。
 *
 * 不排序（按扫描顺序配）会让左下角的点飞向右上角，整片互相穿插，看着像
 * 一团乱麻；按方位角配对之后，整体是绕圈收拢/张开的，变形过程有方向感。
 */
function sortByAngle(dots: Ink[]): Ink[] {
  const c = centroidOf(dots)
  return [...dots].sort(
    (a, b) => Math.atan2(a.y - c.y, a.x - c.x) - Math.atan2(b.y - c.y, b.x - c.x)
  )
}

interface Particle {
  fx: number
  fy: number
  tx: number
  ty: number
  /** 垂直方向的单位偏移，让粒子走弧线而不是直线 */
  nx: number
  ny: number
  /** 弧线的幅度（像素），按序号确定，保证每次构建都一样 */
  bulge: number
  fromCyan: boolean
  toCyan: boolean
}

export function LogoMorph({ className }: { className?: string }) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const wrap = wrapRef.current
    const canvas = canvasRef.current
    if (!wrap || !canvas) return

    let raf = 0
    let particles: Particle[] = []
    let fromDots: Ink[] = []
    let toDots: Ink[] = []
    let startedAt = performance.now()
    let visible = true
    let pending = 0
    let navy = NAVY
    let cyan = CYAN

    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)')

    /** 画一遍标识（粒子收敛后的形态）。reduce 模式下也直接拿它出静态图。 */
    const drawMark = (c: CanvasRenderingContext2D, cssW: number, cssH: number) => {
      // 标识本身是 68×50 的 viewBox，等比缩放到画布中央
      const s = Math.min((cssH * 0.66) / 50, (cssW * 0.44) / 68)
      c.save()
      c.translate((cssW - 68 * s) / 2, (cssH - 50 * s) / 2)
      c.scale(s, s)
      c.lineCap = 'round'

      /* 焊盘几何照抄 Logo.tsx：走线要停在 r=4.6 + 半描边之外，
         否则圆头线帽会戳进空心环里。 */
      const PAD_REACH = 5.8

      c.lineWidth = 5.5
      c.strokeStyle = navy
      c.stroke(new Path2D('M30 3 L11.9 35.9'))
      c.stroke(new Path2D('M30 3 L40 16'))
      c.lineWidth = 3.2
      c.beginPath()
      c.arc(9, 41, 4.6, 0, Math.PI * 2)
      c.stroke()

      c.lineWidth = 5.5
      c.strokeStyle = cyan
      c.stroke(new Path2D(`M35 24 L35 ${41 - PAD_REACH}`))
      c.stroke(new Path2D(`M35 24 L${58 - PAD_REACH} 24`))
      c.lineWidth = 3.2
      c.beginPath()
      c.arc(35, 41, 4.6, 0, Math.PI * 2)
      c.stroke()
      c.beginPath()
      c.arc(58, 24, 4.6, 0, Math.PI * 2)
      c.stroke()
      c.lineWidth = 5.5
      c.stroke(new Path2D('M35 32.5 L50 32.5'))
      c.restore()
    }

    const build = () => {
      const cssW = wrap.clientWidth
      const cssH = wrap.clientHeight
      if (cssW < 60 || cssH < 40) return

      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      canvas.width = Math.round(cssW * dpr)
      canvas.height = Math.round(cssH * dpr)
      const ctx = canvas.getContext('2d')
      if (!ctx) return
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)

      const dark = document.documentElement.classList.contains('dark')
      navy = dark ? NAVY_DARK : NAVY
      cyan = dark ? CYAN_DARK : CYAN

      // 字体跟随应用，不要写死一个栈 —— 否则这块和旁边文字不是一个气质
      const family = getComputedStyle(document.body).fontFamily || 'sans-serif'
      const probe = document.createElement('canvas').getContext('2d')
      if (!probe) return
      probe.font = `600 100px ${family}`
      const widthAt100 = probe.measureText('agentflow').width || 520
      // 字标占画布宽度的 78%；同时不许高过画布的一半，窄框里才不会顶出去
      const fontSize = Math.min((cssW * 0.78 * 100) / widthAt100, cssH * 0.5)

      const drawWord = (c: CanvasRenderingContext2D) => {
        c.font = `600 ${fontSize}px ${family}`
        c.textBaseline = 'middle'
        const wa = c.measureText('agent').width
        const wb = c.measureText('flow').width
        const left = (cssW - (wa + wb)) / 2
        c.fillStyle = navy
        c.fillText('agent', left, cssH / 2)
        c.fillStyle = cyan
        c.fillText('flow', left + wa, cssH / 2)
      }

      const word = sampleInk(cssW, cssH, dpr, drawWord, TARGET_DOTS, navy, cyan)
      const mark = sampleInk(cssW, cssH, dpr, (c) => drawMark(c, cssW, cssH),
                             TARGET_DOTS, navy, cyan)
      if (!word.length || !mark.length) return

      const sortedWord = sortByAngle(word)
      const sortedMark = sortByAngle(mark)
      const n = Math.min(sortedWord.length, sortedMark.length)

      // 两边点数一般不等：多出来的点按等距抽掉，分布仍然是均匀的
      const pick = (arr: Ink[], count: number) => {
        if (arr.length === count) return arr
        const stride = arr.length / count
        return Array.from({ length: count }, (_, i) => arr[Math.floor(i * stride)])
      }
      fromDots = pick(sortedWord, n)
      toDots = pick(sortedMark, n)

      particles = fromDots.map((f, i) => {
        const t = toDots[i]
        const dx = t.x - f.x
        const dy = t.y - f.y
        const len = Math.hypot(dx, dy) || 1
        return {
          fx: f.x,
          fy: f.y,
          tx: t.x,
          ty: t.y,
          nx: -dy / len,
          ny: dx / len,
          // 幅度带上序号，相邻粒子别同步摆 —— 同步就成了一块板子在平移
          bulge: ((i * 37) % 13) - 6,
          fromCyan: f.cyan,
          toCyan: t.cyan,
        }
      })
    }

    const paint = (ctx: CanvasRenderingContext2D, cssW: number, cssH: number, e: number) => {
      ctx.clearRect(0, 0, cssW, cssH)
      const phase = Math.sin(Math.PI * e)
      // 两批：每帧只改两次 fillStyle，比逐点设置省一个量级
      for (const wantCyan of [false, true]) {
        ctx.fillStyle = wantCyan ? cyan : navy
        for (const p of particles) {
          if ((e < 0.5 ? p.fromCyan : p.toCyan) !== wantCyan) continue
          const x = p.fx + (p.tx - p.fx) * e + p.nx * p.bulge * phase
          const y = p.fy + (p.ty - p.fy) * e + p.ny * p.bulge * phase
          ctx.fillRect(x - 1, y - 1, 2, 2)
        }
      }
    }

    const frame = (now: number) => {
      raf = requestAnimationFrame(frame)
      if (!visible || !particles.length) return
      const ctx = canvas.getContext('2d')
      if (!ctx) return
      const cssW = wrap.clientWidth
      const cssH = wrap.clientHeight

      const t = (now - startedAt) % CYCLE
      let p: number
      if (t < HOLD_TEXT) p = 0
      else if (t < HOLD_TEXT + MORPH) p = (t - HOLD_TEXT) / MORPH
      else if (t < HOLD_TEXT + MORPH + HOLD_LOGO) p = 1
      else p = 1 - (t - HOLD_TEXT - MORPH - HOLD_LOGO) / MORPH

      paint(ctx, cssW, cssH, easeInOut(Math.min(Math.max(p, 0), 1)))
    }

    /** 静态一帧（reduce 模式）。 */
    const paintStatic = () => {
      const ctx = canvas.getContext('2d')
      if (!ctx) return
      const cssW = wrap.clientWidth
      const cssH = wrap.clientHeight
      if (cssW < 60 || cssH < 40) return
      ctx.clearRect(0, 0, cssW, cssH)
      if (particles.length) {
        paint(ctx, cssW, cssH, 1)
      } else {
        drawMark(ctx, cssW, cssH)
      }
    }

    const rebuild = () => {
      window.clearTimeout(pending)
      // 拖窗口时每帧都重建太浪费（要重采样两张画布），等停下来再算
      pending = window.setTimeout(() => {
        build()
        startedAt = performance.now()
        if (reduce.matches) paintStatic()
      }, 180)
    }

    const onReduceChange = () => {
      if (reduce.matches) {
        cancelAnimationFrame(raf)
        raf = 0
        paintStatic()
      } else if (!raf) {
        startedAt = performance.now()
        raf = requestAnimationFrame(frame)
      }
    }

    const resize = new ResizeObserver(rebuild)
    resize.observe(wrap)

    const io = new IntersectionObserver(
      ([entry]) => {
        visible = entry.isIntersecting
      },
      { threshold: 0 }
    )
    io.observe(wrap)

    // 主题是切在 <html> 的 class 上，换主题要重新采样（深色底上藏青看不见）
    const theme = new MutationObserver(() => rebuild())
    theme.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['class'],
    })

    build()
    if (reduce.matches) paintStatic()
    else raf = requestAnimationFrame(frame)
    reduce.addEventListener('change', onReduceChange)

    return () => {
      cancelAnimationFrame(raf)
      window.clearTimeout(pending)
      resize.disconnect()
      io.disconnect()
      theme.disconnect()
      reduce.removeEventListener('change', onReduceChange)
    }
  }, [])

  return (
    <div
      ref={wrapRef}
      // 宽扁的框：字标本身是横向的，方框会把字号压得看不清
      className={cn(
        'relative mx-auto aspect-[2/1] w-full max-w-[340px] pointer-events-none select-none',
        className
      )}
      // 纯装饰：名字在旁边的文字里已经有了，读屏不必再念一遍
      aria-hidden="true"
    >
      <canvas ref={canvasRef} className="h-full w-full" />
    </div>
  )
}
