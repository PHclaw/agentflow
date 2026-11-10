import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Button } from '../ui/Button'
import { ArrowRight, Play, Cpu, Globe, Lock, Zap, MessageSquare, Check, Brain, Github } from 'lucide-react'
import { GITHUB_REPO_URL } from '../../lib/links'

const stats = [
  { label: '企业用户', value: '10,000+' },
  { label: 'AI Agent', value: '50,000+' },
  { label: '对话处理', value: '100M+' },
]

const features = [
  { icon: Cpu, text: '拖拽搭建' },
  { icon: Globe, text: '多渠道接入' },
  { icon: Lock, text: '企业级安全' },
  { icon: Zap, text: '内置行业模板' },
]

/**
 * 中间那个节点展开后露出来的四步。
 *
 * 为什么要把节点**展开**、而不是在标题下面写一行小字说完
 * ------------------------------------------------------
 * 「智能体」是最容易被当成黑盒的一个词：访客看到它，脑子里是"模型自己想"，
 * 于是看不出跟直接用 ChatGPT 有什么区别。真正拉开差距的是节点里面这四步 ——
 * 先规划、再挑技能、再调工具，最后交出答案或文件。
 * 所以这里不压缩成一行文案，而是把四步摆开、跟着节点一起走一遍顺序。
 *
 * `anim` 必须是**字面量**类名：Tailwind 靠扫描源码里的字符串来生成样式，
 * 写成 `animate-flow-step-${i}` 是扫不出来的，运行时那四条 keyframes 根本没生成。
 */
const AGENT_STEPS = [
  { label: '规划思考', anim: 'animate-flow-step-1' },
  { label: '技能调用', anim: 'animate-flow-step-2' },
  { label: '工具调用', anim: 'animate-flow-step-3' },
  { label: '生成答案或文件', anim: 'animate-flow-step-4' },
]

/*
  标题中间那行轮播的词，正好是本产品的三件事。

  只写「AI Agent」的话，知识库和工作流要滚到很下面才第一次露面；把三件事
  放在同一个句子的位置上，第一眼就能看到产品的完整形状 —— 而且这个位置
  是"构建你的 ___"，把三种说法都念一遍，语义也顺。
*/
const HEADLINE_WORDS = ['AI Agent', '知识库', '工作流']
/** 每个词停留的时长。太短像在闪，太长看不出它在轮播。 */
const WORD_MS = 2800
/**
 * 一行的高度（em）。容器和每个词必须用同一个值，滚动位移才对得上；
 * 同时它得比 line-height（leading-tight = 1.25）略大，"g" 这类下伸部
 * 才不会被 overflow-hidden 切掉。
 */
const WORD_LINE = 1.4

