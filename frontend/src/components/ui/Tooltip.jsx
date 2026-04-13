import { useState } from 'react'

export default function Tooltip({ children, content }) {
  const [show, setShow] = useState(false)
  return (
    <span className="relative inline-block" onMouseEnter={() => setShow(true)} onMouseLeave={() => setShow(false)}>
      {children}
      {show && (
        <span className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-1.5 rounded-[var(--r-sm)] bg-bg-surface-2 border border-border text-xs text-text-1 whitespace-nowrap shadow-lg pointer-events-none">
          {content}
        </span>
      )}
    </span>
  )
}
