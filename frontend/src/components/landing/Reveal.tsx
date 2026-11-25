import { useEffect, useRef, useState } from 'react'

import { cn } from '../../lib/utils'

/**
 * 滚动进场容器。元素进入视口时淡入并轻微上移。
 *
 * 这个组件的第一原则是：**内容能不能看见，不能由动画来决定。**
 *
 * 所以默认状态是「已显示」，只有在**确认浏览器支持 IntersectionObserver**
 * 时才会先挂上透明态。这样即使脚本报错、被 CSP 拦掉、或者观察器压根没回调，
 * 页面依然是完整的 —— 而不是留下一片空白。
 *
 * 另外还有一道保险丝：挂载 5 秒后无条件显示。哪怕观察器出了任何意料之外的
 * 问题，最坏情况也只是「动画没播」，而不是「内容不见了」。
 *
 * `rootMargin` 取正的下边距，让触发点落在视口下方 12% 处：等元素真的进入
 * 视口才触发的话，用户会先看到内容停在那儿、再突然淡入，反而像卡了一下。
 */

const SUPPORTED = typeof IntersectionObserver !== 'undefined'

/** 保险丝。宁可动画不播，也不能把内容扣住。 */
const FUSE_MS = 5000

interface RevealProps {
  children: React.ReactNode
  /** 同组内第几个，用来错开时间。单位毫秒。 */
  delay?: number
  className?: string
  /**
   * 让直接子元素依次进场，而不是整块一起淡入。
   *
   * 用在卡片网格上：这个组件会**变成**网格容器本身（className 直接透传），
   * 所以用法是 `<Reveal stagger className="grid ...">`，不需要多包一层 ——
   * 多包一层会把网格的子元素关系打断，网格布局就没了。
   */
  stagger?: boolean
}

export function Reveal({ children, delay = 0, className, stagger }: RevealProps) {
  const ref = useRef<HTMLDivElement>(null)
  const [shown, setShown] = useState(!SUPPORTED)

  useEffect(() => {
    if (shown) return
    const el = ref.current
    if (!el) return

    let fuse = window.setTimeout(() => setShown(true), FUSE_MS)

    const io = new IntersectionObserver(
      ([entry]) => {
        /*
          观察器**一定会先回调一次**（告知当前是否相交），所以拿到这次回调
          就说明它是好的 —— 保险丝可以撤了。

          这一步很关键：如果保险丝一直挂着，5 秒后它会把所有区块一次性
          显示掉，进场动画就只剩开头那几屏有效。撤掉之后，正常的滚动路径
          永远有效，而保险丝只在「观察器压根没回调」这种异常里兜底。
        */
        window.clearTimeout(fuse)
        if (entry.isIntersecting) {
          setShown(true)
          io.disconnect()
        }
      },
      { rootMargin: '0px 0px 12% 0px', threshold: 0 }
    )
    io.observe(el)

    return () => {
      io.disconnect()
      window.clearTimeout(fuse)
    }
  }, [shown])

  const state = stagger
    ? shown
      ? 'reveal-stagger-in'
      : 'reveal-stagger-out'
    : shown
      ? 'reveal-in'
      : 'reveal-out'

  return (
    <div
      ref={ref}
      className={cn(state, className)}
      // stagger 模式下延迟由 CSS 的 nth-child 决定，这里的 delay 不参与，
      // 否则会和子元素的错开叠加成两段延迟
      style={shown && !stagger ? { animationDelay: `${delay}ms` } : undefined}
    >
      {children}
    </div>
  )
}
