import { useEffect, useRef, useState } from 'react'
import { MessageSquare, Database, Zap, Check } from 'lucide-react'

/**
 * 「实际使用场景」演示：一段会自己跑起来的对话。
 *
 * 上一轮 Hero 里那条执行流动画讲的是**操作流程**（节点怎么连），这里补另一
 * 半 —— 用户真正在产品里看到的东西：提问 → 检索知识库 → 流式回答 → 给出引用。
 * 两者一个是"怎么搭"，一个是"搭完什么样"，缺了后者访客很难建立实感。
 *
 * 三个设计约束：
 *
 * 1. **文字是逐字流出来的**，不是整块淡入。流式输出是这类产品的标志性体验，
 *    整块出现反而不像。用定时器按字数推进，间隔 24ms（约 40 字/秒，接近
 *    真实模型的输出节奏），不用 CSS 逐帧动画 —— 中文按字数截断比按宽度
 *    裁切可靠，也不会因为字体度量不同而错位。
 * 2. **计时器全部挂在本组件上并在卸载时清掉**。这段循环会一直跑，
 *    漏一个 setInterval 就是页面切走以后还在后台转。
 * 3. **prefers-reduced-motion 直接给最终态**：一轮播完的完整对话 + 引用，
 *    不逐字、不循环。信息不靠动画传达，动画只是让它更好懂。
 */

const USER_TEXT = '订单还没发货，怎么查？'
const AGENT_TEXT =
  '你的订单 #A1029 已经在途中了：承运商顺丰，运单 SF123456789，' +
  '预计明天 18:00 前送达。需要我帮你催一下，或者改成自提点吗？'
const SOURCE = '来源：物流 FAQ.pdf'

/** 每个阶段时长（毫秒）。四段加起来是一轮。 */
const T_USER = 400
const T_TYPING = 1100
const T_STREAM = 900   // 按字数推进，这里是上限；实际按 24ms/字
const T_HOLD = 3200

const STEPS = ['提问', '检索知识库', '生成回答', '完成'] as const

