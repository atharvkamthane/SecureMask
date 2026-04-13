import { Check, X } from 'lucide-react'

export default function NecessityTable({ fields = [], onOverride }) {
  return (
    <div className="bg-bg-surface border border-border rounded-[var(--r-lg)] overflow-hidden">
      <div className="grid grid-cols-[1fr_100px_90px_140px] gap-0 bg-bg-surface-2 px-4 py-2.5 border-b border-border">
        <span className="t-label text-text-3">field</span>
        <span className="t-label text-text-3 text-center">sensitivity</span>
        <span className="t-label text-text-3 text-center">required?</span>
        <span className="t-label text-text-3 text-right">recommendation</span>
      </div>
      {fields.map((f, i) => (
        <div
          key={i}
          className="grid grid-cols-[1fr_100px_90px_140px] gap-0 px-4 py-3 border-b border-border items-center hover:bg-bg-surface-3 transition-colors"
          style={{ borderLeft: `3px solid ${f.required ? 'var(--success)' : 'var(--danger)'}` }}
        >
          <span className="text-sm text-text-1">{f.field_name}</span>
          <div className="flex items-center justify-center gap-1.5">
            <div className="w-12 h-1.5 bg-bg-surface-3 rounded-full overflow-hidden">
              <div className="h-full pei-bar-gradient rounded-full" style={{ width: `${f.sensitivity_weight * 10}%` }} />
            </div>
            <span className="t-mono text-text-3 text-xs">{f.sensitivity_weight}</span>
          </div>
          <div className="flex justify-center">
            {f.required
              ? <Check size={16} className="text-success" />
              : <X size={16} className="text-danger" />
            }
          </div>
          <div className="flex justify-end">
            <span className={`text-xs ${f.required ? 'text-success' : 'text-danger'}`}>
              {f.required ? 'allow' : 'redact'}
            </span>
          </div>
        </div>
      ))}
    </div>
  )
}
