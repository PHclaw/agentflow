import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { Brain, Calculator, Check, Globe, Layers, Search } from 'lucide-react'

import { observeVisibility, prefersReducedMotion } from '../pixel/pixelKit'
import { Reveal } from './Reveal'

/**
 * 「知识库 · Agent · 工作流」—— 三件事怎么串起来。
 *
 * 为什么要有这一段
 * ---------------
 * 首屏讲的是「怎么搭」，「智能体在做什么」讲的是「搭出来的东西干什么」，
 * 到这一步还差最后一块：这三样东西是**一条链路**上的三个环节，不是三个
 * 并列的功能。访客容易把它们理解成「三个独立的模块，各买各的」，于是
 * 看不出产品的完整形状。所以这里不罗列功能，而是把一次请求从头走到尾。
 *
 * 三段各演各的，靠一条会流动的连线串起来
 * ------------------------------------
 * - 知识库：文档被切成格子 → 扫过 → 命中的几格留下来（它们就是回答的出处）
 * - Agent：思考脉冲 + 手里的工具依次点亮 → 给出决定
 * - 工作流：判断条件 → 只有一条分支被选中走通 → 落到完成
 *
 * 三段合起来才是「一个请求走的完整路径」。单独看任何一段都只是一句
 * 功能描述 —— 那不叫演示，叫列表。
 *
 * 一个 interval 驱动全部状态
 * ------------------------
 * 和 LiveDemo / CompareSection 同一套做法：只存「这一轮走了多久」，每个
 * 元素该不该亮由时间反推。好处是循环回到起点时所有状态自动归位，
 * 不用逐个清理 timeout —— 逐个 setTimeout 的老问题就是漏一个就留下
 * "上一轮的字还挂在屏幕上"。
 *
 * 滚出视口就停表。落地页很长，这一段的动画不该在用户看别的区块时空转；
 * 顺便还带来一个好处：滚回来时它是从第一段重新开始演的，而不是半途切进去。
 *
 * prefers-reduced-motion 直接把时钟钉在「三段都跑完」上：结论一样给全，
 * 只是不动。
 */

/** 每个阶段占用的时长。三段等长，节奏才好预期。 */
const STAGE_MS = 3000
/** 起步留白：页面先稳住，再开演 */
const LEAD_MS = 400

const S_KB = LEAD_MS
const S_AGENT = S_KB + STAGE_MS
const S_FLOW = S_AGENT + STAGE_MS
const S_DONE = S_FLOW + STAGE_MS
/** 一轮结束后停一拍，让人看清"三段都跑完了"，再从头来 */
const LOOP_MS = S_DONE + 2400

/* --- 知识库：切片与检索 ------------------------------------------------- */

const KB_COLS = 6
const KB_ROWS = 3
const KB_CELLS = Array.from({ length: KB_COLS * KB_ROWS }, (_, i) => i)
/** 命中的切片。刻意分散在三行：命中是"按内容挑出来的"，不是"取前几条"。 */
const KB_HITS = new Set([1, 8, 15])
/** 第一格亮起 / 每行错开 / 行内每格错开（毫秒，相对本阶段起点） */
const KB_FIRST = 200
const KB_ROW_GAP = 420
const KB_COL_GAP = 60
/** 没命中的格子亮一下就退回去 —— "扫过，但跟你问的没关系" */
const KB_COOL_MS = 700
/** 扫描线走完全程的时长 */
const KB_SCAN_MS = 1900
/** 结论文案出现的时间 */
const KB_NOTE_AT = 2200

/* --- Agent：手里的工具 -------------------------------------------------- */

const AG_TOOLS = [
  { icon: Search, label: '检索' },
  { icon: Globe, label: '查订单' },
  { icon: Calculator, label: '计算' },
]
const AG_FIRST = 200
const AG_GAP = 480
const AG_NOTE_AT = 2000

/* --- 工作流：判断与分支 ------------------------------------------------- */

/** 各元素点亮的时间（毫秒，相对本阶段起点）。顺序就是"跑一遍"的顺序。 */
const FX_START = 200
const FX_DIAMOND = 700
const FX_WIRE = 1200
const FX_NODE = 1700
const FX_END = 2200
const FLOW_NOTE_AT = 2500

type StageState = 'idle' | 'running' | 'done'
/** 图元在链路里的角色：被选中的那条路 / 被排除的那条 / 终点 */
type Role = 'chosen' | 'rejected' | 'ok'

