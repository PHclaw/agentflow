import React, { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Logo } from '../components/layout/Logo'
import { auth } from '../services/api'
import { useAuthStore, useToastStore } from '../stores'
import { Mail, Lock, User, ArrowRight, ShieldCheck } from 'lucide-react'

export default function RegisterPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [nickname, setNickname] = useState('')
  const [code, setCode] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  /** 重发倒计时（秒），>0 时按钮禁用 */
  const [countdown, setCountdown] = useState(0)
  const [sending, setSending] = useState(false)
  /** 验证码发给了哪个邮箱，用于「换邮箱就作废旧码」 */
  const [codeSentTo, setCodeSentTo] = useState('')
  /**
   * 验证码有效期（分钟）。
   *
   * 取后端 `/auth/send-code` 返回的 `expires_in`，**不写死**：这里原本硬编码
   * 「5 分钟内有效」，而有效期是后端 CODE_TTL_SECONDS 配的 —— 两者一旦不一致，
   * 界面就会教用户一个错的数，用户按它掐时间就会白等一趟过期的码。
   */
  const [codeTtlMinutes, setCodeTtlMinutes] = useState(10)
  const { setUser, setToken } = useAuthStore()
  const { addToast } = useToastStore()
  const navigate = useNavigate()

  // 倒计时心跳
  useEffect(() => {
    if (countdown <= 0) return
    const timer = setTimeout(() => setCountdown((c) => c - 1), 1000)
    return () => clearTimeout(timer)
  }, [countdown])

  // 换了邮箱就把已发的码清掉，避免拿 A 邮箱的码去注册 B 邮箱
  useEffect(() => {
    if (codeSentTo && email.trim().toLowerCase() !== codeSentTo) {
      setCode('')
      setCodeSentTo('')
      setCountdown(0)
    }
  }, [email, codeSentTo])

  const handleSendCode = async () => {
    const target = email.trim()
    if (!target) {
      setError('请先填写邮箱')
      return
    }

    setSending(true)
    setError('')
    try {
      const res = await auth.sendCode(target)
      setCountdown(res.resend_after || 60)
      setCodeTtlMinutes(Math.max(1, Math.round((res.expires_in || 600) / 60)))
      setCodeSentTo(target.toLowerCase())
      if (res.mail_enabled) {
        addToast({ type: 'success', message: `验证码已发送至 ${target}` })
      } else {
        // 后端 MAIL_ENABLED=false：邮件没真的发出，验证码只打到后端日志
        addToast({
          type: 'info',
          message: '后端未配置邮件服务，验证码见后端日志（搜索 MAIL_ENABLED=false）',
        })
      }
    } catch (err: any) {
      setError(err.message || '验证码发送失败，请稍后重试')
    } finally {
      setSending(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')

    try {
      const response = await auth.register(email, password, nickname, code)
      setToken(response.token)
      if (response.user) {
        setUser(response.user)
      }
      addToast({ type: 'success', message: '注册成功！' })
      // 同登录：落地到控制台（侧边栏/底栏的第一项），不是技能广场
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

            {/* 验证码：输入框与「获取验证码」并排，高度对齐输入框（label 自行渲染） */}
            <div className="space-y-1.5">
              <label className="block text-sm font-medium text-slate-700">
                邮箱验证码
                <span className="text-red-500 ml-1">*</span>
              </label>
              <div className="flex gap-2">
                <div className="flex-1">
                  <Input
                    type="text"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    maxLength={6}
                    value={code}
                    onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
                    placeholder="6 位数字"
                    leftIcon={<ShieldCheck className="w-5 h-5" />}
                    required
                  />
                </div>
                <Button
                  type="button"
                  variant="outline"
                  onClick={handleSendCode}
                  disabled={!email.trim() || countdown > 0}
                  loading={sending}
                  className="shrink-0 h-[42px] py-0 px-3 whitespace-nowrap"
                >
                  {countdown > 0 ? `${countdown}s 后重发` : '获取验证码'}
                </Button>
              </div>
              <p className="text-sm text-slate-500">
                {codeSentTo
                  ? `验证码已发送至 ${codeSentTo}，${codeTtlMinutes} 分钟内有效`
                  : `验证码会发送到上面的邮箱，${codeTtlMinutes} 分钟内有效`}
              </p>
            </div>

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
            <a href="#" className="text-brand-600 hover:underline">
              服务条款
            </a>{' '}
            和{' '}
            <a href="#" className="text-brand-600 hover:underline">
              隐私政策
            </a>
          </p>

          {/* Footer */}
          <p className="mt-6 text-center text-slate-500 text-sm">
            已有账号？{' '}
            <Link to="/login" className="text-brand-600 hover:underline font-medium">
              立即登录
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
