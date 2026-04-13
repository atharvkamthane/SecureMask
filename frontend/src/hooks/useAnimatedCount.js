import { useEffect, useState, useRef } from 'react'

export function useAnimatedCount(target, duration = 1000) {
  const [value, setValue] = useState(0)
  const raf = useRef(null)

  useEffect(() => {
    const start = performance.now()
    const from = 0
    const to = typeof target === 'number' ? target : 0

    function tick(now) {
      const elapsed = now - start
      const progress = Math.min(elapsed / duration, 1)
      const ease = 1 - Math.pow(1 - progress, 4) // easeOutQuart
      setValue(from + (to - from) * ease)
      if (progress < 1) raf.current = requestAnimationFrame(tick)
    }

    raf.current = requestAnimationFrame(tick)
    return () => { if (raf.current) cancelAnimationFrame(raf.current) }
  }, [target, duration])

  return value
}
