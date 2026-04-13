import { createContext, useState, useCallback } from 'react'

export const ScanContext = createContext(null)

export function ScanProvider({ children }) {
  const [scan, setScanRaw] = useState(null)
  const [decisions, setDecisions] = useState({})

  const setScan = useCallback((valOrFn) => {
    setScanRaw(prev => {
      const next = typeof valOrFn === 'function' ? valOrFn(prev) : valOrFn
      if (next?.detected_fields) {
        const decs = {}
        next.detected_fields.forEach(f => {
          decs[f.field_name] = f.redaction_decision || 'redact'
        })
        setDecisions(prev => ({ ...decs, ...prev }))
      }
      return next
    })
  }, [])

  const updateDecision = useCallback((fieldName, decision) => {
    setDecisions(prev => ({ ...prev, [fieldName]: decision }))
  }, [])

  const resetScan = useCallback(() => {
    setScanRaw(null)
    setDecisions({})
  }, [])

  return (
    <ScanContext.Provider value={{ scan, setScan, decisions, setDecisions, updateDecision, resetScan }}>
      {children}
    </ScanContext.Provider>
  )
}
