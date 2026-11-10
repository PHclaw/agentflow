import type { CSSProperties, ReactNode } from 'react'

import { cn } from '../../lib/utils'

/**
 * CSS 版的像素图形。
 *
 * 和落地页 canvas 点阵共用同一套写法：`#` 是实心、`.` 是空 —— 只是落地页
 * 那几张图有 22×13 那么大、还要逐帧变形，只能上 canvas；而编辑器里这些小
 * 标记（勾、叉、加号）**静止不变**，用 canvas 就得给每个节点挂一块画布，
 * 几十个节点就是几十个 WebGL/2D 上下文，代价完全不成比例。
 *
 * 所以这里换一条路：一个空元素 + 一串 `box-shadow`。
 * 每个 `#` 对应一条阴影 `x*cell y*cell 0 currentColor`，阴影就是一块方块大的
 * 实心色块，偏移到格坐标上 —— 不模糊、不插值、任意缩放下都是硬边。
 * 因为盒子本身透明，连 (0,0) 那一格也照样能显示出来。
 *
 * 颜色走 `currentColor`：外面写 `text-emerald-500`，整张图跟着变，
 * 深色模式交给 Tailwind 的 `dark:` 处理，这里不用管主题。
 */

/** 点阵图形：若干行等宽字符串，`#` 实心、`.` 空。 */
export type PixelPattern = string[]

export const PX_GLYPHS = {
  /** 勾。左上短臂 + 右上长臂，7×7。 */
  check: [
    '.......',
    '......#',
    '.....#.',
    '....#..',
    '#..#...',
    '###....',
    '.#.....',
  ],
  /** 叉，7×7。 */
  cross: [
    '#.....#',
    '##...##',
    '.##.##.',
    '..###..',
    '.##.##.',
    '##...##',
    '#.....#',
  ],
  /** 加号，7×7。空态卡片和「添加」类操作共用。 */
  plus: [
    '...#...',
    '...#...',
    '...#...',
    '#######',
    '...#...',
    '...#...',
    '...#...',
  ],
  /** 待命：一个 3×3 的空心点，表示"还没轮到"。 */
  idle: [
    '###',
    '#.#',
    '###',
  ],
} satisfies Record<string, PixelPattern>

export type PixelGlyphName = keyof typeof PX_GLYPHS

/**
 * 把点阵摊成 box-shadow 列表。
 *
 * 单独抽出来是因为它同时被两处用：组件渲染、以及需要把阴影写进 CSS 变量的
 * 场景（比如首帧还没 hydrate 时的占位）。
 */
export function patternToShadow(pattern: PixelPattern, cell: number) {
  const out: string[] = []
  for (let y = 0; y < pattern.length; y += 1) {
    const row = pattern[y]
    for (let x = 0; x < row.length; x += 1) {
      if (row[x] === '#') out.push(`${x * cell}px ${y * cell}px 0 0 currentColor`)
    }
  }
  return out.join(', ')
}

interface PixelGlyphProps {
  name: PixelGlyphName
  /** 一格多少 CSS 像素。**用整数**，小数会让方块落在半像素上、边缘发虚。 */
  cell?: number
  className?: string
  style?: CSSProperties
  /** 读屏用的说明。默认整块图形是纯装饰，不念。 */
  label?: string
}

export function PixelGlyph({
  name,
  cell = 3,
  className,
  style,
  label,
}: PixelGlyphProps) {
  const pattern = PX_GLYPHS[name]
  return (
    <span
      aria-hidden={label ? undefined : true}
      aria-label={label}
      role={label ? 'img' : undefined}
      className={cn('pointer-events-none block shrink-0', className)}
      style={{
        width: cell,
        height: cell,
        // 本体透明，颜色全部由阴影给出；这样 (0,0) 那格也不会丢
        background: 'transparent',
        boxShadow: patternToShadow(pattern, cell),
        ...style,
      }}
    />
  )
}

/**
 * 把图形包进一个固定尺寸的盒子里并对齐中心。
 *
 * 直接用 PixelGlyph 的话，元素只有 1 格那么大（3px），它在 flex 里几乎
 * 占不到位置，周围的文字会挤上来。这个外壳负责占位与居中，
 * 顺带把 `text-*` 的颜色透给图形。
 */
export function PixelGlyphBox({
  name,
  cell = 3,
  size,
  className,
  children,
}: PixelGlyphProps & { size?: number; children?: ReactNode }) {
  const pattern = PX_GLYPHS[name]
  const w = pattern[0].length * cell
  const h = pattern.length * cell
  return (
    <span
      className={cn('inline-flex items-center justify-center shrink-0', className)}
      style={{ width: size ?? w, height: size ?? h }}
    >
      <PixelGlyph name={name} cell={cell} />
      {children}
    </span>
  )
}
