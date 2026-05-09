import React, { useState } from 'react'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Badge } from '../components/ui/Badge'
import {
  Search,
  Book,
  MessageCircle,
  FileText,
  Video,
  ChevronRight,
  ChevronDown,
  ExternalLink,
  Mail,
  HelpCircle,
  Sparkles,
  Zap,
  Users,
} from 'lucide-react'

const faqs = [
  {
    question: '如何创建第一个 Agent？',
    answer: '点击左侧菜单的"创建 Agent"按钮，填写名称和描述，选择模型，然后配置提示词即可。',
    category: '入门',
  },
  {
    question: '支持哪些语言模型？',
    answer: '支持 GPT-4o、GPT-4o Mini、Claude 3 等主流模型，未来会支持更多。',
    category: '功能',
  },
  {
    question: '如何关联知识库？',
    answer: '在 Agent 编辑页面切换到"知识库"标签，上传文档或连接到现有知识库。',
    category: '知识库',
  },
  {
    question: '如何分享我的 Agent？',
    answer: 'Agent 创建完成后，可以生成分享链接或嵌入代码。',
    category: '功能',
  },
]

const guides = [
  {
    icon: Sparkles,
    title: '快速入门',
    description: '5分钟创建你的第一个 Agent',
    gradient: 'from-indigo-500 to-purple-500',
  },
  {
    icon: Book,
    title: '高级配置',
    description: '学习工作流和知识库配置',
    gradient: 'from-emerald-500 to-green-500',
  },
  {
    icon: Users,
    title: '团队协作',
    description: '与团队成员共享和管理 Agent',
    gradient: 'from-amber-500 to-orange-500',
  },
]

export default function HelpPage() {
  const [searchQuery, setSearchQuery] = useState('')
  const [expandedFaq, setExpandedFaq] = useState<number | null>(null)

  const filteredFaqs = faqs.filter(
    (faq) =>
      faq.question.includes(searchQuery) ||
      faq.answer.includes(searchQuery)
  )

  return (
    <div className="max-w-4xl mx-auto">
      {/* Breadcrumb */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">帮助中心</h1>
        <p className="text-slate-500">找到你需要的答案</p>
      </div>

      {/* Search */}
      <div className="relative mb-8">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
        <input
          type="text"
          placeholder="搜索问题..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full pl-12 pr-4 py-4 rounded-2xl border border-slate-200 bg-white focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 outline-none transition-all text-lg"
        />
      </div>

      {/* Quick Guides */}
      <div className="grid md:grid-cols-3 gap-4 mb-8">
        {guides.map((guide, i) => (
          <Card key={i} hover className="cursor-pointer group">
            <div className="flex items-start gap-4">
              <div className={`p-3 rounded-2xl bg-gradient-to-br ${guide.gradient} shadow-lg group-hover:scale-110 transition-transform`}>
                <guide.icon className="w-5 h-5 text-white" />
              </div>
              <div>
                <h3 className="font-semibold text-slate-900 group-hover:text-indigo-600 transition-colors">
                  {guide.title}
                </h3>
                <p className="text-sm text-slate-500">{guide.description}</p>
              </div>
            </div>
          </Card>
        ))}
      </div>

      {/* FAQ */}
      <Card padding="lg" className="mb-8">
        <div className="flex items-center gap-3 mb-6">
          <HelpCircle className="w-6 h-6 text-indigo-500" />
          <h2 className="text-lg font-semibold text-slate-900">常见问题</h2>
        </div>

        <div className="space-y-3">
          {filteredFaqs.map((faq, i) => (
            <div key={i} className="border border-slate-200 rounded-xl overflow-hidden">
              <button
                onClick={() => setExpandedFaq(expandedFaq === i ? null : i)}
                className="w-full flex items-center justify-between p-4 text-left hover:bg-slate-50 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <Badge variant="default" size="sm">{faq.category}</Badge>
                  <span className="font-medium text-slate-900">{faq.question}</span>
                </div>
                {expandedFaq === i ? (
                  <ChevronDown className="w-5 h-5 text-slate-400" />
                ) : (
                  <ChevronRight className="w-5 h-5 text-slate-400" />
                )}
              </button>
              {expandedFaq === i && (
                <div className="px-4 pb-4 pt-0 text-slate-600 text-sm">
                  {faq.answer}
                </div>
              )}
            </div>
          ))}
        </div>
      </Card>

      {/* Resources */}
      <Card padding="lg" className="mb-8">
        <h2 className="text-lg font-semibold text-slate-900 mb-4">学习资源</h2>
        <div className="grid md:grid-cols-2 gap-4">
          <div className="flex items-center gap-4 p-4 bg-slate-50 rounded-xl hover:bg-slate-100 transition-colors cursor-pointer">
            <div className="p-3 bg-white rounded-xl shadow-sm">
              <FileText className="w-6 h-6 text-indigo-500" />
            </div>
            <div className="flex-1">
              <h3 className="font-medium text-slate-900">文档中心</h3>
              <p className="text-sm text-slate-500">完整的 API 和功能文档</p>
            </div>
            <ExternalLink className="w-5 h-5 text-slate-400" />
          </div>

          <div className="flex items-center gap-4 p-4 bg-slate-50 rounded-xl hover:bg-slate-100 transition-colors cursor-pointer">
            <div className="p-3 bg-white rounded-xl shadow-sm">
              <Video className="w-6 h-6 text-indigo-500" />
            </div>
            <div className="flex-1">
              <h3 className="font-medium text-slate-900">视频教程</h3>
              <p className="text-sm text-slate-500">观看详细操作演示</p>
            </div>
            <ExternalLink className="w-5 h-5 text-slate-400" />
          </div>
        </div>
      </Card>

      {/* Contact */}
      <Card padding="lg" className="bg-gradient-to-br from-indigo-500 to-purple-600 text-white">
        <div className="flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-4">
            <div className="p-4 bg-white/20 rounded-2xl">
              <MessageCircle className="w-8 h-8" />
            </div>
            <div>
              <h3 className="text-xl font-semibold">需要更多帮助？</h3>
              <p className="text-indigo-100">我们的支持团队随时为你解答</p>
            </div>
          </div>
          <div className="flex gap-3">
            <Button variant="outline" className="border-white text-white hover:bg-white/20">
              <Mail className="w-4 h-4 mr-2" />
              发送邮件
            </Button>
            <Button className="bg-white text-indigo-600 hover:bg-indigo-50">
              <MessageCircle className="w-4 h-4 mr-2" />
              在线客服
            </Button>
          </div>
        </div>
      </Card>
    </div>
  )
}
