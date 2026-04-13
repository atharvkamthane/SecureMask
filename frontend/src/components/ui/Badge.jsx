const badgeStyles = {
  high: 'bg-danger-dim text-danger',
  medium: 'bg-warning-dim text-warning',
  low: 'bg-success-dim text-success',
  neutral: 'bg-bg-surface-2 text-text-2',
  accent: 'bg-accent-dim text-accent',
  violet: 'bg-violet-dim text-violet',
}

export default function Badge({ children, variant = 'neutral', pulse, className = '' }) {
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${badgeStyles[variant]} ${className}`}>
      {pulse && (
        <span className="relative flex h-1.5 w-1.5">
          <span className="animate-pulse-dot absolute inline-flex h-full w-full rounded-full bg-current opacity-75" />
          <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-current" />
        </span>
      )}
      {children}
    </span>
  )
}
