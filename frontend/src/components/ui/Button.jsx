import { motion } from 'framer-motion'

const variants = {
  primary: 'bg-accent text-[#080808] font-medium hover:bg-accent-hover',
  ghost: 'bg-transparent border border-border text-text-1 hover:border-border-strong hover:bg-bg-surface-2',
  danger: 'bg-danger-dim border border-danger/40 text-danger hover:bg-danger/20',
  success: 'bg-success-dim border border-success/40 text-success hover:bg-success/20',
  warning: 'bg-warning-dim border border-warning/40 text-warning hover:bg-warning/20',
}

const sizes = {
  sm: 'px-3 py-1.5 text-xs',
  md: 'px-4 py-2 text-sm',
  lg: 'px-6 py-3 text-base',
}

export default function Button({ children, variant = 'primary', size = 'md', disabled, className = '', ...props }) {
  return (
    <motion.button
      whileHover={disabled ? {} : { y: -1 }}
      whileTap={disabled ? {} : { scale: 0.98 }}
      className={`
        inline-flex items-center justify-center gap-2 rounded-[var(--r-md)] font-medium
        transition-colors duration-150 cursor-pointer
        ${variants[variant]} ${sizes[size]}
        ${disabled ? 'opacity-35 cursor-not-allowed' : ''}
        ${className}
      `}
      disabled={disabled}
      {...props}
    >
      {children}
    </motion.button>
  )
}