export function PipelineSection() {
  const ref = useRef<HTMLElement>(null)
  const [t, setT] = useState(0)

  useEffect(() => {
    const el = ref.current
    if (!el) return

    // 降级：钉在"三段都跑完"，信息一样给全
    if (prefersReducedMotion()) {
      setT(S_DONE)
      return
    }

    let id = 0
    let startedAt = 0

    const stop = observeVisibility(el, (visible) => {
      if (visible) {
        if (id) return
        startedAt = Date.now()
        setT(0)
        id = window.setInterval(
          () => setT((Date.now() - startedAt) % LOOP_MS),
          100
        )
      } else if (id) {
        window.clearInterval(id)
        id = 0
      }
    })

    return () => {
      stop()
      if (id) window.clearInterval(id)
    }
  }, [])

  const stateOf = (from: number, to: number): StageState =>
    t < from ? 'idle' : t < to ? 'running' : 'done'

  /* 各阶段自己的内部时钟。减成负数时说明还没轮到它，下面的判断会自动
     全部落回"没亮" —— 不需要额外的 if 分支去挡。 */
  const kb = t - S_KB
  const ag = t - S_AGENT
  const fl = t - S_FLOW
  const running = t >= S_KB && t < S_DONE

  const kbScan = Math.max(0, Math.min(1, kb / KB_SCAN_MS)) * 100

  return (
    <section
      ref={ref}
      id="pipeline"
      className="relative overflow-hidden border-t border-slate-100 bg-white py-20 lg:py-28 dark:border-slate-800 dark:bg-slate-950"
    >
      <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <Reveal className="mx-auto max-w-2xl text-center">
          <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-500 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
            <Layers className="h-3.5 w-3.5" />
            知识库 · Agent · 工作流
          </div>
          <h2 className="mt-4 text-3xl font-black tracking-tight text-slate-900 dark:text-white sm:text-4xl">
            三件事，串成一条线
          </h2>
          <p className="mt-3 text-slate-600 dark:text-slate-400">
            文档留在你自己的知识库里，Agent 负责听问题、做判断，
            工作流把每一步编排成可执行、可回溯的流程。
          </p>
        </Reveal>

        {/* Reveal 直接当 flex 容器用（className 透传）：多包一层会把三个
            阶段和连接线之间的兄弟关系打断，横向对齐就没了 */}
        <Reveal stagger className="mt-12 flex flex-col lg:flex-row lg:items-stretch">
          {/* 1. 知识库 ------------------------------------------------ */}
          <StageCard
            index={1}
            title="知识库"
            desc="上传的文档被切成片段，提问时按内容检索出最相关的那几条。"
            state={stateOf(S_KB, S_AGENT)}
            doneLabel="已就绪"
          >
            <div className="mx-auto w-full max-w-[200px] rounded-xl border border-dashed border-slate-200 bg-white p-3 dark:border-slate-700 dark:bg-slate-950">
              <div className="relative">
                {/* 扫描线：top 用百分比、配 150ms 线性过渡 ——
                    状态机 100ms 一跳，直接落值会看出跳动 */}
                <span
                  aria-hidden="true"
                  className="pointer-events-none absolute inset-x-0 h-px bg-gradient-to-r from-transparent via-brand-500 to-transparent shadow-[0_0_10px_rgba(99,102,241,0.7)] transition-all duration-150 ease-linear"
                  style={{
                    top: `${kbScan}%`,
                    opacity: kb >= 0 && kb < KB_SCAN_MS ? 1 : 0,
                  }}
                />
                <div className="grid grid-cols-6 gap-1.5">
                  {KB_CELLS.map((i) => (
                    <span
                      key={i}
                      className={`h-5 rounded-sm transition-all duration-300 ${kbCellClass(i, kb)}`}
                    />
                  ))}
                </div>
              </div>
            </div>
            <Caption show={kb >= KB_NOTE_AT}>
              命中 3 条片段 · 回答有出处
            </Caption>
          </StageCard>

          <Connector running={running} />

          {/* 2. AI Agent ---------------------------------------------- */}
          <StageCard
            index={2}
            title="AI Agent"
            desc="看懂问题，决定这一步要不要查库、要不要调接口，还是直接答。"
            state={stateOf(S_AGENT, S_FLOW)}
            doneLabel="已决策"
          >
            <div className="flex flex-col items-center gap-3">
              <div className="relative grid h-14 w-14 place-items-center">
                {/* 脉冲环只在"正在想"的时候挂载：卸载即停，
                    不必再去管理 animation-play-state */}
                {stateOf(S_AGENT, S_FLOW) === 'running' && (
                  <>
                    {/* 时长和相位走内联样式，不写成 [animation-duration:2.4s]：
                        animate-ping 是个 animation 简写，长写覆盖它要靠层叠顺序
                        去赌，内联样式没有这个不确定性。 */}
                    <span
                      aria-hidden="true"
                      className="absolute inset-0 animate-ping rounded-2xl bg-brand-400/25"
                      style={{ animationDuration: '2.4s' }}
                    />
                    <span
                      aria-hidden="true"
                      className="absolute inset-0 animate-ping rounded-2xl bg-brand-400/20"
                      style={{ animationDuration: '2.4s', animationDelay: '1.2s' }}
                    />
                  </>
                )}
                <span
                  className={`relative grid h-14 w-14 place-items-center rounded-2xl bg-brand-500 text-white shadow-lg shadow-brand-500/25 transition-transform duration-500 ${
                    ag >= 0 ? 'scale-100' : 'scale-90'
                  }`}
                >
                  <Brain className="h-6 w-6" />
                </span>
              </div>

              <div className="flex items-center gap-1.5">
                {AG_TOOLS.map((tool, i) => {
                  const on = ag >= AG_FIRST + i * AG_GAP
                  return (
                    <span
                      key={tool.label}
                      className={`inline-flex items-center gap-1 rounded-lg border px-2 py-1 text-[11px] transition-all duration-300 ${
                        on
                          ? 'border-brand-200 bg-brand-50 text-brand-700 shadow-soft dark:border-brand-500/40 dark:bg-brand-500/10 dark:text-brand-300'
                          : 'border-slate-200 bg-white text-slate-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-500'
                      }`}
                    >
                      <tool.icon className="h-3 w-3" />
                      {tool.label}
                    </span>
                  )
                })}
              </div>
            </div>
            {/* 结论里点到的两步，和上面亮起来的两个芯片对得上 ——
                不然"它凭什么这么决定"就落不到具体的东西上 */}
            <Caption show={ag >= AG_NOTE_AT}>已决定：先检索，再查订单</Caption>
          </StageCard>

          <Connector running={running} />

          {/* 3. 工作流 ------------------------------------------------- */}
          <StageCard
            index={3}
            title="工作流"
            desc="把上面这些串成流程：条件分支、失败重试、需要人接手时转人工。"
            state={stateOf(S_FLOW, S_DONE)}
            doneLabel="已执行"
          >
            {/*
              分支用 SVG 画而不是 div 拼：两条支线的拐点、菱形、终点圆点
              都是"按坐标落在一条路径上"的，用 HTML 盒子去做对不齐，
              缩放一下更散。SVG 里一个 viewBox 就锁死了。

              字号是按**放大之后**的效果定的：viewBox 240×96 实际渲染成
              300×120，正好放大 1.25 倍，标签 10 号字落下来是 12.5px。
              所以 viewBox 要尽量"扁而宽" —— 高度一大，缩放系数就被它拖住，
              同一条路径上的字会一起变小。三个数字是一组，动一个要重算另外两个。
            */}
            <svg
              viewBox="0 0 240 96"
              className="mx-auto h-[120px] w-full max-w-[300px]"
              aria-hidden="true"
            >
              {/* 起点 → 判断 */}
              <circle
                cx="14"
                cy="48"
                r="5"
                strokeWidth="1.5"
                className={`transition-all duration-500 ${nodeStroke(
                  fl >= FX_START,
                  'chosen'
                )} ${nodeFill(fl >= FX_START, 'chosen')}`}
              />
              <line
                x1="19"
                y1="48"
                x2="44"
                y2="48"
                strokeWidth="2"
                className={`transition-all duration-500 ${wireClass(
                  fl >= FX_DIAMOND,
                  true
                )}`}
              />

              {/* 条件 */}
              <polygon
                points="44,48 68,26 92,48 68,70"
                strokeWidth="1.5"
                className={`transition-all duration-500 ${nodeStroke(
                  fl >= FX_DIAMOND,
                  'chosen'
                )} ${nodeFill(fl >= FX_DIAMOND, 'chosen')}`}
              />
              <text
                x="68"
                y="51"
                textAnchor="middle"
                fontSize="9"
                className={`transition-all duration-500 ${labelFill(
                  fl >= FX_DIAMOND,
                  'chosen'
                )}`}
              >
                条件
              </text>

              {/* 命中：走答复 */}
              <path
                d="M92 48 H112 V22 H140"
                strokeWidth="2"
                fill="none"
                className={`transition-all duration-500 ${wireClass(
                  fl >= FX_WIRE,
                  true
                )}`}
              />
              <rect
                x="140"
                y="12"
                width="76"
                height="20"
                rx="4"
                strokeWidth="1.5"
                className={`transition-all duration-500 ${nodeStroke(
                  fl >= FX_NODE,
                  'chosen'
                )} ${nodeFill(fl >= FX_NODE, 'chosen')}`}
              />
              <text
                x="178"
                y="25.5"
                textAnchor="middle"
                fontSize="10"
                className={`transition-all duration-500 ${labelFill(
                  fl >= FX_NODE,
                  'chosen'
                )}`}
              >
                答复用户
              </text>
              <line
                x1="216"
                y1="22"
                x2="228"
                y2="22"
                strokeWidth="2"
                className={`transition-all duration-500 ${wireClass(
                  fl >= FX_END,
                  true
                )}`}
              />
              <circle
                cx="234"
                cy="22"
                r="4.5"
                strokeWidth="1.5"
                className={`transition-all duration-500 ${nodeStroke(
                  fl >= FX_END,
                  'ok'
                )} ${nodeFill(fl >= FX_END, 'ok')}`}
              />

              {/* 未命中：落选的那条不要消失，要看得出来"存在但没走" */}
              <path
                d="M92 48 H112 V74 H140"
                strokeWidth="2"
                fill="none"
                strokeDasharray={fl >= FX_WIRE ? '3 4' : undefined}
                className={`transition-all duration-500 ${wireClass(
                  fl >= FX_WIRE,
                  false
                )}`}
              />
              <rect
                x="140"
                y="64"
                width="76"
                height="20"
                rx="4"
                strokeWidth="1.5"
                className={`transition-all duration-500 ${nodeStroke(
                  fl >= FX_NODE,
                  'rejected'
                )} ${nodeFill(fl >= FX_NODE, 'rejected')}`}
              />
              <text
                x="178"
                y="77.5"
                textAnchor="middle"
                fontSize="10"
                className={`transition-all duration-500 ${labelFill(
                  fl >= FX_NODE,
                  'rejected'
                )}`}
              >
                转人工
              </text>
            </svg>
            <Caption show={fl >= FLOW_NOTE_AT}>
              条件为真 → 答复；否则转人工
            </Caption>
          </StageCard>
        </Reveal>
      </div>
    </section>
  )
}

