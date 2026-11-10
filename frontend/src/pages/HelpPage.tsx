import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  AlertTriangle,
  ArrowRight,
  Bot,
  ChevronDown,
  ChevronRight,
  FileText,
  HelpCircle,
  History,
  LayoutTemplate,
  Mail,
  Search,
  Sparkles,
  Workflow,
} from 'lucide-react'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { llmModels, type SelectableModel } from '../services/api'

/** 对外支持邮箱。与落地页页脚共用同一个地址，改这里就够。 */
const SUPPORT_EMAIL = '168465420@qq.com'

/**
 * 帮助中心。
 *
 * 三条规矩，都是为了别再写出「看起来能用、点了没反应」的条目：
 *
 * 1. **只写产品里真有的东西。** 这页曾经有一个「团队协作」卡片，和一条
 *    「Agent 创建完成后可以生成分享链接或嵌入代码」的 FAQ —— 两个功能都
 *    不存在。用户照着找只会白费时间，而且不会意识到是自己漏了什么。
 * 2. **每个入口都要真的能到。** 那些卡片当时是 `cursor-pointer` + hover
 *    效果装成可点的，却没有 onClick / href。
 * 3. **模型列表读「当前生效端点下真正能用的模型」**，不是内置静态目录 ——
 *    后者全是 OpenAI 型号名，跟实际端点无关，照着选只会在执行时报
 *    model not found。
 *
 * 另外：答案正文是按**纯文本**渲染的，别在里面写 Markdown 语法 —— 星号会
 * 原样显示出来。
 */

interface Step {
  title: string
  body: string
  action: string
  to: string
}

const STEPS: Step[] = [
  {
    title: '配置模型',
    body: '填你自己的端点、密钥和模型名。本地 Ollama 也支持（端点填 http://localhost:11434/v1）。',
    action: '打开模型配置',
    to: '/settings?tab=models',
  },
  {
    title: '创建 Agent',
    body: '起个名字，写清它是谁、按什么规矩回答。模型留空即跟随上一步的生效配置。',
    action: '创建 Agent',
    to: '/agents/new',
  },
  {
    title: '开始对话',
    body: '在 Agent 列表点进去就能聊。需要私有资料或固定流程时，再去补知识库、Skill 与工作流。',
    action: '我的 Agent',
    to: '/agents',
  },
]

interface Guide {
  icon: typeof Bot
  title: string
  body: string
  to: string
}

const GUIDES: Guide[] = [
  {
    icon: Bot,
    title: 'Agent 与对话',
    body: '创建、配置系统提示词、关联知识库、多轮对话',
    to: '/agents',
  },
  {
    icon: Sparkles,
    title: 'Skill 广场',
    body: '平台预置技能，部分自带脚本与产物导出',
    to: '/skills',
  },
  {
    icon: History,
    title: '对话记录',
    body: '回看历史会话，核对每次调用用掉的量',
    to: '/conversations',
  },
]

interface Faq {
  /** 稳定标识。用它而不是数组下标 —— 搜索过滤后下标会变，展开的会是别人 */
  id: string
  category: string
  question: string
  answer: string
  /** 答案相关的直达入口 */
  to?: string
  toLabel?: string
}

