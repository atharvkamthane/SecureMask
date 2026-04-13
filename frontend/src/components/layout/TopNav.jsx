import { NavLink, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { LayoutDashboard, PlusCircle, History, FileText, Settings, Menu, X } from 'lucide-react'
import { useState } from 'react'
import { useScan } from '../../hooks/useScan'
import { useAuth } from '../../context/AuthContext'
import { peiColor } from '../../utils/peiColor'

const links = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/upload', label: 'New Scan', icon: PlusCircle },
  { to: '/history', label: 'History', icon: History },
]

export default function TopNav() {
  const [mobileOpen, setMobileOpen] = useState(false)
  const { scan } = useScan()
  const { user, logoutUser } = useAuth()
  const navigate = useNavigate()
  const lastPEI = scan?.pei_before

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 glass-nav border-b border-border">
      <div className="max-w-[1400px] mx-auto px-4 h-14 flex items-center justify-between">
        {/* Left — Logo */}
        <button onClick={() => navigate('/dashboard')} className="flex items-center gap-2 shrink-0">
          <span className="w-7 h-7 rounded-lg bg-accent flex items-center justify-center text-[#080808] font-bold text-sm">S</span>
          <span className="text-text-1 font-semibold text-[15px] hidden sm:block">SecureMask</span>
        </button>

        {/* Center — Nav links (desktop) */}
        <div className="hidden md:flex items-center gap-1">
          {links.map(link => (
            <NavLink key={link.to} to={link.to} className="relative px-3 py-1.5 text-sm font-medium transition-colors">
              {({ isActive }) => (
                <>
                  <span className={isActive ? 'text-accent' : 'text-text-2 hover:text-text-1'}>{link.label}</span>
                  {isActive && (
                    <motion.div
                      layoutId="navIndicator"
                      className="absolute bottom-0 left-3 right-3 h-[2px] bg-accent rounded-full"
                      transition={{ type: 'spring', stiffness: 380, damping: 30 }}
                    />
                  )}
                </>
              )}
            </NavLink>
          ))}
        </div>

        {/* Right — PEI pill, avatar, settings */}
        <div className="flex items-center gap-3">
          {lastPEI !== undefined && lastPEI !== null && (
            <span className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-bg-surface-2 border border-border text-xs">
              <span className="text-text-3">PEI</span>
              <span className="t-mono font-medium" style={{ color: peiColor(lastPEI) }}>{Math.round(lastPEI)}</span>
            </span>
          )}
          <div className="w-7 h-7 rounded-full bg-accent/20 border border-accent/30 flex items-center justify-center text-accent text-xs font-semibold">
            {user?.name?.[0]?.toUpperCase() || 'U'}
          </div>
          <button className="text-text-3 hover:text-text-1 hidden md:block">
            <Settings size={16} />
          </button>

          {/* Mobile hamburger */}
          <button className="md:hidden text-text-2 hover:text-text-1" onClick={() => setMobileOpen(!mobileOpen)}>
            {mobileOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </div>

      {/* Mobile dropdown */}
      {mobileOpen && (
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          className="md:hidden border-t border-border bg-bg-surface"
        >
          {links.map(link => (
            <NavLink
              key={link.to}
              to={link.to}
              onClick={() => setMobileOpen(false)}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-3 text-sm border-b border-border transition-colors
                ${isActive ? 'text-accent bg-accent-dim' : 'text-text-2 hover:text-text-1'}`
              }
            >
              <link.icon size={16} />
              {link.label}
            </NavLink>
          ))}
        </motion.div>
      )}
    </nav>
  )
}
