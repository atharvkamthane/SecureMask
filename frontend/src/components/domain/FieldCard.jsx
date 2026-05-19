import { motion } from 'framer-motion'
import Badge from '../ui/Badge'
import { maskValue, methodLabel, methodColor } from '../../utils/fieldHelpers'
import { actionCopy } from '../../utils/recommendations'

export default function FieldCard({ field, decision, onDecisionChange, index = 0 }) {
  const borderColor = field.required ? 'var(--success)' : 'var(--danger)'
  const suggested = field.suggested_action || (field.required ? 'allow' : 'redact')
  const suggestedCopy = actionCopy(suggested)

  const buttons = [
    { key: 'mask', label: 'Mask', color: 'var(--warning)' },
    { key: 'redact', label: 'Redact', color: 'var(--danger)' },
    { key: 'allow', label: 'Allow', color: 'var(--success)' },
  ]

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05, duration: 0.3 }}
      className="bg-bg-surface border border-border rounded-[var(--r-lg)] overflow-hidden flex"
    >
      <div className="w-[3px] shrink-0" style={{ background: borderColor }} />
      <div className="p-4 flex-1 space-y-3">
        <div className="flex items-start justify-between gap-2">
          <div>
            <h4 className="text-text-1 text-sm font-medium">{field.field_name}</h4>
            <p className="t-mono text-accent text-xs mt-0.5">{maskValue(field.field_value)}</p>
          </div>
          <div className="flex items-center gap-1.5 flex-wrap justify-end">
            <Badge variant={field.required ? 'low' : 'high'}>
              {field.required ? 'required' : 'excess'}
            </Badge>
            <span
              className="text-[10px] font-medium px-2 py-0.5 rounded-full border"
              style={{
                color: suggestedCopy.border,
                borderColor: `${suggestedCopy.border}60`,
                background: `${suggestedCopy.border}14`,
              }}
            >
              suggested: {suggested}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <span
            className="text-[10px] font-medium px-2 py-0.5 rounded-full border"
            style={{ color: methodColor(field.detection_method), borderColor: `${methodColor(field.detection_method)}40` }}
          >
            {methodLabel(field.detection_method)}
          </span>
          <span className="text-text-3 text-xs">weight: {field.sensitivity_weight}</span>
          {field.always_redact && <span className="text-danger text-xs">forced redaction</span>}
        </div>

        {(field.suggestion_reason || field.explanation) && (
          <div className="space-y-1.5">
            {field.suggestion_reason && (
              <p className="text-text-2 text-xs leading-relaxed">
                {suggestedCopy.label}: {field.suggestion_reason}
              </p>
            )}
            {field.explanation && (
              <p className="text-text-3 text-xs italic leading-relaxed">{field.explanation}</p>
            )}
          </div>
        )}

        {onDecisionChange && (
          <div className="flex gap-1.5 pt-1 flex-wrap">
            {buttons.map(b => {
              const active = decision === b.key
              const disabled = field.always_redact && b.key !== 'redact'
              return (
                <button
                  key={b.key}
                  onClick={() => !disabled && onDecisionChange(field.field_name, b.key)}
                  disabled={disabled}
                  title={disabled ? 'This field must be fully redacted by policy' : actionCopy(b.key).description}
                  className={`px-3 py-1 rounded-full text-xs font-medium border transition-all duration-150 ${disabled ? 'opacity-30 cursor-not-allowed' : ''}`}
                  style={active
                    ? { background: `${b.color}20`, color: b.color, borderColor: `${b.color}60` }
                    : { background: 'transparent', color: 'var(--text-3)', borderColor: 'var(--border)' }
                  }
                >
                  {b.label}
                </button>
              )
            })}
          </div>
        )}
      </div>
    </motion.div>
  )
}
