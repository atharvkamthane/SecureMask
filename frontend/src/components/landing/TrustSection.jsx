import { motion } from 'framer-motion'
import StatsStrip from './StatsStrip'

export default function TrustSection() {
  return (
    <section id="trust" className="min-h-screen flex flex-col items-center justify-center px-6 py-24">
      <motion.div
        initial={{ opacity: 0, y: 40 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        className="text-center max-w-[680px]"
      >
        <h2 className="t-h1 text-text-1">
          your data isn't our business.<br />keeping it safe is.
        </h2>
        <p className="t-body-l text-text-2 mt-6">
          all documents are processed in your session only.
          nothing is stored permanently without your consent.
        </p>
      </motion.div>
      <StatsStrip />
    </section>
  )
}
