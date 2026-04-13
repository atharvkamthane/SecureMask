import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'

export default function LandingNav() {
  const [scrolled, setScrolled] = useState(false)

  useEffect(() => {
    const handler = () => setScrolled(window.scrollY > 80)
    window.addEventListener('scroll', handler, { passive: true })
    return () => window.removeEventListener('scroll', handler)
  }, [])

  return (
    <motion.nav
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${scrolled ? 'landing-nav-solid' : 'landing-nav-transparent'}`}
    >
      <div className="max-w-[1200px] mx-auto px-6 h-14 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2">
          <span className="w-7 h-7 rounded-lg bg-accent flex items-center justify-center text-[#080808] font-bold text-sm">S</span>
          <span className="text-text-1 font-semibold text-[15px]">SecureMask</span>
        </Link>

        <div className="hidden md:flex items-center gap-6">
          <a href="#features" className="text-text-2 text-sm hover:text-text-1 transition-colors">features</a>
          <a href="#how" className="text-text-2 text-sm hover:text-text-1 transition-colors">how it works</a>
          <a href="#trust" className="text-text-2 text-sm hover:text-text-1 transition-colors">trust</a>
        </div>

        <div className="flex items-center gap-3">
          <Link to="/login" className="text-text-2 text-sm hover:text-text-1 transition-colors hidden sm:block">
            login
          </Link>
          <Link
            to="/signup"
            className="px-4 py-1.5 rounded-[var(--r-md)] bg-accent text-[#080808] text-sm font-medium hover:bg-accent-hover transition-colors"
            data-cursor-hover
          >
            try free
          </Link>
        </div>
      </div>
    </motion.nav>
  )
}
