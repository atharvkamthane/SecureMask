import { motion } from 'framer-motion'
import { Grid3X3, Gauge, Eye, FileText, Layers, Shield } from 'lucide-react'

const features = [
  { icon: Grid3X3, title: 'necessity classifier', body: 'understands what data is actually required for your declared context. flags only the excess.', tag: 'core research novelty' },
  { icon: Gauge, title: 'privacy exposure index', body: 'a weighted score 0–100 for every document. see exactly how much risk you\'re carrying.', tag: 'pei score' },
  { icon: Eye, title: 'explainable detections', body: 'every flagged field comes with a plain-english reason — which model detected it and why.', tag: 'xai layer' },
  { icon: FileText, title: 'compliance audit trail', body: 'every scan generates a timestamped report mapped to india\'s dpdp act and gdpr article 5.', tag: 'dpdp · gdpr' },
  { icon: Layers, title: '7 indian id documents', body: 'aadhaar · pan · passport · driving license · voter id · ration card · esic card', tag: 'tier 1 coverage' },
  { icon: Shield, title: 'you decide, always', body: 'mask, redact, or allow each field individually. nothing is removed without your explicit decision.', tag: 'consent-first' },
]

export default function FeatureCards() {
  return (
    <section id="features" className="py-24 bg-bg-base">
      <div className="max-w-[1200px] mx-auto px-6">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-center mb-16"
        >
          <span className="t-label text-accent">what makes it different</span>
          <h2 className="t-h2 text-text-1 mt-3">not just redaction. intelligence.</h2>
        </motion.div>

        <motion.div
          initial={{ rotateX: 8, y: 80, opacity: 0 }}
          whileInView={{ rotateX: 0, y: 0, opacity: 1 }}
          viewport={{ once: true, margin: '-60px' }}
          transition={{ duration: 0.7, ease: 'easeOut' }}
          style={{ perspective: 1200 }}
          className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5"
        >
          {features.map((f, i) => (
            <motion.div
              key={i}
              whileHover={{ y: -4, borderColor: 'rgba(200,169,110,0.3)' }}
              className="bg-bg-surface border border-border rounded-[var(--r-xl)] p-6 flex flex-col gap-4 transition-shadow card-glow cursor-default"
            >
              <f.icon size={22} className="text-accent" />
              <h3 className="text-text-1 text-base font-semibold">{f.title}</h3>
              <p className="text-text-2 text-sm leading-relaxed flex-1">{f.body}</p>
              <span className="t-label text-text-3 mt-auto">{f.tag}</span>
            </motion.div>
          ))}
        </motion.div>
      </div>
    </section>
  )
}
