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

export function computeProjectedPei(fields = [], decisions = {}) {
  const maxPossible = fields.reduce((total, field) => total + field.sensitivity_weight * 10, 0)
  if (maxPossible === 0) return 0

  const rawScore = fields.reduce((total, field) => {
    const decision = field.always_redact ? 'redact' : (decisions[field.field_name] || field.redaction_decision || 'redact')
    if (decision !== 'allow') return total
    return total + (field.required ? field.sensitivity_weight * 2 : field.sensitivity_weight * 10)
  }, 0)

  return Math.min(Math.round((rawScore / maxPossible) * 1000) / 10, 100)
}
