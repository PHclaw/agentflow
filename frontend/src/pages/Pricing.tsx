import React, { useState, useEffect } from 'react';
import { billing } from '../services/api';

interface Plan {
  name: string;
  price: number;
  agents: number;
  messages: number;
  features: string[];
  price_id?: string;
}

interface PlansData {
  [key: string]: Plan;
}

export default function Pricing() {
  const [plans, setPlans] = useState<PlansData>({});
  const [currentPlan, setCurrentPlan] = useState<string>('free');
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // 获取定价计划
    billing.listPlans()
      .then(res => {
        setPlans(res.data.plans || res.data);
      })
      .catch(err => {
        console.error(err);
        setError('加载定价失败');
      });

    // 获取当前订阅状态
    billing.getSubscription()
      .then(res => {
        setCurrentPlan(res.data.plan || 'free');
      })
      .catch(console.error);
  }, []);

  const handleSubscribe = async (planKey: string) => {
    const plan = plans[planKey];
    if (!plan || !plan.price_id || planKey === currentPlan) return;

    setLoading(planKey);
    
    try {
      const res = await billing.createCheckout({
        price_id: plan.price_id,
        success_url: window.location.origin + '/dashboard?success=1',
        cancel_url: window.location.origin + '/pricing'
      });
      
      if (res.data.url) {
        window.location.href = res.data.url;
      }
    } catch (err: any) {
      console.error(err);
      alert(err.response?.data?.detail || '订阅失败，请稍后重试');
    } finally {
      setLoading(null);
    }
  };

  const planKeys = Object.keys(plans);
  if (planKeys.length === 0 && !error) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-gray-900 to-black text-white flex items-center justify-center">
        <div className="text-gray-400">加载中...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-gray-900 to-black text-white flex items-center justify-center">
        <div className="text-red-400">{error}</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-900 to-black text-white py-20 px-4">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="text-center mb-16">
          <h1 className="text-4xl font-bold mb-4 bg-gradient-to-r from-purple-400 to-pink-500 bg-clip-text text-transparent">
            选择适合你的计划
          </h1>
          <p className="text-gray-400 text-lg">
            从免费开始，随时升级
          </p>
        </div>

        {/* Plans */}
        <div className="grid md:grid-cols-3 gap-8">
          {planKeys.map((key) => {
            const plan = plans[key];
            const isCurrent = currentPlan === key;
            const isPro = key === 'pro';
            
            return (
              <div 
                key={key}
                className={`
                  relative rounded-2xl p-8 border transition-all duration-300
                  ${isPro 
                    ? 'bg-gradient-to-b from-purple-900/50 to-gray-900 border-purple-500 scale-105' 
                    : 'bg-gray-900/50 border-gray-800 hover:border-gray-600'
                  }
                  ${isCurrent ? 'ring-2 ring-green-500' : ''}
                `}
              >
                {isPro && (
                  <div className="absolute -top-4 left-1/2 -translate-x-1/2 px-4 py-1 bg-purple-600 rounded-full text-sm font-medium">
                    最受欢迎
                  </div>
                )}
                
                <div className="text-center mb-8">
                  <h3 className="text-xl font-semibold mb-2">{plan.name}</h3>
                  <div className="flex items-baseline justify-center gap-1">
                    <span className="text-4xl font-bold">¥{plan.price}</span>
                    <span className="text-gray-400">/月</span>
                  </div>
                </div>

                <ul className="space-y-3 mb-8">
                  {plan.features.map((feature: string, i: number) => (
                    <li key={i} className="flex items-center gap-2 text-gray-300">
                      <svg className="w-5 h-5 text-green-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                      {feature}
                    </li>
                  ))}
                </ul>

                <button
                  onClick={() => handleSubscribe(key)}
                  disabled={isCurrent || loading !== null}
                  className={`
                    w-full py-3 rounded-xl font-medium transition-all duration-300
                    ${isCurrent 
                      ? 'bg-green-600/20 text-green-400 cursor-not-allowed border border-green-600'
                      : isPro
                        ? 'bg-purple-600 hover:bg-purple-500 text-white'
                        : 'bg-gray-800 hover:bg-gray-700 text-white border border-gray-700'
                    }
                    disabled:opacity-50
                  `}
                >
                  {loading === key ? '处理中...' : isCurrent ? '当前计划' : '立即订阅'}
                </button>
              </div>
            );
          })}
        </div>

        {/* FAQ */}
        <div className="mt-20 max-w-2xl mx-auto">
          <h2 className="text-2xl font-bold mb-8 text-center">常见问题</h2>
          
          <div className="space-y-4">
            <details className="bg-gray-900/50 rounded-xl p-6 border border-gray-800">
              <summary className="font-medium cursor-pointer">可以随时取消吗？</summary>
              <p className="mt-4 text-gray-400">是的，您可以随时取消订阅，当前计费周期结束后生效。</p>
            </details>
            
            <details className="bg-gray-900/50 rounded-xl p-6 border border-gray-800">
              <summary className="font-medium cursor-pointer">消息数量如何计算？</summary>
              <p className="mt-4 text-gray-400">每次用户与 Agent 对话计为1条消息，包括 Agent 回复。</p>
            </details>
            
            <details className="bg-gray-900/50 rounded-xl p-6 border border-gray-800">
              <summary className="font-medium cursor-pointer">支持哪些支付方式？</summary>
              <p className="mt-4 text-gray-400">支持支付宝、微信支付、信用卡等主流支付方式。</p>
            </details>
          </div>
        </div>

        {/* Trust */}
        <div className="mt-16 text-center text-gray-500 text-sm">
          <p>安全支付 · 数据加密 · 7天无理由退款</p>
        </div>
      </div>
    </div>
  );
}
