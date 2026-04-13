import { motion } from 'framer-motion'

export default function ProgressBar({ value = 0, max = 100, className = '' }) {
  const pct = Math.min((value / max) * 100, 100)
  return (
    <div className={`w-full h-1.5 bg-bg-surface-3 rounded-full overflow-hidden ${className}`}>
      <motion.div
        initial={{ width: 0 }}
        animate={{ width: `${pct}%` }}
        transition={{ duration: 0.8, ease: 'easeOut' }}
        className="h-full rounded-full pei-bar-gradient"
      />
    </div>
  )
}
