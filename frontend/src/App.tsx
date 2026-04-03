import React from 'react'

export default function App() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-lg flex items-center justify-center">
              <span className="text-white font-bold text-xl">A</span>
            </div>
            <h1 className="text-2xl font-bold text-gray-900">AgentFlow</h1>
          </div>
          <nav className="flex items-center gap-6">
            <a href="#templates" className="text-gray-600 hover:text-blue-600">模板市场</a>
            <a href="#pricing" className="text-gray-600 hover:text-blue-600">定价</a>
            <a href="#docs" className="text-gray-600 hover:text-blue-600">文档</a>
            <button className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition">
              开始免费试用
            </button>
          </nav>
        </div>
      </header>

      {/* Hero */}
      <section className="py-20">
        <div className="max-w-4xl mx-auto px-4 text-center">
          <h2 className="text-5xl font-bold text-gray-900 mb-6">
            让每个企业都能拥有<br/>
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-indigo-600">
              专属 AI Agent
            </span>
          </h2>
          <p className="text-xl text-gray-600 mb-8 max-w-2xl mx-auto">
            无需代码，拖拽式构建企业专属 AI 智能体。开箱即用的客服、销售、HR 等行业模板。
          </p>
          <div className="flex items-center justify-center gap-4">
            <button className="px-8 py-3 bg-blue-600 text-white rounded-xl text-lg font-medium hover:bg-blue-700 transition shadow-lg hover:shadow-xl">
              免费开始
            </button>
            <button className="px-8 py-3 bg-white text-gray-700 border border-gray-200 rounded-xl text-lg font-medium hover:bg-gray-50 transition">
              查看演示
            </button>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="py-16 bg-white">
        <div className="max-w-6xl mx-auto px-4">
          <h3 className="text-3xl font-bold text-center text-gray-900 mb-12">
            核心功能
          </h3>
          <div className="grid md:grid-cols-3 gap-8">
            <FeatureCard
              icon="🎯"
              title="拖拽式构建"
              description="可视化界面，拖拽节点即可构建复杂的工作流，无需编程经验"
            />
            <FeatureCard
              icon="📦"
              title="预置行业模板"
              description="客服、销售、HR、财务等开箱即用的行业模板，快速上线"
            />
            <FeatureCard
              icon="🔗"
              title="多渠道集成"
              description="一键接入微信、钉钉、企业微信、网站、API 等多渠道"
            />
            <FeatureCard
              icon="🧠"
              title="知识库 RAG"
              description="上传文档，AI 自动学习企业知识，精准回答专业问题"
            />
            <FeatureCard
              icon="⚡"
              title="工具调用"
              description="支持搜索、计算、API 调用等工具，让 Agent 真正帮你做事"
            />
            <FeatureCard
              icon="📊"
              title="数据分析"
              description="完整的数据面板，了解用户意图，优化 Agent 效果"
            />
          </div>
        </div>
      </section>

      {/* Templates */}
      <section id="templates" className="py-16">
        <div className="max-w-6xl mx-auto px-4">
          <h3 className="text-3xl font-bold text-center text-gray-900 mb-4">
            行业模板
          </h3>
          <p className="text-center text-gray-600 mb-12">
            选择适合你的模板，5 分钟上线你的第一个 AI Agent
          </p>
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
            <TemplateCard
              icon="💬"
              name="智能客服"
              desc="自动回答常见问题，多轮对话"
              color="bg-green-50"
            />
            <TemplateCard
              icon="💰"
              name="销售助手"
              desc="客户跟进、报价、催单"
              color="bg-blue-50"
            />
            <TemplateCard
              icon="👥"
              name="HR 助手"
              desc="假期政策、薪资咨询"
              color="bg-purple-50"
            />
            <TemplateCard
              icon="📊"
              name="财务助手"
              desc="报销审批、发票查询"
              color="bg-yellow-50"
            />
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="py-16 bg-white">
        <div className="max-w-5xl mx-auto px-4">
          <h3 className="text-3xl font-bold text-center text-gray-900 mb-12">
            简单定价
          </h3>
          <div className="grid md:grid-cols-3 gap-8">
            <PricingCard
              name="免费版"
              price="¥0"
              period="/月"
              features={["1 个 Agent", "100 次对话/月", "基础模板", "社区支持"]}
              highlighted={false}
            />
            <PricingCard
              name="专业版"
              price="¥99"
              period="/月"
              features={["5 个 Agent", "5000 次对话/月", "全部模板", "知识库 RAG", "API 接入", "优先支持"]}
              highlighted={true}
            />
            <PricingCard
              name="企业版"
              price="¥299"
              period="/月"
              features={["20 个 Agent", "无限对话", "私有化部署", "定制开发", "专属客服", "SLA 保障"]}
              highlighted={false}
            />
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-gray-900 text-white py-12">
        <div className="max-w-6xl mx-auto px-4">
          <div className="grid md:grid-cols-4 gap-8">
            <div>
              <div className="flex items-center gap-2 mb-4">
                <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-lg"></div>
                <span className="font-bold text-xl">AgentFlow</span>
              </div>
              <p className="text-gray-400 text-sm">
                让每个企业都能轻松拥有专属 AI Agent
              </p>
            </div>
            <div>
              <h4 className="font-semibold mb-4">产品</h4>
              <ul className="space-y-2 text-gray-400 text-sm">
                <li><a href="#" className="hover:text-white">功能</a></li>
                <li><a href="#" className="hover:text-white">模板</a></li>
                <li><a href="#" className="hover:text-white">定价</a></li>
              </ul>
            </div>
            <div>
              <h4 className="font-semibold mb-4">资源</h4>
              <ul className="space-y-2 text-gray-400 text-sm">
                <li><a href="#" className="hover:text-white">文档</a></li>
                <li><a href="#" className="hover:text-white">API</a></li>
                <li><a href="#" className="hover:text-white">博客</a></li>
              </ul>
            </div>
            <div>
              <h4 className="font-semibold mb-4">公司</h4>
              <ul className="space-y-2 text-gray-400 text-sm">
                <li><a href="#" className="hover:text-white">关于我们</a></li>
                <li><a href="#" className="hover:text-white">联系我们</a></li>
                <li><a href="#" className="hover:text-white">隐私政策</a></li>
              </ul>
            </div>
          </div>
          <div className="border-t border-gray-800 mt-8 pt-8 text-center text-gray-500 text-sm">
            © 2025 AgentFlow. All rights reserved.
          </div>
        </div>
      </footer>
    </div>
  )
}

