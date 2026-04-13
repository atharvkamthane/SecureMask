import { Outlet } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import TopNav from './TopNav'

const pageTransition = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -10 },
  transition: { duration: 0.22, ease: [0.25, 0.46, 0.45, 0.94] },
}

export default function AppShell() {
  return (
    <div className="min-h-screen bg-bg-base">
      <TopNav />
      <main className="pt-[72px]">
        <AnimatePresence mode="wait">
          <motion.div key={location.pathname} {...pageTransition}>
            <div className="max-w-[1200px] mx-auto px-6 py-10">
              <Outlet />
            </div>
          </motion.div>
        </AnimatePresence>
      </main>
    </div>
  )
}
