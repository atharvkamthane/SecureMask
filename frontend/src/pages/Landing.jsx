import { useRef, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import LandingNav from '../components/landing/LandingNav'
import HeroSection from '../components/landing/HeroSection'
import HowItWorks from '../components/landing/HowItWorks'
import FeatureCards from '../components/landing/FeatureCards'
import DocTypeStrip from '../components/landing/DocTypeStrip'
import TrustSection from '../components/landing/TrustSection'
import Footer from '../components/layout/Footer'

function StatementSection() {
  return (
    <section className="min-h-screen flex items-center justify-center px-6">
      <motion.div
        initial={{ opacity: 0, y: 80 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: '-100px' }}
        transition={{ duration: 0.6 }}
        className="text-center max-w-[680px]"
      >
        <h2 className="t-h1 text-text-1">
          not every field in your document<br />needs to leave your hands
        </h2>
        <p className="t-body-l text-text-2 mt-6">
          securemask tells you exactly which fields are necessary for your declared purpose — and which ones are not
        </p>
      </motion.div>
    </section>
  )
}

function CTASection() {
  return (
    <section className="min-h-[80vh] flex flex-col items-center justify-center px-6 py-24">
      <motion.div
        initial={{ opacity: 0, y: 40 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        className="text-center"
      >
        <h2 className="t-display text-text-1">
          <span className="gold-gradient-text">protect</span> before<br />you share
        </h2>
        <div className="mt-10">
          <Link
            to="/upload"
            className="px-8 py-4 rounded-[var(--r-md)] bg-accent text-[#080808] font-medium text-base hover:bg-accent-hover transition-colors inline-block"
            data-cursor-hover
          >
            get started free
          </Link>
        </div>
        <p className="text-text-3 text-sm mt-4">no account needed for your first scan</p>
      </motion.div>
    </section>
  )
}

// Custom cursor for landing
function CustomCursor() {
  const [pos, setPos] = useState({ x: 0, y: 0 })
  const [ringPos, setRingPos] = useState({ x: 0, y: 0 })
  const [hovering, setHovering] = useState(false)
  const ringRef = useRef({ x: 0, y: 0 })

  useEffect(() => {
    const onMove = (e) => {
      setPos({ x: e.clientX, y: e.clientY })
      ringRef.current = { x: e.clientX, y: e.clientY }
    }
    window.addEventListener('mousemove', onMove)

    // Lerp ring
    let raf
    const animate = () => {
      setRingPos(prev => ({
        x: prev.x + (ringRef.current.x - prev.x) * 0.12,
        y: prev.y + (ringRef.current.y - prev.y) * 0.12,
      }))
      raf = requestAnimationFrame(animate)
    }
    raf = requestAnimationFrame(animate)

    // Hover detection
    const onOver = (e) => { if (e.target.closest('[data-cursor-hover]')) setHovering(true) }
    const onOut = (e) => { if (e.target.closest('[data-cursor-hover]')) setHovering(false) }
    document.addEventListener('mouseover', onOver)
    document.addEventListener('mouseout', onOut)

    return () => {
      window.removeEventListener('mousemove', onMove)
      cancelAnimationFrame(raf)
      document.removeEventListener('mouseover', onOver)
      document.removeEventListener('mouseout', onOut)
    }
  }, [])

  // Hide on touch devices
  if (typeof window !== 'undefined' && 'ontouchstart' in window) return null

  return (
    <>
      {/* Dot */}
      <div
        className="fixed pointer-events-none z-[9999] w-1.5 h-1.5 rounded-full bg-text-1 transition-opacity duration-100 hidden lg:block"
        style={{
          left: pos.x - 3, top: pos.y - 3,
          opacity: hovering ? 0 : 1,
        }}
      />
      {/* Ring */}
      <div
        className="fixed pointer-events-none z-[9998] rounded-full border transition-all duration-100 hidden lg:block"
        style={{
          width: hovering ? 52 : 36,
          height: hovering ? 52 : 36,
          left: ringPos.x - (hovering ? 26 : 18),
          top: ringPos.y - (hovering ? 26 : 18),
          borderColor: hovering ? 'var(--accent)' : 'rgba(200,169,110,0.5)',
          opacity: hovering ? 1 : 0.5,
        }}
      />
    </>
  )
}

export default function Landing() {
  return (
    <div className="bg-bg-base lg:cursor-none">
      <CustomCursor />
      <LandingNav />
      <HeroSection />
      <StatementSection />
      <HowItWorks />
      <FeatureCards />
      <DocTypeStrip />
      <TrustSection />
      <CTASection />
      <Footer />
    </div>
  )
}