function FeatureCard({ icon, title, description }: { icon: string; title: string; description: string }) {
  return (
    <div className="p-6 bg-white rounded-2xl shadow-sm border border-gray-100 hover:shadow-md transition">
      <div className="text-4xl mb-4">{icon}</div>
      <h4 className="text-xl font-semibold text-gray-900 mb-2">{title}</h4>
      <p className="text-gray-600">{description}</p>
    </div>
  )
}

function TemplateCard({ icon, name, desc, color }: { icon: string; name: string; desc: string; color: string }) {
  return (
    <div className={`${color} rounded-2xl p-6 hover:shadow-lg transition cursor-pointer`}>
      <div className="text-4xl mb-4">{icon}</div>
      <h4 className="text-lg font-semibold text-gray-900 mb-1">{name}</h4>
      <p className="text-gray-600 text-sm">{desc}</p>
    </div>
  )
}

function PricingCard({ 
  name, 
  price, 
  period, 
  features, 
  highlighted 
}: { 
  name: string; 
  price: string; 
  period: string; 
  features: string[]; 
  highlighted: boolean 
}) {
  return (
    <div className={`p-8 rounded-2xl ${
      highlighted 
        ? 'bg-gradient-to-br from-blue-600 to-indigo-600 text-white shadow-xl' 
        : 'bg-white border border-gray-200'
    }`}>
      <h4 className="text-lg font-semibold mb-2">{name}</h4>
      <div className="flex items-baseline gap-1 mb-6">
        <span className="text-4xl font-bold">{price}</span>
        <span className={highlighted ? 'text-blue-100' : 'text-gray-500'}>{period}</span>
      </div>
      <ul className="space-y-3 mb-8">
        {features.map((feature, i) => (
          <li key={i} className="flex items-center gap-2">
            <span className={highlighted ? 'text-blue-200' : 'text-green-500'}>✓</span>
            <span className={highlighted ? 'text-blue-100' : 'text-gray-600'}>{feature}</span>
          </li>
        ))}
      </ul>
      <button className={`w-full py-3 rounded-xl font-medium transition ${
        highlighted 
          ? 'bg-white text-blue-600 hover:bg-blue-50' 
          : 'bg-blue-600 text-white hover:bg-blue-700'
      }`}>
        立即开始
      </button>
    </div>
  )
}
