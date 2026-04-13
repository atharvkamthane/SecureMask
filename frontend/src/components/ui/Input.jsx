import { forwardRef } from 'react'

const Input = forwardRef(({ label, error, className = '', ...props }, ref) => (
  <div className="flex flex-col gap-1.5">
    {label && <label className="t-small text-text-2">{label}</label>}
    <input
      ref={ref}
      className={`
        w-full px-3 py-2.5 rounded-[var(--r-md)]
        bg-bg-surface-2 border border-border text-text-1
        placeholder:text-text-3 text-sm outline-none
        transition-all duration-150
        focus:border-accent focus:shadow-[0_0_0_3px_rgba(200,169,110,0.12)]
        ${error ? 'border-danger' : ''}
        ${className}
      `}
      {...props}
    />
    {error && <span className="text-danger t-small">{error}</span>}
  </div>
))

Input.displayName = 'Input'
export default Input
