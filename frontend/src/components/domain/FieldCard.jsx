import { motion } from 'framer-motion'
import Badge from '../ui/Badge'
import { maskValue, methodLabel, methodColor } from '../../utils/fieldHelpers'
import { peiLabel } from '../../utils/peiColor'

export default function FieldCard({ field, decision, onDecisionChange, index = 0 }) {
  const riskLevel = peiLabel(field.sensitivity_weight * 10)
  const borderColor = field.required ? 'var(--success)' : 'var(--danger)'

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
      <div className="p-4 flex-1 space-y-2.5">
        <div className="flex items-start justify-between gap-2">
          <div>
            <h4 className="text-text-1 text-sm font-medium">{field.field_name}</h4>
            <p className="t-mono text-accent text-xs mt-0.5">{maskValue(field.field_value)}</p>
          </div>
          <Badge variant={field.required ? 'low' : 'high'}>
            {field.required ? 'required' : 'excess'}
          </Badge>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <span
            className="text-[10px] font-medium px-2 py-0.5 rounded-full border"
            style={{ color: methodColor(field.detection_method), borderColor: methodColor(field.detection_method) + '40' }}
          >
            {methodLabel(field.detection_method)}
          </span>
          <span className="text-text-3 text-xs">weight: {field.sensitivity_weight}</span>
        </div>

        {field.explanation && (
          <p className="text-text-3 text-xs italic leading-relaxed">{field.explanation}</p>
        )}

        {onDecisionChange && (
          <div className="flex gap-1.5 pt-1">
            {buttons.map(b => (
              <button
                key={b.key}
                onClick={() => onDecisionChange(field.field_name, b.key)}
                className="px-3 py-1 rounded-full text-xs font-medium border transition-all duration-150"
                style={decision === b.key
                  ? { background: b.color + '20', color: b.color, borderColor: b.color + '60' }
                  : { background: 'transparent', color: 'var(--text-3)', borderColor: 'var(--border)' }
                }
              >
                {b.label}
              </button>
            ))}
          </div>
        )}
      </div>
    </motion.div>
  )
}
