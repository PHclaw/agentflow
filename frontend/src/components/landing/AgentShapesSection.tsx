import { GitBranch } from 'lucide-react'

import { Card } from '../ui/Card'
import { PixelMorph } from './PixelMorph'
import { AGENT_SHAPES } from './agentShapes'
import { Reveal } from './Reveal'

/**
 * 「智能体在做什么」—— 五张卡，每张一个会变形的像素图标。
 *
 * 为什么要这一段
 * ------------
 * 首屏讲的是「怎么搭」，紧接着的问题是：「搭出来的东西本身在干什么？」
 * 访客对"智能体"这个词大多只有一个模糊印象，只列五个名词（听懂 / 拆解 /
 * 取数 / 判断 / 成文）太干，纯文字读不进去。这里用五个会动的图标把过程
 * 演一遍 —— 气泡里先冒出等待的点、再一行行写出字；清单从空框到一个一个
 * 打上勾；柱子逐根长齐。先立概念，后面的功能列表才有落点。
 *
 * 动画不是装饰，它承担的是"顺序"这层信息：五张卡从左到右就是一次任务的推进。
 * 所以图标必须动起来，静止的图标反而会丢掉这一层。
 *
 * 为什么是五张
 * ------------
 * 再多就该画成流程图了，而流程图首屏里已经有了；五张正好铺满一行，
 * 段落高度也可控。
 *
 * 性能：每张卡的画布是独立组件，各自用 IntersectionObserver 判断在不在
 * 视口里，滚过去了就停（落地页很长）。细节见 PixelMorph.tsx。
 */

export function AgentShapesSection() {
  return (
    <section
      id="agent-loop"
      className="relative overflow-hidden bg-slate-50 py-20 dark:bg-slate-950 lg:py-28"
    >
      {/* 底色刻意跟首屏尾部（slate-50 上一层极淡的品牌色）保持接近：
          这一段是首屏的延续，不该出现一条分界线把它切成两块 */}

      <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="max-w-2xl">
          <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-500 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
            <GitBranch className="h-3.5 w-3.5" />
            智能体在做什么
          </div>
          <h2 className="mt-4 text-3xl font-black tracking-tight text-slate-900 dark:text-white sm:text-4xl">
            一句话进来，五步出去
          </h2>
          <p className="mt-3 text-slate-600 dark:text-slate-400">
            回答只是最后一步。中间要先听懂、拆步骤、取数、判断，
            最后交出一份能直接拿去用的东西 —— 这才是它和聊天机器人的区别。
          </p>
        </div>

        {/* Reveal 直接当网格容器用（className 透传），多包一层会把网格的子元素
            关系打断；五张卡依次进场 */}
        <Reveal stagger className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {AGENT_SHAPES.map((card, i) => (
            <Card key={card.title} padding="none" className="overflow-hidden">
              {/*
                图标区：给死高度，画布靠 clientWidth / clientHeight 算格子大小，
                高度塌了就没有尺寸可算。浅底是为了让点阵从卡片里"浮"出来一层。
              */}
              <div className="flex h-[120px] items-center justify-center border-b border-slate-100 bg-slate-50/70 px-3 dark:border-slate-800 dark:bg-slate-900/40">
                <PixelMorph frames={card.frames} className="h-[104px]" />
              </div>

              <div className="p-4">
                <div className="flex items-baseline gap-2">
                  <span className="font-mono text-2xs text-slate-300 dark:text-slate-700">
                    {String(i + 1).padStart(2, '0')}
                  </span>
                  <h3 className="text-sm font-semibold text-slate-900 dark:text-white">
                    {card.title}
                  </h3>
                </div>
                <p className="mt-1.5 text-2xs leading-relaxed text-slate-500 dark:text-slate-400">
                  {card.description}
                </p>
              </div>
            </Card>
          ))}
        </Reveal>
      </div>
    </section>
  )
}
