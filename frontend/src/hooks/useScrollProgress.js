import { useScroll } from 'framer-motion'

export function useScrollProgress() {
  const { scrollYProgress, scrollY } = useScroll()
  return { scrollYProgress, scrollY }
}
