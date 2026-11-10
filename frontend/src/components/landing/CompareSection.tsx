import { useEffect, useRef, useState } from 'react'
import { MessageSquare, Database, Wrench, Check, X, GitBranch, BookOpen } from 'lucide-react'

/**
 * 对比演示：同一个问题，「普通 AI 助手」和 AgentFlow 同时开始，结果不同。
 *
 * 为什么用同步对照而不是并排两张静态卡片：
 * 差异是**过程**的差异（一边卡住然后说"我访问不了"，一边检索、调用、答完），
 * 静态卡片只能罗列结论，看过就忘；两边同时跑起来，对比自己就出来了。
 *
 * 三条自我约束：
 *
 * 1. **不编造量化指标。** 通篇没有"快 3.2 倍""准确率 99%"这种数字 ——
 *    那些数无从核实，而这里真正有说服力的是行为差异：能不能碰到你的系统、
 *    能不能把事办完、给的说法能不能追溯。所以右边窗口里出现的
 *    "命中知识库 3 条 · 响应 0.8s" 是示意界面文案，不是性能声明。
 * 2. **一个 interval 驱动全部状态。** 用「经过时长」推导每个阶段该显示什么，
 *    而不是给每个变化单独挂一个 setTimeout：循环回到 0 时所有状态自动归位，
 *    不会出现"上次的字幕还留在屏幕上"这种残留。100ms 一跳，只有本组件重渲染。
 * 3. **prefers-reduced-motion 直接给终局。** 左边是那句"无法访问"，
 *    右边是完整回答 + 已完成。结论不靠动画传达。
 */

const QUESTION = '帮我查一下订单 #A1029 到哪了'

const ORDINARY_ANSWER =
  '抱歉，我无法访问你的订单系统。建议你登录官网，在「我的订单」页面查看物流信息。'

const OUR_ANSWER =
  '订单 #A1029 已经在途中了：承运商顺丰，运单 SF123456789，预计明天 18:00 前送达。' +
  '需要我帮你催一下，或者改成自提点吗？'

/** 一轮的时长（毫秒）。四个阶段 + 停留。 */
const T_ASK = 400        // 问题出现
const T_SEARCH = 2100    // 我们这边开始检索
const T_TOOL = 3500      // 我们这边调用接口，同时普通助手"想完了"
const T_STREAM_END = 6400 // 回答播完
const LOOP = 10200

const STREAM_MS_PER_CHAR = 24

const DIMENSIONS = [
  {
    icon: BookOpen,
    title: '知识来源',
    ordinary: '只凭公开常识，不了解你的业务',
    ours: '你的知识库 + 实时接口，按内容检索',
  },
  {
    icon: Wrench,
    title: '能做的事',
    ordinary: '答不上就建议你转人工',
    ours: '检索 → 调用 → 答复，事情办完为止',
  },
  {
    icon: GitBranch,
    title: '决策方式',
    ordinary: '一条路走到黑，问什么都一样',
    ours: '条件分支，按情况走不同路径',
  },
  {
    icon: Database,
    title: '结果可信度',
    ordinary: '无从验证，错了也不知道',
    ours: '每条回答都能给出来源片段',
  },
]

