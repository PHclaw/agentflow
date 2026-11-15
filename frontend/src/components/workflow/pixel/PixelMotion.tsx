import { createContext, useContext, useMemo, type ReactNode } from 'react'

/**
 * 把「这个节点刚被加进来」「这个节点正在跑」两条信息送到节点外壳里。
 *
 * 为什么要走 context 而不是 props
 * -----------------------------
 * ReactFlow 的节点组件只收 `NodeProps`，多传一个字段就得改七个节点文件、
 * 而且 `data` 里塞 UI 状态会被 handleSave 一起序列化进数据库（刷新页面后
 * 一个新节点还会再播一次"出现"动画）。context 让外壳自己去取，
 * 节点文件一行都不用动。
 *
 * 为什么不是每个节点各订阅一份 state
 * ------------------------------
 * 试运行期间状态是一起推进的：一个节点完成、下一个开始。用一份 map 由页面
 * 统一下发，节点只做一次 `map[id]` 查表，没有 N 份订阅和 N 次 setState。
 */

export type RunStatus = 'idle' | 'running' | 'success' | 'failed'

/**
 * 只要求带一个 status。
 *
 * 页面上那份 NodeExecutionState 比这多得多（inputs / outputs / error /
 * executionTime），这里刻意只声明用得到的那一个字段 —— 页面就不用为了适配
 * 组件而把状态拆成两份，也不用在每次更新时重建一个只含 status 的 map。
 */
export interface NodeRunLike {
  status: RunStatus
}

interface PixelMotionValue {
  /** 刚从左侧面板添加、正在播放"像素聚合"的节点 id */
  fresh: ReadonlySet<string>
  /** 本轮试运行里每个节点的状态，key 是 node.id */
  run: Record<string, NodeRunLike>
}

const EMPTY_SET: ReadonlySet<string> = new Set()
const EMPTY_RUN: Record<string, NodeRunLike> = {}

/** 默认值故意是"什么都没有"：脱离 Provider 渲染时不该报错，只该没有动画。 */
const PixelMotionContext = createContext<PixelMotionValue>({
  fresh: EMPTY_SET,
  run: EMPTY_RUN,
})

export function PixelMotionProvider({
  fresh,
  run,
  children,
}: {
  fresh: ReadonlySet<string>
  run: Record<string, NodeRunLike>
  children: ReactNode
}) {
  // 每帧都新建对象会让 context 的消费者全部重渲染；只在真正变化时换引用
  const value = useMemo(() => ({ fresh, run }), [fresh, run])
  return (
    <PixelMotionContext.Provider value={value}>{children}</PixelMotionContext.Provider>
  )
}

/** 节点外壳用：一次拿到"是不是新加的"和"跑到哪一步了"。 */
export function useNodeMotion(id: string | undefined) {
  const { fresh, run } = useContext(PixelMotionContext)
  return {
    fresh: id ? fresh.has(id) : false,
    run: (id ? run[id]?.status : undefined) ?? ('idle' as RunStatus),
  }
}

/** 连线用：连线的状态跟随它的**起点**节点 —— 数据是从起点流出去的。 */
export function useEdgeMotion(source: string | undefined) {
  const { run } = useContext(PixelMotionContext)
  return (source ? run[source]?.status : undefined) ?? ('idle' as RunStatus)
}
