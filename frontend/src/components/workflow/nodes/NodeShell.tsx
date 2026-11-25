import { useEffect, useState, type CSSProperties, type ReactNode } from 'react'
import { Handle, Position } from 'reactflow'

import { cn } from '../../../lib/utils'
import { PixelGlyphBox } from '../../pixel/PixelGlyph'
import { PIXEL_BEAT_MS } from '../../pixel/pixelKit'
import { useNodeMotion } from '../pixel/PixelMotion'

/**
 * 工作流节点的统一外壳。
 *
 * 设计取向来自 AgentFlow 2.0.2：**中性卡片 + 左侧细色条**。
 *
 * 旧版每个节点都是「整块彩色渐变背景 + 白色文字」，画布上七种节点全是
 * 高饱和色块，节点之间没有主次，看起来像一堆糖果。而节点类型色其实
 * **携带信息** —— 它是画布上唯一能快速区分节点种类的手段，砍掉就没法用。
 *
 * 所以折中：卡片回归中性，类型色降级成 4px 宽的色条。既守住「全站单一
 * 强调色」的克制，又不丢识别能力。
 *
 * 抽出这个组件是因为七个节点的结构完全同构，复制七遍意味着以后改一处
 * 样式要改七次。
 *
 * 像素动效（2.0.3）
 * ---------------
 * 这个外壳现在也是**编辑器操作反馈的落点**，四种操作各有一层动效，
 * 全部读 pixelKit 的那一拍（90ms）：
 *
 * | 操作       | 表现                                             |
 * |-----------|--------------------------------------------------|
 * | 从面板添加 | 4 帧的像素聚合：卡片逐级放大 + 8 个方块向心汇聚     |
 * | 选中       | 四条边走马灯的像素取景框 + 四角定位块              |
 * | 试运行中   | 顶部像素进度带跳格前进 + 外圈呼吸光晕              |
 * | 跑完       | 一道亮带扫过卡片 + 标题右侧盖一个像素勾/叉          |
 *
 * 动效**不承载信息**：跑完这件事同时由勾、光晕颜色、小地图颜色三处表达，
 * 动画只是让"它刚刚跑完了"这件事被看见。所以 prefers-reduced-motion 下
 * 全部静止也不丢任何东西（见 index.css 末尾那一组覆盖）。
 */

/** 连接点的统一样式。中性色 —— 连线本身不该抢眼。 */
const HANDLE_CLASS =
  '!w-2.5 !h-2.5 !bg-slate-300 dark:!bg-slate-600 !border-2 !border-white dark:!border-slate-900'

/**
 * 新节点周围向心汇聚的 8 个像素点。
 *
 * 位置贴着节点的外框（百分比，跟着节点尺寸走），位移方向朝外 —— 于是动画
 * 看起来是"从四周飞进来拼成这张卡片"。只放 8 个：再多就是一层噪点，
 * 而且这 8 个正好一条边三个，分布是匀的。
 */
const SPARKS = [
  { left: '0%', top: '0%', sx: '-12px', sy: '-12px' },
  { left: '50%', top: '0%', sx: '0px', sy: '-14px' },
  { left: '100%', top: '0%', sx: '12px', sy: '-12px' },
  { left: '0%', top: '50%', sx: '-14px', sy: '0px' },
  { left: '100%', top: '50%', sx: '14px', sy: '0px' },
  { left: '0%', top: '100%', sx: '-12px', sy: '12px' },
  { left: '50%', top: '100%', sx: '0px', sy: '14px' },
  { left: '100%', top: '100%', sx: '12px', sy: '12px' },
]

interface NodeShellProps {
  /** 节点 id。动画状态按 id 取，见 pixel/PixelMotion */
  id?: string
  selected?: boolean
  /** 类型色条的类名，如 `bg-blue-500`。画布上区分节点种类的唯一颜色。 */
  accent: string
  icon: ReactNode
  /** 卡片头部的类型名，如「LLM」 */
  typeLabel: string
  children: ReactNode
  /** 是否需要上方的入边连接点 */
  hasTarget?: boolean
  /** 是否需要下方的出边连接点 */
  hasSource?: boolean
}

