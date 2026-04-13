import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowRight } from 'lucide-react'
import { useScan } from '../hooks/useScan'
import PEIGauge from '../components/domain/PEIGauge'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import ProgressBar from '../components/ui/ProgressBar'
import { peiColor } from '../utils/peiColor'
import { useAnimatedCount } from '../hooks/useAnimatedCount'

export default function PEIScore() {
  const { scan, decisions } = useScan()
  const navigate = useNavigate()

  if (!scan) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh]">
        <p className="text-text-2 mb-4">no scan data available</p>
        <Button onClick={() => navigate('/upload')}>upload a document</Button>
      </div>
    )
  }

  const fields = scan.detected_fields || []
  const peiBefore = scan.pei_before || 0
  const peiAfter = fields.reduce((acc, f) => {
    const dec = decisions[f.field_name] || 'redact'
    if (dec === 'allow') return acc + (f.required ? f.sensitivity_weight * 2 : f.sensitivity_weight * 10)
    return acc + (f.required ? f.sensitivity_weight * 2 : 0)
  }, 0)
  const peiAfterCapped = Math.min(peiAfter, 100)

  const animatedBefore = useAnimatedCount(peiBefore, 800)
  const animatedAfter = useAnimatedCount(peiAfterCapped, 800)

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="max-w-[640px] mx-auto space-y-8">
      <div className="text-center">
        <h1 className="t-h2 text-text-1">your privacy exposure index</h1>
      </div>

      {/* Gauge */}
      <div className="flex justify-center">
        <PEIGauge score={peiBefore} size={240} />
      </div>

      {/* Before → After */}
      <div className="grid grid-cols-[1fr_auto_1fr] gap-4 items-center">
        <Card hover={false} className="text-center">
          <span className="t-label text-text-3">before</span>
          <div className="font-mono text-3xl font-semibold mt-2" style={{ color: peiColor(peiBefore) }}>
            {Math.round(animatedBefore)}
          </div>
        </Card>
        <ArrowRight size={20} className="text-text-3" />
        <Card hover={false} className="text-center">
          <span className="t-label text-text-3">after projected</span>
          <div className="font-mono text-3xl font-semibold mt-2" style={{ color: peiColor(peiAfterCapped) }}>
            {Math.round(animatedAfter)}
          </div>
        </Card>
      </div>

      {/* Field breakdown */}
      <Card hover={false}>
        <h3 className="t-h3 text-text-1 mb-4">field breakdown</h3>
        <div className="space-y-3">
          {fields.map((f, i) => (
            <div key={i} className="flex items-center gap-3">
              <span className="text-text-2 text-sm w-32 shrink-0 truncate">{f.field_name}</span>
              <div className="flex-1 h-1.5 bg-bg-surface-3 rounded-full overflow-hidden">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${f.sensitivity_weight * 10}%` }}
                  transition={{ delay: i * 0.05, duration: 0.6 }}
                  className="h-full rounded-full"
                  style={{ backgroundColor: peiColor(f.sensitivity_weight * 10) }}
                />
              </div>
              <span className="t-mono text-text-3 text-xs w-6 text-right">{f.sensitivity_weight}</span>
            </div>
          ))}
        </div>
      </Card>

      <Button className="w-full" size="lg" onClick={() => navigate('/redaction')}>
        apply redaction →
      </Button>
    </motion.div>
  )
}