const FAQS: Faq[] = [
  // ---- 入门 ----
  {
    id: 'first-agent',
    category: '入门',
    question: '如何创建第一个 Agent？',
    answer:
      '左侧「Agent」→ 右上「创建 Agent」。填名称、描述和系统提示词就够开始了；模型留空表示跟随「模型配置」里当前生效的模型。',
    to: '/agents/new',
    toLabel: '创建 Agent',
  },
  {
    id: 'prompt-tips',
    category: '入门',
    question: '系统提示词要写多详细？',
    answer:
      '写清三件事基本就够：它是谁（角色）、按什么规矩回答（约束）、拿不准时怎么办。写「你是客服助手」很空，写「你是电商客服，只回答退换货与物流问题，政策以外的一律让用户联系人工，不猜测」就稳得多。',
  },

  // ---- 模型 ----
  {
    id: 'supported-models',
    category: '模型',
    question: '支持哪些语言模型？',
    answer: '', // 由 describeAvailableModels() 动态生成
  },
  {
    id: 'model-not-found',
    category: '模型',
    question: '执行时报 model not found 怎么办？',
    answer:
      '节点和 Agent 上的模型名会被原样发给「当前生效的端点」，所以它必须是那个端点上真实存在的名字。到「设置 → 模型配置」把它改成端点上的名字即可：本地 Ollama 用 ollama list 查（例如 glm4:latest），OpenAI 兼容服务看服务商控制台里的标识。',
    to: '/settings?tab=models',
    toLabel: '去改模型名',
  },
  {
    id: 'why-blank-model',
    category: '模型',
    question: '为什么建议把模型名留空？',
    answer:
      '留空 = 跟随生效配置。一旦在 Agent 或工作流节点里写死了型号，之后换端点（比如从 OpenAI 换成本地 Ollama）那些地方会立刻开始报 model not found，而你得逐个去改。',
  },

  // ---- 知识库 ----
  {
    id: 'attach-kb',
    category: '知识库',
    question: '如何给 Agent 关联知识库？',
    answer: 'Agent 编辑页 →「知识库」标签 → 选择已有知识库，或先到「知识库」页面新建一个。',
    to: '/agents',
    toLabel: '我的 Agent',
  },
  {
    id: 'kb-formats',
    category: '知识库',
    question: '上传文档支持哪些格式？',
    answer:
      'txt / md / pdf / docx。上传后会自动切分并写入向量库，稍等即可参与检索。解析失败会明确报错，不会把二进制内容当文本塞进库里。',
  },
  {
    id: 'kb-no-result',
    category: '知识库',
    question: '检索不到内容 / 结果很乱怎么办？',
    answer:
      '常见两种原因。一是相似度阈值偏高，把不相关的结果也挡掉了；二是换过向量模型 —— 不同向量模型的维度不一致，换完必须把文档重新上传一遍，旧向量读不出来（这类情况上传时会直接提示「向量维度不匹配」）。',
  },

  // ---- 工作流 ----
  {
    id: 'workflow-vs-agent',
    category: '工作流',
    question: '工作流和普通 Agent 有什么区别？',
    answer:
      '普通 Agent = 一段系统提示词 + 多轮对话，适合开放问答。工作流把步骤画出来（消息触发、模型调用、知识检索、条件分支…），适合流程固定的场景。两者可以绑在一起：Agent 编辑页的「工作流」标签。',
  },
  {
    id: 'workflow-kb-node',
    category: '工作流',
    question: '模板里的知识节点为什么报「未配置知识库 ID」？',
    answer:
      '知识库是按账号隔离的，模板没法预置一个通用的知识库，所以模板自带的检索节点必然是待配置状态。在节点上显式选一个知识库即可；用不到就直接把那个节点删掉，其余节点仍会正常跑完。',
  },

  // ---- Skill ----
  {
    id: 'where-skills',
    category: 'Skill',
    question: '技能广场的技能从哪来？',
    answer:
      '平台预置，存放在服务器 skills/<名字>/SKILL.md。该目录一有改动广场会自动刷新，不需要重启服务。',
    to: '/skills',
    toLabel: '逛 Skill 广场',
  },
  {
    id: 'add-skill',
    category: 'Skill',
    question: '（管理员）怎么添加技能？',
    answer:
      '管理后台 → 技能管理：可以手写新建，也可以直接导入 zip 技能包。GitHub 仓库整包也收 —— 会自动下钻到 skills/<名字>/，把仓库里的 README、CI 配置、docs 截图挡在外面，广场描述和系统提示词在导入时自己填。',
  },

  // ---- 用量 ----
  {
    id: 'usage',
    category: '用量',
    question: '用量和套餐在哪里看？',
    answer: '设置 → 订阅，能看到当前套餐、已用 Agent 数与消息数。',
    to: '/settings?tab=billing',
    toLabel: '查看订阅',
  },
]

interface ModelInfo {
  ready: boolean
  failed: boolean
  models: SelectableModel[]
}

