import { Link } from 'react-router-dom'
import { Logo } from '../layout/Logo'
import { Github, Twitter, Linkedin, Youtube, Mail, MapPin, Phone } from 'lucide-react'

const footerLinks = {
  product: {
    title: '产品',
    links: [
      { label: '功能介绍', href: '#features' },
      { label: '行业模板', href: '#templates' },
      { label: '定价方案', href: '#pricing' },
      { label: '更新日志', href: '#' },
    ],
  },
  resources: {
    title: '资源',
    links: [
      { label: '开发文档', href: '#' },
      { label: 'API 文档', href: '#' },
      { label: '视频教程', href: '#' },
      { label: '社区论坛', href: '#' },
    ],
  },
  company: {
    title: '公司',
    links: [
      { label: '关于我们', href: '#' },
      { label: '加入团队', href: '#' },
      { label: '联系方式', href: '#' },
      { label: '新闻资讯', href: '#' },
    ],
  },
  legal: {
    title: '法律',
    links: [
      { label: '服务条款', href: '#' },
      { label: '隐私政策', href: '#' },
      { label: 'Cookie 政策', href: '#' },
      { label: 'GDPR 合规', href: '#' },
    ],
  },
}

const socialLinks = [
  { icon: Github, href: '#', label: 'GitHub' },
  { icon: Twitter, href: '#', label: 'Twitter' },
  { icon: Linkedin, href: '#', label: 'LinkedIn' },
  { icon: Youtube, href: '#', label: 'YouTube' },
]

export function Footer() {
  return (
    <footer className="relative bg-slate-900 text-slate-300">
      {/* Gradient top border */}
      <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-indigo-500 to-transparent" />
      
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Main footer */}
        <div className="py-16 lg:py-20">
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-8 lg:gap-12">
            {/* Brand column */}
            <div className="col-span-2">
              <Link to="/" className="inline-flex items-center gap-3 mb-6">
                <div className="bg-gradient-to-br from-indigo-500 to-purple-600 p-2 rounded-xl">
                  <svg className="w-5 h-5 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
                  </svg>
                </div>
                <span className="text-xl font-bold text-white">AgentFlow</span>
              </Link>
              <p className="text-slate-400 text-sm leading-relaxed mb-6 max-w-sm">
                让每个企业都能拥有专属 AI Agent，无需代码，拖拽式构建，5 分钟快速上线。
              </p>
              
              {/* Contact info */}
              <div className="space-y-3 text-sm">
                <div className="flex items-center gap-2 text-slate-400">
                  <Mail className="w-4 h-4" />
                  <span>contact@agentflow.ai</span>
                </div>
                <div className="flex items-center gap-2 text-slate-400">
                  <Phone className="w-4 h-4" />
                  <span>400-888-8888</span>
                </div>
                <div className="flex items-center gap-2 text-slate-400">
                  <MapPin className="w-4 h-4" />
                  <span>北京市朝阳区望京SOHO</span>
                </div>
              </div>

              {/* Social links */}
              <div className="flex items-center gap-3 mt-6">
                {socialLinks.map((social, i) => (
                  <a
                    key={i}
                    href={social.href}
                    className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white transition-all hover:scale-110"
                    aria-label={social.label}
                  >
                    <social.icon className="w-5 h-5" />
                  </a>
                ))}
              </div>
            </div>

            {/* Link columns */}
            {Object.values(footerLinks).map((section, i) => (
              <div key={i}>
                <h4 className="font-semibold text-white mb-4">{section.title}</h4>
                <ul className="space-y-3">
                  {section.links.map((link, j) => (
                    <li key={j}>
                      <a
                        href={link.href}
                        className="text-sm text-slate-400 hover:text-white transition-colors"
                      >
                        {link.label}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>

        {/* Bottom bar */}
        <div className="py-6 border-t border-slate-800">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
            <p className="text-sm text-slate-500">
              © 2024 AgentFlow. 保留所有权利。
            </p>
            <div className="flex items-center gap-6 text-sm text-slate-500">
              <span className="flex items-center gap-2">
                <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                所有系统正常运行
              </span>
            </div>
          </div>
        </div>
      </div>
    </footer>
  )
}
