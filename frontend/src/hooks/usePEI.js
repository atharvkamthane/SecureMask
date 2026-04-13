import { useMemo } from 'react'
import { useScan } from './useScan'

export function usePEI() {
  const { scan } = useScan()

  return useMemo(() => {
    if (!scan) return { before: 0, after: 0, reduction: 0 }
    const before = scan.pei_before ?? 0
    const after = scan.pei_after ?? before
    const reduction = before > 0 ? Math.round(((before - after) / before) * 100) : 0
    return { before, after, reduction }
  }, [scan])
}
