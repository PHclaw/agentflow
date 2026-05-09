import React from 'react'
import { Header } from '../components/layout/Header'
import { HeroSection, FeaturesSection, TemplatesSection, PricingSection, Footer } from '../components/landing'

export default function HomePage() {
  return (
    <div className="min-h-screen bg-slate-50">
      <Header />
      <main>
        <HeroSection />
        <FeaturesSection />
        <TemplatesSection />
        <PricingSection />
      </main>
      <Footer />
    </div>
  )
}
