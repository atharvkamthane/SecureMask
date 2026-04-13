import { motion } from 'framer-motion'

export default function Card({ children, hover = true, className = '', ...props }) {
  return (
    <motion.div
      whileHover={hover ? { y: -2, borderColor: 'var(--border-strong)' } : {}}
      transition={{ duration: 0.15, ease: 'easeOut' }}
      className={`
        bg-bg-surface border border-border rounded-[var(--r-lg)]
        p-5 transition-colors duration-150
        ${className}
      `}
      {...props}
    >
      {children}
    </motion.div>
  )
}