/* -------------------------------------------------------------------------- */
/* 分区内的零件                                                                */
/* -------------------------------------------------------------------------- */

interface StageCardProps {
  index: number
  title: string
  desc: string
  state: StageState
  /** 跑完之后的说法。三段的"完成"含义不同，统一写"已完成"反而含糊。 */
  doneLabel: string
  children: ReactNode
}

function StageCard({
  index,
  title,
  desc,
  state,
  doneLabel,
  children,
}: StageCardProps) {
  return (
    <div
      className={`relative flex flex-1 flex-col overflow-hidden rounded-2xl border bg-white transition-all duration-500 dark:bg-slate-900 ${
        state === 'running'
          ? 'border-brand-300 shadow-medium dark:border-brand-500/40'
          : 'border-slate-200 dark:border-slate-800'
      }`}
    >
      <div className="flex items-center justify-between gap-2 border-b border-slate-100 px-4 py-2.5 dark:border-slate-800">
        <div className="flex items-baseline gap-2">
          <span className="font-mono text-2xs text-slate-300 dark:text-slate-700">
            {String(index).padStart(2, '0')}
          </span>
          <h3 className="text-sm font-semibold text-slate-900 dark:text-white">
            {title}
          </h3>
        </div>
        <StatusPip state={state} doneLabel={doneLabel} />
      </div>

      {/* 视觉区给死高度：三段并排时高度必须一致，否则连接线会对着不同的
          垂直中心，整排看起来是斜的。

          这里**不能**挂 flex-1：卡片的父级是纵向 flex，而 flex-1 的
          flex-basis 是 0，等于把这块的主轴尺寸交给"剩余空间"去分 ——
          视觉区就不再是固定高度，三张卡会各长各的。多出来的空间让下面的
          说明文字吸收（它是 flex-1），视觉区就永远对得齐。 */}
      <div className="flex h-[158px] shrink-0 flex-col justify-center gap-2 border-b border-slate-100 bg-slate-50/60 px-4 dark:border-slate-800 dark:bg-slate-900/40">
        {children}
      </div>

      <p className="flex-1 px-4 py-3 text-2xs leading-relaxed text-slate-500 dark:text-slate-400">
        {desc}
      </p>
    </div>
  )
}

