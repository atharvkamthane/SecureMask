import { useRef, useEffect, useMemo } from 'react'
import { motion, useScroll, useTransform } from 'framer-motion'
import { Link } from 'react-router-dom'

function ParticleField() {
  const canvasRef = useRef(null)
  const particles = useMemo(() =>
    Array.from({ length: 60 }, () => ({
      x: Math.random() * 100,
      y: Math.random() * 100,
      vx: (Math.random() - 0.5) * 0.15,
      vy: (Math.random() - 0.5) * 0.15,
      size: Math.random() * 2 + 1,
    })), [])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    let raf

    function resize() {
      canvas.width = canvas.offsetWidth * window.devicePixelRatio
      canvas.height = canvas.offsetHeight * window.devicePixelRatio
      ctx.scale(window.devicePixelRatio, window.devicePixelRatio)
    }
    resize()
    window.addEventListener('resize', resize)

    function draw() {
      const w = canvas.offsetWidth
      const h = canvas.offsetHeight
      ctx.clearRect(0, 0, w, h)
      ctx.fillStyle = '#2A2A2A'
      particles.forEach(p => {
        p.x += p.vx
        p.y += p.vy
        if (p.x < 0 || p.x > 100) p.vx *= -1
        if (p.y < 0 || p.y > 100) p.vy *= -1
        ctx.beginPath()
        ctx.arc((p.x / 100) * w, (p.y / 100) * h, p.size, 0, Math.PI * 2)
        ctx.fill()
      })
      raf = requestAnimationFrame(draw)
    }
    draw()
    return () => { cancelAnimationFrame(raf); window.removeEventListener('resize', resize) }
  }, [particles])

  return <canvas ref={canvasRef} className="absolute inset-0 w-full h-full pointer-events-none" />
}

const wordVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: (i) => ({
    opacity: 1, y: 0,
    transition: { delay: 0.3 + i * 0.04, duration: 0.5, ease: 'easeOut' },
  }),
}

function SplitText({ text, className = '' }) {
  const words = text.split(' ')
  return (
    <span className={className} style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: '0 0.35em' }}>
      {words.map((word, i) => (
        <motion.span key={i} custom={i} variants={wordVariants} initial="hidden" animate="visible">
          {word}
        </motion.span>
      ))}
    </span>
  )
}

// Mock Aadhaar card with sequential field highlighting
function MockDocCard() {
  return (
    <motion.div
      animate={{ y: [0, -6, 0] }}
      transition={{ repeat: Infinity, duration: 4, ease: 'easeInOut' }}
      className="relative w-full max-w-[400px] mx-auto bg-bg-surface border border-border rounded-[var(--r-xl)] p-5 mt-8"
    >
      <div className="flex items-start gap-3 mb-4">
        <div className="w-10 h-10 rounded-lg bg-bg-surface-2 flex items-center justify-center text-accent font-bold text-sm">आ</div>
        <div>
          <div className="text-text-1 text-sm font-medium">Aadhaar Card</div>
          <div className="text-text-3 text-xs">Government of India</div>
        </div>
      </div>

      {[
        { label: 'Name', value: 'Ravi Kumar Sharma', delay: 0 },
        { label: 'Aadhaar No', value: '9234 5678 9012', delay: 1 },
        { label: 'DOB', value: '15/08/1990', delay: 2 },
        { label: 'Address', value: '42, MG Road, Bengaluru', delay: 3 },
      ].map((field, i) => (
        <motion.div
          key={i}
          className="flex items-center justify-between py-2 border-b border-border/50 last:border-0"
          animate={{
            backgroundColor: ['transparent', 'rgba(229,72,77,0.08)', 'transparent'],
            boxShadow: ['none', '0 0 0 1px var(--danger)', 'none'],
          }}
          transition={{ delay: field.delay * 1.2, duration: 1.5, repeat: Infinity, repeatDelay: 4 }}
        >
          <span className="text-text-3 text-xs">{field.label}</span>
          <motion.span
            className="t-mono text-text-1 text-xs"
            animate={{
              color: ['var(--text-1)', 'var(--text-1)', 'var(--text-3)'],
            }}
            transition={{ delay: field.delay * 1.2 + 1.2, duration: 0.5, repeat: Infinity, repeatDelay: 5.5 }}
          >
            {field.value}
          </motion.span>
        </motion.div>
      ))}
    </motion.div>
  )
}

export default function HeroSection() {
  const ref = useRef(null)
  const { scrollYProgress } = useScroll({ target: ref, offset: ['start start', 'end start'] })

  const opacity = useTransform(scrollYProgress, [0, 0.4], [1, 0])
  const y = useTransform(scrollYProgress, [0, 0.4], [0, -60])
  const scale = useTransform(scrollYProgress, [0, 0.5], [1, 0.93])
  const cardRotateX = useTransform(scrollYProgress, [0, 0.5], [0, 18])

  return (
    <section ref={ref} className="relative min-h-screen flex flex-col items-center justify-center px-4 overflow-hidden">
      <ParticleField />

      <motion.div style={{ opacity, y, scale }} className="relative z-10 flex flex-col items-center text-center max-w-[780px]">
        {/* Label pill */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="px-4 py-1.5 rounded-full border border-border bg-bg-surface-2 text-text-3 t-label mb-8"
        >
          privacy protection · built for india's dpdp act
        </motion.div>

        {/* Headline */}
        <h1 className="t-display text-text-1">
          <SplitText text="your documents carry more than you think" />
        </h1>

        {/* Sub text */}
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.8 }}
          className="t-body-l text-text-2 max-w-[500px] mt-6"
        >
          securemask detects sensitive identity data in your documents before you share them — powered by ai, built for india
        </motion.p>

        {/* CTA row */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 1 }}
          className="flex items-center gap-3 mt-8"
        >
          <Link
            to="/upload"
            className="px-6 py-3 rounded-[var(--r-md)] bg-accent text-[#080808] font-medium text-sm hover:bg-accent-hover transition-colors"
            data-cursor-hover
          >
            protect my document
          </Link>
          <a
            href="#how"
            className="px-6 py-3 rounded-[var(--r-md)] border border-border text-text-1 font-medium text-sm hover:border-border-strong hover:bg-bg-surface-2 transition-colors"
            data-cursor-hover
          >
            see how it works
          </a>
        </motion.div>

        {/* Hero document card with 3D scroll */}
        <motion.div style={{ rotateX: cardRotateX, perspective: 1200 }} className="w-full mt-4">
          <MockDocCard />
        </motion.div>
      </motion.div>
    </section>
  )
}