export function LiveDemo() {
  const [step, setStep] = useState(0)
  const [typed, setTyped] = useState(0)
  const reduce = useRef(
    typeof window !== 'undefined' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches
  )

  useEffect(() => {
    // 降级：直接给完整对话，不起循环
    if (reduce.current) {
      setStep(3)
      setTyped(AGENT_TEXT.length)
      return
    }

    const timers: number[] = []
    let alive = true

    const run = () => {
      if (!alive) return
      setStep(0)
      setTyped(0)

      // 1) 用户消息
      timers.push(window.setTimeout(() => {
        if (alive) setStep(1)
      }, T_USER))

      // 2) 检索中（打字指示）
      timers.push(window.setTimeout(() => {
        if (alive) setStep(2)
      }, T_USER + T_TYPING))

      // 3) 流式回答：按字数推进
      for (let i = 1; i <= AGENT_TEXT.length; i += 1) {
        timers.push(window.setTimeout(() => {
          if (alive) setTyped(i)
        }, T_USER + T_TYPING + i * 24))
      }

      // 4) 停留，然后重来
      timers.push(window.setTimeout(() => {
        if (alive) setStep(3)
      }, T_USER + T_TYPING + T_STREAM))
      timers.push(window.setTimeout(() => {
        if (alive) run()
      }, T_USER + T_TYPING + T_STREAM + T_HOLD))
    }

    run()
    return () => {
      alive = false
      timers.forEach((t) => window.clearTimeout(t))
    }
  }, [])

  const done = step >= 3 || (reduce.current && step >= 3)

  return (
    <div className="grid items-center gap-10 lg:grid-cols-2">
      {/* 左：三个步骤，跟着右侧演示高亮 */}
      <div>
        <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-500 dark:border-slate-800 dark:bg-slate-900">
          <Zap className="h-3.5 w-3.5" />
          一次完整的对话
        </div>
        <h2 className="mt-4 text-3xl font-black tracking-tight text-slate-900 dark:text-white sm:text-4xl">
          提问之后发生了什么
        </h2>
        <p className="mt-3 text-slate-600 dark:text-slate-400">
          不是把问题丢给模型就完事 —— 中间还要检索你自己的知识库。
        </p>

        <ul className="mt-8 space-y-4">
          {[
            { icon: MessageSquare, label: '用户在任意渠道提问', at: 0 },
            { icon: Database, label: '按内容检索知识库，取回相关片段', at: 1 },
            { icon: Zap, label: '模型结合片段组织回答，流式返回', at: 2 },
          ].map((s) => (
            <li
              key={s.label}
              className={`flex items-center gap-3 rounded-xl border p-3.5 transition-colors duration-500 ${
                step >= s.at
                  ? 'border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-900'
                  : 'border-transparent bg-slate-100/60 dark:bg-slate-900/40'
              }`}
            >
              <span
                className={`grid h-9 w-9 shrink-0 place-items-center rounded-lg transition-colors duration-500 ${
                  step >= s.at
                    ? 'bg-brand-500 text-white'
                    : 'bg-slate-200 text-slate-400 dark:bg-slate-800'
                }`}
              >
                <s.icon className="h-4 w-4" />
              </span>
              <span
                className={`text-sm font-medium transition-colors duration-500 ${
                  step >= s.at
                    ? 'text-slate-900 dark:text-white'
                    : 'text-slate-400 dark:text-slate-500'
                }`}
              >
                {s.label}
              </span>
            </li>
          ))}
        </ul>
      </div>

      {/* 右：对话窗口 */}
      <div className="relative">
        <div className="absolute -inset-3 rounded-3xl bg-brand-500/10 blur-2xl motion-reduce:hidden" />

        <div className="relative overflow-hidden rounded-2xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
          {/* 窗口头 */}
          <div className="flex items-center gap-2 border-b border-slate-100 px-4 py-3 dark:border-slate-800">
            <span className="h-2 w-2 rounded-full bg-emerald-500" />
            <span className="text-xs font-medium text-slate-500 dark:text-slate-400">
              客服 Agent · 实时
            </span>
            {/* 步骤指示：四个点，当前步亮 */}
            <span className="ml-auto flex items-center gap-1">
              {STEPS.map((s, i) => (
                <span
                  key={s}
                  title={s}
                  className={`h-1.5 rounded-full transition-all duration-500 ${
                    step >= i ? 'w-4 bg-brand-500' : 'w-1.5 bg-slate-200 dark:bg-slate-700'
                  }`}
                />
              ))}
            </span>
          </div>

          <div className="space-y-3 p-4 sm:p-5">
            {/* 用户消息 */}
            <div
              className={`flex justify-end transition-all duration-300 ${
                step >= 1 ? 'translate-y-0 opacity-100' : 'translate-y-1 opacity-0'
              }`}
            >
              <p className="max-w-[80%] rounded-2xl rounded-br-sm bg-brand-500 px-3.5 py-2 text-sm text-white">
                {USER_TEXT}
              </p>
            </div>

            {/* 检索中 */}
            {step === 2 && typed === 0 && (
              <div className="flex items-center gap-2 text-xs text-slate-400">
                <span className="flex gap-1">
                  {[0, 1, 2].map((i) => (
                    <span
                      key={i}
                      className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-300"
                      style={{ animationDelay: `${i * 0.15}s` }}
                    />
                  ))}
                </span>
                正在检索知识库…
              </div>
            )}

            {/* 回答：流式 */}
            {(typed > 0 || done) && (
              <div className="flex justify-start">
                <div className="max-w-[88%] rounded-2xl rounded-bl-sm bg-slate-100 px-3.5 py-2 dark:bg-slate-800">
                  <p className="text-sm leading-relaxed text-slate-800 dark:text-slate-100">
                    {done ? AGENT_TEXT : AGENT_TEXT.slice(0, typed)}
                    {/* 光标：流式时才有 */}
                    {!done && (
                      <span className="ml-0.5 inline-block h-3.5 w-[2px] translate-y-0.5 animate-pulse bg-brand-500" />
                    )}
                  </p>
                  {/* 引用来源：回答播完才出现 */}
                  <span
                    className={`mt-2 inline-flex items-center gap-1 rounded-md bg-white px-2 py-1 text-[11px] text-slate-500 transition-all duration-500 dark:bg-slate-900 ${
                      done ? 'translate-y-0 opacity-100' : 'translate-y-1 opacity-0'
                    }`}
                  >
                    <Database className="h-3 w-3" />
                    {SOURCE}
                  </span>
                </div>
              </div>
            )}
          </div>

          {/* 底部状态条：完成后给出这轮的数字 */}
          <div className="flex items-center gap-3 border-t border-slate-100 px-4 py-2.5 text-[11px] text-slate-400 dark:border-slate-800">
            <span className="flex items-center gap-1">
              <Check className="h-3 w-3" />
              命中知识库 3 条
            </span>
            <span>·</span>
            <span>响应 0.8s</span>
            <span className="ml-auto">来源可追溯</span>
          </div>
        </div>
      </div>
    </div>
  )
}
