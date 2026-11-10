import React from 'react'
import { Header } from '../components/layout/Header'
import {
  HeroSection,
  AgentShapesSection,
  PipelineSection,
  FeaturesSection,
  LiveDemo,
  CompareSection,
  TemplatesSection,
  PricingSection,
  Footer,
} from '../components/landing'

export default function HomePage() {
  return (
    <div className="min-h-screen bg-slate-50">
      <Header />
      <main>
        <HeroSection />

        {/*
          「智能体在做什么」：一句话进来，五步出去。
          紧接首屏 —— 首屏讲的是「怎么搭」，这里先回答更基础的问题：
          搭出来的东西究竟在干什么。先立概念，再讲功能。
        */}
        <AgentShapesSection />

        {/*
          「三件事，串成一条线」：知识库 → Agent → 工作流。
          上一段讲清了智能体一次任务里的五步，这一段回答更上位的问题 ——
          知识库、Agent、工作流不是三个并列模块，而是同一条链路上的三段。
          放在功能列表之前：先让人看懂形状，再看清单。
        */}
        <PipelineSection />

        <FeaturesSection />

        {/*
          「实际使用场景」演示。放在功能列表之后、模板之前：
          上面刚讲完有哪些功能，这里立刻让人看到它们合起来是什么体验。
          节奏上 Hero 讲"怎么搭"，这一段讲"搭完什么样"。
        */}
        <section className="relative overflow-hidden border-t border-slate-100 bg-white py-20 dark:border-slate-800 dark:bg-slate-950 lg:py-28">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <LiveDemo />
          </div>
        </section>

        {/*
          对比演示：同一个问题，普通 AI 助手 vs AgentFlow 同时开始。
          紧跟在上一段「实际使用场景」之后 —— 先让人看到它怎么工作，
          再让人看到和普通的比差别在哪，最后才进入模板（"那你给我个起点"）。
        */}
        <section className="relative overflow-hidden border-t border-slate-100 bg-slate-50 py-20 dark:border-slate-800 lg:py-28">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <CompareSection />
          </div>
        </section>

        <TemplatesSection />
        <PricingSection />
      </main>
      <Footer />
    </div>
  )
}
