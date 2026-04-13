import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { useScan } from '../hooks/useScan'
import FieldCard from '../components/domain/FieldCard'
import DocumentPreview from '../components/domain/DocumentPreview'
import DocTypeBadge from '../components/domain/DocTypeBadge'
import ProgressBar from '../components/ui/ProgressBar'
import Button from '../components/ui/Button'
import { peiColor } from '../utils/peiColor'

export default function Detection() {
  const { scan, decisions, updateDecision } = useScan()
  const [hoveredField, setHoveredField] = useState(null)
  const navigate = useNavigate()

  if (!scan) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] text-center">
        <p className="text-text-2 mb-4">no scan data found. upload a document first.</p>
        <Button onClick={() => navigate('/upload')}>go to upload</Button>
      </div>
    )
  }

  const fields = scan.detected_fields || []
  const pei = scan.pei_before || 0

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <span className="t-label text-text-3">detected fields</span>
          <h1 className="t-h2 text-text-1 mt-1">scan results</h1>
        </div>
        <div className="flex gap-2">
          <Button variant="ghost" onClick={() => navigate('/necessity')}>necessity check</Button>
          <Button onClick={() => navigate('/pei')}>pei score</Button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[55%_45%] gap-6">
        {/* Left — document preview */}
        <div>
          <DocumentPreview
            imageUrl={scan.processable_image_url || scan.original_file_url}
            fields={fields}
            decisions={decisions}
            hoveredField={hoveredField}
            onFieldHover={setHoveredField}
          />
        </div>

        {/* Right — field panel */}
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <DocTypeBadge docType={scan.document_type} />
            <span className="text-text-2 text-sm">{fields.length} fields detected</span>
          </div>

          <div className="space-y-3 max-h-[60vh] overflow-y-auto pr-1">
            {fields.map((f, i) => (
              <FieldCard
                key={f.field_name}
                field={f}
                decision={decisions[f.field_name]}
                onDecisionChange={updateDecision}
                index={i}
              />
            ))}
          </div>

          {/* PEI widget */}
          <div className="bg-bg-surface border border-border rounded-[var(--r-lg)] p-4">
            <span className="t-label text-text-3">current pei score</span>
            <div className="flex items-center gap-3 mt-2">
              <span className="font-mono text-2xl font-semibold" style={{ color: peiColor(pei) }}>
                {Math.round(pei)}
              </span>
              <span className="text-text-3 text-xs">/ 100</span>
            </div>
            <ProgressBar value={pei} className="mt-3" />
          </div>

          <Button className="w-full" onClick={() => navigate('/redaction')}>
            proceed to redaction →
          </Button>
        </div>
      </div>
    </motion.div>
  )
}
