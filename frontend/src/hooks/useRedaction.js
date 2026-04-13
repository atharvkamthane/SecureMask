import { useScan } from './useScan'
import { redactDocument } from '../api/scan'
import { useState, useCallback } from 'react'

export function useRedaction() {
  const { scan, setScan } = useScan()
  const [loading, setLoading] = useState(false)

  const applyRedaction = useCallback(async (decisions) => {
    if (!scan) return null
    setLoading(true)
    try {
      const result = await redactDocument(scan.scan_id, decisions)
      setScan(prev => ({
        ...prev,
        pei_after: result.pei_after,
        redacted_image_url: result.redacted_image_url,
        audit_report: result.audit_report,
      }))
      return result
    } finally {
      setLoading(false)
    }
  }, [scan, setScan])

  return { applyRedaction, loading }
}
