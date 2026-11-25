/**
 * 像素动效的共用底座。
 *
 * 落地页的「智能体在做什么」点阵和编辑器里的操作反馈是两套完全不同的实现
 * （一个画在 canvas 上、一个走 CSS），但它们必须看起来是**同一种东西**，
 * 否则用户会感觉是两个人做的。统一靠三件事，都收在这个文件里：
 *
 * 1. **同一套颜色**。语义只有五种：ink（中性）/ brand（进行中）/ done（成功）/
 *    fail（失败）/ warn（提醒）。浅色与深色各定义一次，任何一处像素元素都从
 *    这里取色，不允许就地写十六进制。取值与 tailwind.config.js 里的
 *    indigo-600 / emerald-500 / red-500 / amber-500 完全一致 —— CSS 那边用
 *    Tailwind 类名、canvas 这边用这里的常量，两边指向同一个数。
 *
 * 2. **同一个节拍**。像素动画的"像素感"不来自方块形状，而来自**离散的推进**：
 *    每 90ms 跳一格，而不是平滑滑过去。CANVAS 端用 floor(t / beat) 量化时间，
 *    CSS 端用 `steps()` 量化，两边听起来是同一个鼓点。任何时长都写成
 *    `beat 的整数倍`，改这一个常量整站节奏一起变。
 *
 * 3. **同一套缓动**。方块起飞要有"抬起来"的过程，落位要有一点回弹 —— 两端
 *    用同两条曲线，才不会一处硬邦邦、一处软塌塌。
 */

/* -------------------------------------------------------------------------- */
/* 颜色                                                                        */
/* -------------------------------------------------------------------------- */

/** 像素元素的语义。用语义而不是颜色名，是为了让"进行中"这类含义只有一处定义。 */
export type PixelKind = 'ink' | 'brand' | 'done' | 'fail' | 'warn'

export type PixelPalette = Record<PixelKind, string>

/*
  与 tailwind.config.js 对齐：
    brand = indigo-600 #4f46e5 / dark indigo-400 #818cf8
    done  = emerald-500 #10b981 / dark emerald-400 #34d399
    fail  = red-500     #ef4444 / dark red-400     #f87171
    warn  = amber-500   #f59e0b / dark amber-400   #fbbf24
    ink   = slate-700   #334155 / dark slate-300   #cbd5e1
  深色不是简单提亮：饱和度要降一档，否则在深底上会"发光"，比浅色模式更刺眼。
*/
const LIGHT: PixelPalette = {
  ink: '#334155',
  brand: '#4f46e5',
  done: '#10b981',
  fail: '#ef4444',
  warn: '#f59e0b',
}

const DARK: PixelPalette = {
  ink: '#cbd5e1',
  brand: '#818cf8',
  done: '#34d399',
  fail: '#f87171',
  warn: '#fbbf24',
}

/** 全站主题开关挂在 `<html class="dark">` 上（tailwind darkMode: 'class'）。 */
export function isDarkTheme() {
  return (
    typeof document !== 'undefined' &&
    document.documentElement.classList.contains('dark')
  )
}

export function pixelPalette(dark = isDarkTheme()): PixelPalette {
  return dark ? DARK : LIGHT
}

/**
 * 监听主题切换，切换时回调。
 *
 * 只在 `<html>` 的 class 上观察：主题可能由 Header 的按钮、系统的
 * prefers-color-scheme、或某个 effect 改掉，来源不止一处，盯着 class 最省心。
 */
export function observeTheme(onChange: () => void) {
  if (typeof MutationObserver === 'undefined') return () => {}
  const mo = new MutationObserver(onChange)
  mo.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['class'],
  })
  return () => mo.disconnect()
}

/* -------------------------------------------------------------------------- */
/* 节拍与缓动                                                                  */
/* -------------------------------------------------------------------------- */

/**
 * 一拍 = 90ms。
 *
 * 90 而不是 100：100ms 正好是人类的"瞬间"阈值，听起来像在等；70 以下又太快，
 * 方块之间的先后次序分不出来，看起来像一团抖动的噪点。90ms 是既看得出"一格
 * 一格在走"、又不拖沓的位置。
 */
