import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { useScan } from '../hooks/useScan'
import NecessityTable from '../components/domain/NecessityTable'
import DocTypeBadge from '../components/domain/DocTypeBadge'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import { CONTEXT_MAP } from '../constants/contexts'

export default function NecessityCheck() {
  const { scan, setDecisions } = useScan()
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
  const excess = fields.filter(f => !f.required)
  const required = fields.filter(f => f.required)
  const contextLabel = CONTEXT_MAP[scan.declared_context] || scan.declared_context
  const peiBefore = scan.pei_before || 0
  const peiAfterProjected = fields.reduce((acc, f) => {
    if (f.required) return acc + f.sensitivity_weight * 2
    return acc
  }, 0)
  const reductionPct = peiBefore > 0 ? Math.round(((peiBefore - peiAfterProjected) / peiBefore) * 100) : 0

  const applyAll = () => {
    const decs = {}
    fields.forEach(f => { decs[f.field_name] = f.required ? 'allow' : 'redact' })
    setDecisions(decs)
    navigate('/redaction')
  }

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6">
      {/* Header */}
      <div className="bg-bg-surface border border-border rounded-[var(--r-lg)] p-6">
        <h1 className="t-h2 text-text-1">necessity check</h1>
        <div className="flex items-center gap-3 mt-3 flex-wrap">
          <DocTypeBadge docType={scan.document_type} />
          <Badge variant="violet">{contextLabel}</Badge>
        </div>
        <p className="text-text-2 text-sm mt-3">
          {excess.length} of {fields.length} fields are unnecessary for <span className="text-text-1">{contextLabel}</span>
        </p>
      </div>

      {/* Table */}
      <NecessityTable fields={fields} />

      {/* Recommendation banner */}
      {excess.length > 0 && (
        <div className="bg-accent-dim border border-accent/30 rounded-[var(--r-lg)] p-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <p className="text-text-1 text-sm">
            applying recommendations reduces pei from{' '}
            <span className="t-mono font-semibold text-danger">{Math.round(peiBefore)}</span>
            {' → '}
            <span className="t-mono font-semibold text-success">{Math.min(peiAfterProjected, 100)}</span>
            {' '}({reductionPct}% reduction)
          </p>
          <Button onClick={applyAll} size="sm">apply all recommendations</Button>
        </div>
      )}
    </motion.div>
  )
}
