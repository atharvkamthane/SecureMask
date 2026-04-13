import { motion, useInView } from 'framer-motion'
import { useRef, useState } from 'react'

function TiltCard({ children, index }) {
  const [rotate, setRotate] = useState({ x: 0, y: 0 })

  const handleMouse = (e) => {
    const rect = e.currentTarget.getBoundingClientRect()
    const dx = (e.clientX - rect.left - rect.width / 2) / rect.width
    const dy = (e.clientY - rect.top - rect.height / 2) / rect.height
    setRotate({ x: dy * -4, y: dx * 4 })
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 60 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-80px' }}
      transition={{ delay: index * 0.05, duration: 0.5 }}
      onMouseMove={handleMouse}
      onMouseLeave={() => setRotate({ x: 0, y: 0 })}
      style={{ perspective: 800, transformStyle: 'preserve-3d' }}
    >
      <motion.div
        animate={{ rotateX: rotate.x, rotateY: rotate.y }}
        transition={{ type: 'spring', stiffness: 200, damping: 20 }}
        className="bg-bg-surface border border-border rounded-[var(--r-xl)] p-8 h-full"
        style={{ transformStyle: 'preserve-3d' }}
      >
        <div style={{ transform: 'translateZ(20px)' }}>
          {children}
        </div>
      </motion.div>
    </motion.div>
  )
}

const steps = [
  { num: '01', title: 'upload your document', body: 'drop any aadhaar, pan, passport, voter id, driving license, ration card, or esic card' },
  { num: '02', title: 'ai detects sensitive fields', body: 'hybrid ocr + ner + regex pipeline identifies every sensitive field and explains why' },
  { num: '03', title: 'download the safe version', body: 'mask or redact excess fields — your pei score drops, your privacy is protected' },
]

export default function HowItWorks() {
  const ref = useRef(null)

  return (
    <section id="how" ref={ref} className="py-24 bg-bg-surface border-t border-b border-border">
      <div className="max-w-[1200px] mx-auto px-6">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-center mb-16"
        >
          <span className="t-label text-accent">how it works</span>
          <h2 className="t-h2 text-text-1 mt-3">three steps to privacy</h2>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {steps.map((step, i) => (
            <TiltCard key={i} index={i}>
              <span className="t-mono text-accent text-[48px] font-medium leading-none">{step.num}</span>
              <h3 className="t-h3 text-text-1 mt-4">{step.title}</h3>
              <p className="text-text-2 text-sm mt-3 leading-relaxed">{step.body}</p>
            </TiltCard>
          ))}
        </div>
      </div>
    </section>
  )
}
