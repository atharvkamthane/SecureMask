import { Check } from 'lucide-react'

export default function StepIndicator({ steps, current = 0 }) {
  return (
    <div className="flex items-center justify-center gap-0">
      {steps.map((step, i) => (
        <div key={i} className="flex items-center">
          <div className="flex flex-col items-center gap-1.5">
            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-semibold border transition-colors
              ${i < current ? 'bg-accent text-[#080808] border-accent' : ''}
              ${i === current ? 'border-accent text-accent bg-accent-dim' : ''}
              ${i > current ? 'border-border text-text-3 bg-bg-surface-2' : ''}
            `}>
              {i < current ? <Check size={14} /> : i + 1}
            </div>
            <span className={`text-xs whitespace-nowrap ${i <= current ? 'text-text-1' : 'text-text-3'}`}>{step}</span>
          </div>
          {i < steps.length - 1 && (
            <div className={`w-16 h-px mx-2 mb-5 ${i < current ? 'bg-accent' : 'bg-border'}`} />
          )}
        </div>
      ))}
    </div>
  )
}