export function CompareSection() {
  const [t, setT] = useState(0)
  const reduce = useRef(
    typeof window !== 'undefined' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches
  )

  useEffect(() => {
    if (reduce.current) {
      setT(T_STREAM_END)
      return
    }
    const started = Date.now()
    const id = window.setInterval(() => {
      setT((Date.now() - started) % LOOP)
    }, 100)
    return () => window.clearInterval(id)
  }, [])

  const asked = t >= T_ASK
  const leftThinking = asked && t < T_TOOL
  const leftFailed = t >= T_TOOL
  const rightStep = t < T_SEARCH ? 0 : t < T_TOOL ? 1 : t < T_STREAM_END ? 2 : 3
  const typed = Math.min(
    OUR_ANSWER.length,
    Math.max(0, Math.floor((t - T_TOOL) / STREAM_MS_PER_CHAR))
  )
  const done = t >= T_STREAM_END

  return (
    <div>
      {/* 区块标题 */}
      <div className="mx-auto max-w-2xl text-center">
        <div className="mx-auto mb-5 inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-500 dark:border-slate-800 dark:bg-slate-900">
          <GitBranch className="h-3.5 w-3.5" />
          差别在哪
        </div>
        <h2 className="text-3xl font-black tracking-tight text-slate-900 dark:text-white sm:text-4xl">
          同样一个问题，两种结果
        </h2>
        <p className="mt-3 text-slate-600 dark:text-slate-400">
          下面两边同时收到同一个请求，注意看它们各自能做什么。
        </p>
      </div>

      {/* 同步对照的两个窗口 */}
      <div className="mt-12 grid items-start gap-6 lg:grid-cols-2">
        {/* 左：普通 AI 助手 */}
        <div className="rounded-2xl border border-slate-200 bg-slate-50 p-5 dark:border-slate-800 dark:bg-slate-900/50">
          <div className="mb-4 flex items-center gap-2">
            <span className="grid h-7 w-7 place-items-center rounded-lg bg-slate-200 text-slate-500 dark:bg-slate-800">
              <MessageSquare className="h-3.5 w-3.5" />
            </span>
            <span className="text-sm font-medium text-slate-600 dark:text-slate-300">
              普通 AI 助手
            </span>
            <span className="ml-auto text-[11px] text-slate-400">只会聊天</span>
          </div>

          {/* 用户问题 */}
          <div
            className={`flex justify-end transition-all duration-300 ${
              asked ? 'translate-y-0 opacity-100' : 'translate-y-1 opacity-0'
            }`}
          >
            <p className="max-w-[85%] rounded-2xl rounded-br-sm bg-slate-300 px-3.5 py-2 text-sm text-slate-700 dark:bg-slate-700 dark:text-slate-200">
              {QUESTION}
            </p>
          </div>

          <div className="mt-3 min-h-[92px]">
            {leftThinking && (
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
                思考中…
              </div>
            )}

            {leftFailed && (
              <div className="animate-fade-in">
                <p className="max-w-[92%] rounded-2xl rounded-bl-sm bg-white px-3.5 py-2 text-sm leading-relaxed text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                  {ORDINARY_ANSWER}
                </p>
                <span className="mt-2 inline-flex items-center gap-1 rounded-md bg-red-50 px-2 py-1 text-[11px] font-medium text-red-600 dark:bg-red-500/10 dark:text-red-400">
                  <X className="h-3 w-3" />
                  无法完成，需要你自己操作
                </span>
              </div>
            )}
          </div>
        </div>

        {/* 右：AgentFlow */}
        <div className="relative rounded-2xl border border-brand-200 bg-white p-5 dark:border-brand-500/30 dark:bg-slate-900">
          <div className="absolute -inset-px -z-10 rounded-2xl bg-brand-500/10 blur-md motion-reduce:hidden" />

          <div className="mb-4 flex items-center gap-2">
            <span className="grid h-7 w-7 place-items-center rounded-lg bg-brand-500 text-white">
              <MessageSquare className="h-3.5 w-3.5" />
            </span>
            <span className="text-sm font-medium text-slate-800 dark:text-white">
              AgentFlow
            </span>
            <span className="ml-auto text-[11px] text-slate-400">能连你的系统</span>
          </div>

          <div className="flex justify-end">
            <p className="max-w-[85%] rounded-2xl rounded-br-sm bg-brand-500 px-3.5 py-2 text-sm text-white">
              {QUESTION}
            </p>
          </div>

          {/* 三步过程指示 */}
          <div className="mt-3 space-y-1.5">
            {[
              { label: '检索知识库，取回物流条款', at: 1 },
              { label: '调用物流查询接口', at: 2 },
              { label: '组织回答，流式返回', at: 3 },
            ].map((s) => (
              <div
                key={s.label}
                className={`flex items-center gap-2 text-xs transition-colors duration-500 ${
                  rightStep >= s.at
                    ? 'text-slate-700 dark:text-slate-200'
                    : 'text-slate-300 dark:text-slate-600'
                }`}
              >
                <span
                  className={`grid h-4 w-4 shrink-0 place-items-center rounded-full transition-colors duration-500 ${
                    rightStep >= s.at
                      ? 'bg-brand-500 text-white'
                      : 'bg-slate-200 dark:bg-slate-700'
                  }`}
                >
                  {rightStep >= s.at ? <Check className="h-2.5 w-2.5" /> : null}
                </span>
                {s.label}
              </div>
            ))}
          </div>

          {/* 回答 */}
          <div className="mt-3 min-h-[92px]">
            {typed > 0 && (
              <div className="animate-fade-in">
                <p className="max-w-[95%] rounded-2xl rounded-bl-sm bg-slate-100 px-3.5 py-2 text-sm leading-relaxed text-slate-800 dark:bg-slate-800 dark:text-slate-100">
                  {OUR_ANSWER.slice(0, typed)}
                  {!done && (
                    <span className="ml-0.5 inline-block h-3.5 w-[2px] translate-y-0.5 animate-pulse bg-brand-500" />
                  )}
                </p>
                {done && (
                  <span className="mt-2 inline-flex items-center gap-1 rounded-md bg-emerald-50 px-2 py-1 text-[11px] font-medium text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400">
                    <Check className="h-3 w-3" />
                    已完成，来源可追溯
                  </span>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 四维对照 */}
      <div className="mt-10 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {DIMENSIONS.map((d) => (
          <div
            key={d.title}
            className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900"
          >
            <div className="mb-3 flex items-center gap-2">
              <span className="grid h-7 w-7 place-items-center rounded-lg bg-slate-100 text-slate-500 dark:bg-slate-800">
                <d.icon className="h-3.5 w-3.5" />
              </span>
              <span className="text-sm font-semibold text-slate-800 dark:text-white">
                {d.title}
              </span>
            </div>

            <div className="space-y-2 text-xs leading-relaxed">
              <p className="flex gap-1.5 text-slate-400">
                <X className="mt-0.5 h-3 w-3 shrink-0 text-slate-300" />
                <span>{d.ordinary}</span>
              </p>
              <p className="flex gap-1.5 text-slate-700 dark:text-slate-200">
                <Check className="mt-0.5 h-3 w-3 shrink-0 text-brand-500" />
                <span>{d.ours}</span>
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
