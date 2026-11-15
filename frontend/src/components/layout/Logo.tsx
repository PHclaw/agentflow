import React from 'react'
import { cn } from '../../lib/utils'

/**
 * 标识：电路板走线风格的「AF」单字标 + 小写字标。
 *
 * 两个色值直接取自原始设计稿，不是从主题色推的：
 *
 * - 藏青只出现在标识里。它足够暗（接近中性深灰），当成「深色中性」看待
 *   不违和。
 * - 青蓝只出现在标识里。**它和界面的靛蓝强调色（#4F46E5）是两个蓝**，
 *   放在一起能看出区别。这是有意的取舍：标识是品牌资产，改它的色会让
 *   「logo 要改成这张图」这件事失去意义。想统一的话把下面两个常量
 *   改成界面强调色即可，全站标识一处跟着变。
 */
const NAVY = '#091B4D'
const CYAN = '#00BFEF'

/** 深色底上把藏青提亮成近白 —— 否则深蓝画在深底上等于看不见。 */
const NAVY_ON_DARK = '#E7EBF5'
/** 深色底上青蓝也要提一档，否则 #00BFEF 在 #171717 上对比度不够。 */
const CYAN_ON_DARK = '#38C9F5'

interface LogoProps {
  size?: 'sm' | 'md' | 'lg'
  showText?: boolean
  className?: string
  /**
   * 字标配色跟随哪个主题：
   * - auto：跟随根元素的 dark 类（应用内使用，侧边栏等有完整深色主题）
   * - light：固定用深色配色（落地页顶栏永远是浅色底，即使根元素被切到
   *   dark 也不能换成浅色字，否则浅字压浅底看不见）
   */
  tone?: 'auto' | 'light'
}

const sizes = {
  // 这个标识的细节（三个焊盘空心环）比一般的几何图标多，尺寸给小了会糊成一团
  sm: { mark: 34, text: 'text-lg' },
  md: { mark: 40, text: 'text-xl' },
  lg: { mark: 50, text: 'text-2xl' },
}

/**
 * AF 单字标。
 *
 * 走线用 `stroke="currentColor"` + Tailwind 的文字色类，而不是写死 fill，
 * 这样深色模式只需要换颜色类，不必维护两份 SVG。
 *
 * 末端那几个「焊盘」画成空心圆（fill=none），中间透出背景 —— 这正好和
 * 原图一致，也避免了在不同底色上还要给圆心单独配一个填充色。
 */
function AFMark({ px, tone }: { px: number; tone: 'auto' | 'light' }) {
  const a = tone === 'light' ? 'text-[#091B4D]' : 'text-[#091B4D] dark:text-[#E7EBF5]'
  const b = tone === 'light' ? 'text-[#00BFEF]' : 'text-[#00BFEF] dark:text-[#38C9F5]'

  /* 焊盘几何：r=4.6 + 描边 3.2 → 外沿 6.2、内沿 3.0。
     **走线必须停在 6.2 之外**，否则 stroke 的圆头线帽会戳进环心，
     空心圆里就多出一小段弧，看着像画错了。 */
  const PAD_REACH = 5.8

  return (
    <svg
      viewBox="0 0 68 50"
      fill="none"
      width={px}
      height={Math.round((px * 50) / 68)}
      aria-hidden="true"
      className="shrink-0"
    >
      {/* A：折线两笔，一长一短；长脚末端带焊盘 */}
      <path
        d="M30 3 L11.9 35.9"
        stroke="currentColor"
        strokeWidth={5.5}
        strokeLinecap="round"
        className={a}
      />
      {/* 右腿刻意收短：再往下就会贴上 F 的顶横，两个色块糊在一起 */}
      <path
        d="M30 3 L40 16"
        stroke="currentColor"
        strokeWidth={5.5}
        strokeLinecap="round"
        className={a}
      />
      <circle cx="9" cy="41" r="4.6" stroke="currentColor" strokeWidth={3.2} className={a} />

      {/* F：竖笔 + 顶横（末端带焊盘）+ 中横 */}
      <path
        d={`M35 24 L35 ${41 - PAD_REACH}`}
        stroke="currentColor"
        strokeWidth={5.5}
        strokeLinecap="round"
        className={b}
      />
      <path
        d={`M35 24 L${58 - PAD_REACH} 24`}
        stroke="currentColor"
        strokeWidth={5.5}
        strokeLinecap="round"
        className={b}
      />
      <circle cx="35" cy="41" r="4.6" stroke="currentColor" strokeWidth={3.2} className={b} />
      <circle cx="58" cy="24" r="4.6" stroke="currentColor" strokeWidth={3.2} className={b} />
      <path
        d="M35 32.5 L50 32.5"
        stroke="currentColor"
        strokeWidth={5.5}
        strokeLinecap="round"
        className={b}
      />
    </svg>
  )
}

export function Logo({
  size = 'md',
  showText = true,
  className,
  tone = 'auto',
}: LogoProps) {
  const sizeConfig = sizes[size]

  return (
    <div className={cn('flex items-center gap-2.5', className)}>
      <AFMark px={sizeConfig.mark} tone={tone} />

      {showText && (
        /*
         * 字标分两段上色：「agent」藏青、「flow」青蓝，对应单字标的两色。
         * 旧版这里是「AgentFlow + 品牌色渐变」—— 渐变是上一套设计语言里
         * 「品牌色 = 一种颜色」的产物，现在标识本身就有双色，再叠渐变只会
         * 把两个色搅浑。
         */
        <span className={cn('font-semibold tracking-tight', sizeConfig.text)}>
          <span
            className={cn(
              tone === 'light' ? 'text-[#091B4D]' : 'text-[#091B4D] dark:text-[#E7EBF5]'
            )}
          >
            agent
          </span>
          <span
            className={cn(
              tone === 'light' ? 'text-[#00BFEF]' : 'text-[#00BFEF] dark:text-[#38C9F5]'
            )}
          >
            flow
          </span>
        </span>
      )}
    </div>
  )
}

/** 仅图标版本（折叠态侧边栏等）。 */
export function LogoSmall({
  className,
  tone = 'auto',
}: {
  className?: string
  tone?: 'auto' | 'light'
}) {
  return (
    <div className={cn('w-10 h-10 flex items-center justify-center', className)}>
      <AFMark px={34} tone={tone} />
    </div>
  )
}

/** 供别处复用同一套标识色（比如邮件页头的水印方块）。 */
export const LOGO_COLORS = { NAVY, CYAN }
