export function peiColor(score) {
  if (score >= 60) return 'var(--danger)'
  if (score >= 30) return 'var(--warning)'
  return 'var(--success)'
}

export function peiLabel(score) {
  if (score >= 60) return 'high'
  if (score >= 30) return 'medium'
  return 'low'
}

export function peiColorClass(score) {
  if (score >= 60) return 'text-danger'
  if (score >= 30) return 'text-warning'
  return 'text-success'
}

export function peiBgClass(score) {
  if (score >= 60) return 'bg-danger-dim'
  if (score >= 30) return 'bg-warning-dim'
  return 'bg-success-dim'
}
