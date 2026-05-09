import React, { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Logo } from '../components/layout/Logo'
import { auth } from '../services/api'
import { useAuthStore, useToastStore } from '../stores'
import { Mail, Lock, User, ArrowRight } from 'lucide-react'

export default function RegisterPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [nickname, setNickname] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const { setUser, setToken } = useAuthStore()
  const { addToast } = useToastStore()
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')

    try {
      const response = await auth.register(email, password, nickname)
      setToken(response.token)
      if (response.user) {
        setUser(response.user)
      }
      addToast({ type: 'success', message: '注册成功！' })
      navigate('/dashboard')
    } catch (err: any) {
      setError(err.message || '注册失败，请重试')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <Link to="/" className="inline-block">
            <Logo size="lg" />
          </Link>
        </div>

        {/* Form Card */}
        <div className="bg-white rounded-2xl shadow-xl p-8">
          <div className="text-center mb-8">
            <h1 className="text-2xl font-bold text-slate-900 mb-2">创建账号</h1>
            <p className="text-slate-500">开始使用 AgentFlow</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            {error && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-red-600 text-sm">
                {error}
              </div>
            )}

            <Input
              label="昵称"
              type="text"
              value={nickname}
              onChange={(e) => setNickname(e.target.value)}
              placeholder="你的昵称"
              leftIcon={<User className="w-5 h-5" />}
            />

            <Input
              label="邮箱"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              leftIcon={<Mail className="w-5 h-5" />}
              required
            />

            <Input
              label="密码"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="至少 8 个字符"
              leftIcon={<Lock className="w-5 h-5" />}
              hint="密码至少需要 8 个字符"
              required
            />

            <Button
              type="submit"
              className="w-full"
              size="lg"
              loading={loading}
              rightIcon={<ArrowRight className="w-4 h-4" />}
            >
              注册
            </Button>
          </form>

          {/* Terms */}
          <p className="mt-6 text-center text-xs text-slate-500">
            注册即表示你同意我们的{' '}
            <a href="#" className="text-indigo-600 hover:underline">
              服务条款
            </a>{' '}
            和{' '}
            <a href="#" className="text-indigo-600 hover:underline">
              隐私政策
            </a>
          </p>

          {/* Footer */}
          <p className="mt-6 text-center text-slate-500 text-sm">
            已有账号？{' '}
            <Link to="/login" className="text-indigo-600 hover:underline font-medium">
              立即登录
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