function StatusPip({
  state,
  doneLabel,
}: {
  state: StageState
  doneLabel: string
}) {
  if (state === 'running') {
    return (
      <span className="inline-flex shrink-0 items-center gap-1.5 text-2xs font-medium text-brand-600 dark:text-brand-400">
        <span className="relative flex h-1.5 w-1.5">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-brand-400 opacity-75" />
          <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-brand-500" />
        </span>
        进行中
      </span>
    )
  }

  if (state === 'done') {
    return (
      <span className="inline-flex shrink-0 items-center gap-1 text-2xs font-medium text-emerald-600 dark:text-emerald-400">
        <Check className="h-3 w-3" />
        {doneLabel}
      </span>
    )
  }

  return (
    <span className="inline-flex shrink-0 items-center gap-1.5 text-2xs text-slate-400 dark:text-slate-600">
      <span className="h-1.5 w-1.5 rounded-full bg-slate-300 dark:bg-slate-700" />
      等待
    </span>
  )
}

/** 结论文案。用透明度而不是条件挂载：留着占位，出现时不会把上面的图形顶动。 */
function Caption({ show, children }: { show: boolean; children: ReactNode }) {
  return (
    <p
      className={`text-center text-[11px] transition-all duration-500 ${
        show ? 'translate-y-0 opacity-100' : 'translate-y-1 opacity-0'
      }`}
    >
      {children}
    </p>
  )
}