export function NodeShell({
  id,
  selected,
  accent,
  icon,
  typeLabel,
  children,
  hasTarget = true,
  hasSource = true,
}: NodeShellProps) {
  const { fresh, run } = useNodeMotion(id)

  /*
    扫光只在状态**刚变**的那一下播一次。

    不能把动画类直接挂在 run 上：类一直在，CSS 动画只播一次就再也不会重来，
    第二次试运行就没有反馈了。所以用一个短暂存活的布尔把它"重新点一次"。
    540ms 是 px-scan 的时长，取 6 拍（540ms）刚好接得住。
  */
  const [flash, setFlash] = useState(false)
  useEffect(() => {
    if (run !== 'success' && run !== 'failed') return
    setFlash(true)
    const timer = window.setTimeout(() => setFlash(false), PIXEL_BEAT_MS * 6)
    return () => window.clearTimeout(timer)
  }, [run])

  return (
    /*
      多包一层的原因：下面那些动效叠层有画到卡片**外面**的（取景框、光晕、
      汇聚的像素点），而卡片本身是 overflow-hidden 的（圆角要裁）。所以
      拆成两层 —— 外层定位、不裁剪；内层还是原来那张卡片。

      这一层是普通 block，宽高跟着内层走；ReactFlow 量到的节点尺寸不变。
    */
    <div className={cn('relative', fresh && 'px-enter')}>
      <div
        className={`relative flex rounded-xl overflow-hidden min-w-[180px] bg-white dark:bg-slate-900 border transition-colors ${
          selected
            ? 'border-indigo-500'
            : 'border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700'
        }`}
      >
        <span className={`w-1 shrink-0 ${accent}`} />

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 px-3 py-2 border-b border-slate-100 dark:border-slate-800">
            <span className="text-slate-400 shrink-0">{icon}</span>
            <span className="text-[13px] font-medium text-slate-700 dark:text-slate-200">
              {typeLabel}
            </span>
            {run === 'success' && (
              <PixelGlyphBox
                name="check"
                cell={2}
                className="ml-auto text-emerald-500"
                label="执行成功"
              />
            )}
            {run === 'failed' && (
              <PixelGlyphBox
                name="cross"
                cell={2}
                className="ml-auto text-red-500"
                label="执行失败"
              />
            )}
          </div>

          <div className="px-3 py-2.5">{children}</div>
        </div>

        {hasTarget && (
          <Handle
            type="target"
            position={Position.Top}
            className={`${HANDLE_CLASS} !top-[-5px]`}
          />
        )}
        {hasSource && (
          <Handle
            type="source"
            position={Position.Bottom}
            className={`${HANDLE_CLASS} !bottom-[-5px]`}
          />
        )}

        {/* 卡内层：会被圆角裁掉，所以放这里面 */}
        {run === 'running' && <span className="px-run-strip" />}
        {flash && run === 'success' && <span className="px-scan" />}
        {flash && run === 'failed' && <span className="px-scan px-scan--failed" />}
      </div>

      {/* 卡外层：要画到卡片边界以外，不能被 overflow-hidden 裁 */}
      {selected && <span className="px-frame" />}
      {run !== 'idle' && (
        <span className={cn('px-halo', `px-halo--${run}`)} />
      )}
      {fresh && (
        <span className="px-sparks">
          {SPARKS.map((s, i) => (
            <i
              key={i}
              className="px-spark"
              style={
                {
                  left: s.left,
                  top: s.top,
                  '--sx': s.sx,
                  '--sy': s.sy,
                } as CSSProperties
              }
            />
          ))}
        </span>
      )}
    </div>
  )
}

/** 节点正文里的标题行。 */
export function NodeTitle({ children }: { children: ReactNode }) {
  return (
    <div className="text-[13px] font-medium text-slate-900 dark:text-slate-100 truncate">
      {children}
    </div>
  )
}

/** 节点正文里的次要说明行。 */
export function NodeMeta({ children }: { children: ReactNode }) {
  return (
    <div className="text-xs text-slate-500 dark:text-slate-400 mt-0.5 truncate">
      {children}
    </div>
  )
}

/**
 * 状态小标签。
 *
 * 旧版每个节点用自己的类型色做底（`bg-pink-50 text-pink-600` 之类），
 * 等于把类型色又用了一遍，卡片上出现第三处彩色。现在统一走中性底，
 * 强调色在节点上只保留色条那一处。
 */
export function NodeBadge({ children }: { children: ReactNode }) {
  return (
    <span className="mt-2 inline-block text-2xs px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400">
      {children}
    </span>
  )
}