export default function HelpPage() {
  const navigate = useNavigate()
  const [searchQuery, setSearchQuery] = useState('')
  const [expanded, setExpanded] = useState<string | null>(null)
  const [modelInfo, setModelInfo] = useState<ModelInfo>({
    ready: false,
    failed: false,
    models: [],
  })

  useEffect(() => {
    llmModels
      .list()
      .then((res) => {
        const payload: any = (res as any)?.data ?? res
        setModelInfo({ ready: true, failed: false, models: payload?.models || [] })
      })
      .catch(() => setModelInfo({ ready: true, failed: true, models: [] }))
  }, [])

  /**
   * 「支持哪些模型」的答案。
   *
   * 读的是「当前生效端点下真正能用的模型」（/llm-configs/models），不是那份
   * 内置静态目录 —— 目录里全是 OpenAI 型号名，跟实际端点没有关系。还没配过
   * 任何模型时，答案应该是「去配一个」，而不是列一串他根本用不了的名字。
   *
   * 措辞用「当前可用」而不是「你自己的」：模型配置是**平台级**的（后端建
   * 配置时 owner_id=None），所有用户看到的是同一份。说成个人配置会让人以为
   * 改它只影响自己。
   */
  function describeAvailableModels(): string {
    if (!modelInfo.ready) return '正在读取当前可用的模型…'
    if (modelInfo.failed) {
      return '暂时读不到模型列表，请直接到「设置 → 模型配置」查看。'
    }

    const configured = modelInfo.models.filter((m) => m.source === 'config')
    if (configured.length === 0) {
      return (
        '当前还没有配置模型，走的是服务端默认设置。到「设置 → 模型配置」填上端点与模型名即可，' +
        '本地 Ollama 也支持（端点形如 http://localhost:11434/v1）。配好之后，' +
        'Agent 与工作流节点里模型留空就会自动用它。'
      )
    }

    const names = configured.map((m) => m.label || m.id).join('、')
    const effective = configured.find((m) => m.is_effective)
    const tail = effective
      ? `其中「${effective.label || effective.id}」是当前生效项，模型留空的 Agent 与工作流节点都用它。`
      : ''
    return `当前可用的模型：${names}。${tail}这份列表来自「设置 → 模型配置」，端点换了要同步改这里。`
  }

  const q = searchQuery.trim().toLowerCase()
  const hit = (...fields: string[]) =>
    !q || fields.some((f) => f.toLowerCase().includes(q))

  // 两份清单都很小，直接算就行 —— 套 useMemo 只会多一层依赖数组要维护
  const visibleGuides = GUIDES.filter((g) => hit(g.title, g.body))

  // 「支持哪些模型」的答案在渲染时才生成：它依赖异步取回的 modelInfo
  const visibleFaqs = FAQS.map((f) =>
    f.id === 'supported-models' ? { ...f, answer: describeAvailableModels() } : f,
  ).filter((f) => hit(f.category, f.question, f.answer))

  const nothingFound = Boolean(q) && visibleGuides.length === 0 && visibleFaqs.length === 0

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">帮助中心</h1>
        <p className="text-slate-500 dark:text-slate-400">
          从配置模型到搭出第一个 Agent，都可以在这里找到入口
        </p>
      </div>

      {/* 搜索。同时过滤「功能指南」和「常见问题」—— 只过滤常见问题的话，
          搜不到的用户会以为整页没有相关内容。 */}
      <div className="relative mb-8">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
        <input
          type="text"
          placeholder="搜索功能或问题，例如「知识库」「模型」"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full pl-12 pr-4 py-4 rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-white placeholder:text-slate-400 focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 outline-none transition-all text-lg"
        />
      </div>

      {nothingFound && (
        <Card padding="lg" className="mb-8">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-amber-500 mt-0.5 shrink-0" />
            <div>
              <p className="font-medium text-slate-900 dark:text-white">
                没有匹配「{searchQuery}」的内容
              </p>
              <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                换个关键词试试，或者把问题发到{' '}
                <a
                  href={`mailto:${SUPPORT_EMAIL}?subject=${encodeURIComponent('使用问题')}`}
                  className="text-brand-600 dark:text-brand-400 hover:underline"
                >
                  {SUPPORT_EMAIL}
                </a>
                ，我们会补进这一页。
              </p>
            </div>
          </div>
        </Card>
      )}

      {/* 快速上手。搜索时收起 —— 三步引导是「第一次来」的内容，
          用户搜「知识库」时还占着半个屏幕，等于把搜索结果往下挤。 */}
      {!q && (
        <Card padding="lg" className="mb-8">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-1">
            5 分钟跑通第一个 Agent
          </h2>
          <p className="text-sm text-slate-500 dark:text-slate-400 mb-6">
            三步，每步都能直接点进去
          </p>
          <div className="grid gap-4 md:grid-cols-3">
            {STEPS.map((step, i) => (
              <div
                key={step.to}
                className="flex flex-col gap-3 p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50"
              >
                <div className="flex items-center gap-2">
                  <span className="w-6 h-6 rounded-full bg-brand-500 text-white text-xs font-semibold grid place-items-center shrink-0">
                    {i + 1}
                  </span>
                  <h3 className="font-medium text-slate-900 dark:text-white">{step.title}</h3>
                </div>
                <p className="text-sm text-slate-600 dark:text-slate-300 flex-1">{step.body}</p>
                <Button
                  variant="outline"
                  size="sm"
                  rightIcon={<ArrowRight className="w-4 h-4" />}
                  onClick={() => navigate(step.to)}
                >
                  {step.action}
                </Button>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* 功能指南 */}
      {visibleGuides.length > 0 && (
        <Card padding="lg" className="mb-8">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">
            功能指南
            {q && (
              <span className="ml-2 text-sm font-normal text-slate-400">
                {visibleGuides.length} 项匹配
              </span>
            )}
          </h2>
          <div className="grid gap-3 md:grid-cols-2">
            {visibleGuides.map((guide) => (
              <button
                key={guide.to}
                onClick={() => navigate(guide.to)}
                className="flex items-start gap-4 p-4 rounded-xl text-left bg-slate-50 hover:bg-slate-100 dark:bg-slate-800/50 dark:hover:bg-slate-800 transition-colors"
              >
                <div className="p-2.5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700">
                  <guide.icon className="w-5 h-5 text-brand-500" />
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="font-medium text-slate-900 dark:text-white">{guide.title}</h3>
                  <p className="text-sm text-slate-500 dark:text-slate-400">{guide.body}</p>
                </div>
                <ChevronRight className="w-5 h-5 text-slate-400 shrink-0 mt-0.5" />
              </button>
            ))}
          </div>
        </Card>
      )}

      {/* 常见问题 */}
      {visibleFaqs.length > 0 && (
        <Card padding="lg" className="mb-8">
          <div className="flex items-center gap-3 mb-6">
            <HelpCircle className="w-6 h-6 text-brand-500" />
            <h2 className="text-lg font-semibold text-slate-900 dark:text-white">常见问题</h2>
            {q && (
              <span className="text-sm text-slate-400">{visibleFaqs.length} 条匹配</span>
            )}
          </div>

          <div className="space-y-3">
            {visibleFaqs.map((faq) => {
              const open = expanded === faq.id
              // 提成 const：这样 narrow 出的 string 能带进下面的闭包
              const link = faq.to
              return (
                <div
                  key={faq.id}
                  className="border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden"
                >
                  <button
                    onClick={() => setExpanded(open ? null : faq.id)}
                    className="w-full flex items-center justify-between gap-3 p-4 text-left hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <Badge variant="default" size="sm">
                        {faq.category}
                      </Badge>
                      <span className="font-medium text-slate-900 dark:text-white">
                        {faq.question}
                      </span>
                    </div>
                    {open ? (
                      <ChevronDown className="w-5 h-5 text-slate-400 shrink-0" />
                    ) : (
                      <ChevronRight className="w-5 h-5 text-slate-400 shrink-0" />
                    )}
                  </button>
                  {open && (
                    <div className="px-4 pb-4 text-sm text-slate-600 dark:text-slate-300">
                      <p className="leading-relaxed">{faq.answer}</p>
                      {link && (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="mt-2 -ml-2"
                          rightIcon={<ArrowRight className="w-4 h-4" />}
                          onClick={() => navigate(link)}
                        >
                          {faq.toLabel || '去看看'}
                        </Button>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </Card>
      )}

      {/* 联系支持。只留真实可用的邮件入口 —— 原来那个「在线客服」按钮
          点了没有任何反应，客服系统并不存在。 */}
      <Card padding="lg" className="bg-gradient-to-br from-brand-500 to-brand-600 text-white">
        <div className="flex flex-col md:flex-row items-center justify-between gap-6">
          <div>
            <h3 className="text-xl font-semibold">上面都没解决？</h3>
            <p className="text-brand-100 mt-1">
              把操作步骤和报错原文发过来，我们补进这一页
            </p>
          </div>
          <a
            href={`mailto:${SUPPORT_EMAIL}?subject=${encodeURIComponent('使用问题')}`}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-white text-brand-600 font-medium hover:bg-brand-50 transition-colors"
          >
            <Mail className="w-4 h-4" />
            {SUPPORT_EMAIL}
          </a>
        </div>
      </Card>
    </div>
  )
}