export const PIXEL_BEAT_MS = 90

/** 把毫秒折算成拍数，保证动画时长永远是整数拍。 */
export function beats(ms: number) {
  return Math.round(ms / PIXEL_BEAT_MS)
}

/** 量化到拍：canvas 端靠它把连续时间切成离散的格。 */
export function quantize(t: number, beatMs = PIXEL_BEAT_MS) {
  return Math.floor(t / beatMs) * beatMs
}

/** 三次缓动。变形的主干用它 —— 起止都慢，中段快。 */
export function easeInOut(p: number) {
  return p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2
}

/**
 * 落位回弹：冲过终点一点点再收回来。
 *
 * 幅度刻意压得很小（c1 = 1.28，标准 easeOutBack 是 1.70158）。像素方块本来就
 * 是硬的，回弹一大就像弹簧玩具，和"这是一块方块"的直觉打架。
 */
export function easeOutBack(p: number) {
  const c1 = 1.28
  const c3 = c1 + 1
  return 1 + c3 * Math.pow(p - 1, 3) + c1 * Math.pow(p - 1, 2)
}

export function clamp01(p: number) {
  return p < 0 ? 0 : p > 1 ? 1 : p
}

/**
 * 错峰：把一条 0→1 的进度按"排队序号"拆成有先后的多条。
 *
 * spread 是一整队走完全程需要多花的时间比例：spread = 0.55 表示第一个方块
 * 到 45% 进度时最后一个才开始动，整队走完时第一个已经停稳。
 * 不做错峰的话所有方块齐步走，看起来像一张纸被整体推过去，是"位移"不是"变形"。
 */
export function stagger(p: number, order: number, total: number, spread = 0.55) {
  if (total <= 1) return clamp01(p)
  const slot = order / (total - 1)
  const head = 1 / (1 + spread)
  return clamp01((p - slot * spread * head) / head)
}

/* -------------------------------------------------------------------------- */
/* 画布                                                                        */
/* -------------------------------------------------------------------------- */

/**
 * 取 2D 上下文并按 DPR 设定变换。返回 null 表示这块画布用不了。
 *
 * DPR 上限取 2：3 倍屏上像素方块本来就只有几个 CSS 像素宽，再高的分辨率
 * 换不来可见的清晰度，只是让每帧多填几倍的面积。
 */
export function prepareCanvas(
  canvas: HTMLCanvasElement,
  cssW: number,
  cssH: number
): CanvasRenderingContext2D | null {
  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  canvas.width = Math.max(1, Math.round(cssW * dpr))
  canvas.height = Math.max(1, Math.round(cssH * dpr))
  const ctx = canvas.getContext('2d')
  if (!ctx) return null
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  return ctx
}

/** 画一格。方块之间的缝隙靠 inset 留，是像素风"看得出格"的关键。 */
export function fillCell(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  size: number,
  color: string,
  alpha = 1
) {
  if (alpha <= 0.004) return
  ctx.globalAlpha = alpha
  ctx.fillStyle = color
  ctx.fillRect(x, y, size, size)
}

/**
 * 离屏停机：元素滚出视口就回调 false。
 *
 * 落地页很长、编辑器画布也可能被滚走，不能让人滚过去之后这里还在烧 CPU。
 * 返回取消函数。
 */
export function observeVisibility(
  el: Element,
  onChange: (visible: boolean) => void
) {
  if (typeof IntersectionObserver === 'undefined') {
    onChange(true)
    return () => {}
  }
  const io = new IntersectionObserver(
    ([entry]) => onChange(entry.isIntersecting),
    { threshold: 0 }
  )
  io.observe(el)
  return () => io.disconnect()
}

/** 是否要求减弱动效。所有动画组件都得先问这一句。 */
export function prefersReducedMotion() {
  return (
    typeof window !== 'undefined' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  )
}
