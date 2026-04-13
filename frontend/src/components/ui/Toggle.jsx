export default function Toggle({ checked, onChange, label }) {
  return (
    <label className="flex items-center gap-2 cursor-pointer">
      <button
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative w-10 h-5 rounded-full transition-colors duration-200 ${checked ? 'bg-accent' : 'bg-bg-surface-3'}`}
      >
        <span className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform duration-200 ${checked ? 'translate-x-5' : ''}`} />
      </button>
      {label && <span className="text-sm text-text-2">{label}</span>}
    </label>
  )
}
