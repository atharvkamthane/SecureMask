import { motion } from 'framer-motion'

const stats = [
  { value: '47,000+', label: 'documents scanned' },
  { value: '89%', label: 'average risk reduction' },
  { value: 'DPDP', label: 'act compliant' },
]

export default function StatsStrip() {
  return (
    <div className="flex flex-col sm:flex-row items-center justify-center gap-4 sm:gap-6 mt-12">
      {stats.map((s, i) => (
        <motion.div
          key={i}
          initial={{ opacity: 0, scale: 0.88 }}
          whileInView={{ opacity: 1, scale: 1 }}
          viewport={{ once: true }}
          transition={{ delay: i * 0.1, duration: 0.5 }}
          className="bg-bg-surface border border-border rounded-[var(--r-lg)] px-8 py-5 text-center min-w-[180px]"
        >
          <div className="t-mono text-accent text-2xl font-semibold">{s.value}</div>
          <div className="text-text-2 text-xs mt-1">{s.label}</div>
        </motion.div>
      ))}
    </div>
  )
}