export function HeroSection() {
  const [word, setWord] = useState(0)

  useEffect(() => {
    // 关掉动效偏好就停在第一个词上，不轮播
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const id = window.setInterval(
      () => setWord((v) => (v + 1) % HEADLINE_WORDS.length),
      WORD_MS
    )
    return () => window.clearInterval(id)
  }, [])

  return (
    <section className="relative min-h-screen flex items-center pt-20 overflow-hidden">
      {/* Animated background */}
      <div className="absolute inset-0 -z-10">
        {/* Base gradient */}
        <div className="absolute inset-0 bg-gradient-to-br from-slate-50 via-brand-50/30 to-brand-50/30" />
        
        {/* Animated orbs */}
        {/*
          氛围光斑。原来是 animate-pulse（缩放 + 透明度闪烁），节奏快、存在感强，
          更像"在闪"而不是"在呼吸"。改成极慢的漂移（22s），并且**只动 transform**：
          blur-3xl 的元素每重绘一次就是几百万像素的模糊运算，transform 会在合成层
          上平移缩放，不必重算模糊。

          下面那团居中的光斑没加动画：它靠 -translate-x/y-1/2 定位，而 keyframes
          里的 transform 会把这段居中整个盖掉，光斑会跳位。
        */}
        <div className="absolute top-1/4 -left-32 w-96 h-96 bg-brand-400/20 rounded-full blur-3xl animate-drift motion-reduce:animate-none" />
        <div
          className="absolute bottom-1/4 -right-32 w-96 h-96 bg-brand-400/20 rounded-full blur-3xl animate-drift motion-reduce:animate-none"
          style={{ animationDelay: '-8s' }}
        />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-gradient-to-r from-brand-500/10 via-brand-500/10 to-pink-500/10 rounded-full blur-3xl animate-breathe motion-reduce:animate-none" />
        
        {/* Grid pattern */}
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#80808012_1px,transparent_1px),linear-gradient(to_bottom,#80808012_1px,transparent_1px)] bg-[size:24px_24px]" />
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 lg:py-20">
        <div className="grid lg:grid-cols-2 gap-12 lg:gap-16 items-center">
          {/* Left - Content。rise-seq 让下面五个子块依次落位（0 / 70 / 140…ms） */}
          <div className="rise-seq text-center lg:text-left">
            {/* Badge */}
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-gradient-to-r from-brand-500/10 to-brand-500/10 border border-brand-200/50 backdrop-blur-sm mb-8">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-brand-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-brand-500" />
              </span>
              <span className="text-sm font-medium bg-gradient-to-r from-brand-600 to-brand-600 bg-clip-text text-transparent">
                v2.0 已发布
              </span>
            </div>

            {/* Heading */}
            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-black text-slate-900 mb-6 leading-tight tracking-tight">
              <span className="block">构建你的</span>
              {/*
                三个词轮播：AI Agent → 知识库 → 工作流。

                位移用 em，不用百分比 —— 百分比是按内层那一列算的，它有三行
                高，-100% 会一次跳掉三行。容器高度写死 1.4em，换词时整段标题
                的总高不变，下面的字不会被顶动。
              */}
              <span className="block h-[1.4em] overflow-hidden">
                <span
                  className="block transition-transform duration-700 ease-[cubic-bezier(0.16,1,0.3,1)] motion-reduce:transition-none"
                  style={{ transform: `translateY(-${word * WORD_LINE}em)` }}
                >
                  {HEADLINE_WORDS.map((w) => (
                    <span
                      key={w}
                      className="block h-[1.4em] bg-gradient-to-r from-brand-600 via-brand-600 to-pink-600 bg-clip-text text-transparent"
                    >
                      {w}
                    </span>
                  ))}
                </span>
              </span>
              <span className="block text-3xl sm:text-4xl lg:text-5xl text-slate-500 font-bold mt-2">
                不需要写代码
              </span>
            </h1>

            {/* Subheading */}
            <p className="text-lg sm:text-xl text-slate-600 mb-8 max-w-xl mx-auto lg:mx-0 leading-relaxed">
              拖拽节点即可搭建企业自己的 AI 助手。内置客服、销售、HR 等场景模板，
              也可以从空白画布开始。
            </p>

            {/* CTA Buttons */}
            <div className="flex flex-col sm:flex-row sm:flex-wrap items-center justify-center lg:justify-start gap-4 mb-10">
              {/* viewTransition：支持的浏览器会在跳转时对新旧两屏做交叉淡化，
                  不支持的浏览器就是普通跳转，不会卡住导航（见 index.css 的说明） */}
              <Link to="/register" viewTransition>
                <Button size="lg" className="w-full sm:w-auto shadow-xl shadow-brand-500/30 hover:shadow-brand-500/50 group">
                  <span>免费开始</span>
                  <ArrowRight className="ml-2 w-5 h-5 group-hover:translate-x-1 transition-transform" />
                </Button>
              </Link>
              <Link to="/templates" viewTransition>
                <Button variant="outline" size="lg" className="w-full sm:w-auto group">
                  <Play className="mr-2 w-5 h-5" />
                  浏览模板
                </Button>
              </Link>
              <a href={GITHUB_REPO_URL} target="_blank" rel="noopener noreferrer" className="w-full sm:w-auto">
                <Button variant="ghost" size="lg" className="w-full sm:w-auto group">
                  <Github className="mr-2 w-5 h-5" />
                  在 GitHub 上查看
                </Button>
              </a>
            </div>

            {/* Feature pills */}
            <div className="flex flex-wrap items-center justify-center lg:justify-start gap-3">
              {features.map((feature, i) => (
                <div
                  key={i}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/80 backdrop-blur-sm border border-slate-200/50 shadow-sm"
                >
                  <feature.icon className="w-4 h-4 text-brand-500" />
                  <span className="text-sm font-medium text-slate-700">{feature.text}</span>
                </div>
              ))}
            </div>
          </div>

          {/*
            关键视觉。原来只写了 `hidden lg:block` —— 手机打开落地页整段只有文字，
            看不到产品长什么样，而这块「工作流长这样」恰恰是最该给人看的东西。
            现在手机上也在文字下方出现，只把内边距和最小高度收一档。
          */}
          {/*
            宽度上限 560px 是给 lg 以下用的：那一段是单列布局，卡片会被
            拉到整个容器宽（1024px 附近接近 960px），而里面的节点只有 192px ——
            右边会空出一大片。lg 以上由两列网格自己约束（448~512px），
            这个上限不会生效。
          */}
          <div
            className="relative mx-auto mt-4 w-full max-w-[560px] animate-rise motion-reduce:animate-none lg:mt-0"
            style={{ animationDelay: '0.2s' }}
          >
            {/* Main card */}
            <div className="relative">
              {/* Glow effect */}
              <div className="absolute -inset-4 bg-gradient-to-r from-brand-500/20 via-brand-500/20 to-pink-500/20 rounded-3xl blur-2xl" />
              
              {/* Card */}
              <div className="relative bg-white/90 backdrop-blur-xl rounded-3xl border border-slate-200/50 shadow-2xl overflow-hidden">
                {/* Header。加了右侧工具条：只有节点和箭头时它像一张流程图，
                    补上「缩放 + 运行」，它才像"一个能用的编辑器"。
                    原来浮在右上角那张「运行中」小卡片撤掉了 —— 状态已经在
                    这个按钮上，同一个信息没必要在两处说，而且它会和工具条打架。 */}
                <div className="flex items-center gap-3 border-b border-slate-100 bg-gradient-to-r from-slate-50 to-white px-6 py-3.5">
                  <div className="flex gap-1.5">
                    <div className="w-3 h-3 rounded-full bg-red-400" />
                    <div className="w-3 h-3 rounded-full bg-yellow-400" />
                    <div className="w-3 h-3 rounded-full bg-green-400" />
                  </div>
                  <span className="text-sm font-medium text-slate-500">工作流编辑器</span>

                  <div className="ml-auto flex items-center gap-2">
                    <span className="hidden rounded-md border border-slate-200 px-1.5 py-0.5 font-mono text-[10px] text-slate-400 sm:inline">
                      100%
                    </span>
                    <span className="inline-flex items-center gap-1.5 rounded-lg bg-brand-500 px-2.5 py-1 text-[11px] font-medium text-white shadow-sm shadow-brand-500/30">
                      <span className="relative flex h-1.5 w-1.5">
                        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-white/80" />
                        <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-white" />
                      </span>
                      运行中
                    </span>
                  </div>
                </div>
                
                {/* Content - Workflow preview */}
                <div className="relative flex min-h-[300px] flex-col gap-6 bg-gradient-to-br from-slate-50 to-brand-50/30 p-5 sm:flex-row sm:items-center sm:gap-4 sm:p-8 lg:min-h-[400px]">
                  {/* 画布点阵。空着的画布在观感上就是"没做完"，一层极淡的
                      网格既补上质感，又让人一眼认出这是编辑器画布而不是空框。 */}
                  <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle,#94a3b8_1px,transparent_1px)] bg-[size:16px_16px] opacity-25" />

                  {/* 左节点链 + 右运行记录。
                      窄屏（sm 以下）只留节点链：手机上横向本来就放不下两块，
                      硬塞只会把节点挤变形。
                      这块的宽度由上面那层 max-w-[560px] 兜着 —— 少了它，
                      平板宽度下节点只占左边 192px，右边会空出好几百像素。 */}
                  {/* Nodes。行距 20px 而不是 24px：中间那个智能体节点展开之后
                      整条链子变高了（+100px 左右），收一收行距，首屏才不至于
                      把下面的数据条挤出屏幕。 */}
                  <div className="space-y-5 sm:w-48 sm:shrink-0">
                    {/* Trigger node */}
                    <div className="flex items-center gap-4">
                      <div className="relative">
                        <div className="relative w-48 p-4 bg-gradient-to-r from-brand-500 to-brand-600 rounded-xl text-white shadow-lg shadow-brand-500/30">
                          {/*
                            被「点亮」的高亮环。三个节点的延迟是 0s / 2s / 4s，
                            合起来演的就是「消息 → 分析 → 回复」的执行顺序 ——
                            这块视觉本身就在讲产品在干什么，比加个装饰动画有用。

                            这里必须用**正**延迟。负延迟是把相位往前推，元素反而会
                            提前走完自己的时间窗：周期 6s 时写 -2s 等价于 +4s，第二个
                            节点会在第 4 秒亮。想让第 2 步比第 1 步晚 2 秒，就老实地写 2s。
                          */}
                          <span
                            className="pointer-events-none absolute -inset-1 rounded-2xl border-2 border-brand-300/80 opacity-0 shadow-[0_0_18px_rgba(99,102,241,0.45)] animate-flow-node motion-reduce:animate-none"
                            aria-hidden="true"
                          />
                          <div className="flex items-center gap-3">
                            <MessageSquare className="w-5 h-5" />
                            <div>
                              <div className="font-semibold text-sm">用户消息</div>
                              <div className="text-xs opacity-75">触发节点</div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                    
                    {/* Arrow + 跑动的光点。
                        `w-48` 是跟节点同宽：原来只写 justify-center，箭头是在整块
                        内容里居中，落在节点右边约 60px 的空白处 —— 三个节点连不起来，
                        加了这个光点之后更明显（点会跑在空地上）。

                        路径：竖线到 y=28，再画一个人字形的箭头（尖在 y=36）。
                        原来的写法 `m0 0l8 8m-8 8l8-8` 里，第二笔是从 viewBox
                        外面画回来的，渲染出来是个歪在外面的钩子，不像箭头。
                        另外长度收在 36 而不是 40，正好和光点的行程（0→38）对齐。 */}
                    <div className="relative flex w-48 justify-center">
                      <svg className="w-6 h-10 text-brand-400" fill="none" viewBox="0 0 24 40">
                        <path d="M12 0v28m-7-8l7 8l7-8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                      {/*
                        光点用 left-[calc(50%-3px)] 定位，而不是 -translate-x-1/2 ——
                        keyframes 里已经在动 transform，再挂一个 translate 会被整个盖掉。
                        延迟 0.9s：节点 1 第 0 秒亮、第 0.9 秒淡出，光点紧接着出发，
                        走完 1.2 秒正好落在第 2 秒亮起的节点 2 上。
                      */}
                      <span
                        className="pointer-events-none absolute left-[calc(50%-3px)] top-0 h-1.5 w-1.5 rounded-full bg-brand-500 opacity-0 shadow-[0_0_8px_rgba(99,102,241,0.9)] animate-flow-dot motion-reduce:animate-none"
                        style={{ animationDelay: '0.9s' }}
                        aria-hidden="true"
                      />
                    </div>
                    
                    {/* Agent node。比另外两个节点高一截：它把内部四步摊开了，
                        而这张卡片最该说清楚的就是"智能体不是黑盒" ——
                        外面那两个节点只是一进一出，中间这个才是产品本身。

                        外面写 GPT-4 分析 / LLM 节点的时候，它看起来就是个模型调用；
                        换成智能体 + 四步之后，才有"它会自己决定先干什么"这层意思。 */}
                    <div className="flex items-center gap-4">
                      <div className="relative w-48 rounded-xl bg-gradient-to-r from-brand-500 to-brand-600 p-4 text-white shadow-lg shadow-brand-500/30">
                        <span
                          className="pointer-events-none absolute -inset-1 rounded-2xl border-2 border-brand-300/80 opacity-0 shadow-[0_0_18px_rgba(99,102,241,0.45)] animate-flow-node motion-reduce:animate-none"
                          style={{ animationDelay: '2s' }}
                          aria-hidden="true"
                        />
                        <div className="flex items-center gap-3">
                          <Brain className="w-5 h-5" />
                          <div>
                            <div className="font-semibold text-sm">智能体</div>
                            <div className="text-xs opacity-75">Agent 节点</div>
                          </div>
                        </div>

                        {/*
                          四步。亮度在 0.55↔1 之间走，某一刻只有一步是"满亮"的 ——
                          顺序由 tailwind.config.js 里的 flowStep1~4 排好，
                          这里只负责把它们排在节点里，不在 JS 里管时序。
                        */}
                        <ul className="mt-2.5 space-y-1 border-t border-white/25 pt-2.5">
                          {AGENT_STEPS.map((step) => (
                            <li
                              key={step.label}
                              className={`flex items-center gap-2 text-[11px] font-medium ${step.anim} motion-reduce:animate-none`}
                            >
                              <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-white" />
                              {step.label}
                            </li>
                          ))}
                        </ul>
                      </div>
                    </div>
                    
                    {/* Arrow + 跑动的光点（同宽 w-48，对齐到节点中心） */}
                    <div className="relative flex w-48 justify-center">
                      <svg className="w-6 h-10 text-brand-400" fill="none" viewBox="0 0 24 40">
                        <path d="M12 0v28m-7-8l7 8l7-8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                      {/* 延迟 2.9s：接在节点 2（第 2 秒）后面，走完正好落在第 4 秒的节点 3 上 */}
                      <span
                        className="pointer-events-none absolute left-[calc(50%-3px)] top-0 h-1.5 w-1.5 rounded-full bg-brand-500 opacity-0 shadow-[0_0_8px_rgba(99,102,241,0.9)] animate-flow-dot motion-reduce:animate-none"
                        style={{ animationDelay: '2.9s' }}
                        aria-hidden="true"
                      />
                    </div>
                    
                    {/* Response node */}
                    <div className="flex items-center gap-4">
                      <div className="relative w-48 p-4 bg-gradient-to-r from-green-500 to-emerald-500 rounded-xl text-white shadow-lg shadow-green-500/30">
                        {/* 这个节点是绿的，高亮环也跟着走绿 —— 换成品牌靛蓝会像是
                            另一个东西盖在上面 */}
                        <span
                          className="pointer-events-none absolute -inset-1 rounded-2xl border-2 border-green-300/80 opacity-0 shadow-[0_0_18px_rgba(34,197,94,0.45)] animate-flow-node motion-reduce:animate-none"
                          style={{ animationDelay: '4s' }}
                          aria-hidden="true"
                        />
                        <div className="flex items-center gap-3">
                          <Zap className="w-5 h-5" />
                          <div>
                            <div className="font-semibold text-sm">回复用户</div>
                            <div className="text-xs opacity-75">响应节点</div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* 右：运行记录。左边在"亮"，这里说明每一步到底干了什么 */}
                  <RunLog />
                </div>
              </div>
              
              {/* Floating elements。手机上把外扩的偏移收一点，否则会顶到
                  区块的 overflow-hidden 边界上被切掉。

                  位置：右上角原本有张「运行中」的小卡片，已经并进头部工具条了；
                  左下角原本是这张「准确率」，但那里的节点链已经排到最左边，
                  卡片正好压住最后一个节点的图标 —— 挪到右下角，那儿是空的。 */}
              <div className="absolute -bottom-4 -right-4 p-4 bg-white rounded-2xl shadow-xl border border-slate-100">
                <div className="text-2xl font-bold bg-gradient-to-r from-brand-600 to-brand-600 bg-clip-text text-transparent">98.5%</div>
                <div className="text-xs text-slate-500">准确率</div>
              </div>
            </div>
          </div>
        </div>

        {/* Stats */}
        <div
          className="mt-12 animate-rise motion-reduce:animate-none lg:mt-16"
          style={{ animationDelay: '0.35s' }}
        >
          <div className="grid grid-cols-3 gap-4 sm:gap-8 max-w-2xl mx-auto">
            {stats.map((stat, i) => (
              <div key={i} className="text-center">
                <div className="text-2xl sm:text-3xl lg:text-4xl font-black bg-gradient-to-r from-brand-600 to-brand-600 bg-clip-text text-transparent">
                  {stat.value}
                </div>
                <div className="text-xs sm:text-sm text-slate-500 mt-1">{stat.label}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}

/* -------------------------------------------------------------------------- */
/* 编辑器右侧的「运行记录」                                                     */
/* -------------------------------------------------------------------------- */

/**
 * 一轮的时长。**必须**是 6000ms —— 左边三个节点的高亮环就是按 6s 一轮跑的
 * （tailwind.config.js 里的 flowNode）。两边同一个周期，看起来才是"同一个
 * 流程在跑"，而不是两个各动各的动画。
 */
const LOG_CYCLE_MS = 6000
/** 每一步的开始时间（相对本轮起点），和节点的延迟一一对应 */
const LOG_STEPS = [
  { at: 0, title: '收到消息', detail: '触发节点 · 新会话' },
  // 中间这条对着"智能体节点"亮起的那一秒：节点里在走四步，这里记一句结论。
  // 明细写"调用知识库"，是为了让知识库在这张卡片里也有一处落点 ——
  // 它是三件事里最容易被忽略的一件。
  { at: 2000, title: '智能体执行', detail: '调用知识库 · 命中 3 条' },
  { at: 4000, title: '生成回复', detail: '响应节点 · 已发送' },
]
/**
 * 一步"跑完"比"开始"晚多久。
 * 这个值要小于每步的间隔（2000），留出的那 700ms 正是第三步打勾之后、
 * 下一轮清空之前的那一小段 —— 没有它，第三步永远等不到自己的对勾，
 * 进度条走到头就重来了，看起来像"没跑完"。
 */
const LOG_STEP_DONE_MS = 1300

/**
 * 为什么这一段要单独一个组件、自己带一个 interval
 * ----------------------------------------------
 * 记录是**累积**的（第 2 条出现时第 1 条还留在上面），这种「只增不减、
 * 到点一起清空」的节奏没法用「一条 keyframes + 不同延迟」演出来：周期性
 * 动画为了让第 3 步亮到第 6 秒，第 0 秒它也一定亮着（周期使然）。
 * 所以交给状态机 —— 只存"本轮走了多久"，每一条该是什么状态由时间反推，
 * 循环回到起点时全部自动归位，不必逐个清理 timeout。
 *
 * 独立成组件是为了收敛重渲染：这里 100ms 跳一次，而 Hero 的其余部分
 * （标题、按钮、节点）是静态的，不该跟着一起重算。
 */
function RunLog() {
  const [t, setT] = useState(0)

  useEffect(() => {
    // 关掉动效偏好：直接给"全部跑完"，信息一样给全，只是不动
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      setT(LOG_CYCLE_MS)
      return
    }
    const started = Date.now()
    const id = window.setInterval(
      () => setT((Date.now() - started) % LOG_CYCLE_MS),
      100
    )
    return () => window.clearInterval(id)
  }, [])

  const done = LOG_STEPS.filter((s) => t >= s.at + LOG_STEP_DONE_MS).length

  return (
    <div className="hidden min-w-0 flex-1 flex-col rounded-xl border border-slate-200 bg-white sm:flex dark:border-slate-800 dark:bg-slate-900">
      <div className="flex items-center gap-2 border-b border-slate-100 px-3 py-2 dark:border-slate-800">
        <span className="relative flex h-1.5 w-1.5">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
          <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-500" />
        </span>
        <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400">
          运行记录
        </span>
        <span className="ml-auto font-mono text-[10px] text-slate-400 dark:text-slate-500">
          {done}/{LOG_STEPS.length}
        </span>
      </div>

      {/* 这里刻意不给 flex-1：面板的高度是"内容撑出来的"（父级是 items-center，
          不会拉伸它），空高里挂一个 flex-basis:0 的子项只会让浏览器去算
          "剩余空间"，行距被压扁、文字和下面的进度条叠在一起。 */}
      <ul className="space-y-2.5 p-3">
        {LOG_STEPS.map((step) => {
          const state =
            t >= step.at + LOG_STEP_DONE_MS
              ? 'done'
              : t >= step.at
                ? 'running'
                : 'idle'
          return (
            <li key={step.title} className="flex items-start gap-2">
              <span
                className={`mt-0.5 grid h-3.5 w-3.5 shrink-0 place-items-center rounded-full transition-colors duration-300 ${
                  state === 'done'
                    ? 'bg-emerald-500 text-white'
                    : state === 'running'
                      ? 'bg-brand-500 text-white'
                      : 'bg-slate-200 dark:bg-slate-700'
                }`}
              >
                {state === 'done' ? (
                  <Check className="h-2 w-2" strokeWidth={3} />
                ) : (
                  <span className="h-1 w-1 rounded-full bg-white/90" />
                )}
              </span>
              <div className="min-w-0">
                <div
                  className={`truncate text-[11px] font-medium transition-colors duration-300 ${
                    state === 'idle'
                      ? 'text-slate-400 dark:text-slate-600'
                      : 'text-slate-700 dark:text-slate-200'
                  }`}
                >
                  {step.title}
                </div>
                <div className="truncate text-[10px] text-slate-400 dark:text-slate-500">
                  {step.detail}
                </div>
              </div>
            </li>
          )
        })}
      </ul>

      {/* 本轮进度。用 scaleX 而不是 width：宽度是布局属性，每帧改它要重排；
          100ms 一跳的状态机靠 200ms 的过渡补平成连续移动。 */}
      <div className="px-3 pt-0 pb-2.5">
        <span className="block h-1 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
          <span
            className="block h-full origin-left rounded-full bg-brand-500 transition-transform duration-200 ease-linear"
            style={{ transform: `scaleX(${Math.min(1, t / LOG_CYCLE_MS)})` }}
          />
        </span>
      </div>
    </div>
  )
}