/**
 * 连接线：虚线一直往前流，一颗光点在上面来回跑。
 *
 * 桌面是横的、手机是竖的，所以两套（线 + 光点）都写出来，靠断点各显各的 ——
 * 用旋转去做会让元素的对齐基准跟着转，反而更难对。
 */
function Connector({ running }: { running: boolean }) {
  const dot = running
    ? 'bg-brand-500 shadow-[0_0_8px_rgba(99,102,241,0.9)]'
    : 'bg-slate-300 dark:bg-slate-600'

  return (
    <div className="flex shrink-0 items-center justify-center py-3 lg:w-14 lg:py-0">
      <div className="relative h-9 w-px lg:h-px lg:w-full">
        <span className="pipe-wire-h absolute inset-0 hidden lg:block" />
        <span className="pipe-wire-v absolute inset-0 lg:hidden" />
        <span
          aria-hidden="true"
          className={`pipe-dot-x absolute top-1/2 -ml-[3px] -mt-[3px] hidden h-1.5 w-1.5 rounded-full lg:block ${dot}`}
        />
        <span
          aria-hidden="true"
          className={`pipe-dot-y absolute left-1/2 -ml-[3px] -mt-[3px] h-1.5 w-1.5 rounded-full lg:hidden ${dot}`}
        />
      </div>
    </div>
  )
}

/* -------------------------------------------------------------------------- */
/* 知识库的格子与工作流的图元                                                   */
/* -------------------------------------------------------------------------- */

function kbCellClass(i: number, kb: number) {
  const row = Math.floor(i / KB_COLS)
  const col = i % KB_COLS
  const at = KB_FIRST + row * KB_ROW_GAP + col * KB_COL_GAP

  if (kb < at) return 'bg-slate-200 dark:bg-slate-800'
  // 命中：留在答案里，所以一直亮着
  if (KB_HITS.has(i)) return 'bg-brand-500 scale-110 dark:bg-brand-400'
  return kb < at + KB_COOL_MS
    ? 'bg-brand-300 scale-105 dark:bg-brand-500/60'
    : 'bg-slate-200 dark:bg-slate-800'
}

function nodeFill(on: boolean, role: Role) {
  if (!on) return 'fill-white dark:fill-slate-900'
  if (role === 'ok') return 'fill-emerald-500'
  return role === 'chosen'
    ? 'fill-brand-500'
    : 'fill-slate-100 dark:fill-slate-800'
}

function nodeStroke(on: boolean, role: Role) {
  if (!on) return 'stroke-slate-200 dark:stroke-slate-800'
  if (role === 'ok') return 'stroke-emerald-500'
  return role === 'chosen'
    ? 'stroke-brand-500'
    : 'stroke-slate-300 dark:stroke-slate-700'
}

function labelFill(on: boolean, role: Role) {
  if (role === 'ok') return 'fill-white'
  if (!on) return 'fill-slate-400 dark:fill-slate-600'
  return role === 'chosen' ? 'fill-white' : 'fill-slate-400 dark:fill-slate-600'
}

function wireClass(on: boolean, chosen: boolean) {
  if (!on) return 'stroke-slate-200 dark:stroke-slate-800'
  // 落选的那条不删掉、只压暗：它存在这件事本身就是"按情况走不同路径"的信息
  return chosen
    ? 'stroke-brand-500'
    : 'stroke-slate-300 opacity-50 dark:stroke-slate-700'
}
