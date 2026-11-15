import { BaseEdge, getBezierPath, type EdgeProps } from 'reactflow'

import { useEdgeMotion } from './PixelMotion'

/**
 * 会走像素方块的连线。
 *
 * 在 ReactFlow 默认的那条细线之上，再叠一条虚线路径。虚线的每一段都是
 * 5×5 的方块（`stroke-width: 5` + `stroke-dasharray: 5 7`，方头笔帽），
 * 通过动画 `stroke-dashoffset` 让它一格一格往前跳 —— 看起来就是数据
 * 正沿着连线往下一站走。
 *
 * 为什么用 stroke-dashoffset 而不是 offset-path
 * ------------------------------------------
 * `offset-path: path()` + `offset-distance` 是更直观的做法，但它作用在 SVG
 * 子元素上的支持仍然参差（Safari 一直没跟上）。dashoffset 是 SVG 1.1 就有的
 * 东西，任何浏览器都稳，而且天然就是"沿路径"—— 路径多弯它都贴着走。
 *
 * 状态怎么来
 * --------
 * 跟随起点节点。起点在跑 → 方块的流动快（像正在传输）；起点跑完 → 变绿、
 * 变慢（像已经落库，但还连着）；失败 → 变红、停住。默认待命时这一层
 * 完全透明，只在鼠标划过或被选中时露出来 —— 画布上几十条边全在跑会很吵，
 * 而且"在跑"这个信息也就不值钱了。
 */
export function PixelEdge({
  id,
  source,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  markerEnd,
  style,
}: EdgeProps) {
  const [path] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  })

  const status = useEdgeMotion(source)

  return (
    <>
      <BaseEdge id={id} path={path} markerEnd={markerEnd} style={style} />
      <path className="px-edge" data-px={status} d={path} />
    </>
  )
}
