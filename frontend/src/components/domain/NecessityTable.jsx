import { Check, X } from 'lucide-react'
import { actionCopy } from '../../utils/recommendations'

export default function NecessityTable({ fields = [] }) {
  return (
    <div className="bg-bg-surface border border-border rounded-[var(--r-lg)] overflow-hidden">
      <div className="hidden md:grid grid-cols-[1fr_100px_90px_160px] gap-0 bg-bg-surface-2 px-4 py-2.5 border-b border-border">
        <span className="t-label text-text-3">field</span>
        <span className="t-label text-text-3 text-center">sensitivity</span>
        <span className="t-label text-text-3 text-center">required?</span>
        <span className="t-label text-text-3 text-right">recommendation</span>
      </div>
      {fields.map((f, i) => {
        const recommendation = f.suggested_action || (f.required ? 'allow' : 'redact')
        const copy = actionCopy(recommendation)
        return (
          <div
            key={i}
            className="grid grid-cols-1 md:grid-cols-[1fr_100px_90px_160px] gap-3 md:gap-0 px-4 py-3 border-b border-border items-center hover:bg-bg-surface-3 transition-colors"
            style={{ borderLeft: `3px solid ${f.required ? 'var(--success)' : 'var(--danger)'}` }}
          >
            <div>
              <span className="text-sm text-text-1">{f.field_name}</span>
              {f.suggestion_reason && (
                <p className="text-text-3 text-xs mt-1 leading-relaxed md:hidden">{f.suggestion_reason}</p>
              )}
            </div>
            <div className="flex items-center md:justify-center gap-1.5">
              <div className="w-12 h-1.5 bg-bg-surface-3 rounded-full overflow-hidden">
                <div className="h-full pei-bar-gradient rounded-full" style={{ width: `${f.sensitivity_weight * 10}%` }} />
              </div>
              <span className="t-mono text-text-3 text-xs">{f.sensitivity_weight}</span>
            </div>
            <div className="flex md:justify-center">
              {f.required
                ? <Check size={16} className="text-success" />
                : <X size={16} className="text-danger" />
              }
            </div>
            <div className="md:text-right">
              <span className={`text-xs font-medium ${copy.tone}`}>
                {recommendation}
              </span>
              {f.suggestion_reason && (
                <p className="hidden md:block text-text-3 text-[11px] leading-relaxed mt-1">{f.suggestion_reason}</p>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
